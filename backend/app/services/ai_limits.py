"""
AI rate-limiting service.

Checks per-user cooldown, daily request limit, monthly request limit,
and monthly cost cap before allowing a provider call.  Also provides
a helper to persist AIUsageEvent records.

All DB reads use simple COUNT / MAX queries — no ORM lazy-loading.
"""
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.ai_usage_event import AIUsageEvent

log = logging.getLogger(__name__)


# ── result type ───────────────────────────────────────────────────────────────

class RateLimitResult(NamedTuple):
    allowed: bool
    reason: str | None = None                 # human-readable Russian message
    cooldown_seconds_remaining: int | None = None


# ── public API ────────────────────────────────────────────────────────────────

async def check_rate_limits(
    user_id: uuid.UUID | None,
    db: AsyncSession,
    settings: Settings,
) -> RateLimitResult:
    """
    Return RateLimitResult(allowed=True) if all checks pass,
    or RateLimitResult(allowed=False, reason=...) on first exceeded limit.
    """
    now = datetime.now(timezone.utc)

    if user_id is None:
        # Anonymous / dev — skip per-user limits but still allow
        return RateLimitResult(allowed=True)

    # ── 1. Cooldown ───────────────────────────────────────────────────────────
    cooldown = settings.ai_cooldown_seconds
    if cooldown > 0:
        # Find the most recent non-blocked event for this user
        stmt = (
            select(func.max(AIUsageEvent.created_at))
            .where(
                AIUsageEvent.user_id == user_id,
                AIUsageEvent.status.notin_(["blocked"]),
            )
        )
        result = await db.execute(stmt)
        last_at: datetime | None = result.scalar_one_or_none()
        if last_at is not None:
            # Ensure timezone-aware comparison
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            elapsed = (now - last_at).total_seconds()
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed) + 1
                return RateLimitResult(
                    allowed=False,
                    reason=f"Подождите {remaining} сек. перед следующим запросом.",
                    cooldown_seconds_remaining=remaining,
                )

    # ── 2. Daily request limit ────────────────────────────────────────────────
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(func.count())
        .select_from(AIUsageEvent)
        .where(
            AIUsageEvent.user_id == user_id,
            AIUsageEvent.status.in_(["success", "error", "rate_limited"]),
            AIUsageEvent.created_at >= day_start,
        )
    )
    result = await db.execute(stmt)
    daily_count: int = result.scalar_one()
    if daily_count >= settings.ai_daily_request_limit:
        return RateLimitResult(
            allowed=False,
            reason=f"Дневной лимит запросов исчерпан ({settings.ai_daily_request_limit}/день). Попробуйте завтра.",
        )

    # ── 3. Monthly request limit ──────────────────────────────────────────────
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(func.count())
        .select_from(AIUsageEvent)
        .where(
            AIUsageEvent.user_id == user_id,
            AIUsageEvent.status.in_(["success", "error"]),
            AIUsageEvent.created_at >= month_start,
        )
    )
    result = await db.execute(stmt)
    monthly_count: int = result.scalar_one()
    if monthly_count >= settings.ai_monthly_request_limit:
        return RateLimitResult(
            allowed=False,
            reason=f"Месячный лимит запросов исчерпан ({settings.ai_monthly_request_limit}/мес).",
        )

    # ── 4. Monthly cost cap (per-user) ────────────────────────────────────────
    if settings.ai_user_monthly_budget_usd > 0:
        stmt = (
            select(func.coalesce(func.sum(AIUsageEvent.estimated_cost_usd), 0))
            .where(
                AIUsageEvent.user_id == user_id,
                AIUsageEvent.status == "success",
                AIUsageEvent.estimated_cost_usd.isnot(None),
                AIUsageEvent.created_at >= month_start,
            )
        )
        result = await db.execute(stmt)
        monthly_cost: Decimal = result.scalar_one()
        if float(monthly_cost) >= settings.ai_user_monthly_budget_usd:
            return RateLimitResult(
                allowed=False,
                reason="Месячный бюджет на AI исчерпан. Свяжитесь с поддержкой.",
            )

    return RateLimitResult(allowed=True)


async def log_usage_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    provider: str,
    model: str | None,
    request_kind: str,
    input_chars: int,
    status: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
) -> AIUsageEvent | None:
    """
    Insert an AIUsageEvent and flush (caller commits).

    Fault-tolerant:
    - If insert fails with a FK/integrity error (e.g. user_id not in users),
      rolls back and retries once with user_id=None.
    - If retry also fails, swallows the error so the parse response is unaffected.
    - Never raises.
    """
    def _make_event(uid: uuid.UUID | None) -> AIUsageEvent:
        return AIUsageEvent(
            user_id=uid,
            provider=provider,
            model=model,
            request_kind=request_kind,
            input_chars=input_chars,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            status=status,
            error_message=error_message,
            latency_ms=latency_ms,
        )

    try:
        event = _make_event(user_id)
        db.add(event)
        await db.flush()
        return event
    except Exception as exc:
        log.warning("log_usage_event: flush failed (%s), retrying with user_id=null", exc)
        try:
            await db.rollback()
        except Exception:
            pass
        if user_id is not None:
            # Retry with null user_id to avoid FK constraint
            try:
                event = _make_event(None)
                db.add(event)
                await db.flush()
                return event
            except Exception as exc2:
                log.error("log_usage_event: retry also failed (%s) — event dropped", exc2)
        return None
