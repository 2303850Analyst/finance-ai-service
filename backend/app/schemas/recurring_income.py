import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RecurringIncomeCreate(BaseModel):
    name: str = "Зарплата"
    account_id: uuid.UUID
    amount: Decimal
    income_source: str = "salary"
    day_of_month: int  # 1..31
    is_active: bool = True


class RecurringIncomeOut(BaseModel):
    id: uuid.UUID
    name: str
    account_id: uuid.UUID
    amount: Decimal
    income_source: str
    day_of_month: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SalaryDueOut(BaseModel):
    is_due: bool
    already_received: bool
    template: RecurringIncomeOut | None
