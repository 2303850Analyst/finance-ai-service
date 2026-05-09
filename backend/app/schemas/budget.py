from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class BudgetSummaryOut(BaseModel):
    period_from: date
    period_to: date
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


class CategoryLineOut(BaseModel):
    group: str
    category: str
    total: Decimal
    count: int


class ExpensesByCategoryOut(BaseModel):
    period_from: date
    period_to: date
    lines: list[CategoryLineOut]
