import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account


class AccountInterestSettings(Base, TimestampMixin):
    __tablename__ = "account_interest_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), unique=True, nullable=False, index=True
    )
    is_interest_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    annual_rate_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    interest_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    interest_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payout_frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    capitalization: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payout_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    account: Mapped["Account"] = relationship("Account", back_populates="interest_settings")
