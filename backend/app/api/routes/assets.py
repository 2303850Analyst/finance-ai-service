import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.asset import Asset, AssetType
from app.models.operation import Operation
from app.models.position import Position
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetOut, AssetUpdate, PHYSICAL_ASSET_TYPES

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
    ticker = payload.ticker

    if ticker is None:
        if payload.asset_type in PHYSICAL_ASSET_TYPES:
            # Generate an internal identifier; hidden from user-facing UI
            ticker = f"PHYS-{str(uuid.uuid4())[:8].upper()}"
        else:
            raise HTTPException(
                400, "Тикер обязателен для рыночных активов (акции, облигации, ETF, крипто и т.д.)"
            )

    existing = await db.execute(select(Asset).where(Asset.ticker == ticker))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, f"Asset '{ticker}' already exists")

    asset = Asset(
        ticker=ticker,
        name=payload.name,
        asset_type=payload.asset_type,
        currency=payload.currency,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.patch("/{asset_id}", response_model=AssetOut)
async def edit_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    _: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")

    # Ticker change: validate uniqueness; keep PHYS-* internal ticker unchanged
    if payload.ticker is not None:
        new_ticker = payload.ticker.upper()
        if new_ticker != asset.ticker:
            existing = await db.execute(select(Asset).where(Asset.ticker == new_ticker))
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(409, f"Тикер '{new_ticker}' уже используется")
            asset.ticker = new_ticker

    for field_name in payload.model_fields_set:
        if field_name == "ticker":
            continue  # handled above
        if hasattr(asset, field_name):
            setattr(asset, field_name, getattr(payload, field_name))

    # If credit link unchecked, clear credit details
    if "is_credit_linked" in payload.model_fields_set and not payload.is_credit_linked:
        asset.credit_kind = None
        asset.credit_note = None

    await db.commit()
    await db.refresh(asset)
    return asset


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: uuid.UUID,
    _: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")

    used_in_ops = (
        await db.execute(
            select(Operation.id).where(Operation.asset_id == asset_id).limit(1)
        )
    ).scalar_one_or_none()
    if used_in_ops is not None:
        raise HTTPException(
            409,
            f"Актив «{asset.name}» используется в операциях и не может быть удалён.",
        )

    used_in_pos = (
        await db.execute(
            select(Position.id).where(Position.asset_id == asset_id).limit(1)
        )
    ).scalar_one_or_none()
    if used_in_pos is not None:
        raise HTTPException(
            409,
            f"Актив «{asset.name}» есть в открытых позициях и не может быть удалён.",
        )

    await db.delete(asset)
    await db.commit()
