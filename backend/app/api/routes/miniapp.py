import uuid
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.schemas.analytics import AnalyticsQuestion, AnalyticsSpec
from app.schemas.miniapp import DraftInput, DraftUpdate, DraftDecision, MiniAccountCreate
from app.services import miniapp_service as service, telegram_service as tg
from app.services.analytics_service import execute_report, plan_question
from app.services.miniapp_auth import current_miniapp_user

router = APIRouter(prefix="/miniapp", tags=["miniapp"])
User = Depends(current_miniapp_user)
DB = Depends(get_db)


@router.get("/bootstrap")
async def bootstrap(user=User, db: AsyncSession=DB):
    return {**await service.bootstrap(user, db), "bot_username": settings.telegram_bot_username}


@router.post("/accounts", status_code=201)
async def account(body: MiniAccountCreate, user=User, db: AsyncSession=DB):
    return await service.add_account(body, user, db)


@router.get("/overview")
async def overview(start: date, end: date, account_id: uuid.UUID | None=None, user=User, db: AsyncSession=DB):
    return await service.overview(start, end, account_id, user, db)


@router.get("/history")
async def history(start: date, end: date, account_id: uuid.UUID | None=None, offset: int=Query(default=0,ge=0,le=100000), user=User, db: AsyncSession=DB):
    return await service.history(start, end, account_id, offset, user, db)


@router.get("/drafts")
async def drafts(user=User, db: AsyncSession=DB):
    return await service.pending_drafts(user, db)


@router.post("/drafts/parse")
async def parse(body: DraftInput, user=User, db: AsyncSession=DB):
    return await service.parse_draft(body, user, db)


@router.get("/drafts/{draft_id}")
async def draft(draft_id: uuid.UUID, user=User, db: AsyncSession=DB):
    return service.draft_out(await service.get_draft(draft_id, user, db, lock=True))


@router.patch("/drafts/{draft_id}")
async def update(draft_id: uuid.UUID, body: DraftUpdate, user=User, db: AsyncSession=DB):
    return await service.update_draft(draft_id, body, user, db)


@router.post("/drafts/{draft_id}/decide")
async def decide(draft_id: uuid.UUID, body: DraftDecision, user=User, db: AsyncSession=DB):
    await tg.decide(draft_id, body.action, user, db, expected_revision=body.revision)
    return service.draft_out(await service.get_draft(draft_id, user, db))


@router.post("/query")
async def query(body: AnalyticsQuestion, user=User, db: AsyncSession=DB):
    spec = await plan_question(body.question, user, db, context=body.context)
    return await execute_report(spec, user, db)


@router.post("/reports")
async def report(body: AnalyticsSpec, user=User, db: AsyncSession=DB):
    service.checked_period(body.date_from, body.date_to)
    return await execute_report(body, user, db)
