"""
AI parser service.

Calls the AI provider (mock or OpenRouter), resolves account/asset names
to DB IDs, applies rate limiting, logs every request to ai_usage_events.

The parser NEVER writes financial data to the database.
It only returns a draft that the user confirms.

Flow:
  1. Scope guard  → blocked  → log blocked event, return not_operation
  2. Rate limits  → exceeded → log rate_limited event, return rate_limited
  3. Provider call (timed)
     a. success   → log success event, map proposal → OperationDraft
     b. error     → log error event,   return provider_error
  4. Normalise entity text (asset alias map, account alias map)
  5. Resolve account/asset IDs
  6. Return ParseResponse
"""
import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as _global_settings
from app.models.account import Account
from app.models.asset import Asset
from app.models.user import User
from app.schemas.ai_command import OperationDraft, ParseResponse
from app.services.ai_limits import check_rate_limits, log_usage_event
from app.services.ai_providers.base import AIProvider, RawProposal
from app.services.ai_providers.mock_provider import MockProvider
from app.services.ai_scope_guard import ScopeCategory, classify


# ── provider factory ──────────────────────────────────────────────────────────

def _make_provider() -> AIProvider | None:
    """
    Return the configured provider, or None if configuration is invalid.
    Returning None signals a provider_error to the caller.
    """
    cfg = _global_settings
    if cfg.ai_provider == "openrouter":
        if cfg.openrouter_api_key is None:
            return None
        from app.services.ai_providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            api_key=cfg.openrouter_api_key.get_secret_value(),
            model_primary=cfg.openrouter_model_primary,
            model_fallback=cfg.openrouter_model_fallback,
            max_output_tokens=cfg.ai_max_output_tokens,
            temperature=cfg.ai_temperature,
        )
    # default: mock
    return MockProvider()


# Module-level singleton — built once at import time.
# Tests may swap this via parser_module._provider = <stub>.
_provider: AIProvider | None = _make_provider()
_provider_name: str = _global_settings.ai_provider


# ── entity normalisation (MVP alias resolver) ─────────────────────────────────

_ASSET_NOISE = re.compile(
    r"\b(акций|акции|акцию|акция|бумаг|бумаги|бумагу|паев|паи|тикер|тикера)\b",
    re.IGNORECASE | re.UNICODE,
)

# Canonical ticker map — Russian inflections and common spellings
_ASSET_ALIASES: dict[str, str] = {
    # Сбербанк
    "сбер": "SBER", "сбера": "SBER", "сбербанк": "SBER", "сбербанка": "SBER",
    # Яндекс
    "яндекс": "YDEX", "яндекса": "YDEX",
    # Лукойл
    "лукойл": "LKOH", "лукойла": "LKOH", "лукойле": "LKOH",
    # Bitcoin
    "биткоин": "BTC", "биткоина": "BTC", "биток": "BTC", "bitcoin": "BTC", "btc": "BTC",
    # Газпром
    "газпром": "GAZP", "газпрома": "GAZP",
    # ВТБ
    "втб": "VTBR",
    # Норникель
    "норникель": "GMKN", "норникеля": "GMKN",
}

_CURRENCY_TICKERS_SET = frozenset({"RUB", "USD", "EUR", "GBP", "CNY", "JPY", "USDT", "USDC"})

# Account canonical name map — covers common inflection forms
_ACCOUNT_ALIASES: dict[str, str] = {
    "наличных": "Наличные",
    "наличка": "Наличные",
    "наличными": "Наличные",
    "налички": "Наличные",
    "наличное": "Наличные",
    "т-инвестиции": "Т-Инвестиции",
    "тинькофф инвестиции": "Т-Инвестиции",
    "т инвестиции": "Т-Инвестиции",
    "тинькофф": "Т-Инвестиции",
}

# "карта" and similar → try to find a unique cash/bank account
_CARD_ALIASES = frozenset({
    "карта", "картой", "карты", "карточка",
    "кредитка", "дебетовая карта", "дебетовой карты",
})


