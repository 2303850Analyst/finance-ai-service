from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.operation import OperationType
from app.services.cash_engine import _apply_operation
from app.schemas.budget import BudgetSummaryOut, CategoryLineOut, ExpensesByCategoryOut


@dataclass
class BudgetSummary:
    income_total: Decimal
    living_expense_total: Decimal
    investment_expense_total: Decimal
    credit_payment_total: Decimal
    credit_principal_total: Decimal
    credit_interest_fee_total: Decimal
    free_cashflow: Decimal
    invested_total: Decimal
    sold_assets_total: Decimal
    cash_start: Decimal
    cash_end: Decimal
    cash_reconciliation_delta: Decimal | None
    has_reconciliation_warning: bool


def compute_budget_summary(
    pre_period_ops: list,
    period_ops: list,
    period_from: date,
    period_to: date,
    currency: str = "RUB",
) -> BudgetSummaryOut:
    Q = Decimal("0.01")

    # 1. cash_start: fold _apply_operation over pre_period_ops filtered to currency
    cash_start = Decimal("0")
    for op in pre_period_ops:
        if op.currency == currency:
            cash_start = _apply_operation(cash_start, op)

    # 2. income_total: deposit ops with income_source set and note != "[auto_funding]"
    # transfers are excluded from all budget categories by operation_type mismatch
    income_total = Decimal("0")
    for op in period_ops:
        if (
            op.operation_type == OperationType.deposit
            and op.income_source is not None
            and op.note != "[auto_funding]"
        ):
            income_total += op.amount

    # 3. living_expense_total
    living_expense_total = Decimal("0")
    for op in period_ops:
        if op.operation_type == OperationType.expense:
            is_refund = getattr(op, "is_refund", False) or False
            group = getattr(op, "expense_group", None)
            if group == "living":
                if is_refund:
                    living_expense_total -= op.amount
                else:
                    living_expense_total += op.amount + (op.fee or Decimal("0"))

    # 4. investment_expense_total
    investment_expense_total = Decimal("0")
    for op in period_ops:
        ot = op.operation_type
        is_refund = getattr(op, "is_refund", False) or False
        group = getattr(op, "expense_group", None)

        if ot == OperationType.expense and group == "investment" and not is_refund:
            investment_expense_total += op.amount + (op.fee or Decimal("0"))
        elif ot == OperationType.tax:
            investment_expense_total += op.amount
        elif ot == OperationType.fee:
            investment_expense_total += op.amount
        elif ot in (
            OperationType.buy,
            OperationType.sell,
            OperationType.deposit,
            OperationType.withdraw,
        ):
            # Embedded fee has no extra cash effect beyond what _apply_operation already does
            if op.fee:
                investment_expense_total += op.fee

    # 5. credit_payment_total, credit_principal_total, credit_interest_fee_total
    credit_payment_total = Decimal("0")
    credit_principal_total = Decimal("0")
    credit_interest_fee_total = Decimal("0")
    for op in period_ops:
        if op.operation_type == OperationType.expense:
            is_refund = getattr(op, "is_refund", False) or False
            group = getattr(op, "expense_group", None)
            if group == "credit" and not is_refund:
                credit_payment_total += op.amount
                principal = getattr(op, "principal_amount", None)
                if principal is not None:
                    credit_principal_total += principal
                interest = getattr(op, "interest_amount", None)
                credit_interest_fee_total += (interest or Decimal("0")) + (op.fee or Decimal("0"))

    # 8. invested_total: buy ops: amount + fee
    # transfers are excluded from all budget categories by operation_type mismatch
    invested_total = Decimal("0")
    for op in period_ops:
        if op.operation_type == OperationType.buy:
            invested_total += op.amount + (op.fee or Decimal("0"))

    # 9. sold_assets_total: sell ops: amount
    sold_assets_total = Decimal("0")
    for op in period_ops:
        if op.operation_type == OperationType.sell:
            sold_assets_total += op.amount

    # 10. free_cashflow
    free_cashflow = income_total - living_expense_total - credit_payment_total

    # 11. cash_end: fold over all ops (pre + period) filtered to currency
    cash_end = Decimal("0")
    for op in pre_period_ops + period_ops:
        if op.currency == currency:
            cash_end = _apply_operation(cash_end, op)

    # 12. cash_reconciliation_delta
    cash_reconciliation_delta = cash_end - cash_start

    # 13. has_reconciliation_warning
    has_reconciliation_warning = cash_end < Decimal("0")

    return BudgetSummaryOut(
        period_from=period_from,
        period_to=period_to,
        income_total=income_total.quantize(Q),
        living_expense_total=living_expense_total.quantize(Q),
        investment_expense_total=investment_expense_total.quantize(Q),
        credit_payment_total=credit_payment_total.quantize(Q),
        credit_principal_total=credit_principal_total.quantize(Q),
        credit_interest_fee_total=credit_interest_fee_total.quantize(Q),
        free_cashflow=free_cashflow.quantize(Q),
        invested_total=invested_total.quantize(Q),
        sold_assets_total=sold_assets_total.quantize(Q),
        cash_start=cash_start.quantize(Q),
        cash_end=cash_end.quantize(Q),
        cash_reconciliation_delta=cash_reconciliation_delta.quantize(Q),
        has_reconciliation_warning=has_reconciliation_warning,
    )


def compute_expenses_by_category(
    period_ops: list,
    period_from: date,
    period_to: date,
) -> ExpensesByCategoryOut:
    Q = Decimal("0.01")

    # group -> category -> (total, count)
    totals: dict[tuple[str, str], list] = defaultdict(lambda: [Decimal("0"), 0])

    for op in period_ops:
        if op.operation_type != OperationType.expense:
            continue
        is_refund = getattr(op, "is_refund", False) or False
        if is_refund:
            continue
        group = getattr(op, "expense_group", None) or ""
        category = getattr(op, "expense_category", None) or ""
        key = (group, category)
        totals[key][0] += op.amount + (Decimal("0") if group == "credit" else (op.fee or Decimal("0")))
        totals[key][1] += 1

    lines = [
        CategoryLineOut(
            group=group,
            category=category,
            total=total.quantize(Q),
            count=count,
        )
        for (group, category), (total, count) in sorted(totals.items())
    ]

    return ExpensesByCategoryOut(
        period_from=period_from,
        period_to=period_to,
        lines=lines,
    )
