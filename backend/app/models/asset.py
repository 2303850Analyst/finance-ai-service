import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, String
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

    operations: Mapped[list["Operation"]] = relationship("Operation", back_populates="asset")
    positions: Mapped[list["Position"]] = relationship("Position", back_populates="asset")
