from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user_dev
from app.schemas.analytics import AnalyticsQuestion
from app.services.analytics_service import execute_report, plan_question

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/query")
async def query(body: AnalyticsQuestion, user=Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    spec = await plan_question(body.question, user, db, context=body.context)
    return await execute_report(spec, user, db)
