from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawProposal:
    is_operation: bool
    operation_type: str | None = None
    asset_ticker: str | None = None
    asset_name: str | None = None
    account_name: str | None = None
    quantity: str | None = None
    price: str | None = None
    amount: str | None = None  # for non-buy/sell ops
    fee: str | None = None     # informational fee from buy/sell text (fee, dividend, deposit...)
    currency: str = "RUB"
    clarification_needed: bool = False
    missing_fields: list[str] = field(default_factory=list)
    message: str | None = None


class AIProvider(Protocol):
    def parse_operation(self, text: str) -> RawProposal: ...
