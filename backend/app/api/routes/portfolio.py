from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.position import Position
from app.models.user import User
from app.schemas.portfolio import AllocationItem, PortfolioSummary, PositionOut

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


async def _load_positions(user: User, db: AsyncSession) -> list[Position]:
    account_ids_result = await db.execute(
        select(Account.id).where(Account.user_id == user.id)
    )
    account_ids = [row[0] for row in account_ids_result.fetchall()]
    if not account_ids:
        return []

    result = await db.execute(
        select(Position)
        .where(Position.account_id.in_(account_ids))
        .options(selectinload(Position.asset))
        .order_by(Position.account_id)
    )
    return result.scalars().all()


def _to_position_out(pos: Position) -> PositionOut:
    return PositionOut(
        id=pos.id,
        account_id=pos.account_id,
        asset_id=pos.asset_id,
        ticker=pos.asset.ticker,
        asset_name=pos.asset.name,
        asset_type=pos.asset.asset_type,
        quantity=pos.quantity,
        average_price=pos.average_price,
        total_cost=(pos.quantity * pos.average_price).quantize(Decimal("0.01")),
    )


def _build_allocation(positions: list[PositionOut]) -> list[AllocationItem]:
    totals: dict = {}
    for p in positions:
        totals[p.asset_type] = totals.get(p.asset_type, Decimal("0")) + p.total_cost
    grand = sum(totals.values())
    return [
        AllocationItem(
            asset_type=at,
            total_cost=cost,
            percentage=float(cost / grand * 100) if grand else 0.0,
        )
        for at, cost in sorted(totals.items(), key=lambda x: x[1], reverse=True)
    ]


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    positions_db = await _load_positions(user, db)
    positions = [_to_position_out(p) for p in positions_db]
    total_cost = sum((p.total_cost for p in positions), Decimal("0"))
    return PortfolioSummary(
        total_cost=total_cost,
        positions_count=len(positions),
        positions=positions,
        allocation=_build_allocation(positions),
    )


@router.get("/positions", response_model=list[PositionOut])
async def portfolio_positions(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    positions_db = await _load_positions(user, db)
    return [_to_position_out(p) for p in positions_db]


@router.get("/allocation", response_model=list[AllocationItem])
async def portfolio_allocation(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    positions_db = await _load_positions(user, db)
    positions = [_to_position_out(p) for p in positions_db]
    return _build_allocation(positions)
