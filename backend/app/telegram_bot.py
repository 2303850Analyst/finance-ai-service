"""Polling transport only; business decisions are made by the backend."""
import asyncio
import base64
import io
import logging
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from app.config import settings

log = logging.getLogger(__name__)
dp = Dispatcher()


def keyboard(draft_id, revision=1):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Подтвердить", callback_data=f"confirm:{draft_id}:{revision}"),
        InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{draft_id}:{revision}")]])


async def backend(path, payload):
    try:
        async with httpx.AsyncClient(timeout=150) as client:
            r = await client.post(settings.backend_internal_url + "/api/v1/telegram/internal/" + path,
                headers={"X-Telegram-Secret": settings.telegram_internal_secret.get_secret_value()}, json=payload)
        if r.is_success:
            return r.json()
        detail = r.json().get("detail")
        return {"message": detail if isinstance(detail, str) else "Проверьте сообщение и повторите ввод.", "error": True}
    except (httpx.HTTPError, ValueError):
        return {"message": "Сервис временно недоступен. Попробуйте позже. Черновики доступны через /pending.", "error": True}


async def answer(message, result):
    await message.answer(result["message"][:4000], reply_markup=keyboard(result["draft_id"], result.get("revision", 1)) if result.get("draft_id") else None)
    for draft in result.get("drafts", []):
        await answer(message, draft)


@dp.message(F.chat.type == "private")
async def incoming(message: Message, bot: Bot):
    if not message.from_user or message.from_user.is_bot:
        return
    payload = {"sender_id": message.from_user.id, "chat_id": message.chat.id,
        "message_id": message.message_id, "text": message.text or ""}
    if message.voice:
        if message.voice.duration > 120 or (message.voice.file_size or 0) > 5_000_000:
            await message.answer("Отправьте голосовое сообщение до 2 минут и 5 МБ.")
            return
        authorized = await backend("message", {**payload, "text": "/help"})
        if authorized.get("error"):
            await answer(message, authorized)
            return
        data = io.BytesIO()
        try:
            await bot.download(message.voice, destination=data)
        except Exception:
            await message.answer("Не удалось скачать голосовое сообщение. Повторите отправку.")
            return
        payload["audio"] = base64.b64encode(data.getvalue()).decode()
    elif not message.text:
        await message.answer("Отправьте текст или голосовое сообщение.")
        return
    await answer(message, await backend("message", payload))


@dp.callback_query()
async def callback(query: CallbackQuery):
    if not query.message or query.message.chat.type != "private" or not query.data:
        await query.answer()
        return
    await query.answer()
    try:
        parts = query.data.split(":")
        action, draft_id = parts[:2]
        revision = int(parts[2]) if len(parts) == 3 else None
    except ValueError:
        return
    result = await backend("decide", {"sender_id": query.from_user.id, "chat_id": query.message.chat.id,
        "action": action, "draft_id": draft_id, "revision": revision})
    await answer(query.message, result)
    if not result.get("error"):
        await query.message.edit_reply_markup(reply_markup=None)


async def main():
    if not settings.telegram_bot_token or not settings.telegram_internal_secret:
        raise RuntimeError("Telegram configuration is missing")
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    async with Bot(settings.telegram_bot_token.get_secret_value()) as bot:
        info = await bot.get_webhook_info()
        if info.url:
            raise RuntimeError("Existing webhook detected; polling will not replace it")
        me = await bot.get_me()
        log.warning("Finance bot @%s started", me.username)
        await dp.start_polling(bot, handle_as_tasks=False, close_bot_session=False)


if __name__ == "__main__":
    asyncio.run(main())
