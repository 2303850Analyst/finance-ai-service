from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.user import User

CashKey = tuple[str, str]  # (account_id_str, currency)


def _apply_operation(balance: Decimal, op: Operation) -> Decimal:
    fee = op.fee or Decimal("0")
    ot = op.operation_type
    if ot == OperationType.deposit:
        return balance + op.amount
    elif ot == OperationType.withdraw:
        return balance - op.amount - fee
    elif ot == OperationType.buy:
        return balance - op.amount - fee
    elif ot == OperationType.sell:
        return balance + op.amount - fee
    elif ot in (OperationType.dividend, OperationType.coupon):
        return balance + op.amount
    elif ot in (OperationType.fee, OperationType.tax):
        return balance - op.amount
    elif ot == OperationType.manual_valuation:
        return balance
    elif ot == OperationType.expense:
        is_refund = getattr(op, "is_refund", False) or False
        expense_group = getattr(op, "expense_group", None)
        if is_refund:
            return balance + op.amount
        elif expense_group == "credit":
            # fee is already included in amount (principal + interest + fee = amount)
            return balance - op.amount
        else:
            # living/investment: fee is an extra transaction cost on top of purchase amount
            return balance - op.amount - fee
    elif ot == OperationType.transfer:
        # Net effect on aggregate cash: only fee reduces total cash
        # (from_account loses amount+fee, to_account gains amount — net is -fee)
        return balance - fee
    return balance


async def calculate_all_cash_balances(
    user: User, db: AsyncSession
) -> dict[CashKey, Decimal]:
    account_ids_result = await db.execute(
        select(Account.id).where(Account.user_id == user.id)
    )
    account_ids = [row[0] for row in account_ids_result.fetchall()]
    if not account_ids:
        return {}

    ops_result = await db.execute(
        select(Operation).where(
            Operation.account_id.in_(account_ids),
            Operation.status == OperationStatus.confirmed,
        ).order_by(Operation.operated_at.asc(), Operation.created_at.asc())
    )
    operations = ops_result.scalars().all()

    balances: dict[CashKey, Decimal] = defaultdict(Decimal)
    for op in operations:
        key: CashKey = (str(op.account_id), op.currency)
        if op.operation_type == OperationType.transfer:
            fee_amt = op.fee or Decimal("0")
            balances[key] -= op.amount + fee_amt
            if op.to_account_id is not None:
                to_key: CashKey = (str(op.to_account_id), op.currency)
                balances[to_key] += op.amount
        else:
            balances[key] = _apply_operation(balances[key], op)

    return dict(balances)


async def get_account_cash_balance(
    account_id: str, currency: str, user: User, db: AsyncSession
) -> Decimal:
    all_balances = await calculate_all_cash_balances(user, db)
    return all_balances.get((account_id, currency), Decimal("0"))
