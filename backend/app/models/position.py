import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.asset import Asset


class Position(Base, TimestampMixin):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("account_id", "asset_id", name="uq_position_account_asset"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    average_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)

    account: Mapped["Account"] = relationship("Account", back_populates="positions")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="positions")
