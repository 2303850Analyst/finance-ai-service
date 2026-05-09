from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.operation import Operation, OperationStatus
from app.models.user import User
from app.schemas.budget import BudgetSummaryOut, ExpensesByCategoryOut
from app.schemas.recurring_income import RecurringIncomeCreate, RecurringIncomeOut, SalaryDueOut
from app.services.budget_engine import compute_budget_summary, compute_expenses_by_category
from app.services.recurring_income_service import (
    get_salary_due,
    list_recurring_income,
    upsert_recurring_income,
)

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/summary", response_model=BudgetSummaryOut)
async def get_budget_summary(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> BudgetSummaryOut:
    result = await db.execute(
        select(Operation)
        .where(
            Operation.user_id == user.id,
            Operation.status == OperationStatus.confirmed,
        )
        .order_by(Operation.operated_at.asc(), Operation.created_at.asc())
    )
    all_ops = result.scalars().all()

    # operated_at is timezone-aware datetime; compare date part only
    from datetime import timezone

    def op_date(op) -> date:
        dt = op.operated_at
        if dt.tzinfo is None:
            return dt.date()
        return dt.astimezone(timezone.utc).date()

    pre_period = [op for op in all_ops if op_date(op) < from_date]
    period = [op for op in all_ops if from_date <= op_date(op) <= to_date]

    return compute_budget_summary(pre_period, period, from_date, to_date)


@router.get("/expenses-by-category", response_model=ExpensesByCategoryOut)
async def get_expenses_by_category(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> ExpensesByCategoryOut:
    result = await db.execute(
        select(Operation)
        .where(
            Operation.user_id == user.id,
            Operation.status == OperationStatus.confirmed,
        )
        .order_by(Operation.operated_at.asc())
    )
    all_ops = result.scalars().all()

    from datetime import timezone

    def op_date(op) -> date:
        dt = op.operated_at
        if dt.tzinfo is None:
            return dt.date()
        return dt.astimezone(timezone.utc).date()

    period = [op for op in all_ops if from_date <= op_date(op) <= to_date]
    return compute_expenses_by_category(period, from_date, to_date)


@router.get("/salary-due", response_model=SalaryDueOut)
async def check_salary_due(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> SalaryDueOut:
    return await get_salary_due(user, db)


@router.post("/recurring-income", response_model=RecurringIncomeOut, status_code=201)
async def create_recurring_income(
    payload: RecurringIncomeCreate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> RecurringIncomeOut:
    ri = await upsert_recurring_income(payload, user, db)
    return RecurringIncomeOut.model_validate(ri)


@router.get("/recurring-income", response_model=list[RecurringIncomeOut])
async def get_recurring_income(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> list[RecurringIncomeOut]:
    items = await list_recurring_income(user, db)
    return [RecurringIncomeOut.model_validate(item) for item in items]
