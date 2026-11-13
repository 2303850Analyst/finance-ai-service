"""Opt-in live provider smoke. Run only against the disposable finance_ai_smoke DB.

Requires tests/fixtures/smoke.ogg containing the synthetic phrase documented in README.
Never runs as part of pytest. Sends only synthetic text/audio to the configured AI API.
"""
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
from app.services.seed_service import seed_dev_data
from app.services.telegram_service import transcribe, make_draft, decide
from app.services.analytics_service import plan_question, execute_report


async def main():
    assert settings.database_url.endswith('/finance_ai_smoke'), 'Requires isolated smoke database'
    settings.ai_cooldown_seconds = 0
    async with AsyncSessionLocal() as db:
        await seed_dev_data(db)
        user = await get_current_user_dev(db)
        before = await db.scalar(select(func.count()).select_from(Operation))
        encoded = base64.b64encode(Path('tests/fixtures/smoke.ogg').read_bytes()).decode()
        text = await transcribe(encoded, user, db)
        print('TRANSCRIPTION:', text, flush=True)
        result = await make_draft(text, 'live-smoke:' + str(uuid.uuid4()), user, db, check_limit=False)
        assert result.get('draft_id'), result
        assert await db.scalar(select(func.count()).select_from(Operation)) == before
        print('DRAFT created; ledger unchanged before confirmation', flush=True)
        did = uuid.UUID(result['draft_id'])
        await decide(did, 'confirm', user, db)
        await decide(did, 'confirm', user, db)
        assert await db.scalar(select(func.count()).select_from(Operation)) == before + 1
        op = (await db.execute(select(Operation).order_by(Operation.created_at.desc()).limit(1))).scalar_one()
        assert op.amount == Decimal('450') and op.expense_group == 'living'
        print('CONFIRMATION: exactly one expense of 450 RUB', flush=True)
        spec = await plan_question('Расходы по категориям за этот месяц', user, db)
        report = await execute_report(spec, user, db)
        assert spec.intent == 'expenses_by_category'
        assert sum(Decimal(r['value']) for r in report['rows']) >= Decimal('450')
        print('GENBI: real AI specification + backend totals verified', spec.model_dump(mode='json'), flush=True)
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
