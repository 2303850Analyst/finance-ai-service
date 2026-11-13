import hmac
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.telegram import OperationDraftRecord, TelegramLink, TelegramPairing
from app.services import telegram_service as service
from app.services.cash_engine import calculate_all_cash_balances

router = APIRouter(prefix="/telegram", tags=["telegram"])


async def internal_auth(x_telegram_secret: str = Header(default="")):
    secret = settings.telegram_internal_secret
    if not secret or not hmac.compare_digest(x_telegram_secret, secret.get_secret_value()):
        raise HTTPException(403, "Forbidden")


class Incoming(BaseModel):
    sender_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    text: str = Field(default="", max_length=2000)
    message_id: int = Field(default=0, ge=0)
    audio: str | None = Field(default=None, max_length=6_700_000)


class Decision(Incoming):
    draft_id: uuid.UUID
    action: Literal["confirm", "cancel"]
    revision: int | None = Field(default=None, ge=1)


@router.get("/status")
async def status(user=Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    link = (await db.execute(select(TelegramLink).where(TelegramLink.user_id == user.id))).scalar_one_or_none()
    return {"configured": bool(settings.telegram_bot_token), "linked": link is not None, "bot_username": settings.telegram_bot_username}


@router.post("/pairing")
async def pairing(user=Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await service.pairing(user, db)


@router.delete("/link", status_code=204)
async def unlink(user=Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(TelegramLink).where(TelegramLink.user_id == user.id))
    await db.execute(delete(TelegramPairing).where(TelegramPairing.user_id == user.id))
    await db.commit()


@router.post("/internal/message", dependencies=[Depends(internal_auth)])
async def message(body: Incoming, db: AsyncSession = Depends(get_db)):
    if body.sender_id != body.chat_id:
        raise HTTPException(403, "Используйте личный чат")
    if body.text.startswith("/start "):
        return await service.bind(body.text.split(maxsplit=1)[1], body.sender_id, db)
    user = await service.linked_user(body.sender_id, body.chat_id, db)
    if body.text in ("/start", "/help"):
        return {"message": "Отправьте операцию текстом или голосом. Укажите название счёта. /accounts - счета, /pending - черновики, /summary - деньги на счетах. Черновик действует 24 часа."}
    if body.text == "/accounts":
        accounts = (await db.execute(select(Account).where(Account.user_id == user.id))).scalars().all()
        return {"message": "Счета:\n" + "\n".join(a.name for a in accounts) if accounts else "Сначала создайте счёт в приложении."}
    if body.text == "/pending":
        drafts = (await db.execute(select(OperationDraftRecord).where(OperationDraftRecord.user_id == user.id,
            OperationDraftRecord.state == "pending", OperationDraftRecord.expires_at > service.now())
            .order_by(OperationDraftRecord.expires_at.desc()).limit(10))).scalars().all()
        return {"message": "Последние черновики:" if drafts else "Нет ожидающих черновиков.",
            "drafts": [service.draft_message(d) for d in drafts]}
    if body.text == "/summary":
        balances = await calculate_all_cash_balances(user, db)
        total = sum(v for (account, currency), v in balances.items() if currency == "RUB")
        return {"message": f"Деньги на счетах: {total:.2f} RUB. Это денежный остаток, без инвестиционных активов. Подробная аналитика - в приложении."}
    text = await service.transcribe(body.audio, user, db) if body.audio else body.text.removeprefix("/add ")
    result = await service.make_draft(text, f"telegram:{body.chat_id}:{body.message_id}", user, db, check_limit=not bool(body.audio))
    if body.audio:
        result["message"] = "Распознано: " + text + "\n\n" + result["message"]
    return result


@router.post("/internal/decide", dependencies=[Depends(internal_auth)])
async def decide(body: Decision, db: AsyncSession = Depends(get_db)):
    user = await service.linked_user(body.sender_id, body.chat_id, db)
    return await service.decide(body.draft_id, body.action, user, db, expected_revision=body.revision)
