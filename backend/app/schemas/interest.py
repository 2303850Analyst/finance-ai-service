import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccountInterestSettingsCreate(BaseModel):
    is_interest_enabled: bool = True
    annual_rate_percent: Decimal
    interest_start_date: date
    interest_end_date: date | None = None
    payout_frequency: str = "monthly"   # monthly | at_maturity
    capitalization: bool = False
    payout_day: int | None = None


class AccountInterestSettingsOut(AccountInterestSettingsCreate):
    id: uuid.UUID
    account_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InterestAccrualOut(BaseModel):
    account_id: uuid.UUID
    account_name: str
    currency: str
    accrued_interest: Decimal
    annual_rate_percent: Decimal
    as_of: date


class DepositSummaryOut(BaseModel):
    account_id: uuid.UUID
    name: str
    currency: str
    account_type: str
    principal: Decimal
    annual_rate_percent: Decimal | None
    interest_start_date: date | None
    interest_end_date: date | None
    payout_frequency: str | None
    capitalization: bool | None
    accrued_interest: Decimal
    as_of: date
    has_settings: bool
