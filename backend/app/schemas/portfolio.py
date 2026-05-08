import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.asset import AssetType


class PositionOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID
    ticker: str
    asset_name: str
    asset_type: AssetType
    quantity: Decimal
    average_price: Decimal
    total_cost: Decimal


class AllocationItem(BaseModel):
    asset_type: AssetType
    total_cost: Decimal
    percentage: float


class PortfolioSummary(BaseModel):
    total_cost: Decimal
    positions_count: int
    positions: list[PositionOut]
    allocation: list[AllocationItem]
