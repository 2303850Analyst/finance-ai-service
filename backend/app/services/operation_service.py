import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset import Asset
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.position import Position
from app.models.user import User
from app.schemas.operation import OperationCreate
from app.services.portfolio_engine import recalculate_positions


def _validate(payload: OperationCreate) -> None:
    op = payload.operation_type

    if op in (OperationType.buy, OperationType.sell):
        if payload.asset_id is None:
            raise HTTPException(400, "asset_id is required for buy/sell")
        if payload.quantity is None or payload.quantity <= 0:
            raise HTTPException(400, "quantity must be positive for buy/sell")
        if payload.price is None or payload.price <= 0:
            raise HTTPException(400, "price must be positive for buy/sell")

    if op == OperationType.manual_valuation:
        if payload.asset_id is None:
            raise HTTPException(400, "asset_id is required for manual_valuation")
        if payload.price is None or payload.price <= 0:
            raise HTTPException(400, "price must be positive for manual_valuation")

    if op == OperationType.fee and payload.amount < 0:
        raise HTTPException(400, "fee amount cannot be negative")


async def create_operation(
    payload: OperationCreate, user: User, db: AsyncSession
) -> Operation:
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

    # Sell: check sufficient position before writing anything
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

    op = Operation(
        user_id=user.id,
        account_id=payload.account_id,
        asset_id=payload.asset_id,
        operation_type=payload.operation_type,
        status=OperationStatus.confirmed,
        quantity=payload.quantity,
        price=payload.price,
        amount=payload.amount,
        fee=payload.fee,
        currency=payload.currency,
        operated_at=payload.operated_at,
        note=payload.note,
    )
    db.add(op)
    await db.flush()  # assign id, stay in transaction

    await recalculate_positions(payload.account_id, db)
    await db.commit()
    await db.refresh(op)
    return op


async def delete_operation(
    operation_id: uuid.UUID, user: User, db: AsyncSession
) -> None:
    op = await db.get(Operation, operation_id)
    if op is None or op.user_id != user.id:
        raise HTTPException(404, "Operation not found")

    account_id = op.account_id
    await db.delete(op)
    await db.flush()

    await recalculate_positions(account_id, db)
    await db.commit()


async def list_operations(user: User, db: AsyncSession) -> list[Operation]:
    result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user.id)
        .order_by(Operation.operated_at.desc())
    )
    return result.scalars().all()
