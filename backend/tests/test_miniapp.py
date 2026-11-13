import asyncio
import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import date, timedelta
from urllib.parse import urlencode
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.config import settings
from app.dependencies import get_current_user_dev
from app.models.account import Account
from app.models.operation import Operation
from app.models.telegram import TelegramLink, OperationDraftRecord
from app.models.user import User
from app.schemas.ai_command import OperationDraft, ParseResponse
from app.schemas.analytics import AnalyticsSpec
from app.services import analytics_service as analytics, telegram_service as tg
from app.services.miniapp_auth import telegram_identity

PREFIX = '/api/v1/miniapp'


def signed(user_id=123456, age=0, **changes):
    data = {'auth_date': str(int(time.time()) - age), 'user': json.dumps({'id': user_id, 'first_name': 'Fixture'}), 'query_id': 'test'}
    data.update(changes)
    secret = hmac.new(b'WebAppData', b'mini-test', hashlib.sha256).digest()
    data['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k,v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


@pytest.fixture
def mini_config(monkeypatch):
    monkeypatch.setattr(settings, 'telegram_bot_token', SecretStr('mini-test'))
    monkeypatch.setattr(settings, 'ai_cooldown_seconds', 0)


async def owner(client, db):
    await client.post('/api/v1/seed/dev-data')
    user = await get_current_user_dev(db)
    db.add(TelegramLink(telegram_id=123456, user_id=user.id))
    await db.commit()
    accounts = (await client.get('/api/v1/accounts')).json()
    aid = next(a['id'] for a in accounts if a['name'] == 'Наличные')
    client.headers['Authorization'] = 'tma ' + signed()
    return user, aid


async def make(client, db, monkeypatch):
    user, aid = await owner(client, db)
    proposal = ParseResponse(status='parsed', raw_text='synthetic', account_id=aid,
        operation=OperationDraft(operation_type='expense', account_name='Наличные', amount='450',
            expense_group='living', expense_category='Продукты', operated_at='2026-11-13T12:00:00+03:00'))
    parse_mock = AsyncMock(return_value=proposal)
    monkeypatch.setattr(tg, 'parse_operation_text', parse_mock)
    body = {'request_id': str(uuid.uuid4()), 'text': 'fixture operation'}
    response = await client.post(PREFIX + '/drafts/parse', json=body)
    assert response.status_code == 200, response.text
    return user, aid, response.json(), body, parse_mock


def test_valid_signed_identity(mini_config):
    assert telegram_identity(signed()) == 123456


@pytest.mark.parametrize('raw', ['', 'user=x', 'hash='+'0'*64+'&auth_date=1&user=%7B%7D'])
def test_invalid_identity(mini_config, raw):
    with pytest.raises(HTTPException) as error:
        telegram_identity(raw)
    assert error.value.status_code == 401


@pytest.mark.parametrize('age', [4000, -300])
def test_identity_time_window(mini_config, age):
    with pytest.raises(HTTPException):
        telegram_identity(signed(age=age))


def test_identity_tamper_and_duplicate(mini_config):
    for raw in [signed().replace('123456', '654321'), signed() + '&auth_date=1', signed(user_id=True)]:
        with pytest.raises(HTTPException):
            telegram_identity(raw)


async def test_auth_binding_and_owner_scope(client, db, mini_config):
    assert (await client.get(PREFIX+'/bootstrap')).status_code == 401
    client.headers['Authorization'] = 'tma '+signed()
    assert (await client.get(PREFIX+'/bootstrap')).status_code == 403
    user, aid = await owner(client, db)
    other = User(email='other@mini.test', username='other', hashed_password='fixture')
    db.add(other); await db.flush()
    foreign = Account(user_id=other.id, name='Foreign', account_type='cash', currency='RUB')
    db.add(foreign); await db.commit()
    result = (await client.get(PREFIX+'/bootstrap')).json()
    assert all(a['id'] != str(foreign.id) for a in result['accounts'])
    response = await client.get(PREFIX+'/overview', params={'start':'2026-11-01','end':'2026-11-13','account_id':str(foreign.id)})
    assert response.status_code == 404
    client.headers['Authorization'] = 'tma '+signed(user_id=999)
    assert (await client.get(PREFIX+'/bootstrap')).status_code == 403


async def test_draft_edit_stale_confirm_replay(client, db, monkeypatch, mini_config):
    user, aid, draft, body, parse_mock = await make(client, db, monkeypatch)
    replay = await client.post(PREFIX+'/drafts/parse', json=body)
    assert replay.json()['id'] == draft['id'] and parse_mock.await_count == 1
    assert await db.scalar(select(func.count()).select_from(Operation)) == 0
    operation = {**draft['operation'], 'amount':'700', 'expense_category':'Дом'}
    response = await client.patch(PREFIX+'/drafts/'+draft['id'], json={'revision':1,'operation':operation})
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited['revision'] == 2 and edited['operation']['amount'] == '700'
    assert (await client.post(PREFIX+'/drafts/'+draft['id']+'/decide', json={'revision':1,'action':'confirm'})).status_code == 409
    with pytest.raises(HTTPException) as error:
        await tg.decide(uuid.UUID(draft['id']), 'confirm', user, db)
    assert error.value.status_code == 409  # old bot button cannot confirm edited content
    assert await db.scalar(select(func.count()).select_from(Operation)) == 0
    result = await client.post(PREFIX+'/drafts/'+draft['id']+'/decide', json={'revision':2,'action':'confirm'})
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'confirmed'
    await client.post(PREFIX+'/drafts/'+draft['id']+'/decide', json={'revision':2,'action':'confirm'})
    assert await db.scalar(select(func.count()).select_from(Operation)) == 1
    status = (await client.get(PREFIX+'/drafts/'+draft['id'])).json()
    assert status['state'] == 'confirmed' and status['operation_id']
    replay = (await client.post(PREFIX+'/drafts/parse',json=body)).json()
    assert replay['state'] == 'confirmed' and parse_mock.await_count == 1
    overview = (await client.get(PREFIX+'/overview',params={'start':'2026-11-01','end':'2026-11-13'})).json()
    assert overview['cash'] == '-700.00000000' and overview['count'] == 1


async def test_draft_foreign_account_and_invalid_values(client, db, monkeypatch, mini_config):
    user, aid, draft, _, _ = await make(client, db, monkeypatch)
    for patch in [{'amount':'-1'},{'amount':'1e20'},{'currency':'USD'},{'is_refund':True},{'operation_type':'deposit'}, {'expense_category':'x'*51}, {'income_source':'x'*51}]:
        result = await client.patch(PREFIX+'/drafts/'+draft['id'], json={'revision':1,'operation':{**draft['operation'],**patch}})
        assert result.status_code in (400,422), result.text
    other = User(email='foreign@mini.test', username='foreign', hashed_password='fixture')
    db.add(other); await db.flush()
    account = Account(user_id=other.id, name='Foreign',account_type='cash',currency='RUB')
    db.add(account); await db.commit()
    result = await client.patch(PREFIX+'/drafts/'+draft['id'], json={'revision':1,'operation':{**draft['operation'],'account_id':str(account.id)}})
    assert result.status_code == 404
    db.add(TelegramLink(telegram_id=777,user_id=other.id)); await db.commit()
    client.headers['Authorization'] = 'tma '+signed(user_id=777)
    assert (await client.get(PREFIX+'/drafts/'+draft['id'])).status_code == 404
    assert (await client.get(PREFIX+'/drafts')).json() == []


async def test_cancel_expiry_and_account_creation(client, db, monkeypatch, mini_config):
    user, aid, draft, _, _ = await make(client, db, monkeypatch)
    result=await client.post(PREFIX+'/drafts/'+draft['id']+'/decide',json={'action':'cancel','revision':1})
    assert result.json()['state']=='cancelled'
    assert (await client.post(PREFIX+'/drafts/'+draft['id']+'/decide',json={'action':'confirm','revision':1})).json()['state']=='cancelled'
    assert await db.scalar(select(func.count()).select_from(Operation))==0
    record=await db.get(OperationDraftRecord,uuid.UUID(draft['id'])); record.state='pending';record.expires_at=tg.now()-timedelta(seconds=1);await db.commit()
    assert (await client.get(PREFIX+'/drafts/'+draft['id'])).json()['state']=='expired'
    assert (await client.post(PREFIX+'/drafts/'+draft['id']+'/decide',json={'action':'confirm','revision':1})).status_code==410
    assert (await client.post(PREFIX+'/accounts',json={'name':'Mini cash','account_type':'cash'})).status_code==201
    assert (await client.post(PREFIX+'/accounts',json={'name':'mini CASH','account_type':'cash'})).status_code==409


async def test_shared_confirm_concurrency(client, db, monkeypatch, mini_config, test_engine):
    user, aid, draft, _, _ = await make(client, db, monkeypatch)
    factory=async_sessionmaker(test_engine,expire_on_commit=False)
    async def confirm(revision):
        async with factory() as session:
            u=await session.get(User,user.id)
            await tg.decide(uuid.UUID(draft['id']),'confirm',u,session,expected_revision=revision)
    await asyncio.gather(confirm(1),confirm(None))
    assert await db.scalar(select(func.count()).select_from(Operation))==1


async def test_context_retains_account_and_intent(client, db, monkeypatch, mini_config):
    user, aid=await owner(client,db)
    response={'changes':{'date_from':'2026-10-01','date_to':'2026-10-31'}}
    ai=AsyncMock(return_value={'choices':[{'message':{'content':json.dumps(response)}}]})
    monkeypatch.setattr(analytics,'call_ai',ai)
    context=AnalyticsSpec(intent='expenses_by_category',date_from=date(2026,11,1),date_to=date(2026,11,13),account_name='Наличные')
    spec=await analytics.plan_question('А за прошлый месяц?',user,db,context=context)
    assert spec.account_name=='Наличные' and spec.intent==context.intent and spec.date_from==date(2026,10,1)
    assert 'changes' in ai.call_args.args[1]['messages'][0]['content']
    response=await client.post(PREFIX+'/query',json={'question':'А за прошлый месяц?','context':context.model_dump(mode='json')})
    assert response.status_code==200 and response.json()['spec']['account_name']=='Наличные'


@pytest.mark.parametrize('question', ['На что ушли деньги в этом месяце?', 'Куда ушли деньги?', 'Покажи отчёт за месяц'])
async def test_visible_genbi_prompt_reaches_planner(client, db, monkeypatch, mini_config, question):
    await owner(client,db)
    spec={'intent':'expenses_by_category','date_from':'2026-11-01','date_to':'2026-11-13','account_name':None}
    planner=AsyncMock(return_value={'choices':[{'message':{'content':json.dumps(spec)}}]})
    monkeypatch.setattr(analytics,'call_ai',planner)
    response=await client.post(PREFIX+'/query',json={'question':question})
    assert response.status_code==200,response.text
    planner.assert_awaited_once()
    assert response.json()['spec']==spec


@pytest.mark.parametrize('answer',[{'changes':{'merchant':'X'}},{'changes':{'date_to':'2026-10-31'}},{'unsupported':True},{'clarification':'Какой счёт выбрать?'}])
async def test_context_does_not_silently_ignore_invalid_request(client,db,monkeypatch,mini_config,answer):
    user,aid=await owner(client,db)
    monkeypatch.setattr(analytics,'call_ai',AsyncMock(return_value={'choices':[{'message':{'content':json.dumps(answer)}}]}))
    response=await client.post(PREFIX+'/query',json={'question':'А за прошлый месяц?','context':{'intent':'expenses_by_category','date_from':'2026-11-01','date_to':'2026-11-13','account_name':'Наличные'}})
    assert response.status_code==422


@pytest.mark.parametrize('account_name',[None,'Наличные'])
async def test_repeating_question_after_preset_refreshes_current_report(client,db,monkeypatch,mini_config,account_name):
    await owner(client,db)
    initial=await client.post(PREFIX+'/reports',json={'intent':'expenses_by_category',
        'date_from':'2026-11-01','date_to':'2026-11-13','account_name':account_name})
    assert initial.status_code==200
    context=initial.json()['spec']
    # Captured live provider response when the user's question repeats the preset.
    planner=AsyncMock(return_value={'choices':[{'message':{'content':'{"changes": {}}'}}]})
    monkeypatch.setattr(analytics,'call_ai',planner)
    for _ in range(2):
        response=await client.post(PREFIX+'/query',json={
            'question':'на что ушли деньги в этом месяце?','context':context})
        assert response.status_code==200,response.text
        assert response.json()['spec']==context
        assert response.json()['rows']==initial.json()['rows']
    assert planner.await_count==2


async def test_audio_rejected_before_provider(client,db,mini_config):
    await owner(client,db)
    result=await client.post(PREFIX+'/drafts/parse',json={'request_id':str(uuid.uuid4()),'audio':base64.b64encode(b'not an audio file').decode()})
    assert result.status_code==422


async def test_reports_need_valid_period_and_account(client,db,mini_config):
    await owner(client,db)
    spec={'intent':'expenses_by_category','date_from':'2026-11-01','date_to':'2026-11-13','account_name':'unknown'}
    assert (await client.post(PREFIX+'/reports',json=spec)).status_code==422
    spec.update(account_name=None,date_to='2999-01-01')
    assert (await client.post(PREFIX+'/reports',json=spec)).status_code==422


@pytest.mark.parametrize('audio_format,codec', [('webm','libopus'),('mp4','aac'),('wav','pcm_s16le')])
async def test_browser_audio_conversion(audio_format,codec,monkeypatch,tmp_path):
    from app.services.miniapp_service import transcribe_media
    source=tmp_path/('recording.'+audio_format)
    process=await asyncio.create_subprocess_exec('ffmpeg','-v','error','-f','lavfi','-i',
        'sine=frequency=440:duration=0.2','-c:a',codec,str(source))
    assert await process.wait()==0
    transcribe=AsyncMock(return_value='Распознанная операция')
    monkeypatch.setattr(tg,'transcribe',transcribe)
    assert await transcribe_media(base64.b64encode(source.read_bytes()).decode(),None,None)=='Распознанная операция'
    assert base64.b64decode(transcribe.call_args.args[0]).startswith(b'OggS')


async def test_overview_transfer_legs_and_moscow_boundary(client,db,mini_config):
    from datetime import datetime
    from decimal import Decimal
    user, aid=await owner(client,db)
    target=Account(user_id=user.id,name='Получатель',account_type='bank',currency='RUB')
    db.add(target); await db.flush()
    rows=[dict(operation_type='deposit',amount='1000',operated_at='2026-10-31T20:59:00+00:00',income_source='salary'),
          dict(operation_type='transfer',amount='300',fee='10',to_account_id=target.id,operated_at='2026-10-31T21:00:00+00:00'),
          dict(operation_type='expense',amount='100',fee='10',expense_group='credit',principal_amount='80',interest_amount='10',operated_at='2026-11-01T12:00:00+03:00')]
    for row in rows:
        row['operated_at']=datetime.fromisoformat(row['operated_at'])
        db.add(Operation(user_id=user.id,account_id=uuid.UUID(aid),currency='RUB',status='confirmed',**row))
    await db.commit()
    params={'start':'2026-11-01','end':'2026-11-01'}
    result=(await client.get(PREFIX+'/overview',params=params)).json()
    assert Decimal(result['cash'])==890 and Decimal(result['credit'])==100
    assert Decimal(result['income'])==0 and result['count']==2
    result=(await client.get(PREFIX+'/overview',params={**params,'account_id':str(target.id)})).json()
    assert Decimal(result['cash'])==300 and result['count']==1
    assert Decimal(result['free'])==0
    history=(await client.get(PREFIX+'/history',params={**params,'account_id':str(target.id)})).json()
    assert len(history['items'])==1 and history['items'][0]['operation_type']=='transfer'
    boot=(await client.get(PREFIX+'/bootstrap')).json()
    assert Decimal(next(a['cash_balance'] for a in boot['accounts'] if a['id']==str(target.id)))==300


@pytest.mark.parametrize('intent,key,expected',[
    ('expenses_by_category','value','50.00'),
    ('monthly_cashflow','income','1000.00'),
    ('dividends_over_time','value','20.00'),
    ('allocation_by_account','value','200.00'),
    ('allocation_by_asset_type','value','200.00'),
])
async def test_all_report_modules_with_real_ledger(client,db,mini_config,intent,key,expected):
    from app.models.asset import Asset
    user,aid=await owner(client,db)
    asset=await db.scalar(select(Asset).where(Asset.ticker=='SBER'))
    common={'account_id':aid,'currency':'RUB','operated_at':'2026-11-12T12:00:00+03:00'}
    for fields in [
        {'operation_type':'deposit','amount':'1000','income_source':'salary'},
        {'operation_type':'buy','amount':'200','asset_id':str(asset.id),'quantity':'2','price':'100','fee':'10'},
        {'operation_type':'expense','amount':'50','expense_group':'living','expense_category':'Продукты'},
        {'operation_type':'dividend','amount':'20','asset_id':str(asset.id)},
    ]:
        response=await client.post('/api/v1/operations',json={**common,**fields})
        assert response.status_code==201,response.text
    response=await client.post(PREFIX+'/reports',json={'intent':intent,'date_from':'2026-11-01',
        'date_to':'2026-11-13','account_name':'Наличные'})
    assert response.status_code==200,response.text
    # Project rule: the 10 RUB trade fee reduces cash and belongs to investment
    # expenses; it is not added to the 200 RUB position cost.
    assert response.json()['totals'][key]==expected
    assert not response.json()['empty']
