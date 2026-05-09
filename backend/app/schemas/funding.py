import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.operation import OperationType
from app.schemas.operation import OperationCreate, OperationOut


class CashBalance(BaseModel):
    account_id: uuid.UUID
    currency: str
    balance: Decimal

    model_config = ConfigDict(from_attributes=True)


class ConfirmWithFundingRequest(BaseModel):
    operation: OperationCreate
    force_funding: bool = False
    deposit_fee: Decimal | None = None


class FundingRequired(BaseModel):
    cash_available: Decimal
    cash_required: Decimal
    missing_cash: Decimal
    currency: str
    account_id: uuid.UUID


class ConfirmWithFundingResponse(BaseModel):
    status: str  # "ok" | "funding_required"
    operation: OperationOut | None = None
    deposit: OperationOut | None = None
    funding_required: FundingRequired | None = None
