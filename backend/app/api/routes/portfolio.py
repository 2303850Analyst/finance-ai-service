import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.interest_settings import AccountInterestSettings
from app.models.operation import Operation, OperationStatus
from app.models.position import Position
from app.models.user import User
from app.models.account import AccountType
from app.schemas.funding import CashBalance
from app.schemas.interest import DepositSummaryOut, InterestAccrualOut
from app.schemas.portfolio import AllocationItem, PortfolioSummary, PositionOut
from app.services.cash_engine import calculate_all_cash_balances
from app.services.interest_engine import compute_accrued_interest

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


@router.get("/cash-balances", response_model=list[CashBalance])
async def cash_balances(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    all_balances = await calculate_all_cash_balances(user, db)
    return [
        CashBalance(
            account_id=uuid.UUID(account_id_str),
            currency=currency,
            balance=balance,
        )
        for (account_id_str, currency), balance in all_balances.items()
    ]


@router.get("/interest-accruals", response_model=list[InterestAccrualOut])
async def interest_accruals(
    as_of: date | None = None,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    today = as_of or date.today()

    accounts_result = await db.execute(
        select(Account).where(Account.user_id == user.id)
    )
    accounts = accounts_result.scalars().all()

    result = []
    for account in accounts:
        settings_result = await db.execute(
            select(AccountInterestSettings).where(
                AccountInterestSettings.account_id == account.id
            )
        )
        settings = settings_result.scalar_one_or_none()
        if settings is None or not settings.is_interest_enabled:
            continue

        ops_result = await db.execute(
            select(Operation)
            .where(
                Operation.account_id == account.id,
                Operation.status == OperationStatus.confirmed,
            )
            .order_by(Operation.operated_at.asc(), Operation.created_at.asc())
        )
        ops = ops_result.scalars().all()

        accrued = compute_accrued_interest(ops, settings, account.currency, today)
        result.append(
            InterestAccrualOut(
                account_id=account.id,
                account_name=account.name,
                currency=account.currency,
                accrued_interest=accrued,
                annual_rate_percent=settings.annual_rate_percent,
                as_of=today,
            )
        )

    return result


@router.get("/deposits", response_model=list[DepositSummaryOut])
async def deposits_summary(
    as_of: date | None = None,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    today = as_of or date.today()

    dep_accounts_result = await db.execute(
        select(Account).where(
            Account.user_id == user.id,
            Account.account_type.in_([AccountType.deposit, AccountType.savings]),
        )
    )
    dep_accounts = dep_accounts_result.scalars().all()
    if not dep_accounts:
        return []

    all_balances = await calculate_all_cash_balances(user, db)

    result = []
    for account in dep_accounts:
        settings_result = await db.execute(
            select(AccountInterestSettings).where(
                AccountInterestSettings.account_id == account.id
            )
        )
        settings = settings_result.scalar_one_or_none()

        principal = all_balances.get((str(account.id), account.currency), Decimal("0"))

        accrued = Decimal("0")
        if settings and settings.is_interest_enabled:
            ops_result = await db.execute(
                select(Operation)
                .where(
                    Operation.account_id == account.id,
                    Operation.status == OperationStatus.confirmed,
                )
                .order_by(Operation.operated_at.asc(), Operation.created_at.asc())
            )
            ops = ops_result.scalars().all()
            accrued = compute_accrued_interest(ops, settings, account.currency, today)

        result.append(
            DepositSummaryOut(
                account_id=account.id,
                name=account.name,
                currency=account.currency,
                account_type=account.account_type.value,
                principal=principal,
                annual_rate_percent=settings.annual_rate_percent if settings else None,
                interest_start_date=settings.interest_start_date if settings else None,
                interest_end_date=settings.interest_end_date if settings else None,
                payout_frequency=settings.payout_frequency if settings else None,
                capitalization=settings.capitalization if settings else None,
                accrued_interest=accrued,
                as_of=today,
                has_settings=settings is not None,
            )
        )

    return result
