from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawProposal:
    is_operation: bool
    operation_type: str | None = None

    # Asset / account resolution hints (text extracted from user input)
    asset_ticker: str | None = None    # explicit ticker (SBER) — used by mock provider
    asset_name: str | None = None      # human-readable name
    account_name: str | None = None    # source account
    to_account_name: str | None = None  # target account for transfers

    # Core numeric fields
    quantity: str | None = None
    price: str | None = None
    amount: str | None = None  # for non-buy/sell ops
    fee: str | None = None

    currency: str = "RUB"

    # Expense-specific
    expense_group: str | None = None      # "living" | "investment" | "credit"
    expense_category: str | None = None
    merchant: str | None = None

    # Credit payment breakdown
    principal_amount: str | None = None
    interest_amount: str | None = None
    linked_asset_name: str | None = None  # asset this payment is for

    # Income-specific
    income_source: str | None = None

    # Datetime
    operated_at: str | None = None   # ISO date or datetime string

    # Miscellaneous
    note: str | None = None
    confidence: float = 1.0

    # Clarification
    clarification_needed: bool = False
    missing_fields: list[str] = field(default_factory=list)
    message: str | None = None


class AIProvider(Protocol):
    async def parse_operation(self, text: str) -> RawProposal: ...
