"""Small bounded gateway for analytics planning and speech. Never sends ledger data."""
from decimal import Decimal
import httpx
from fastapi import HTTPException
from app.config import settings
from app.services.ai_transport import tls_context
from app.services.ai_limits import check_rate_limits, log_usage_event


async def call_ai(path, payload, kind, user, db, *, check_limit=True):
    if not settings.openrouter_api_key:
        raise HTTPException(503, "Не настроен ключ AI")
    if check_limit:
        limit = await check_rate_limits(user.id, db, settings)
        if not limit.allowed:
            raise HTTPException(429, limit.reason)
    try:
        async with httpx.AsyncClient(timeout=60, verify=tls_context()) as client:
            response = await client.post("https://openrouter.ai/api/v1/" + path,
                headers={"Authorization": "Bearer " + settings.openrouter_api_key.get_secret_value()}, json=payload)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Invalid provider response")
    except (httpx.HTTPError, ValueError):
        await log_usage_event(db, user_id=user.id, provider="openrouter", model=payload["model"],
            request_kind=kind, input_chars=0, status="error")
        await db.commit()
        raise HTTPException(503, "AI временно недоступен. Повторите запрос позже.") from None
    usage = body.get("usage") or {}
    await log_usage_event(db, user_id=user.id, provider="openrouter", model=payload["model"],
        request_kind=kind, input_chars=0, status="success", input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        estimated_cost_usd=Decimal(str(usage["cost"])) if usage.get("cost") is not None else None)
    await db.commit()
    return body
