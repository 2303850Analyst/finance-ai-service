"""Opt-in live AI verification using synthetic data in finance_ai_smoke only."""
import asyncio
import base64
import uuid
from pathlib import Path
from decimal import Decimal
from sqlalchemy import func, select
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.dependencies import get_current_user_dev
from app.models.operation import Operation
from app.schemas.miniapp import DraftInput, DraftUpdate
from app.schemas.operation import OperationCreate
from app.services.seed_service import seed_dev_data
from app.services import miniapp_service as mini, telegram_service as tg
from app.services.analytics_service import plan_question, execute_report


async def main():
    assert settings.database_url.endswith('/finance_ai_smoke'), 'Requires isolated smoke database'
    settings.ai_cooldown_seconds=0
    async with AsyncSessionLocal() as db:
        await seed_dev_data(db)
        user=await get_current_user_dev(db)
        before=await db.scalar(select(func.count()).select_from(Operation))
        media=await asyncio.create_subprocess_exec('ffmpeg','-y','-v','error','-i','tests/fixtures/smoke.ogg',
            '-c:a','aac','/tmp/miniapp-smoke.m4a')
        assert await media.wait()==0
        audio=base64.b64encode(Path('/tmp/miniapp-smoke.m4a').read_bytes()).decode()
        draft=await mini.parse_draft(DraftInput(request_id=uuid.uuid4(),audio=audio),user,db)
        assert Decimal(draft['operation']['amount'])==450
        assert await db.scalar(select(func.count()).select_from(Operation))==before
        operation=OperationCreate.model_validate({**draft['operation'],'amount':'475'})
        draft=await mini.update_draft(uuid.UUID(draft['id']),DraftUpdate(revision=draft['revision'],operation=operation),user,db)
        await tg.decide(uuid.UUID(draft['id']),'confirm',user,db,expected_revision=draft['revision'])
        await tg.decide(uuid.UUID(draft['id']),'confirm',user,db,expected_revision=draft['revision'])
        assert await db.scalar(select(func.count()).select_from(Operation))==before+1
        print('PASS: real MP4 audio -> transcription -> draft -> edit -> one confirmed operation',flush=True)
        spec=await plan_question('Расходы по категориям за этот месяц со счёта Наличные',user,db)
        assert spec.intent=='expenses_by_category' and spec.account_name=='Наличные'
        report=await execute_report(spec,user,db)
        assert Decimal(report['totals']['value'])>=475
        followup=await plan_question('А за прошлый месяц?',user,db,context=spec)
        assert followup.intent==spec.intent and followup.account_name==spec.account_name
        assert followup.date_to<spec.date_from
        await execute_report(followup,user,db)
        print('PASS: real GenBI + follow-up retains report/account and changes period',flush=True)
    await engine.dispose()

if __name__=='__main__':
    asyncio.run(main())
