import asyncio
import base64
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.operation import Operation
from app.models.telegram import OperationDraftRecord, TelegramPairing
from app.models.user import User
from app.schemas.ai_command import OperationDraft, ParseResponse
from app.schemas.analytics import AnalyticsSpec
from app.services import telegram_service as tg, analytics_service as analytics


@pytest.fixture
def ai_config(monkeypatch):
    monkeypatch.setattr(settings, 'telegram_bot_token', SecretStr('test'))
    monkeypatch.setattr(settings, 'telegram_internal_secret', SecretStr('test-internal'))
    monkeypatch.setattr(settings, 'ai_cooldown_seconds', 0)


async def setup(client, db):
    await client.post('/api/v1/seed/dev-data')
    user = await get_current_user_dev(db)
    accounts = (await client.get('/api/v1/accounts')).json()
    account = next(a for a in accounts if a['name'] == 'Наличные')
    return user, account['id']


def proposal(account_id, **changes):
    data = dict(operation_type='expense', account_name='Наличные', amount='450.00',
        operated_at='2026-11-13T12:00:00+03:00', expense_group='living', expense_category='Продукты')
    data.update(changes)
    return ParseResponse(status='parsed', raw_text='fixture', account_id=account_id, operation=OperationDraft(**data))


async def draft(client, db, monkeypatch, **changes):
    user, aid = await setup(client, db)
    monkeypatch.setattr(tg, 'parse_operation_text', AsyncMock(return_value=proposal(aid, **changes)))
    result = await tg.make_draft('fixture', 'telegram:1:1', user, db)
    return user, result


async def count_ops(db):
    return await db.scalar(select(func.count()).select_from(Operation))


async def test_confirmation_is_atomic_and_idempotent(client, db, monkeypatch):
    user, result = await draft(client, db, monkeypatch)
    assert await count_ops(db) == 0
    did = uuid.UUID(result['draft_id'])
    await tg.decide(did, 'confirm', user, db)
    await tg.decide(did, 'confirm', user, db)
    assert await count_ops(db) == 1
    record = await db.get(OperationDraftRecord, did)
    assert record.state == 'confirmed' and record.operation_id is not None


async def test_concurrent_confirm_creates_one_operation(client, db, monkeypatch, test_engine):
    user, result = await draft(client, db, monkeypatch)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async def confirm():
        async with factory() as session:
            u = await session.get(User, user.id)
            return await tg.decide(uuid.UUID(result['draft_id']), 'confirm', u, session)
    await asyncio.gather(confirm(), confirm())
    assert await count_ops(db) == 1


async def test_cancel_and_expiry_do_not_write(client, db, monkeypatch):
    user, result = await draft(client, db, monkeypatch)
    did = uuid.UUID(result['draft_id'])
    await tg.decide(did, 'cancel', user, db)
    await tg.decide(did, 'confirm', user, db)
    assert await count_ops(db) == 0
    record = await db.get(OperationDraftRecord, did)
    record.state = 'pending'
    record.expires_at = tg.now() - timedelta(seconds=1)
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await tg.decide(did, 'confirm', user, db)
    assert e.value.status_code == 410
    assert await count_ops(db) == 0


async def test_owner_and_private_chat_required(client, db, monkeypatch):
    user, result = await draft(client, db, monkeypatch)
    other = User(email='other@test', username='other', hashed_password='test')
    db.add(other); await db.commit()
    with pytest.raises(HTTPException) as e:
        await tg.decide(uuid.UUID(result['draft_id']), 'confirm', other, db)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException):
        await tg.linked_user(1, 2, db)
    assert (await client.post('/api/v1/telegram/internal/message', json={'sender_id': 1, 'chat_id': 1})).status_code == 403


async def test_pairing_single_use_and_unlink(client, db, ai_config):
    user, _ = await setup(client, db)
    result = await tg.pairing(user, db)
    token = result['url'].split('start=')[1]
    record = (await db.execute(select(TelegramPairing))).scalar_one()
    assert token != record.token_hash
    await tg.bind(token, 123, db)
    assert (await tg.linked_user(123, 123, db)).id == user.id
    with pytest.raises(HTTPException):
        await tg.bind(token, 123, db)
    assert (await client.delete('/api/v1/telegram/link')).status_code == 204
    with pytest.raises(HTTPException):
        await tg.linked_user(123, 123, db)


async def test_duplicate_message_reuses_draft(client, db, monkeypatch):
    user, result = await draft(client, db, monkeypatch)
    again = await tg.make_draft('fixture', 'telegram:1:1', user, db)
    assert again['draft_id'] == result['draft_id']
    assert tg.parse_operation_text.await_count == 1


@pytest.mark.parametrize('changes', [{'amount': '-10'}, {'currency': 'USD'}, {'expense_group': 'invented'}, {'amount': None}, {'amount': 'NaN'}])
def test_invalid_ai_financial_values_rejected(changes):
    with pytest.raises((ValueError, ArithmeticError)):
        tg.validate_draft(proposal(uuid.uuid4(), **changes))


