import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_dev
from app.models.user import User
from app.schemas.ai_command import ParseRequest, ParseResponse
from app.services.ai_parser import parse_operation_text

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse-operation", response_model=ParseResponse)
async def parse_operation(
    body: ParseRequest,
    user: User = Depends(get_current_user_dev),
    db: AsyncSession = Depends(get_db),
) -> ParseResponse:
    result = await parse_operation_text(body.text, user, db)
    # Commit the usage event that was logged during parse.
    # parse_operation_text never writes financial data — commit is safe.
    try:
        await db.commit()
    except Exception:
        log.warning("ai_route: failed to commit usage event — rolling back", exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
    return result
