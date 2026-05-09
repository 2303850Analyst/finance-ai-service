import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.operation import Operation
    from app.models.position import Position


class AssetType(str, enum.Enum):
    stock = "stock"
    bond = "bond"
    etf = "etf"
    currency = "currency"
    cash = "cash"
    deposit = "deposit"
    crypto = "crypto"
    real_estate = "real_estate"
    vehicle = "vehicle"
    other_physical = "other_physical"
    other = "other"


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(SAEnum(AssetType), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")

    # Extended fields (migration h8i9j0k1l2m3)
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    acquisition_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Credit/mortgage marker — MVP only, not a full liabilities module
    is_credit_linked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    credit_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    credit_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Capital accounting: set to False to exclude from Total Capital without deleting
    include_in_capital: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    operations: Mapped[list["Operation"]] = relationship(
        "Operation", foreign_keys="[Operation.asset_id]", back_populates="asset"
    )
    positions: Mapped[list["Position"]] = relationship("Position", back_populates="asset")
