from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset import Asset
from app.models.operation import OperationType
from app.models.position import Position
from app.models.user import User
from app.schemas.funding import (
    ConfirmWithFundingRequest,
    ConfirmWithFundingResponse,
    FundingRequired,
)
from app.schemas.operation import OperationCreate
from app.services.cash_engine import get_account_cash_balance
from app.services.operation_service import _build_and_insert_operation, _validate
from app.services.portfolio_engine import recalculate_positions


async def confirm_with_funding(
    req: ConfirmWithFundingRequest, user: User, db: AsyncSession
) -> ConfirmWithFundingResponse:
    payload = req.operation

    # Account ownership
    account = await db.get(Account, payload.account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")

    # Asset existence
    if payload.asset_id is not None:
        asset = await db.get(Asset, payload.asset_id)
        if asset is None:
            raise HTTPException(404, "Asset not found")

    _validate(payload)

    # Sell: check sufficient position
    if payload.operation_type == OperationType.sell and payload.asset_id is not None:
        result = await db.execute(
            select(Position).where(
                Position.account_id == payload.account_id,
                Position.asset_id == payload.asset_id,
            )
        )
        pos = result.scalar_one_or_none()
        available = pos.quantity if pos else Decimal("0")
        requested = payload.quantity or Decimal("0")
        if available < requested:
            raise HTTPException(
                400,
                f"Insufficient quantity: available {available}, requested {requested}",
            )

    # Only buy operations need cash check
    if payload.operation_type != OperationType.buy:
        op = await _build_and_insert_operation(payload, user.id, db)
        await recalculate_positions(payload.account_id, db)
        await db.commit()
        await db.refresh(op)
        return ConfirmWithFundingResponse(status="ok", operation=op)

    # Cash check for buy
    fee = payload.fee or Decimal("0")
    cash_required = payload.amount + fee
    cash_available = await get_account_cash_balance(
        str(payload.account_id), payload.currency, user, db
    )
    missing_cash = cash_required - cash_available

    if missing_cash > Decimal("0") and not req.force_funding:
        return ConfirmWithFundingResponse(
            status="funding_required",
            funding_required=FundingRequired(
                cash_available=cash_available,
                cash_required=cash_required,
                missing_cash=missing_cash,
                currency=payload.currency,
                account_id=payload.account_id,
            ),
        )

    deposit_op = None
    if missing_cash > Decimal("0"):
        deposit_payload = OperationCreate(
            account_id=payload.account_id,
            asset_id=None,
            operation_type=OperationType.deposit,
            quantity=None,
            price=None,
            amount=missing_cash,
            fee=req.deposit_fee,
            currency=payload.currency,
            operated_at=payload.operated_at or datetime.now(timezone.utc),
            note="[auto_funding]",
        )
        deposit_op = await _build_and_insert_operation(deposit_payload, user.id, db)

    buy_op = await _build_and_insert_operation(payload, user.id, db)
    await recalculate_positions(payload.account_id, db)
    await db.commit()

    if deposit_op is not None:
        await db.refresh(deposit_op)
    await db.refresh(buy_op)

    return ConfirmWithFundingResponse(
        status="ok",
        operation=buy_op,
        deposit=deposit_op,
    )
