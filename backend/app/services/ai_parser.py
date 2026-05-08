"""
AI parser service.

Calls the AI provider (mock by default), then resolves account/asset names
to DB IDs using the current user's data.  Returns a ParseResponse that the
frontend can display as a preview before the user confirms.

The parser NEVER writes to the database.  It only returns a draft.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset import Asset
from app.models.user import User
from app.schemas.ai_command import OperationDraft, ParseResponse
from app.services.ai_providers.base import AIProvider
from app.services.ai_providers.mock_provider import MockProvider

_provider: AIProvider = MockProvider()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def parse_operation_text(
    text: str,
    user: User,
    db: AsyncSession,
) -> ParseResponse:
    proposal = _provider.parse_operation(text)

    # ── not an operation ──────────────────────────────────────────────────────
    if not proposal.is_operation:
        return ParseResponse(
            status="not_operation",
            raw_text=text,
            message=proposal.message or "Это не финансовая операция.",
        )

    # ── provider itself flagged clarification needed ───────────────────────────
    if proposal.clarification_needed and proposal.missing_fields:
        return ParseResponse(
            status="need_clarification",
            raw_text=text,
            missing_fields=proposal.missing_fields,
            message=f"Не хватает полей: {', '.join(proposal.missing_fields)}",
        )

    # ── resolve account ───────────────────────────────────────────────────────
    account_id: uuid.UUID | None = None
    missing: list[str] = []

    if proposal.account_name:
        result = await db.execute(
            select(Account).where(
                Account.user_id == user.id,
                Account.name == proposal.account_name,
            )
        )
        acc = result.scalar_one_or_none()
        if acc is None:
            missing.append("account")
        else:
            account_id = acc.id

    # ── resolve asset ─────────────────────────────────────────────────────────
    asset_id: uuid.UUID | None = None
    resolved_ticker: str | None = proposal.asset_ticker
    resolved_name: str | None = proposal.asset_name

    if proposal.asset_ticker:
        result = await db.execute(
            select(Asset).where(Asset.ticker == proposal.asset_ticker)
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            missing.append("asset")
        else:
            asset_id = asset.id
            resolved_ticker = asset.ticker
            resolved_name = asset.name

    # ── build draft ───────────────────────────────────────────────────────────
    draft = OperationDraft(
        operation_type=proposal.operation_type or "unknown",
        account_name=proposal.account_name,
        asset_ticker=resolved_ticker,
        asset_name=resolved_name,
        quantity=proposal.quantity,
        price=proposal.price,
        amount=proposal.amount,
        fee=proposal.fee,
        currency=proposal.currency,
        operated_at=_now_iso(),
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
        asset_id=asset_id,
        warnings=["AI-разбор. Проверьте данные перед подтверждением."],
    )
