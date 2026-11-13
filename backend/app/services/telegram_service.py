"""Persistent drafts, owner binding and atomic confirmation. No ledger writes during parsing."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.models.account import Account
from app.models.telegram import OperationDraftRecord, TelegramLink, TelegramPairing
from app.models.user import User
from app.schemas.operation import OperationCreate
from app.schemas.transfer import TransferCreate
from app.services.ai_parser import parse_operation_text
from app.services.ai_gateway import call_ai
from app.services.cash_engine import get_account_cash_balance
from app.services.operation_service import create_operation
from app.services.transfer_service import create_transfer


def now():
    return datetime.now(timezone.utc)


async def pairing(user, db):
    if not settings.telegram_bot_token:
        raise HTTPException(503, "Telegram не настроен")
    token = secrets.token_urlsafe(24)
    await db.execute(select(User).where(User.id == user.id).with_for_update())
    await db.execute(delete(TelegramPairing).where(TelegramPairing.user_id == user.id))
    db.add(TelegramPairing(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
        expires_at=now() + timedelta(minutes=10)))
    await db.commit()
    return {"url": f"https://t.me/{settings.telegram_bot_username}?start={token}", "expires_in": 600}


async def bind(token, sender_id, db):
    record = (await db.execute(select(TelegramPairing).where(
        TelegramPairing.token_hash == hashlib.sha256(token.encode()).hexdigest()).with_for_update())).scalar_one_or_none()
    if record is None or record.expires_at <= now():
        raise HTTPException(400, "Ссылка истекла или уже использована. Создайте новую в разделе Telegram.")
    existing = await db.get(TelegramLink, sender_id)
    if existing and existing.user_id != record.user_id:
        raise HTTPException(409, "Telegram уже привязан к другому пользователю")
    await db.execute(delete(TelegramLink).where(TelegramLink.user_id == record.user_id))
    await db.flush()
    db.add(TelegramLink(telegram_id=sender_id, user_id=record.user_id))
    await db.delete(record)
    await db.commit()
    return {"message": "Telegram подключён. Отправьте операцию текстом или голосом. Запись появится только после подтверждения. /accounts - счета, /pending - черновики, /summary - сводка."}


async def linked_user(sender_id, chat_id, db):
    if sender_id != chat_id:
        raise HTTPException(403, "Используйте личный чат с ботом")
    link = await db.get(TelegramLink, sender_id)
    if link is None:
        raise HTTPException(403, "Сначала откройте Telegram в локальном приложении и нажмите «Подключить».")
    return await db.get(User, link.user_id)


def draft_message(record):
    p = record.payload
    d = p["operation"]
    labels = {"expense": "Расход", "deposit": "Доход" if d.get("income_source") else "Пополнение",
        "buy": "Покупка", "sell": "Продажа", "transfer": "Перевод", "fee": "Комиссия", "tax": "Налог",
        "dividend": "Дивиденд", "coupon": "Купон", "manual_valuation": "Переоценка"}
    parts = [labels.get(d["operation_type"], d["operation_type"]),
        f"Счёт: {d.get('account_name')}", f"Сумма: {p['validated']['amount']} RUB",
        f"Дата: {p['validated']['operated_at']}"]
    for key, label in [("to_account_name", "Куда"), ("asset_name", "Актив"), ("quantity", "Количество"),
        ("price", "Цена"), ("fee", "Комиссия"), ("expense_group", "Группа"), ("expense_category", "Категория"),
        ("merchant", "Продавец"), ("income_source", "Источник дохода"), ("principal_amount", "Основной долг"),
        ("interest_amount", "Проценты"), ("note", "Примечание")]:
        if d.get(key) is not None:
            parts.append(f"{label}: {d[key]}")
    return {"message": "\n".join(parts) + "\nПроверьте данные. Подтвердить запись?", "draft_id": str(record.id), "revision": record.revision}


def validate_draft(parsed):
    d = parsed.operation
    if not d or not parsed.account_id:
        raise ValueError("Укажите точное название счёта")
    raw = d.model_dump()
    raw.update(account_id=parsed.account_id, asset_id=parsed.asset_id, to_account_id=parsed.to_account_id)
    if raw['amount'] is None:
        if d.operation_type in ("buy", "sell") and d.quantity and d.price:
            raw['amount'] = Decimal(d.quantity) * Decimal(d.price)
        elif d.operation_type == "manual_valuation":
            raw['amount'] = 0
        else:
            raise ValueError("Не указана сумма")
    payload = OperationCreate.model_validate(raw)
    for key in ("amount", "fee", "quantity", "price", "principal_amount", "interest_amount"):
        value = getattr(payload, key)
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("Суммы должны быть конечными и неотрицательными")
    if payload.currency != "RUB":
        raise ValueError("Поддерживается только RUB")
    if payload.operation_type != "manual_valuation" and payload.amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    if payload.operation_type == "expense" and payload.expense_group not in ("living", "investment", "credit"):
        raise ValueError("Не определена группа расходов")
    if payload.operation_type == "transfer" and not payload.to_account_id:
        raise ValueError("Укажите счёт получателя")
    if payload.operation_type in ("buy", "sell", "manual_valuation") and not payload.asset_id:
        raise ValueError("Сначала добавьте актив в веб-интерфейсе")
    if d.linked_asset_text:
        raise ValueError("Для платежа со связью с имуществом используйте веб-интерфейс")
    if payload.operated_at.tzinfo is None:
        payload.operated_at = payload.operated_at.replace(tzinfo=ZoneInfo("Europe/Moscow"))
    return payload


async def make_draft(text, source_key, user, db, *, check_limit=True):
    owner_id = user.id
    existing = (await db.execute(select(OperationDraftRecord).where(OperationDraftRecord.source_key == source_key,
        OperationDraftRecord.user_id == user.id))).scalar_one_or_none()
    if existing:
        return draft_message(existing) if existing.state == "pending" and existing.expires_at > now() else {"message": "Этот запрос уже обработан."}
    parsed = await parse_operation_text(text, user, db, check_limit=check_limit)
    await db.commit()
    if parsed.status != "parsed" or parsed.operation is None:
        return {"message": parsed.provider_error or parsed.message or "Уточните операцию и отправьте её заново."}
    try:
        payload = validate_draft(parsed)
    except (ValueError, ArithmeticError):
        return {"message": "Не удалось собрать корректную операцию. Укажите сумму, точное название счёта (/accounts), а для покупки - актив, количество и цену. Для сложного платежа используйте веб-интерфейс."}
    record = OperationDraftRecord(user_id=user.id, source_key=source_key,
        payload={**parsed.model_dump(mode="json"), "validated": payload.model_dump(mode="json"), "input_text": text},
        expires_at=now() + timedelta(hours=24))
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        record = (await db.execute(select(OperationDraftRecord).where(OperationDraftRecord.source_key == source_key,
            OperationDraftRecord.user_id == owner_id))).scalar_one_or_none()
        if record is None:
            raise
    return draft_message(record)


async def decide(draft_id, action, user, db, *, expected_revision=None):
    if action not in ("confirm", "cancel"):
        raise HTTPException(422, "Неизвестное действие")
    record = (await db.execute(select(OperationDraftRecord).where(OperationDraftRecord.id == draft_id,
        OperationDraftRecord.user_id == user.id).with_for_update())).scalar_one_or_none()
    if record is None:
        raise HTTPException(404, "Черновик не найден")
    if record.state != "pending":
        return {"message": "Операция уже сохранена." if record.state == "confirmed" else "Черновик отменён."}
    if record.expires_at <= now():
        raise HTTPException(410, "Черновик истёк. Отправьте операцию заново.")
    if record.revision != (expected_revision if expected_revision is not None else 1):
        raise HTTPException(409, "Черновик изменён. Откройте его заново и проверьте актуальные данные. В боте: /pending.")
    if action == "cancel":
        record.state = "cancelled"
        await db.commit()
        return {"message": "Отменено. Операция не записана."}
    payload = OperationCreate.model_validate(record.payload["validated"])
    account_ids = sorted({payload.account_id, *([payload.to_account_id] if payload.to_account_id else [])}, key=str)
    await db.execute(select(Account).where(Account.id.in_(account_ids)).order_by(Account.id).with_for_update())
    if payload.operation_type == "buy":
        balance = await get_account_cash_balance(str(payload.account_id), "RUB", user, db)
        if balance < payload.amount + (payload.fee or Decimal(0)):
            raise HTTPException(400, "Недостаточно денег для покупки. Пополните счёт в приложении и подтвердите черновик снова.")
    if payload.operation_type == "transfer":
        transfer = TransferCreate(from_account_id=payload.account_id, to_account_id=payload.to_account_id,
            amount=payload.amount, fee=payload.fee, currency=payload.currency, operated_at=payload.operated_at, note=payload.note)
        op = await create_transfer(transfer, user, db, commit=False)
    else:
        op = await create_operation(payload, user, db, commit=False)
    record.state = "confirmed"
    record.operation_id = op.id
    await db.commit()
    return {"message": "Операция сохранена. Она уже доступна в приложении."}


async def transcribe(data, user, db):
    try:
        audio = base64.b64decode(data, validate=True)
    except ValueError:
        raise HTTPException(422, "Некорректное аудио") from None
    if not audio or len(audio) > 5_000_000 or not audio.startswith(b"OggS"):
        raise HTTPException(422, "Принимаются голосовые сообщения OGG до 5 МБ")
    body = await call_ai("audio/transcriptions", {"model": settings.transcription_model,
        "input_audio": {"data": data, "format": "ogg"}, "language": "ru"}, "transcription", user, db)
    text = body.get("text", "").strip()
    if not text or len(text) > settings.ai_max_input_chars:
        raise HTTPException(422, "Не удалось распознать короткую операцию. Повторите сообщение.")
    return text
