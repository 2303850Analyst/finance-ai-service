"""Mobile adapter service. Finance rules stay in the existing domain engines."""
import asyncio
import base64
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from app.models.account import Account
from app.models.asset import Asset
from app.models.operation import Operation, OperationStatus
from app.models.telegram import OperationDraftRecord
from app.models.user import User
from app.schemas.operation import OperationOut
from app.services import telegram_service as tg
from app.services.budget_engine import compute_budget_summary
from app.services.cash_engine import calculate_all_cash_balances, calculate_cash_balances_from_operations
from app.services.operation_service import _validate

TZ = ZoneInfo("Europe/Moscow")


def checked_period(start, end):
    if end < start or (end - start).days > 366 or end > datetime.now(TZ).date():
        raise HTTPException(422, "Выберите период до года, не позднее сегодняшнего дня.")


async def owned_account(account_id, user, db):
    account = await db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Счёт не найден")
    return account


async def bootstrap(user, db):
    accounts = (await db.execute(select(Account).where(Account.user_id == user.id).order_by(Account.name))).scalars().all()
    assets = (await db.execute(select(Asset).order_by(Asset.name))).scalars().all()
    balances = await calculate_all_cash_balances(user, db)
    return {"accounts": [{"id": str(a.id), "name": a.name, "account_type": a.account_type, "currency": a.currency,
            "cash_balance": str(balances.get((str(a.id), a.currency), Decimal(0)))} for a in accounts],
            "assets": [{"id": str(a.id), "name": a.name, "ticker": a.ticker} for a in assets]}


async def add_account(body, user, db):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Введите название счёта")
    await db.execute(select(User).where(User.id == user.id).with_for_update())
    exists = await db.scalar(select(Account.id).where(Account.user_id == user.id, func.lower(Account.name) == name.lower()))
    if exists:
        raise HTTPException(409, "Счёт с таким названием уже есть")
    record = Account(user_id=user.id, name=name, account_type=body.account_type, currency="RUB")
    db.add(record)
    await db.commit()
    return {"id": str(record.id), "name": record.name}


async def overview(start, end, account_id, user, db):
    checked_period(start, end)
    if account_id:
        await owned_account(account_id, user, db)
    boundary = datetime.combine(end + timedelta(days=1), datetime.min.time(), TZ)
    ops = (await db.execute(select(Operation).where(Operation.user_id == user.id,
        Operation.status == OperationStatus.confirmed, Operation.currency == "RUB", Operation.operated_at < boundary)
        .order_by(Operation.operated_at, Operation.created_at))).scalars().all()
    balances = calculate_cash_balances_from_operations(ops)
    cash = sum((v for (aid, currency), v in balances.items() if not account_id or aid == str(account_id)), Decimal(0))
    visible = [o for o in ops if not account_id or o.account_id == account_id or o.to_account_id == account_id]
    before = [o for o in visible if o.operated_at.astimezone(TZ).date() < start]
    period = [o for o in visible if o.operated_at.astimezone(TZ).date() >= start]
    budget = compute_budget_summary(before, period, start, end)
    return {"cash": str(cash), "cash_as_of": end.isoformat(), "period_from": start.isoformat(), "period_to": end.isoformat(),
        "income": str(budget.income_total), "living": str(budget.living_expense_total), "credit": str(budget.credit_payment_total),
        "investment": str(budget.investment_expense_total), "free": str(budget.free_cashflow), "count": len(period),
        "recent": [OperationOut.model_validate(o).model_dump(mode="json") for o in reversed(period[-5:])]}


async def history(start, end, account_id, offset, user, db):
    checked_period(start, end)
    if account_id:
        await owned_account(account_id, user, db)
    query = select(Operation).where(Operation.user_id == user.id, Operation.status == OperationStatus.confirmed,
        Operation.currency == "RUB", Operation.operated_at >= datetime.combine(start, datetime.min.time(), TZ),
        Operation.operated_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), TZ))
    if account_id:
        query = query.where(or_(Operation.account_id == account_id, Operation.to_account_id == account_id))
    rows = (await db.execute(query.order_by(Operation.operated_at.desc(), Operation.created_at.desc(), Operation.id.desc()).offset(offset).limit(51))).scalars().all()
    return {"items": [OperationOut.model_validate(o).model_dump(mode="json") for o in rows[:50]], "has_more": len(rows) > 50}


def draft_out(record):
    state = "expired" if record.state == "pending" and record.expires_at <= tg.now() else record.state
    return {"id": str(record.id), "state": state, "revision": record.revision, "operation": record.payload["validated"],
        "raw_text": record.payload.get("input_text", record.payload.get("raw_text", "")),
        "warnings": record.payload.get("warnings", []), "expires_at": record.expires_at.isoformat(),
        "operation_id": str(record.operation_id) if record.operation_id else None}


async def get_draft(draft_id, user, db, *, lock=False):
    query = select(OperationDraftRecord).where(OperationDraftRecord.id == draft_id, OperationDraftRecord.user_id == user.id)
    if lock:
        query = query.with_for_update()
    record = (await db.execute(query)).scalar_one_or_none()
    if record is None:
        raise HTTPException(404, "Черновик не найден")
    return record


