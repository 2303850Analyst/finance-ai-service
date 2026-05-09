import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.operation import OperationStatus, OperationType


class OperationCreate(BaseModel):
    account_id: uuid.UUID
    asset_id: uuid.UUID | None = None
    operation_type: OperationType
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal
    fee: Decimal | None = None
    currency: str = "RUB"
    operated_at: datetime
    note: str | None = None
    income_source: str | None = None

    # Expense-specific fields
    expense_group: str | None = None
    expense_category: str | None = None
    merchant: str | None = None
    is_refund: bool = False
    principal_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    liability_name: str | None = None
    linked_asset_id: uuid.UUID | None = None

    # Transfer-specific field
    to_account_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def coerce_buy_sell_amount(self) -> "OperationCreate":
        # For buy/sell the authoritative amount is always quantity * price.
        # Client-supplied amount is overridden so stored rows are always consistent.
        if self.operation_type in (OperationType.buy, OperationType.sell):
            if self.quantity is not None and self.price is not None:
                self.amount = self.quantity * self.price
        return self

    @model_validator(mode="after")
    def validate_credit_breakdown(self) -> "OperationCreate":
        if (
            self.operation_type == OperationType.expense
            and self.expense_group == "credit"
            and (self.principal_amount is not None or self.interest_amount is not None)
        ):
            principal = self.principal_amount or Decimal("0")
            interest = self.interest_amount or Decimal("0")
            fee = self.fee or Decimal("0")
            expected = principal + interest + fee
            if abs(expected - self.amount) > Decimal("0.01"):
                raise ValueError(
                    f"Credit expense breakdown mismatch: "
                    f"principal ({principal}) + interest ({interest}) + fee ({fee}) "
                    f"= {expected}, but amount = {self.amount}. "
                    f"Difference must not exceed 0.01."
                )
        return self


class OperationUpdate(BaseModel):
    """Partial update schema. Only fields present in the request body are applied.
    To clear an optional field, include it with a null value.
    buy and sell operations cannot be updated — delete and recreate instead.
    """
    amount: Decimal | None = None
    fee: Decimal | None = None
    currency: str | None = None
    operated_at: datetime | None = None
    note: str | None = None
    income_source: str | None = None

    # Expense-specific
    expense_group: str | None = None
    expense_category: str | None = None
    merchant: str | None = None
    principal_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    liability_name: str | None = None
    linked_asset_id: uuid.UUID | None = None


class OperationOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID | None
    operation_type: OperationType
    status: OperationStatus
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal
    fee: Decimal | None
    currency: str
    operated_at: datetime
    note: str | None
    income_source: str | None
    created_at: datetime

    # Expense-specific fields
    expense_group: str | None = None
    expense_category: str | None = None
    merchant: str | None = None
    is_refund: bool = False
    principal_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    liability_name: str | None = None
    linked_asset_id: uuid.UUID | None = None

    # Transfer-specific field
    to_account_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)
