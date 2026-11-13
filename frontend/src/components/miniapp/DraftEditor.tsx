'use client'
import { useState } from 'react'
import { Account, Asset, Draft, Operation, money, moscowDate, operationLabel } from '@/lib/miniapp-api'

export default function DraftEditor({ draft, accounts, assets, busy, error, onReview, onCancel, onReload }: {
  draft: Draft; accounts: Account[]; assets: Asset[]; busy: boolean; error: string;
  onReview: (operation: Operation) => Promise<void>; onCancel: () => void; onReload: () => void
}) {
  const [operation, setOperation] = useState<Operation>({ ...draft.operation })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const value = (key: string) => String(operation[key] ?? '')
  const change = (key: string, raw: string) => setOperation(previous => ({ ...previous, [key]: raw || null }))
  const trade = ['buy', 'sell'].includes(operation.operation_type)
  function field(key: string, label: string, numeric = false, required = false) {
    const id = 'draft-' + key
    return <div className="mini-field" key={key}><label htmlFor={id}>{label}</label><input id={id} value={value(key)} inputMode={numeric ? 'decimal' : undefined} maxLength={numeric ? 24 : key==='expense_category' ? 50 : key==='merchant' ? 255 : 2000} required={required} disabled={busy} aria-invalid={!!fieldErrors[key]} aria-describedby={fieldErrors[key] ? id + '-error' : undefined}
      onChange={e => change(key, numeric ? e.target.value.replace(',', '.') : e.target.value)} />{fieldErrors[key] && <p className="field-error" id={id + '-error'}>{fieldErrors[key]}</p>}</div>
  }
  async function review(event: React.FormEvent) {
    event.preventDefault()
    const errors: Record<string, string> = {}
    for (const key of ['amount','fee','quantity','price','principal_amount','interest_amount']) {
      if (operation[key] != null && (!Number.isFinite(Number(operation[key])) || Number(operation[key]) < 0)) errors[key] = 'Введите неотрицательное число.'
    }
    if (!trade && operation.operation_type !== 'manual_valuation' && Number(operation.amount) <= 0) errors.amount = 'Сумма должна быть больше нуля.'
    if (trade) for (const key of ['quantity','price']) if (Number(operation[key]) <= 0) errors[key] = 'Значение должно быть больше нуля.'
    setFieldErrors(errors)
    if (!Object.keys(errors).length) await onReview(operation)
  }
  return <form id="mini-draft-form" onSubmit={review}>
    <p className="mini-eyebrow">Черновик</p><h1>Проверьте операцию</h1><p className="mini-hint">{operationLabel(operation)} · ещё не записан</p>
    {draft.raw_text && <details><summary>Исходный текст</summary><p>{draft.raw_text}</p></details>}
    {draft.warnings?.map((warning, index) => <p className="mini-note" key={index}>{warning}</p>)}
    {!trade && operation.operation_type !== 'manual_valuation' && field('amount','Сумма, ₽',true,true)}
    <div className="mini-field"><label htmlFor="draft-account">{operation.operation_type === 'transfer' ? 'Откуда' : 'Счёт'}</label><select id="draft-account" value={operation.account_id} onChange={e=>change('account_id',e.target.value)} disabled={busy}>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
    {['transfer','buy'].includes(operation.operation_type) && <p className="mini-hint">Доступно на счёте: {money(accounts.find(a=>a.id===operation.account_id)?.cash_balance||'0')}. Проверим остаток ещё раз при подтверждении.</p>}
    {operation.operation_type === 'transfer' && <div className="mini-field"><label htmlFor="draft-target">Куда</label><select id="draft-target" required value={value('to_account_id')} disabled={busy} onChange={e=>change('to_account_id',e.target.value)}><option value="">Выберите счёт</option>{accounts.filter(a=>a.id!==operation.account_id).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></div>}
    {(trade || operation.operation_type === 'manual_valuation' || operation.asset_id) && <div className="mini-field"><label htmlFor="draft-asset">Актив</label><select id="draft-asset" value={value('asset_id')} required disabled={busy} onChange={e=>change('asset_id',e.target.value)}><option value="">Выберите актив</option>{assets.map(a=><option key={a.id} value={a.id}>{a.ticker ? a.ticker + ' · ' : ''}{a.name}</option>)}</select></div>}
    {trade && field('quantity','Количество',true,true)}{(trade || operation.operation_type === 'manual_valuation') && field('price',operation.operation_type === 'manual_valuation' ? 'Оценка единицы, ₽' : 'Цена единицы, ₽',true,true)}
    {trade && <p className="mini-hint">Итоговую сумму рассчитаем из количества и цены на следующем шаге.</p>}
    {operation.operation_type === 'expense' && <><div className="mini-field"><label htmlFor="draft-group">Группа расходов</label><select id="draft-group" value={value('expense_group')} disabled={busy} onChange={e=>change('expense_group',e.target.value)}><option value="living">Бытовые расходы</option><option value="investment">Инвестиционные расходы</option><option value="credit">Кредитный платёж</option></select></div>{field('expense_category','Категория')}{field('merchant','Продавец')}</>}
    <div className="mini-field"><label htmlFor="draft-date">Дата</label><input id="draft-date" type="date" required disabled={busy} value={moscowDate(new Date(operation.operated_at))} onChange={e=>{if(e.target.value)change('operated_at',e.target.value+'T12:00:00+03:00')}} /></div>
    {field('fee',operation.expense_group === 'credit' ? 'Комиссия внутри платежа, ₽' : 'Комиссия, ₽',true)}
    {operation.expense_group === 'credit' && <>{field('principal_amount','Основной долг, ₽',true)}{field('interest_amount','Проценты, ₽',true)}<p className="mini-hint">Сумма платежа включает основной долг, проценты и комиссию.</p></>}
    {operation.operation_type === 'deposit' && <div className="mini-field"><label htmlFor="draft-income">Назначение поступления</label><select id="draft-income" value={value('income_source')} disabled={busy} onChange={e=>change('income_source',e.target.value)}><option value="">Пополнение своими деньгами</option><option value="salary">Зарплата</option><option value="bonus">Премия</option><option value="freelance">Подработка</option><option value="gift">Подарок</option><option value="interest">Фактически полученные проценты</option><option value="sale">Продажа имущества вне учёта</option><option value="other">Другой доход</option></select></div>}
    {field('note','Примечание')}
    <p className="mini-note">До подтверждения финансовая операция не записывается.</p>
    {error && <div className="mini-error" role="alert"><p>{error}</p><button type="button" className="secondary" disabled={busy} onClick={onReload}>Загрузить актуальный черновик</button></div>}
    <div className="mini-sticky-actions"><button type="submit" className="primary" disabled={busy}>{busy ? 'Проверяем…' : 'Проверить данные'}</button><button type="button" className="secondary" disabled={busy} onClick={onCancel}>Отменить черновик</button></div>
  </form>
}

export function DraftPreview({ draft, accounts, assets }: { draft: Draft; accounts: Account[]; assets: Asset[] }) {
  const operation = draft.operation
  const labels: Record<string,string> = { expense_category:'Категория', expense_group:'Группа', quantity:'Количество',price:'Цена единицы',fee:'Комиссия',principal_amount:'Основной долг',interest_amount:'Проценты',income_source:'Источник дохода',merchant:'Продавец',note:'Примечание' }
  const group: Record<string,string> = { living:'Бытовые расходы', investment:'Инвестиционные расходы',credit:'Кредитный платёж',salary:'Зарплата',bonus:'Премия',freelance:'Подработка',gift:'Подарок',interest:'Проценты',sale:'Продажа имущества вне учёта',other:'Другой доход' }
  return <><p className="mini-eyebrow">{operationLabel(operation)}</p><h1>Подтвердите операцию</h1><p className="mini-large">{money(operation.operation_type === 'manual_valuation' ? String(operation.price || '0') : operation.amount)}</p><dl className="mini-facts"><div><dt>Счёт</dt><dd>{accounts.find(a=>a.id===operation.account_id)?.name}</dd></div>{operation.to_account_id && <div><dt>Куда</dt><dd>{accounts.find(a=>a.id===operation.to_account_id)?.name}</dd></div>}{operation.asset_id && <div><dt>Актив</dt><dd>{assets.find(a=>a.id===operation.asset_id)?.name}</dd></div>}<div><dt>Дата</dt><dd>{moscowDate(new Date(operation.operated_at)).split('-').reverse().join('.')}</dd></div>{Object.entries(labels).filter(([key])=>operation[key]!=null&&operation[key]!=='').map(([key,label])=><div key={key}><dt>{label}</dt><dd>{group[String(operation[key])] || String(operation[key])}</dd></div>)}</dl><p className="mini-note">Операция ещё не записана. Проверьте данные перед подтверждением.</p></>
}