async def pending_drafts(user, db):
    records = (await db.execute(select(OperationDraftRecord).where(OperationDraftRecord.user_id == user.id,
        OperationDraftRecord.state == "pending", OperationDraftRecord.expires_at > tg.now())
        .order_by(OperationDraftRecord.expires_at.desc()).limit(50))).scalars().all()
    return [draft_out(record) for record in records]


async def check_operation(payload, user, db):
    _validate(payload)
    for field in ("amount", "fee", "price", "quantity", "principal_amount", "interest_amount"):
        value = getattr(payload, field)
        if value is not None and (not value.is_finite() or value < 0 or value >= Decimal("1e12")
                or value != value.quantize(Decimal("0.00000001"))):
            raise HTTPException(422, f"Поле {field}: допустимо неотрицательное число до 1 трлн, не более 8 знаков после запятой.")
    if payload.currency != "RUB" or payload.is_refund:
        raise HTTPException(422, "Поддерживаются обычные операции в RUB.")
    if payload.operation_type != "manual_valuation" and payload.amount <= 0:
        raise HTTPException(422, "Сумма должна быть положительной")
    if payload.operation_type == "expense" and payload.expense_group not in ("living", "investment", "credit"):
        raise HTTPException(422, "Выберите группу расходов")
    account = await owned_account(payload.account_id, user, db)
    target = None
    if payload.to_account_id:
        target = await owned_account(payload.to_account_id, user, db)
    if payload.operation_type == "transfer" and (not target or target.id == account.id):
        raise HTTPException(422, "Для перевода нужны два разных счёта")
    asset = await db.get(Asset, payload.asset_id) if payload.asset_id else None
    if payload.asset_id and asset is None:
        raise HTTPException(422, "Актив не найден")
    if payload.linked_asset_id and await db.get(Asset, payload.linked_asset_id) is None:
        raise HTTPException(422, "Связанный актив не найден")
    if payload.operated_at.tzinfo is None:
        payload.operated_at = payload.operated_at.replace(tzinfo=TZ)
    for field, maximum in {"note": 2000, "merchant": 255, "expense_category": 50, "liability_name": 255, "income_source": 50}.items():
        if len(getattr(payload, field) or "") > maximum:
            raise HTTPException(422, f"Сократите поле {field} до {maximum} символов.")
    return account, target, asset


async def update_draft(draft_id, body, user, db):
    record = await get_draft(draft_id, user, db, lock=True)
    if record.state != "pending" or record.expires_at <= tg.now():
        raise HTTPException(409, "Черновик уже обработан или истёк. Обновите его статус.")
    if record.revision != body.revision:
        raise HTTPException(409, "Черновик изменился в другом окне. Загрузите актуальную версию.")
    payload = body.operation
    if payload.operation_type != record.payload["validated"]["operation_type"]:
        raise HTTPException(422, "Для другого типа операции измените исходный текст и создайте новый черновик.")
    account, target, asset = await check_operation(payload, user, db)
    validated = payload.model_dump(mode="json")
    display = {**record.payload["operation"], **validated, "account_name": account.name,
               "to_account_name": target.name if target else None, "asset_name": asset.name if asset else None}
    record.payload = {**record.payload, "validated": validated, "operation": display}
    record.revision += 1
    await db.commit()
    return draft_out(record)


async def parse_draft(body, user, db):
    key = f"miniapp:{user.id}:{body.request_id}"
    existing = (await db.execute(select(OperationDraftRecord).where(OperationDraftRecord.source_key == key,
        OperationDraftRecord.user_id == user.id))).scalar_one_or_none()
    if existing:
        return draft_out(existing)
    text = await transcribe_media(body.audio, user, db) if body.audio else body.text.strip()
    result = await tg.make_draft(text, key, user, db, check_limit=not bool(body.audio))
    if not result.get("draft_id"):
        raise HTTPException(422, result["message"])
    import uuid
    record = await get_draft(uuid.UUID(result["draft_id"]), user, db)
    return draft_out(record)


async def transcribe_media(encoded, user, db):
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise HTTPException(422, "Некорректная аудиозапись") from None
    if not data or len(data) > 5_000_000:
        raise HTTPException(422, "Запись должна быть не больше 5 МБ")
    if data.startswith(b"OggS"):
        return await tg.transcribe(encoded, user, db)
    # Browser formats vary. Convert in a bounded subprocess, denying network protocols.
    if not (data.startswith(b"\x1aE\xdf\xa3") or data[4:8] == b"ftyp" or data.startswith(b"RIFF")):
        raise HTTPException(422, "Неизвестный формат записи. Отправьте голос боту или введите текст.")
    with tempfile.TemporaryDirectory(prefix="finai-audio-") as folder:
        source = Path(folder) / "recording"
        source.write_bytes(data)
        try:
            process = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-nostdin", "-threads", "1",
                "-protocol_whitelist", "file,pipe", "-i", str(source), "-t", "120", "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "pipe:1", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            try:
                output, _ = await asyncio.wait_for(process.communicate(), timeout=20)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                process.kill()
                await process.wait()
                raise
        except (FileNotFoundError, asyncio.TimeoutError):
            raise HTTPException(503, "Не удалось обработать запись. Отправьте голос боту или введите текст.") from None
    if process.returncode or not output.startswith(b"OggS") or len(output) > 5_000_000:
        raise HTTPException(422, "Не удалось прочитать запись. Попробуйте ещё раз или отправьте голос боту.")
    return await tg.transcribe(base64.b64encode(output).decode(), user, db)
