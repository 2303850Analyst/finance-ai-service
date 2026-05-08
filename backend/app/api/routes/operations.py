import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.user import User
from app.schemas.operation import OperationCreate, OperationOut
from app.services.operation_service import (
    create_operation,
    delete_operation,
    list_operations,
)

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
