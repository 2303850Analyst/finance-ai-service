"""Configure the bound owner's chat menu. This does not send chat messages."""
import asyncio
from urllib.parse import urlparse
from aiogram import Bot
from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy import select
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.telegram import TelegramLink
from app.models.user import User
from app.dependencies import DEV_USER_EMAIL


async def configure():
    url = settings.miniapp_url
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path != "/miniapp":
        raise ValueError("Invalid Mini App HTTPS address")
    async with AsyncSessionLocal() as db:
        link = (await db.execute(select(TelegramLink).join(User, User.id == TelegramLink.user_id)
            .where(User.email == DEV_USER_EMAIL, User.is_active.is_(True)))).scalar_one_or_none()
        if not link:
            raise ValueError("Connect Telegram in the local app first")
        async with Bot(settings.telegram_bot_token.get_secret_value()) as bot:
            button = MenuButtonWebApp(text="Открыть FinAI", web_app=WebAppInfo(url=url))
            await bot.set_chat_menu_button(chat_id=link.telegram_id, menu_button=button)
            actual = await bot.get_chat_menu_button(chat_id=link.telegram_id)
            if not isinstance(actual, MenuButtonWebApp) or actual.web_app.url != url:
                raise RuntimeError("Menu verification failed")
    print("Mini App menu configured and verified.")


if __name__ == "__main__":
    try:
        asyncio.run(configure())
    except Exception as error:
        # API errors may contain request URLs. Never print token-bearing tracebacks.
        print("Mini App menu setup failed: " + type(error).__name__)
        raise SystemExit(1)