async def test_voice_path_has_no_write_before_confirmation(client, db, monkeypatch, ai_config):
    user, aid = await setup(client, db)
    link = await tg.pairing(user, db)
    await tg.bind(link['url'].split('start=')[1], 123, db)
    monkeypatch.setattr(tg, 'call_ai', AsyncMock(return_value={'text': 'Потратил 450 рублей со счёта Наличные'}))
    monkeypatch.setattr(tg, 'parse_operation_text', AsyncMock(return_value=proposal(aid)))
    response = await client.post('/api/v1/telegram/internal/message', headers={'X-Telegram-Secret': 'test-internal'},
        json={'sender_id': 123, 'chat_id': 123, 'message_id': 42, 'audio': base64.b64encode(b'OggSfixture').decode()})
    assert response.status_code == 200 and response.json()['draft_id']
    assert 'Распознано:' in response.json()['message']
    assert await count_ops(db) == 0
    assert tg.parse_operation_text.call_args.kwargs['check_limit'] is False


async def test_transcription_rejects_wrong_format(db):
    with pytest.raises(HTTPException) as e:
        await tg.transcribe(base64.b64encode(b'not audio').decode(), None, db)
    assert e.value.status_code == 422


def spec(intent, **kw):
    return AnalyticsSpec(intent=intent, date_from=date(2026, 11, 1), date_to=date(2026, 11, 30), **kw)


async def add(client, aid, **kw):
    payload = dict(account_id=aid, operation_type='expense', amount='100', currency='RUB',
        operated_at='2026-11-12T12:00:00+03:00', expense_group='living')
    payload.update(kw)
    r = await client.post('/api/v1/operations', json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_genbi_credit_fee_and_timezone(client, db):
    user, aid = await setup(client, db)
    await add(client, aid, amount='1000', fee='100', expense_group='credit', principal_amount='800', interest_amount='100')
    # November in Moscow, October in UTC. Must be included.
    await add(client, aid, amount='50', operated_at='2026-10-31T22:00:00Z')
    # December in Moscow. Must be excluded.
    await add(client, aid, amount='900', operated_at='2026-11-30T22:00:00Z')
    report = await analytics.execute_report(spec('expenses_by_category'), user, db)
    assert sum(Decimal(r['value']) for r in report['rows']) == 1050


async def test_genbi_excludes_pending_other_users_and_currency(client, db):
    user, aid = await setup(client, db)
    await add(client, aid, amount='100')
    pending = await add(client, aid, amount='200')
    op = await db.get(Operation, uuid.UUID(pending['id'])); op.status = 'pending'
    other = User(email='other@test', username='other', hashed_password='test')
    db.add(other); await db.flush()
    db.add(Operation(user_id=other.id, account_id=uuid.UUID(aid), operation_type='expense', status='confirmed',
        amount=999, currency='RUB', expense_group='living', operated_at=datetime(2026,11,12,tzinfo=timezone.utc)))
    await db.commit()
    await add(client, aid, amount='300', currency='USD')
    report = await analytics.execute_report(spec('expenses_by_category'), user, db)
    assert sum(Decimal(r['value']) for r in report['rows']) == 100


async def test_cashflow_excludes_funding_and_counts_fees_once(client, db):
    user, aid = await setup(client, db)
    await add(client, aid, operation_type='deposit', amount='1000', income_source='salary')
    await add(client, aid, operation_type='deposit', amount='5000', note='[auto_funding]')
    await add(client, aid, amount='100', fee='10')
    report = await analytics.execute_report(spec('monthly_cashflow'), user, db)
    assert report['rows'][0]['income'] == '1000.00'
    assert report['rows'][0]['free'] == '890.00'


async def test_planner_rejects_sql_and_unknown_spec(client, db, monkeypatch):
    user, _ = await setup(client, db)
    fake = AsyncMock(return_value={'choices': [{'message': {'content': '{"sql":"DROP TABLE operations"}'}}]})
    monkeypatch.setattr(analytics, 'call_ai', fake)
    with pytest.raises(HTTPException) as e:
        await analytics.plan_question('Расходы за месяц', user, db)
    assert e.value.status_code == 422
    assert await count_ops(db) == 0


async def test_unknown_account_and_bad_period_rejected(client, db):
    user, _ = await setup(client, db)
    with pytest.raises(HTTPException):
        await analytics.execute_report(spec('monthly_cashflow', account_name='Missing'), user, db)
    with pytest.raises(ValidationError):
        AnalyticsSpec(intent='monthly_cashflow', date_from='2020-01-01', date_to='2026-01-01')


async def test_empty_report_and_dividends(client, db):
    user, aid = await setup(client, db)
    assert (await analytics.execute_report(spec('dividends_over_time'), user, db))['empty']
    await add(client, aid, operation_type='dividend', amount='123.45')
    report = await analytics.execute_report(spec('dividends_over_time'), user, db)
    assert report['rows'][0]['value'] == '123.45'
