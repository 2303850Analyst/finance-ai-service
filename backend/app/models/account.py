import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.interest_settings import AccountInterestSettings
    from app.models.operation import Operation
    from app.models.position import Position
    from app.models.user import User


class AccountType(str, enum.Enum):
    broker = "broker"
    bank = "bank"
    crypto = "crypto"
    cash = "cash"
    deposit = "deposit"
    savings = "savings"
    other = "other"


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(SAEnum(AccountType), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")

    user: Mapped["User"] = relationship("User", back_populates="accounts")
    operations: Mapped[list["Operation"]] = relationship("Operation", back_populates="account")
    positions: Mapped[list["Position"]] = relationship("Position", back_populates="account")
    interest_settings: Mapped["AccountInterestSettings | None"] = relationship(
        "AccountInterestSettings", back_populates="account", uselist=False
    )
