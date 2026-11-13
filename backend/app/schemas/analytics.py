from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyticsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["expenses_by_category", "monthly_cashflow", "dividends_over_time", "allocation_by_account", "allocation_by_asset_type"]
    date_from: date
    date_to: date
    account_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def valid_period(self):
        if self.date_to < self.date_from or (self.date_to - self.date_from).days > 366:
            raise ValueError("Период должен быть от 1 до 367 дней")
        return self


class AnalyticsQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2000)
    context: AnalyticsSpec | None = None
