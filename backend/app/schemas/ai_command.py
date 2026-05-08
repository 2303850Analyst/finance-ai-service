import uuid
from typing import Literal

from pydantic import BaseModel


class ParseRequest(BaseModel):
    text: str


class OperationDraft(BaseModel):
    operation_type: str
    account_name: str | None = None
    asset_ticker: str | None = None
    asset_name: str | None = None
    quantity: str | None = None
    price: str | None = None
    amount: str | None = None  # for fee / dividend / deposit — not for buy/sell
    fee: str | None = None     # informational fee extracted from buy/sell text
    currency: str = "RUB"
    operated_at: str           # ISO datetime string


class ParseResponse(BaseModel):
    status: Literal["parsed", "need_clarification", "not_operation"]
    raw_text: str
    operation: OperationDraft | None = None
    account_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    warnings: list[str] = []
    missing_fields: list[str] = []
    message: str | None = None
