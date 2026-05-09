import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.interest_settings import AccountInterestSettings
from app.models.operation import Operation
from app.models.user import User
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.schemas.interest import AccountInterestSettingsCreate, AccountInterestSettingsOut

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


@router.patch("/{account_id}", response_model=AccountOut)
async def edit_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")

    for field_name in payload.model_fields_set:
        if hasattr(account, field_name):
            setattr(account, field_name, getattr(payload, field_name))

    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")

    has_ops = (
        await db.execute(
            select(Operation.id).where(Operation.account_id == account_id).limit(1)
        )
    ).scalar_one_or_none()
    if has_ops is not None:
        raise HTTPException(
            409,
            f"Счёт «{account.name}» содержит операции и не может быть удалён.",
        )

    # Remove interest settings first (FK constraint)
    settings = (
        await db.execute(
            select(AccountInterestSettings).where(
                AccountInterestSettings.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if settings is not None:
        await db.delete(settings)
        await db.flush()

    await db.delete(account)
    await db.commit()


@router.get("/{account_id}/interest-settings", response_model=AccountInterestSettingsOut)
async def get_interest_settings(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")

    result = await db.execute(
        select(AccountInterestSettings).where(
            AccountInterestSettings.account_id == account_id
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        raise HTTPException(404, "Interest settings not configured for this account")
    return settings


@router.put("/{account_id}/interest-settings", response_model=AccountInterestSettingsOut)
async def set_interest_settings(
    account_id: uuid.UUID,
    payload: AccountInterestSettingsCreate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")

    result = await db.execute(
        select(AccountInterestSettings).where(
            AccountInterestSettings.account_id == account_id
        )
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = AccountInterestSettings(account_id=account_id, **payload.model_dump())
        db.add(settings)
    else:
        for k, v in payload.model_dump().items():
            setattr(settings, k, v)

    await db.commit()
    await db.refresh(settings)
    return settings