def _normalize_asset(
    ticker: str | None,
    name: str | None,
) -> tuple[str | None, str | None]:
    """
    Return (ticker, name) with normalisation applied.
    Priority: explicit uppercase ticker > alias lookup on name text.
    """
    # If ticker already set (e.g. from mock provider), keep it
    if ticker and ticker.upper() not in _CURRENCY_TICKERS_SET:
        return ticker.upper(), name

    if not name:
        return ticker, name

    # Look for an explicit uppercase word in the name text (e.g. "SBER", "BTC")
    for word in name.split():
        w = word.strip(",.!?()[]")
        if w.isupper() and 2 <= len(w) <= 5 and w not in _CURRENCY_TICKERS_SET:
            return w, name

    # Remove stock noise words ("акций", "бумаг", …)
    cleaned = _ASSET_NOISE.sub("", name).strip()

    # Check each remaining word against alias map
    for word in cleaned.split():
        wl = word.lower().strip(",.!?()[]")
        if wl in _ASSET_ALIASES:
            return _ASSET_ALIASES[wl], cleaned or name

    # Try the whole cleaned text as an alias
    if cleaned.lower() in _ASSET_ALIASES:
        return _ASSET_ALIASES[cleaned.lower()], cleaned

    return ticker, name


def _normalize_account_name(name: str | None) -> tuple[str | None, bool]:
    """
    Return (canonical_name, is_fuzzy_card).
    is_fuzzy_card=True → caller should attempt to find a unique cash/bank account.
    """
    if not name:
        return None, False
    lower = name.lower().strip()
    if lower in _ACCOUNT_ALIASES:
        return _ACCOUNT_ALIASES[lower], False
    if lower in _CARD_ALIASES:
        return None, True   # signal: find unique cash/bank account
    return name, False


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_since(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


# ── main entry point ──────────────────────────────────────────────────────────

async def parse_operation_text(
    text: str,
    user: User,
    db: AsyncSession,
    *, check_limit: bool = True,
) -> ParseResponse:
    cfg = _global_settings
    user_id: uuid.UUID | None = user.id if user else None
    input_chars = len(text)

    # ── 1. Scope guard ────────────────────────────────────────────────────────
    scope = classify(text)
    if scope.category == ScopeCategory.BLOCKED:
        await log_usage_event(
            db,
            user_id=user_id,
            provider=_provider_name,
            model=None,
            request_kind="parse_operation",
            input_chars=input_chars,
            status="blocked",
        )
        return ParseResponse(
            status="not_operation",
            raw_text=text,
            message=scope.safe_response,
        )

    # ── 2. Provider availability ──────────────────────────────────────────────
    if _provider is None:
        # ai_provider=openrouter but no key configured
        return ParseResponse(
            status="not_operation",
            raw_text=text,
            provider_error=(
                "AI провайдер не настроен: отсутствует OPENROUTER_API_KEY. "
                "Обратитесь к администратору."
            ),
        )

    # ── 3. Rate limits ────────────────────────────────────────────────────────
    limit_result = await check_rate_limits(user_id, db, cfg)
    if check_limit and not limit_result.allowed:
        await log_usage_event(
            db,
            user_id=user_id,
            provider=_provider_name,
            model=None,
            request_kind="parse_operation",
            input_chars=input_chars,
            status="rate_limited",
            error_message=limit_result.reason,
        )
        return ParseResponse(
            status="not_operation",
            raw_text=text,
            rate_limited=True,
            cooldown_seconds_remaining=limit_result.cooldown_seconds_remaining,
            message=limit_result.reason,
        )

    # ── 4. Truncate oversized input ───────────────────────────────────────────
    if input_chars > cfg.ai_max_input_chars:
        text = text[: cfg.ai_max_input_chars]

    # ── 5. Provider call (timed) ──────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        proposal: RawProposal = await _provider.parse_operation(text)
        latency_ms = _ms_since(t0)
    except Exception as exc:  # noqa: BLE001
        latency_ms = _ms_since(t0)
        await log_usage_event(
            db,
            user_id=user_id,
            provider=_provider_name,
            model=None,
            request_kind="parse_operation",
            input_chars=input_chars,
            status="error",
            error_message=str(exc)[:500],
            latency_ms=latency_ms,
        )
        return ParseResponse(
            status="not_operation",
            raw_text=text,
            provider_error="AI временно недоступен. Попробуйте ещё раз.",
        )

    # Log success event (fault-tolerant; never raises)
    await log_usage_event(
        db,
        user_id=user_id,
        provider=_provider_name,
        model=None,
        request_kind="parse_operation",
        input_chars=input_chars,
        status="success",
        latency_ms=latency_ms,
    )

    # ── 6. Not an operation ───────────────────────────────────────────────────
    if not proposal.is_operation:
        return ParseResponse(
            status="not_operation",
            raw_text=text,
            message=proposal.message or "Это не финансовая операция.",
        )

    # ── 7. Clarification needed (provider flagged missing fields) ─────────────
    if proposal.clarification_needed:
        draft = _build_draft(proposal)
        return ParseResponse(
            status="need_clarification",
            raw_text=text,
            operation=draft,
            missing_fields=proposal.missing_fields,
            message=proposal.message or f"Не хватает полей: {', '.join(proposal.missing_fields)}",
        )

    # ── 8. Normalise entity text ──────────────────────────────────────────────
    norm_ticker, norm_name = _normalize_asset(proposal.asset_ticker, proposal.asset_name)
    norm_account, is_card_account = _normalize_account_name(proposal.account_name)
    norm_to_account, is_card_to_account = _normalize_account_name(proposal.to_account_name)

    # ── 9. Resolve account ────────────────────────────────────────────────────
    account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    missing: list[str] = []

    if norm_account:
        acc = await _find_account(norm_account, user.id, db)
        if acc is None:
            missing.append("account")
        else:
            account_id = acc.id
            norm_account = acc.name   # use exact DB name
    elif is_card_account:
        # "карта" and similar — try unique cash/bank account
        acc = await _find_unique_cash_bank_account(user.id, db)
        if acc is not None:
            account_id = acc.id
            norm_account = acc.name
        # If ambiguous (0 or >1), leave account_id=None without adding to missing

    if norm_to_account:
        to_acc = await _find_account(norm_to_account, user.id, db)
        if to_acc is None:
            missing.append("to_account")
        else:
            to_account_id = to_acc.id
            norm_to_account = to_acc.name
    elif is_card_to_account:
        to_acc = await _find_unique_cash_bank_account(user.id, db)
        if to_acc is not None:
            to_account_id = to_acc.id
            norm_to_account = to_acc.name

    # ── 10. Resolve asset ─────────────────────────────────────────────────────
    asset_id: uuid.UUID | None = None

    if norm_ticker:
        result = await db.execute(
            select(Asset).where(Asset.ticker == norm_ticker.upper())
        )
        asset = result.scalar_one_or_none()
        if asset is None and norm_name:
            # Try name partial match as fallback
            result = await db.execute(
                select(Asset).where(Asset.name.ilike(f"%{norm_name}%"))
            )
            asset = result.scalar_one_or_none()
        if asset is None:
            if proposal.operation_type in ("buy", "sell", "manual_valuation"):
                missing.append("asset")
        else:
            asset_id = asset.id
            norm_ticker = asset.ticker
            norm_name = asset.name

    # ── 11. Build draft ───────────────────────────────────────────────────────
    draft = _build_draft(
        proposal,
        resolved_ticker=norm_ticker,
        resolved_name=norm_name,
        resolved_account=norm_account,
        resolved_to_account=norm_to_account,
    )

    if missing:
        return ParseResponse(
            status="need_clarification",
            raw_text=text,
            operation=draft,
            missing_fields=missing,
            message=f"Не найдено в базе: {', '.join(missing)}",
        )

    return ParseResponse(
        status="parsed",
        raw_text=text,
        operation=draft,
        account_id=account_id,
        to_account_id=to_account_id,
        asset_id=asset_id,
        warnings=["AI-разбор. Проверьте данные перед подтверждением."],
    )


# ── helpers ───────────────────────────────────────────────────────────────────

async def _find_account(
    name: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Account | None:
    result = await db.execute(
        select(Account).where(
            Account.user_id == user_id,
            func.lower(Account.name) == name.lower(),
        )
    )
    accounts = result.scalars().all()
    return accounts[0] if len(accounts) == 1 else None


async def _find_unique_cash_bank_account(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Account | None:
    """Return account if there is exactly one cash or bank account; None if ambiguous."""
    result = await db.execute(
        select(Account).where(
            Account.user_id == user_id,
            Account.account_type.in_(["cash", "bank"]),
        )
    )
    accounts = result.scalars().all()
    return accounts[0] if len(accounts) == 1 else None


def _build_draft(
    p: RawProposal,
    *,
    resolved_ticker: str | None = None,
    resolved_name: str | None = None,
    resolved_account: str | None = None,
    resolved_to_account: str | None = None,
) -> OperationDraft:
    return OperationDraft(
        operation_type=p.operation_type or "unknown",
        account_name=resolved_account or p.account_name,
        to_account_name=resolved_to_account or p.to_account_name,
        asset_ticker=resolved_ticker or p.asset_ticker,
        asset_name=resolved_name or p.asset_name,
        quantity=p.quantity,
        price=p.price,
        amount=p.amount,
        fee=p.fee,
        currency=p.currency,
        operated_at=p.operated_at or _now_iso(),
        expense_group=p.expense_group,
        expense_category=p.expense_category,
        merchant=p.merchant,
        income_source=p.income_source,
        principal_amount=p.principal_amount,
        interest_amount=p.interest_amount,
        linked_asset_text=p.linked_asset_name,
        note=p.note,
    )
