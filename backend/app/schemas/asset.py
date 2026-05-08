import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.asset import AssetType


class AssetCreate(BaseModel):
    ticker: str
    name: str
    asset_type: AssetType
    currency: str = "RUB"

    @field_validator("ticker")
    @classmethod
    def ticker_upper(cls, v: str) -> str:
        return v.upper()


class AssetOut(BaseModel):
    id: uuid.UUID
    ticker: str
    name: str
    asset_type: AssetType
    currency: str

    model_config = ConfigDict(from_attributes=True)
