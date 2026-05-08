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
    currency: str = "RUB"
    operated_at: datetime
    note: str | None = None

    @model_validator(mode="after")
    def coerce_buy_sell_amount(self) -> "OperationCreate":
        # For buy/sell the authoritative amount is always quantity * price.
        # Client-supplied amount is overridden so stored rows are always consistent.
        if self.operation_type in (OperationType.buy, OperationType.sell):
            if self.quantity is not None and self.price is not None:
                self.amount = self.quantity * self.price
        return self


class OperationOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID | None
    operation_type: OperationType
    status: OperationStatus
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal
    currency: str
    operated_at: datetime
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
