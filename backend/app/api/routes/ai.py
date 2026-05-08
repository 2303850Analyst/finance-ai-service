from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.user import User
from app.schemas.ai_command import ParseRequest, ParseResponse
from app.services.ai_parser import parse_operation_text

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse-operation", response_model=ParseResponse)
async def parse_operation(
    body: ParseRequest,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> ParseResponse:
    return await parse_operation_text(body.text, user, db)
