'use client'
import Script from 'next/script'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Account, Bootstrap, Draft, MiniApiError, Operation, Overview, miniRequest, money, moscowDate, operationLabel } from '@/lib/miniapp-api'
import DraftEditor, { DraftPreview } from './DraftEditor'
import GenBI from './GenBI'
import VoiceInput from './VoiceInput'
import { openBot } from './telegram'

type Tab = 'overview'|'analytics'|'entry'|'draft'|'review'|'status'|'history'|'account'
const RECOVERY = 'finai:pending-confirmation'
function readRecovery() { try { return localStorage.getItem(RECOVERY) } catch { return null } }
function storeRecovery(id: string|null) { try { if(id)localStorage.setItem(RECOVERY,id);else localStorage.removeItem(RECOVERY) } catch { /* Recovery in the pending list remains available. */ } }

export default function MiniApp() {
  const [sdkReady,setSdkReady]=useState(false)
  const [initData,setInitData]=useState('')
  const [authError,setAuthError]=useState('')
  const [boot,setBoot]=useState<Bootstrap|null>(null)
  const [tab,setTab]=useState<Tab>('overview')
  const [dark,setDark]=useState(false)
  const [keyboard,setKeyboard]=useState(false)
  const today=moscowDate()
  const [start,setStart]=useState(today.slice(0,7)+'-01')
  const [end,setEnd]=useState(today)
  const [account,setAccount]=useState('')
  const [summary,setSummary]=useState<Overview|null>(null)
  const [summaryError,setSummaryError]=useState('')
  const [summaryLoading,setSummaryLoading]=useState(false)
  const [drafts,setDrafts]=useState<Draft[]>([])
  const [draftsError,setDraftsError]=useState('')
  const [draft,setDraft]=useState<Draft|null>(null)
  const [input,setInput]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [recovering,setRecovering]=useState(false)
  const [unknown,setUnknown]=useState(false)
  const [history,setHistory]=useState<Operation[]>([])
  const [historyFilter,setHistoryFilter]=useState('')
  const [more,setMore]=useState(false)
  const [accountName,setAccountName]=useState('')
  const [accountType,setAccountType]=useState('cash')
  const shell=useRef<HTMLDivElement>(null)
  const main=useRef<HTMLElement>(null)
  const recoveringRef=useRef(false)
  const decidingRef=useRef(false)
  const pendingId=useRef<string|null>(null)
  const request=useRef<{key:string;id:string}|null>(null)
  const summarySequence=useRef(0)
  const api=useCallback(<T,>(path:string,body?:unknown,method?:string)=>miniRequest<T>(initData,path,body,method),[initData])
  const bot=boot?.bot_username||'FinAI_sychikoff_bot'
  const filterQuery=new URLSearchParams({start,end,...(account?{account_id:account}:{})}).toString()

  useEffect(()=>{
    if(!sdkReady)return
    const web=window.Telegram?.WebApp
    if(!web?.initData){setAuthError('Откройте Mini App из меню бота Telegram. Здесь нужен ваш подтверждённый вход.');return}
    web.ready();web.expand();setInitData(web.initData)
    let baseline=window.innerHeight, width=window.innerWidth
    function updateTheme(){const isDark=web?.colorScheme==='dark';setDark(isDark);try{web?.setHeaderColor?.(isDark?'#211b16':'#fcfaf6');web?.setBackgroundColor?.(isDark?'#211b16':'#fcfaf6')}catch{/* Older clients use their own chrome. */}}
    function updateViewport(){
      const viewport=window.visualViewport
      if(window.innerWidth!==width){width=window.innerWidth;baseline=window.innerHeight}
      baseline=Math.max(baseline,window.innerHeight,web?.viewportStableHeight||0)
      const height=Math.min(viewport?.height||window.innerHeight, web?.viewportHeight||window.innerHeight)
      const focused=document.activeElement?.tagName||''
      setKeyboard(['INPUT','TEXTAREA','SELECT'].includes(focused)&&baseline-height>120)
      shell.current?.style.setProperty('--mini-height',`${height}px`)
      shell.current?.style.setProperty('--mini-safe-top',`${(web?.safeAreaInset?.top||0)+(web?.contentSafeAreaInset?.top||0)}px`)
      shell.current?.style.setProperty('--mini-safe-bottom',`${(web?.safeAreaInset?.bottom||0)+(web?.contentSafeAreaInset?.bottom||0)}px`)
    }
    updateTheme();updateViewport()
    web.onEvent('themeChanged',updateTheme);web.onEvent('viewportChanged',updateViewport);web.onEvent('safeAreaChanged',updateViewport);web.onEvent('contentSafeAreaChanged',updateViewport)
    window.visualViewport?.addEventListener('resize',updateViewport);window.addEventListener('resize',updateViewport);document.addEventListener('focusin',updateViewport);document.addEventListener('focusout',updateViewport)
    return()=>{web.offEvent('themeChanged',updateTheme);web.offEvent('viewportChanged',updateViewport);web.offEvent('safeAreaChanged',updateViewport);web.offEvent('contentSafeAreaChanged',updateViewport);window.visualViewport?.removeEventListener('resize',updateViewport);window.removeEventListener('resize',updateViewport);document.removeEventListener('focusin',updateViewport);document.removeEventListener('focusout',updateViewport)}
  },[sdkReady])

  const loadBoot=useCallback(async()=>{try{setBoot(await api<Bootstrap>('/bootstrap'));setAuthError('')}catch(e){setAuthError(e instanceof Error?e.message:'Не удалось войти')}},[api])
  const loadDrafts=useCallback(async()=>{try{setDrafts(await api<Draft[]>('/drafts'));setDraftsError('')}catch(e){setDraftsError(e instanceof Error?e.message:'Не удалось загрузить черновики')}},[api])
  const loadSummary=useCallback(async()=>{
    const sequence=++summarySequence.current;setSummaryLoading(true);setSummaryError('')
    try{const result=await api<Overview>('/overview?'+filterQuery);if(sequence===summarySequence.current)setSummary(result)}
    catch(e){if(sequence===summarySequence.current){setSummary(null);setSummaryError(e instanceof Error?e.message:'Не удалось обновить обзор')}}
    finally{if(sequence===summarySequence.current)setSummaryLoading(false)}
  },[api,filterQuery])
  useEffect(()=>{if(initData)void loadBoot()},[initData,loadBoot])
  useEffect(()=>{if(initData&&boot){void loadSummary();void loadDrafts()}},[initData,!!boot,loadSummary,loadDrafts])

  const recover=useCallback(async(id:string)=>{
    if(recoveringRef.current||decidingRef.current)return
    recoveringRef.current=true;setRecovering(true);setUnknown(true);setError('');setTab('status')
    try{
      const result=await api<Draft>('/drafts/'+id);setDraft(result);setUnknown(false);storeRecovery(null);pendingId.current=null
      if(result.state==='confirmed'){setInput('');request.current=null}
      await Promise.all([loadSummary(),loadDrafts()])
    }catch(e){setError(e instanceof Error?e.message:'Не удалось проверить запись');if(e instanceof MiniApiError&&[401,403].includes(e.status))setAuthError(e.message)}
    finally{recoveringRef.current=false;setRecovering(false)}
  },[api,loadSummary,loadDrafts])
  useEffect(()=>{
    if(!initData||!boot)return
    const resume=()=>{const id=pendingId.current||readRecovery();if(id)void recover(id);else void loadDrafts()}
    const visible=()=>{if(document.visibilityState==='visible')resume()}
    resume();window.addEventListener('online',resume);document.addEventListener('visibilitychange',visible);window.Telegram?.WebApp?.onEvent('activated',resume)
    return()=>{window.removeEventListener('online',resume);document.removeEventListener('visibilitychange',visible);window.Telegram?.WebApp?.offEvent('activated',resume)}
  },[initData,!!boot,recover,loadDrafts])
  useEffect(()=>{const id=pendingId.current||readRecovery();if(!unknown||!id||!initData||busy)return;const timer=setInterval(()=>{if(navigator.onLine)void recover(id)},12000);return()=>clearInterval(timer)},[unknown,initData,recover,busy])
  useEffect(()=>{main.current?.scrollTo(0,0);setNotice('');const back=window.Telegram?.WebApp?.BackButton;const fn=()=>{if(!busy&&!recovering){setTab(tab==='review'?'draft':'overview');setError('')}};if(!['overview','analytics','entry'].includes(tab)){back?.show();back?.onClick(fn)}else back?.hide();return()=>back?.offClick(fn)},[tab,busy,recovering])
  useEffect(()=>{const web=window.Telegram?.WebApp;try{if(input.trim()||draft?.state==='pending')web?.enableClosingConfirmation?.();else web?.disableClosingConfirmation?.()}catch{/* Optional platform feature. */}},[input,draft?.state])

  function go(next:Tab){if(busy||recovering)return;setTab(next);setError('')}
  async function openDraft(id:string){setBusy(true);setError('');try{const result=await api<Draft>('/drafts/'+id);setDraft(result);setTab(result.state==='pending'?'draft':'status')}catch(e){setError(e instanceof Error?e.message:'Черновик недоступен')}finally{setBusy(false)}}
  async function parse(audio?:string){
    if(busy)return
    const key=audio?'audio:'+audio.length+':'+audio.slice(-40):'text:'+input
    if(request.current?.key!==key)request.current={key,id:crypto.randomUUID()}
    setBusy(true);setError('');setNotice(audio?'Распознаём речь и разбираем операцию…':'Разбираем операцию…')
    try{const result=await api<Draft>('/drafts/parse',{request_id:request.current.id,...(audio?{audio}:{text:input})});setDraft(result);setTab(result.state==='pending'?'draft':'status');request.current=null;await loadDrafts()}
    catch(e){setError(e instanceof Error?e.message:'Не удалось разобрать ввод')}
    finally{setBusy(false);setNotice('')}
  }
  async function review(operation:Operation){if(!draft)return;setBusy(true);setError('');try{const result=await api<Draft>('/drafts/'+draft.id,{revision:draft.revision,operation},'PATCH');setDraft(result);setTab('review')}catch(e){setError(e instanceof Error?e.message:'Проверьте поля')}finally{setBusy(false)}}
  async function decide(action:'confirm'|'cancel'){
    if(!draft||busy)return
    const id=draft.id;decidingRef.current=true;pendingId.current=id;storeRecovery(id);setBusy(true);setUnknown(true);setTab('status');setError('')
    try{const result=await api<Draft>('/drafts/'+id+'/decide',{revision:draft.revision,action});setDraft(result);setUnknown(false);storeRecovery(null);pendingId.current=null;if(result.state==='confirmed'){setInput('');request.current=null}await Promise.all([loadSummary(),loadDrafts(),loadBoot()])}
    catch(e){if(e instanceof MiniApiError&&e.status!==0&&e.status<500){setUnknown(false);storeRecovery(null);pendingId.current=null;await openDraft(id);setError(e.message)}else{setError('Ответ не получен. Проверяем, сохранилась ли операция.');decidingRef.current=false;await recover(id)}}
    finally{decidingRef.current=false;setBusy(false)}
  }
  async function loadHistory(append=false){const extending=append&&historyFilter===filterQuery;setBusy(true);setError('');setTab('history');try{const result=await api<{items:Operation[];has_more:boolean}>('/history?'+filterQuery+'&offset='+(extending?history.length:0));setHistory(previous=>extending?[...previous,...result.items]:result.items);setHistoryFilter(filterQuery);setMore(result.has_more)}catch(e){setError(e instanceof Error?e.message:'Не удалось загрузить историю')}finally{setBusy(false)}}
  async function createAccount(event:React.FormEvent){event.preventDefault();setBusy(true);setError('');try{await api('/accounts',{name:accountName,account_type:accountType});await loadBoot();setAccountName('');setTab('entry')}catch(e){setError(e instanceof Error?e.message:'Не удалось создать счёт')}finally{setBusy(false)}}
  const filters=<div className="mini-filters"><div><label htmlFor="period-start">С</label><input id="period-start" type="date" value={start} max={end} onChange={e=>{if(e.target.value)setStart(e.target.value)}} /></div><div><label htmlFor="period-end">По</label><input id="period-end" type="date" value={end} min={start} max={today} onChange={e=>{if(e.target.value)setEnd(e.target.value)}} /></div><div className="mini-account-filter"><label htmlFor="filter-account">Счёт</label><select id="filter-account" value={account} onChange={e=>setAccount(e.target.value)}><option value="">Все счета</option>{boot?.accounts.map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</select></div></div>
  const statusTitle=unknown?(recovering?'Проверяем запись':'Проверяем запись'):draft?.state==='confirmed'?'Операция сохранена':draft?.state==='cancelled'?'Черновик отменён':draft?.state==='expired'?'Срок черновика истёк':'Операция ещё не записана'
  const hideNavigation=keyboard||['draft','review','status'].includes(tab)
  return <><Script src="https://telegram.org/js/telegram-web-app.js" onReady={()=>setSdkReady(true)} onError={()=>setAuthError('Не удалось загрузить Telegram. Проверьте подключение и откройте приложение заново.')} />
    <div ref={shell} className={`mini-shell ${dark?'mini-dark':''} ${keyboard?'mini-keyboard':''}`}>
      <header className="mini-top"><span>Finance AI</span><span className="mini-connection">{boot?'Личный учёт':'Telegram Mini App'}</span></header>
      <main ref={main} className="mini-main" id="mini-content">
      {authError?<section><p className="mini-eyebrow">Вход</p><h1>Откройте через Telegram</h1><p className="mini-error" role="alert">{authError}</p><button className="primary" onClick={()=>openBot(bot)}>Открыть бота</button>{initData&&<button className="secondary mini-wide" onClick={()=>void loadBoot()}>Повторить вход</button>}</section>:!boot?<p role="status">Подключаем личный учёт…</p>:<>
        {['overview','analytics','history'].includes(tab)&&filters}
        {tab==='overview'&&<section><p className="mini-eyebrow">Ваши финансы</p><h1>Обзор</h1>{summaryLoading&&<p role="status">Обновляем данные…</p>}{summaryError&&<div className="mini-error" role="alert"><p>{summaryError}</p><button className="secondary" onClick={()=>void loadSummary()}>Повторить</button></div>}{summary&&!summaryLoading&&<><div className="mini-metric"><p>Деньги на счетах</p><strong>{money(summary.cash)}</strong><p className="mini-hint">На {summary.cash_as_of.split('-').reverse().join('.')} · по подтверждённым операциям</p></div><div className="mini-two"><div><span>Доход за период</span><strong>{money(summary.income)}</strong></div><div><span>Бытовые расходы</span><strong>{money(summary.living)}</strong></div></div><div className="mini-line"><span>Кредитные платежи</span><strong>{money(summary.credit)}</strong></div><div className="mini-line"><div><strong>Свободный поток</strong><p className="mini-hint">После бытовых расходов и кредита</p></div><strong className="accent">{money(summary.free)}</strong></div><div className="mini-actions"><button className="primary" onClick={()=>go('entry')}>Добавить</button><button className="secondary" onClick={()=>go('analytics')}>Задать вопрос</button></div><div className="mini-section-heading"><h2>Последние операции</h2><button className="quiet" onClick={()=>void loadHistory()}>Все</button></div>{summary.recent.length?<Ledger operations={summary.recent} accounts={boot.accounts}/>:<div className="mini-note"><h3>Пока нет операций за период</h3><p>Добавьте доход или расход. После подтверждения он появится в отчётах.</p></div>}</>}{!boot.accounts.length&&<button className="secondary mini-wide" onClick={()=>go('account')}>Создать первый счёт</button>}</section>}
        <section hidden={tab!=='analytics'}><GenBI api={api} filters={{date_from:start,date_to:end,account_name:boot.accounts.find(a=>a.id===account)?.name||null}} /></section>
        {tab==='entry'&&<section><p className="mini-eyebrow">AI-ввод</p><h1>Добавить операцию</h1>{!boot.accounts.length?<div className="mini-note"><p>Для операции нужен счёт.</p><button className="primary" onClick={()=>go('account')}>Создать счёт</button></div>:<><form onSubmit={e=>{e.preventDefault();void parse()}}><div className="mini-field"><label htmlFor="operation-input">Что произошло?</label><textarea id="operation-input" value={input} onChange={e=>setInput(e.target.value)} rows={3} maxLength={2000} placeholder={`Потратил 450 рублей на продукты со счёта ${boot.accounts[0]?.name}`} /></div><button className="primary mini-keyboard-action" disabled={busy||!input.trim()}>{busy?'Обрабатываем…':'Разобрать операцию'}</button></form><p className="mini-hint">Сначала покажем черновик. Запись - после вашего подтверждения.</p><VoiceInput disabled={busy} bot={bot} onAudio={parse}/></>}{notice&&<p role="status">{notice}</p>}{error&&<p className="mini-error" role="alert">{error}</p>}<div className="mini-section-heading"><h2>Ожидают проверки</h2><button className="quiet" disabled={busy} onClick={()=>void loadDrafts()}>Обновить</button></div>{draftsError&&<p className="mini-error" role="alert">{draftsError}</p>}{!draftsError&&!drafts.length&&<p className="mini-hint">Нет ожидающих черновиков. Здесь также появятся записи, отправленные боту.</p>}{drafts.map(d=><button className="mini-draft-row" key={d.id} disabled={busy} onClick={()=>void openDraft(d.id)}><span>{operationLabel(d.operation)}<small>{boot.accounts.find(a=>a.id===d.operation.account_id)?.name}</small></span><strong>{money(d.operation.amount)}</strong></button>)}</section>}
        {tab==='draft'&&draft&&<DraftEditor key={draft.id+':'+draft.revision} draft={draft} accounts={boot.accounts} assets={boot.assets} busy={busy} error={error} onReview={review} onCancel={()=>void decide('cancel')} onReload={()=>void openDraft(draft.id)}/>}
        {tab==='review'&&draft&&<section><DraftPreview draft={draft} accounts={boot.accounts} assets={boot.assets}/>{error&&<p role="alert" className="mini-error">{error}</p>}<div className="mini-sticky-actions"><button className="primary" disabled={busy} onClick={()=>void decide('confirm')}>Подтвердить {operationLabel(draft.operation).toLowerCase()}</button><button className="secondary" disabled={busy} onClick={()=>go('draft')}>Исправить поля</button><button className="quiet" disabled={busy} onClick={()=>void decide('cancel')}>Отменить черновик</button></div></section>}
        {tab==='status'&&<section><p className="mini-eyebrow">Статус операции</p><h1 aria-live="polite">{statusTitle}</h1>{draft&&<><p className="mini-large">{money(draft.operation.amount)}</p><p>{operationLabel(draft.operation)} · {boot.accounts.find(a=>a.id===draft.operation.account_id)?.name}</p></>}{unknown?<><p>Уточняем результат. Повторную операцию не создаём.</p><button className="secondary mini-wide" disabled={recovering} onClick={()=>{const id=pendingId.current||readRecovery();if(id)void recover(id)}}>{recovering?'Проверяем…':'Проверить сейчас'}</button></>:draft?.state==='confirmed'?<><p className="mini-note">Операция записана. Обзор и отчёты можно обновить.</p><button className="primary" onClick={()=>go('analytics')}>Перейти к аналитике</button><button className="secondary mini-wide" onClick={()=>{setDraft(null);go('entry')}}>Добавить ещё</button></>:draft?.state==='pending'?<><p className="mini-note">Черновик сохранён. Проверьте данные и подтвердите запись.</p><button className="primary" onClick={()=>void openDraft(draft.id)}>Открыть черновик</button></>:<><p>{draft?.state==='cancelled'?'Операция не записана. Баланс не изменился.':'Создайте новый черновик и проверьте его перед записью.'}</p><button className="primary" onClick={()=>{setDraft(null);go('entry')}}>Добавить операцию</button></>}{error&&<p className="mini-error" role="alert">{error}</p>}<button className="quiet" disabled={busy||recovering} onClick={()=>go('overview')}>К обзору</button></section>}
        {tab==='history'&&<section><h1>История операций</h1>{error&&<div className="mini-error" role="alert"><p>{error}</p><button className="secondary" disabled={busy} onClick={()=>void loadHistory(history.length>0)}>Повторить загрузку</button></div>}{historyFilter!==filterQuery?<p className="mini-note">Фильтры изменились. Примените их, чтобы обновить историю.</p>:<>{!history.length&&!busy&&!error&&<p>Нет операций за выбранный период.</p>}<Ledger operations={history} accounts={boot.accounts}/>{more&&<button className="secondary mini-wide" disabled={busy} onClick={()=>void loadHistory(true)}>Показать ещё</button>}</>}{busy&&<p role="status">Загружаем операции…</p>}<button className="quiet" disabled={busy} onClick={()=>void loadHistory()}>Применить фильтры</button></section>}
        {tab==='account'&&<section><h1>Новый счёт</h1><form onSubmit={createAccount}><div className="mini-field"><label htmlFor="new-account-name">Название</label><input id="new-account-name" required maxLength={100} value={accountName} onChange={e=>setAccountName(e.target.value)} placeholder="Наличные"/></div><div className="mini-field"><label htmlFor="new-account-type">Тип счёта</label><select id="new-account-type" value={accountType} onChange={e=>setAccountType(e.target.value)}><option value="cash">Наличные</option><option value="bank">Банковский</option><option value="broker">Брокерский</option><option value="savings">Накопительный</option><option value="other">Другой</option></select></div><p className="mini-hint">Валюта RUB. Начальный остаток задаётся отдельной подтверждённой операцией.</p>{error&&<p className="mini-error" role="alert">{error}</p>}<button className="primary" disabled={busy||!accountName.trim()}>Создать счёт</button></form></section>}
      </>}
      </main>
      {boot&&!authError&&!hideNavigation&&<nav className="mini-nav" aria-label="Разделы приложения">{([['overview','Обзор'],['analytics','Аналитика'],['entry','Добавить']] as const).map(([route,label])=><button key={route} type="button" aria-current={tab===route?'page':undefined} disabled={busy} onClick={()=>go(route)}><span aria-hidden="true">{route==='overview'?'◫':route==='analytics'?'▥':'＋'}</span>{label}</button>)}</nav>}
    </div>
  </>
}

function Ledger({operations,accounts}:{operations:Operation[];accounts:Account[]}){
  return <ul className="mini-ledger">{operations.map((operation,index)=>{const outgoing=['expense','withdraw','buy','fee','tax'].includes(operation.operation_type);const incoming=['deposit','sell','dividend','coupon'].includes(operation.operation_type);return <li key={String(operation.id||index)}><div><strong>{String(operation.expense_category||operationLabel(operation))}</strong><span>{moscowDate(new Date(operation.operated_at)).split('-').reverse().join('.')} · {accounts.find(a=>a.id===operation.account_id)?.name}{operation.operation_type==='transfer'?' → '+accounts.find(a=>a.id===operation.to_account_id)?.name:''}</span></div><strong>{outgoing?'−':incoming?'+':''}{money(operation.amount)}</strong></li>})}</ul>
}
