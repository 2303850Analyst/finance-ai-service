import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.user import User
from app.schemas.transfer import TransferCreate, TransferUpdate
from app.services.cash_engine import calculate_all_cash_balances


async def create_transfer(
    payload: TransferCreate, user: User, db: AsyncSession
) -> Operation:
    """Create a transfer operation between two accounts owned by the same user."""
    # Validate from != to
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(400, "from_account_id and to_account_id must be different")

    # Validate both accounts belong to user
    from_acc = await db.get(Account, payload.from_account_id)
    if from_acc is None or from_acc.user_id != user.id:
        raise HTTPException(404, "Source account not found")

    to_acc = await db.get(Account, payload.to_account_id)
    if to_acc is None or to_acc.user_id != user.id:
        raise HTTPException(404, "Target account not found")

    if payload.amount <= Decimal("0"):
        raise HTTPException(400, "amount must be positive")

    # Validate sufficient funds: amount + fee must not exceed source account cash.
    # Expenses may go negative (e.g. credit card), but transfers must not.
    all_balances = await calculate_all_cash_balances(user, db)
    key = (str(payload.from_account_id), payload.currency)
    available = all_balances.get(key, Decimal("0"))
    fee = payload.fee or Decimal("0")
    required = payload.amount + fee
    if required > available:
        raise HTTPException(
            400,
            f"Insufficient funds on source account: "
            f"available {available} {payload.currency}, "
            f"required {required} ({payload.amount} + fee {fee})",
        )

    op = Operation(
        user_id=user.id,
        account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        operation_type=OperationType.transfer,
        status=OperationStatus.confirmed,
        amount=payload.amount,
        fee=payload.fee,
        currency=payload.currency,
        operated_at=payload.operated_at,
        note=payload.note,
    )
    db.add(op)
    await db.flush()
    await db.commit()
    await db.refresh(op)
    return op


async def update_transfer(
    operation_id: uuid.UUID, payload: TransferUpdate, user: User, db: AsyncSession
) -> Operation:
    """Update amount, fee, date, or note on an existing transfer.

    from_account and to_account cannot be changed; delete + recreate for that.
    Validates that the new amount+fee does not exceed the source account balance
    after reversing the original transfer's effect.
    """
    op = await db.get(Operation, operation_id)
    if op is None or op.user_id != user.id:
        raise HTTPException(404, "Operation not found")
    if op.operation_type != OperationType.transfer:
        raise HTTPException(400, "Operation is not a transfer")

    # Determine effective new values
    new_amount = payload.amount if payload.amount is not None else op.amount
    new_fee = payload.fee if "fee" in payload.model_fields_set else op.fee
    new_currency = payload.currency if payload.currency is not None else op.currency

    if new_amount <= Decimal("0"):
        raise HTTPException(400, "amount must be positive")

    # Validate funds: current balance + reversed current transfer effect
    all_balances = await calculate_all_cash_balances(user, db)
    source_key = (str(op.account_id), new_currency)
    available = all_balances.get(source_key, Decimal("0"))

    # Reverse the existing transfer's deduction from the source account
    old_fee = op.fee or Decimal("0")
    available += op.amount + old_fee

    new_fee_dec = new_fee or Decimal("0")
    required = new_amount + new_fee_dec
    if required > available:
        raise HTTPException(
            400,
            f"Недостаточно средств: доступно {available} {new_currency}, "
            f"требуется {required} ({new_amount} + комиссия {new_fee_dec})",
        )

    # Apply only explicitly provided fields
    for field_name in payload.model_fields_set:
        if hasattr(op, field_name):
            setattr(op, field_name, getattr(payload, field_name))

    await db.commit()
    await db.refresh(op)
    return op
