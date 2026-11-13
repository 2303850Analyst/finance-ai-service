import uuid
from typing import Literal

from pydantic import BaseModel


class ParseRequest(BaseModel):
    text: str


class OperationDraft(BaseModel):
    operation_type: str
    account_name: str | None = None
    to_account_name: str | None = None      # for transfers
    asset_ticker: str | None = None
    asset_name: str | None = None
    quantity: str | None = None
    price: str | None = None
    amount: str | None = None               # for fee / dividend / expense / deposit
    fee: str | None = None
    currency: str = "RUB"
    operated_at: str                        # ISO datetime string

    # Expense-specific
    expense_group: str | None = None        # "living" | "investment" | "credit"
    expense_category: str | None = None
    merchant: str | None = None

    # Income-specific
    income_source: str | None = None

    # Credit payment breakdown
    principal_amount: str | None = None
    interest_amount: str | None = None
    linked_asset_text: str | None = None    # raw text hint from AI

    # Miscellaneous
    note: str | None = None


class ParseResponse(BaseModel):
    status: Literal["parsed", "need_clarification", "not_operation"]
    raw_text: str
    operation: OperationDraft | None = None
    account_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    warnings: list[str] = []
    missing_fields: list[str] = []
    message: str | None = None

    # Provider-level errors (key missing, API down, etc.) — not user input errors
    provider_error: str | None = None

    # Rate limiting feedback
    rate_limited: bool = False
    cooldown_seconds_remaining: int | None = None
