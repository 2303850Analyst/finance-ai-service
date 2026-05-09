from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recurring_income import RecurringIncome
from app.models.user import User
from app.schemas.recurring_income import RecurringIncomeCreate, RecurringIncomeOut, SalaryDueOut


async def upsert_recurring_income(
    payload: RecurringIncomeCreate, user: User, db: AsyncSession
) -> RecurringIncome:
    """MVP: one template per user — if exists, update it; if not, create."""
    result = await db.execute(
        select(RecurringIncome).where(RecurringIncome.user_id == user.id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        ri = RecurringIncome(user_id=user.id, **payload.model_dump())
        db.add(ri)
        await db.commit()
        await db.refresh(ri)
        return ri


async def get_salary_due(user: User, db: AsyncSession) -> SalaryDueOut:
    """Check whether the user's recurring income is due this month."""
    today = date.today()

    # Get active template
    result = await db.execute(
        select(RecurringIncome).where(
            RecurringIncome.user_id == user.id,
            RecurringIncome.is_active == True,  # noqa: E712
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        return SalaryDueOut(is_due=False, already_received=False, template=None)

    # Check if due this month
    is_time = today.day >= template.day_of_month
    if not is_time:
        return SalaryDueOut(
            is_due=False,
            already_received=False,
            template=RecurringIncomeOut.model_validate(template),
        )

    # Check if already received this month: any confirmed deposit with same income_source this month
    month_start_dt = datetime(today.year, today.month, 1, tzinfo=timezone.utc)

    from sqlalchemy import and_
    from app.models.operation import Operation, OperationStatus, OperationType
    from app.models.account import Account

    # Get user's account ids
    acc_result = await db.execute(
        select(Account.id).where(Account.user_id == user.id)
    )
    account_ids = [row[0] for row in acc_result.fetchall()]

    if not account_ids:
        return SalaryDueOut(
            is_due=True,
            already_received=False,
            template=RecurringIncomeOut.model_validate(template),
        )

    ops_result = await db.execute(
        select(Operation).where(
            and_(
                Operation.account_id.in_(account_ids),
                Operation.operation_type == OperationType.deposit,
                Operation.income_source == template.income_source,
                Operation.status == OperationStatus.confirmed,
                Operation.operated_at >= month_start_dt,
            )
        )
    )
    existing_income = ops_result.scalars().first()
    already_received = existing_income is not None

    return SalaryDueOut(
        is_due=not already_received,
        already_received=already_received,
        template=RecurringIncomeOut.model_validate(template),
    )


async def list_recurring_income(user: User, db: AsyncSession) -> list[RecurringIncome]:
    """Return all recurring income templates for the user."""
    result = await db.execute(
        select(RecurringIncome).where(RecurringIncome.user_id == user.id)
    )
    return result.scalars().all()
