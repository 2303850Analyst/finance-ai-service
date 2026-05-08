from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.user import User
from app.schemas.account import AccountCreate, AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.user_id == user.id))
    return result.scalars().all()


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    payload: AccountCreate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    account = Account(user_id=user.id, **payload.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account
