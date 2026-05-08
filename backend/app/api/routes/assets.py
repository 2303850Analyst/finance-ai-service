from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetOut

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
async def list_assets(
    _: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).order_by(Asset.ticker))
    return result.scalars().all()


@router.post("", response_model=AssetOut, status_code=201)
async def create_asset(
    payload: AssetCreate,
    _: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Asset).where(Asset.ticker == payload.ticker))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, f"Asset '{payload.ticker}' already exists")

    asset = Asset(**payload.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset
