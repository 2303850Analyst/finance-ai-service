import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TransferCreate(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal  # must be > 0
    currency: str = "RUB"
    operated_at: datetime
    fee: Decimal | None = None
    note: str | None = None


class TransferUpdate(BaseModel):
    """Partial update for a transfer. Only amount, fee, date, note are editable.
    from_account / to_account cannot be changed — delete and recreate instead.
    """
    amount: Decimal | None = None
    fee: Decimal | None = None
    currency: str | None = None
    operated_at: datetime | None = None
    note: str | None = None


class TransferOut(BaseModel):
    id: uuid.UUID
    from_account_id: uuid.UUID  # = operation.account_id
    to_account_id: uuid.UUID
    amount: Decimal
    fee: Decimal | None
    currency: str
    operated_at: datetime
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
