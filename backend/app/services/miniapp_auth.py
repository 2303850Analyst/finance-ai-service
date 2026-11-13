"""Telegram-signed identity, scoped to an existing binding. No dev-user fallback."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.telegram import TelegramLink
from app.models.user import User


def telegram_identity(raw: str) -> int:
    denied = HTTPException(401, "Откройте Mini App заново из меню бота.")
    if not settings.telegram_bot_token or not raw or len(raw) > 16384:
        raise denied
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError("duplicate field")
        received = data.pop("hash")
        if len(received) != 64:
            raise ValueError("hash")
        secret = hmac.new(b"WebAppData", settings.telegram_bot_token.get_secret_value().encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, "\n".join(f"{k}={v}" for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received, expected):
            raise ValueError("signature")
        age = time.time() - int(data["auth_date"])
        if age < -30 or age > settings.miniapp_auth_max_age_seconds:
            raise ValueError("expired")
        identity = json.loads(data["user"])
        user_id = identity["id"]
        if type(user_id) is not int or user_id <= 0 or identity.get("is_bot"):
            raise ValueError("identity")
        return user_id
    except (ValueError, KeyError, TypeError):
        raise denied from None


async def current_miniapp_user(authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    if not authorization.startswith("tma "):
        raise HTTPException(401, "Откройте Mini App из меню бота Telegram.")
    identity = telegram_identity(authorization[4:])
    link = await db.get(TelegramLink, identity)
    user = await db.get(User, link.user_id) if link else None
    if user is None or not user.is_active:
        raise HTTPException(403, "Сначала подключите Telegram в локальном приложении: раздел Telegram → Подключить.")
    return user
