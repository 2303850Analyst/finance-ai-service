import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.user import User
from app.schemas.funding import ConfirmWithFundingRequest, ConfirmWithFundingResponse
from app.schemas.operation import OperationCreate, OperationOut, OperationUpdate
from app.schemas.transfer import TransferCreate, TransferUpdate
from app.services.funding_service import confirm_with_funding
from app.services.operation_service import (
    create_operation,
    delete_operation,
    list_operations,
    update_operation,
)
from app.services.transfer_service import create_transfer, update_transfer

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=list[OperationOut])
async def get_operations(
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    return await list_operations(user, db)


@router.post("", response_model=OperationOut, status_code=201)
async def add_operation(
    payload: OperationCreate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    return await create_operation(payload, user, db)


@router.delete("/{operation_id}", status_code=204)
async def remove_operation(
    operation_id: uuid.UUID,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    await delete_operation(operation_id, user, db)


@router.post("/confirm-with-funding", response_model=ConfirmWithFundingResponse, status_code=201)
async def add_operation_with_funding(
    req: ConfirmWithFundingRequest,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    return await confirm_with_funding(req, user, db)


# ── Transfer endpoints ────────────────────────────────────────────────────────

@router.post("/transfer", response_model=OperationOut, status_code=201)
async def add_transfer(
    payload: TransferCreate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    return await create_transfer(payload, user, db)


@router.patch("/transfer/{operation_id}", response_model=OperationOut)
async def edit_transfer(
    operation_id: uuid.UUID,
    payload: TransferUpdate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    """Update amount, fee, date, or note on an existing transfer."""
    return await update_transfer(operation_id, payload, user, db)


# ── Generic operation update — registered AFTER /transfer/{id} to avoid overlap ──

@router.patch("/{operation_id}", response_model=OperationOut)
async def edit_operation(
    operation_id: uuid.UUID,
    payload: OperationUpdate,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
):
    """Update an operation. buy/sell not supported — delete and recreate instead."""
    return await update_operation(operation_id, payload, user, db)
