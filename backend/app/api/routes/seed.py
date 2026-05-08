from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.seed_service import seed_dev_data

router = APIRouter(prefix="/seed", tags=["seed"])


@router.post("/dev-data", summary="Seed dev user, accounts and assets (idempotent)")
async def seed_endpoint(db: AsyncSession = Depends(get_db)):
    return await seed_dev_data(db)
