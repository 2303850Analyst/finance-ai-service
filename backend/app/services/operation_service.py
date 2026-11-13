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
from app.schemas.operation import OperationCreate, OperationUpdate
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

    if op == OperationType.expense:
        if payload.amount <= 0:
            raise HTTPException(400, "expense amount must be positive")
        if not payload.is_refund and not payload.expense_group:
            raise HTTPException(400, "expense_group is required for expense operations")


async def _build_and_insert_operation(
    payload: OperationCreate, user_id: uuid.UUID, db: AsyncSession
) -> Operation:
    """Insert one operation row and flush (no commit). Caller owns the transaction."""
    op = Operation(
        user_id=user_id,
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
        income_source=payload.income_source,
        expense_group=getattr(payload, "expense_group", None),
        expense_category=getattr(payload, "expense_category", None),
        merchant=getattr(payload, "merchant", None),
        is_refund=getattr(payload, "is_refund", False) or False,
        principal_amount=getattr(payload, "principal_amount", None),
        interest_amount=getattr(payload, "interest_amount", None),
        liability_name=getattr(payload, "liability_name", None),
        linked_asset_id=getattr(payload, "linked_asset_id", None),
        to_account_id=getattr(payload, "to_account_id", None),
    )
    db.add(op)
    await db.flush()
    return op


async def create_operation(
    payload: OperationCreate, user: User, db: AsyncSession, *, commit: bool = True
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

    op = await _build_and_insert_operation(payload, user.id, db)
    await recalculate_positions(payload.account_id, db)
    if commit:
        await db.commit()
        await db.refresh(op)
    return op


async def update_operation(
    operation_id: uuid.UUID, payload: OperationUpdate, user: User, db: AsyncSession
) -> Operation:
    """Update a non-transfer, non-buy/sell operation.

    Only fields present in the request body (model_fields_set) are applied.
    Pass a field with null value to clear it.
    """
    op = await db.get(Operation, operation_id)
    if op is None or op.user_id != user.id:
        raise HTTPException(404, "Operation not found")

    if op.operation_type in (OperationType.buy, OperationType.sell):
        raise HTTPException(
            400,
            "Редактирование покупок и продаж временно недоступно. "
            "Удалите операцию и создайте заново.",
        )
    if op.operation_type == OperationType.transfer:
        raise HTTPException(
            400,
            "Для редактирования перевода используйте PATCH /api/v1/operations/transfer/{id}",
        )

    # Validate linked_asset_id if being changed
    if "linked_asset_id" in payload.model_fields_set and payload.linked_asset_id is not None:
        asset = await db.get(Asset, payload.linked_asset_id)
        if asset is None:
            raise HTTPException(404, "Linked asset not found")

    # Apply only the fields that were explicitly included in the request
    for field_name in payload.model_fields_set:
        if hasattr(op, field_name):
            setattr(op, field_name, getattr(payload, field_name))

    # Recalculate positions if the operation affects portfolio state
    if op.operation_type == OperationType.manual_valuation:
        await recalculate_positions(op.account_id, db)

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
