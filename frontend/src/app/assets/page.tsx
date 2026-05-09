'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Account, Asset, AssetType, DepositSummary } from '@/lib/types'
import { ASSET_TYPES, PHYSICAL_ASSET_TYPES } from '@/lib/types'

const inputCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors'
const selectCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors'
const labelCls = 'block text-xs text-gray-400 mb-1.5'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className={labelCls}>{label}</label>
      {children}
    </div>
  )
}

// ── Deposit Close Modal ───────────────────────────────────────────────────────

function DepositCloseModal({
  deposit,
  accounts,
  onClose,
  onSuccess,
}: {
  deposit: DepositSummary
  accounts: Account[]
  onClose: () => void
  onSuccess: () => void
}) {
  const principalAmount = parseFloat(deposit.principal).toFixed(2)
  const today = new Date().toISOString().slice(0, 10)
  const defaultDate = deposit.interest_end_date ?? today
  const targetAccounts = accounts.filter((a) => a.id !== deposit.account_id)

  const [targetAccountId, setTargetAccountId] = useState(targetAccounts[0]?.id ?? '')
  const [amount, setAmount] = useState(principalAmount)
  const [closeDate, setCloseDate] = useState(defaultDate)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!targetAccountId) { setError('Выберите счёт для перевода'); return }
    const amt = parseFloat(amount)
    if (isNaN(amt) || amt <= 0) { setError('Введите положительную сумму'); return }
    setSubmitting(true)
    try {
      await api.operations.transfer({
        from_account_id: deposit.account_id,
        to_account_id: targetAccountId,
        amount,
        currency: deposit.currency,
        operated_at: new Date(closeDate).toISOString(),
        note: `Закрытие вклада: ${deposit.name}`,
      })
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при закрытии вклада')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div>
            <h2 className="text-base font-semibold text-white">Закрыть вклад</h2>
            <p className="text-xs text-gray-500 mt-0.5">{deposit.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">{error}</div>
          )}
          <div className="rounded-lg bg-gray-800/50 p-3 space-y-1 text-xs text-gray-400">
            <div className="flex justify-between">
              <span>Тело вклада (к переводу)</span>
              <span className="tabular-nums text-white">{fmt(deposit.principal)} {deposit.currency}</span>
            </div>
            {parseFloat(deposit.accrued_interest) > 0 && (
              <div className="flex justify-between">
                <span>Расчётные проценты (не переводятся)</span>
                <span className="tabular-nums text-gray-500">{fmt(deposit.accrued_interest)} {deposit.currency}</span>
              </div>
            )}
          </div>
          <div className="rounded-lg border border-blue-800/30 bg-blue-950/15 px-3 py-2.5 text-xs text-blue-300 leading-relaxed">
            Переводится только основная сумма вклада. Если банк выплатил проценты,
            создайте отдельную операцию <strong>«Ввести доход»</strong> с источником «Проценты».
          </div>
          <div>
            <label className={labelCls}>Сумма перевода *</label>
            <input type="number" step="any" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputCls} />
            <p className="text-xs text-gray-600 mt-1">По умолчанию: основная сумма вклада без процентов</p>
          </div>
          <div>
            <label className={labelCls}>Зачислить на счёт *</label>
            <select value={targetAccountId} onChange={(e) => setTargetAccountId(e.target.value)} className={selectCls}>
              <option value="">— выберите счёт —</option>
              {targetAccounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Дата закрытия</label>
            <input type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)} className={inputCls} />
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={submitting} className="flex-1 px-4 py-2 text-sm rounded-lg bg-amber-700 hover:bg-amber-600 text-white disabled:opacity-50 transition-colors">
              {submitting ? 'Закрываю…' : 'Закрыть и перевести'}
            </button>
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">Отмена</button>
          </div>
        </form>
      </div>
    </div>
  )
}

const PAYOUT_FREQ_LABELS: Record<string, string> = {
  daily: 'Ежедневно',
  monthly: 'Ежемесячно',
  at_maturity: 'В конце срока',
}

const TYPE_COLORS: Record<AssetType, string> = {
  stock: 'text-blue-400 bg-blue-900/30',
  bond: 'text-green-400 bg-green-900/30',
  etf: 'text-violet-400 bg-violet-900/30',
  currency: 'text-gray-300 bg-gray-700/50',
  cash: 'text-slate-400 bg-slate-800/50',
  deposit: 'text-sky-400 bg-sky-900/30',
  crypto: 'text-amber-400 bg-amber-900/30',
  real_estate: 'text-red-400 bg-red-900/30',
  vehicle: 'text-orange-400 bg-orange-900/30',
  other_physical: 'text-stone-400 bg-stone-800/40',
  other: 'text-gray-400 bg-gray-800',
}

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  stock: 'Акция',
  bond: 'Облигация',
  etf: 'ETF',
  currency: 'Валюта',
  cash: 'Наличные',
  deposit: 'Вклад',
  crypto: 'Крипто',
  real_estate: 'Недвижимость',
  vehicle: 'Автомобиль',
  other_physical: 'Физ. актив',
  other: 'Другое',
}

const CREDIT_KIND_LABELS: Record<string, string> = {
  mortgage: 'Ипотека',
  auto_loan: 'Автокредит',
  consumer_loan: 'Потребкредит',
  personal_loan: 'Личный займ',
  other: 'Кредит',
}

function fmt(value: string | number | null | undefined) {
  if (value === null || value === undefined) return '—'
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU')
}

// ── Edit Asset Modal ──────────────────────────────────────────────────────────

function EditAssetModal({
  asset,
  onClose,
  onSaved,
}: {
  asset: Asset
  onClose: () => void
  onSaved: () => void
}) {
  const isPhysical = PHYSICAL_ASSET_TYPES.has(asset.asset_type)

  const [form, setForm] = useState({
    name: asset.name,
    ticker: asset.ticker,
    currency: asset.currency,
    estimated_value: asset.estimated_value ?? '',
    note: asset.note ?? '',
    acquisition_date: asset.acquisition_date ?? '',
    is_credit_linked: asset.is_credit_linked,
    credit_kind: asset.credit_kind ?? 'mortgage',
    credit_note: asset.credit_note ?? '',
    include_in_capital: asset.include_in_capital,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name.trim()) { setError('Укажите название'); return }
    if (!isPhysical && !form.ticker.trim()) { setError('Тикер обязателен'); return }
    setError(null)
    setSubmitting(true)
    try {
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        currency: form.currency.trim().toUpperCase(),
        estimated_value: form.estimated_value !== '' ? form.estimated_value : null,
        note: form.note.trim() || null,
        acquisition_date: form.acquisition_date || null,
        is_credit_linked: form.is_credit_linked,
        credit_kind: form.is_credit_linked ? form.credit_kind : null,
        credit_note: form.is_credit_linked ? (form.credit_note.trim() || null) : null,
        include_in_capital: form.include_in_capital,
      }
      if (!isPhysical) {
        payload.ticker = form.ticker.trim().toUpperCase()
      }
      await api.assets.update(asset.id, payload)
      onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка сохранения')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4 sticky top-0 bg-gray-900 z-10">
          <div>
            <h2 className="text-sm font-semibold text-white">Редактировать актив</h2>
            <p className="text-xs text-gray-500 mt-0.5">{ASSET_TYPE_LABELS[asset.asset_type]} · {asset.currency}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg leading-none">×</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">{error}</div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className={isPhysical ? 'col-span-2' : ''}>
              <Field label="Название *">
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => set('name', e.target.value)}
                  autoFocus
                  className={inputCls}
                />
              </Field>
            </div>
            {!isPhysical && (
              <Field label="Тикер *">
                <input
                  type="text"
                  value={form.ticker}
                  onChange={(e) => set('ticker', e.target.value.toUpperCase())}
                  className={inputCls}
                />
              </Field>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Валюта">
              <input
                type="text"
                maxLength={10}
                value={form.currency}
                onChange={(e) => set('currency', e.target.value.toUpperCase())}
                className={inputCls}
              />
            </Field>
            <Field label="Дата приобретения">
              <input
                type="date"
                value={form.acquisition_date}
                onChange={(e) => set('acquisition_date', e.target.value)}
                className={inputCls}
              />
            </Field>
          </div>

          <Field label="Оценочная стоимость">
            <input
              type="number"
              step="any"
              min="0"
              placeholder="Например: 2500000"
              value={form.estimated_value}
              onChange={(e) => set('estimated_value', e.target.value)}
              className={inputCls}
            />
            <p className="text-xs text-gray-600 mt-1">Используется для расчёта капитала (только RUB-активы)</p>
          </Field>

          <Field label="Комментарий">
            <input
              type="text"
              placeholder="Необязательно"
              value={form.note}
              onChange={(e) => set('note', e.target.value)}
              className={inputCls}
            />
          </Field>

          {/* Credit link section */}
          <div className="rounded-lg border border-gray-700/50 p-3 space-y-3">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.is_credit_linked}
                onChange={(e) => set('is_credit_linked', e.target.checked)}
                className="w-4 h-4 rounded accent-orange-500"
              />
              <span className="text-sm text-gray-300">Актив куплен в кредит / ипотеку</span>
            </label>
            {form.is_credit_linked && (
              <div className="space-y-3 pt-1">
                <div>
                  <label className={labelCls}>Вид кредита</label>
                  <select
                    value={form.credit_kind}
                    onChange={(e) => set('credit_kind', e.target.value)}
                    className={selectCls}
                  >
                    <option value="mortgage">Ипотека</option>
                    <option value="auto_loan">Автокредит</option>
                    <option value="consumer_loan">Потребкредит</option>
                    <option value="personal_loan">Личный займ</option>
                    <option value="other">Другое</option>
                  </select>
                </div>
                <Field label="Примечание по кредиту">
                  <input
                    type="text"
                    placeholder="Например: Сбер, ставка 9%, до 2032"
                    value={form.credit_note}
                    onChange={(e) => set('credit_note', e.target.value)}
                    className={inputCls}
                  />
                </Field>
              </div>
            )}
          </div>

          {/* include_in_capital */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={form.include_in_capital}
              onChange={(e) => set('include_in_capital', e.target.checked)}
              className="w-4 h-4 rounded accent-blue-500"
            />
            <span className="text-sm text-gray-300">Учитывать в расчёте капитала</span>
          </label>
          {!form.include_in_capital && (
            <p className="text-xs text-amber-400/80 -mt-2">
              Актив останется в системе и истории операций, но не будет учтён в итоговом капитале.
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Сохранение…' : 'Сохранить'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Create Deposit Modal ──────────────────────────────────────────────────────

interface CreateDepositModalProps {
  onClose: () => void
  onCreated: () => void
}

interface DepositFormState {
  name: string
  currency: string
  amount: string
  annual_rate_percent: string
  interest_start_date: string
  interest_end_date: string
  payout_frequency: string
  capitalization: boolean
  note: string
}

function CreateDepositModal({ onClose, onCreated }: CreateDepositModalProps) {
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState<DepositFormState>({
    name: '',
    currency: 'RUB',
    amount: '',
    annual_rate_percent: '',
    interest_start_date: today,
    interest_end_date: '',
    payout_frequency: 'monthly',
    capitalization: false,
    note: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof DepositFormState>(key: K, value: DepositFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!form.name.trim()) { setError('Укажите название вклада'); return }
    const amt = parseFloat(form.amount)
    if (!form.amount || isNaN(amt) || amt <= 0) { setError('Укажите сумму вклада'); return }
    if (!form.annual_rate_percent || parseFloat(form.annual_rate_percent) <= 0) {
      setError('Укажите процентную ставку'); return
    }
    if (!form.interest_start_date) { setError('Укажите дату начала'); return }
    if (!form.interest_end_date) { setError('Укажите дату окончания (обязательно для вклада)'); return }
    if (form.interest_end_date <= form.interest_start_date) {
      setError('Дата окончания должна быть позже даты начала'); return
    }

    setSubmitting(true)
    try {
      const account = await api.accounts.create({
        name: form.name.trim(),
        account_type: 'deposit',
        currency: form.currency,
      })
      await api.operations.create({
        account_id: account.id,
        operation_type: 'deposit',
        amount: form.amount,
        currency: form.currency,
        operated_at: new Date(form.interest_start_date).toISOString(),
        note: form.note.trim() || null,
      })
      await api.accounts.setInterestSettings(account.id, {
        is_interest_enabled: true,
        annual_rate_percent: form.annual_rate_percent,
        interest_start_date: form.interest_start_date,
        interest_end_date: form.interest_end_date,
        payout_frequency: form.payout_frequency,
        capitalization: form.capitalization,
      })
      onCreated()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при создании вклада')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-white">Создать вклад</h2>
            <p className="text-xs text-gray-500 mt-0.5">Банковский вклад с фиксированной ставкой</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>
        <div className="flex gap-0 divide-x divide-gray-800">
          <form onSubmit={handleSubmit} className="flex-1 p-5 space-y-4 min-w-0">
            {error && (
              <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">{error}</div>
            )}
            <Field label="Название вклада *">
              <input
                type="text"
                placeholder="Например: Вклад Сбер 18%"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                className={inputCls}
              />
            </Field>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Field label="Сумма вклада *">
                  <input type="number" step="any" min="0.01" placeholder="100 000" value={form.amount} onChange={(e) => set('amount', e.target.value)} className={inputCls} />
                </Field>
              </div>
              <Field label="Валюта">
                <input type="text" maxLength={10} placeholder="RUB" value={form.currency} onChange={(e) => set('currency', e.target.value.toUpperCase())} className={inputCls} />
              </Field>
            </div>
            <div className="px-3 py-2 rounded-lg bg-teal-950/40 border-l-2 border-teal-700/60">
              <p className="text-xs text-gray-500 mb-0.5">Период выплаты процентов</p>
              <p className="text-xs font-medium text-teal-400">{PAYOUT_FREQ_LABELS[form.payout_frequency] ?? form.payout_frequency}</p>
              <p className="text-xs text-gray-600 mt-0.5 leading-relaxed">Расчётная база: ежедневный остаток. Период выплаты определяет, когда проценты зачисляются.</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Ставка, % годовых *">
                <input type="number" step="0.01" min="0" placeholder="18.5" value={form.annual_rate_percent} onChange={(e) => set('annual_rate_percent', e.target.value)} className={inputCls} />
              </Field>
              <div>
                <label className={labelCls}>Период выплаты процентов</label>
                <select value={form.payout_frequency} onChange={(e) => set('payout_frequency', e.target.value)} className={selectCls}>
                  <option value="daily">Ежедневно</option>
                  <option value="monthly">Ежемесячно</option>
                  <option value="at_maturity">В конце срока</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Дата начала *">
                <input type="date" value={form.interest_start_date} onChange={(e) => set('interest_start_date', e.target.value)} className={inputCls} />
              </Field>
              <Field label="Дата окончания *">
                <input type="date" value={form.interest_end_date} onChange={(e) => set('interest_end_date', e.target.value)} className={inputCls} />
              </Field>
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={form.capitalization} onChange={(e) => set('capitalization', e.target.checked)} className="w-4 h-4 rounded accent-teal-500" />
              <span className="text-sm text-gray-300">Капитализация процентов</span>
            </label>
            <Field label="Комментарий">
              <input type="text" placeholder="Необязательно" value={form.note} onChange={(e) => set('note', e.target.value)} className={inputCls} />
            </Field>
            <div className="flex gap-2 pt-1">
              <button type="submit" disabled={submitting} className="flex-1 py-2 text-sm rounded-lg bg-sky-600 hover:bg-sky-700 text-white disabled:opacity-50 transition-colors">
                {submitting ? 'Создание…' : 'Создать вклад'}
              </button>
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">Отмена</button>
            </div>
          </form>
          <div className="w-52 shrink-0 p-5 space-y-3">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Обычно для вкладов в РФ</p>
            <ul className="space-y-2.5">
              {[
                'У вклада есть срок окончания',
                'Выплата процентов: ежемесячно или в конце срока',
                'Капитализация зависит от условий банка',
                'Пополнение и снятие зависят от условий',
                'Накопительный счёт считает проценты по ежедневному остатку',
              ].map((text) => (
                <li key={text} className="flex gap-2 text-xs text-gray-500 leading-relaxed">
                  <span className="mt-0.5 text-gray-600 shrink-0">·</span>
                  {text}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Edit Deposit Modal ────────────────────────────────────────────────────────

function EditDepositModal({
  deposit,
  onClose,
  onSaved,
}: {
  deposit: DepositSummary
  onClose: () => void
  onSaved: () => void
}) {
  const [accountName, setAccountName] = useState(deposit.name)
  const [form, setForm] = useState({
    annual_rate_percent: deposit.annual_rate_percent ?? '',
    payout_frequency: deposit.payout_frequency ?? 'monthly',
    capitalization: deposit.capitalization ?? false,
    interest_start_date: deposit.interest_start_date ?? new Date().toISOString().slice(0, 10),
    interest_end_date: deposit.interest_end_date ?? '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!accountName.trim()) { setError('Укажите название'); return }
    if (!form.annual_rate_percent || parseFloat(form.annual_rate_percent) <= 0) {
      setError('Укажите ставку'); return
    }
    if (!form.interest_start_date) { setError('Укажите дату начала'); return }
    if (!form.interest_end_date && deposit.account_type !== 'savings') {
      setError('Укажите дату окончания'); return
    }
    setSubmitting(true)
    try {
      // Save account name if changed
      if (accountName.trim() !== deposit.name) {
        await api.accounts.update(deposit.account_id, { name: accountName.trim() })
      }
      await api.accounts.setInterestSettings(deposit.account_id, {
        is_interest_enabled: true,
        annual_rate_percent: form.annual_rate_percent,
        interest_start_date: form.interest_start_date,
        interest_end_date: form.interest_end_date || null,
        payout_frequency: form.payout_frequency,
        capitalization: form.capitalization,
      } as Partial<import('@/lib/types').AccountInterestSettings>)
      onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка сохранения')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div>
            <h2 className="text-sm font-semibold text-white">Редактировать вклад</h2>
            <p className="text-xs text-gray-500 mt-0.5">{deposit.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">{error}</div>
          )}

          <Field label="Название *">
            <input
              type="text"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              className={inputCls}
            />
          </Field>

          <div className="rounded-lg bg-gray-800/50 px-3 py-2 text-xs text-gray-500 leading-relaxed">
            Сумма вклада и валюта определяются операциями и не редактируются здесь.
            Для изменений — добавьте или удалите операции.
          </div>

          <div className="px-3 py-2 rounded-lg bg-teal-950/40 border-l-2 border-teal-700/60">
            <p className="text-xs text-gray-500 mb-0.5">Период выплаты процентов</p>
            <p className="text-xs font-medium text-teal-400">{PAYOUT_FREQ_LABELS[form.payout_frequency] ?? form.payout_frequency}</p>
            <p className="text-xs text-gray-600 mt-0.5">Расчётная база: ежедневный остаток.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Ставка, % годовых *</label>
              <input type="number" step="0.01" min="0" placeholder="18.5" value={form.annual_rate_percent} onChange={(e) => setForm((f) => ({ ...f, annual_rate_percent: e.target.value }))} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Период выплаты</label>
              <select value={form.payout_frequency} onChange={(e) => setForm((f) => ({ ...f, payout_frequency: e.target.value }))} className={selectCls}>
                <option value="daily">Ежедневно</option>
                <option value="monthly">Ежемесячно</option>
                <option value="at_maturity">В конце срока</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Дата начала *</label>
              <input type="date" value={form.interest_start_date} onChange={(e) => setForm((f) => ({ ...f, interest_start_date: e.target.value }))} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>{deposit.account_type !== 'savings' ? 'Дата окончания *' : 'Дата окончания'}</label>
              <input type="date" value={form.interest_end_date} onChange={(e) => setForm((f) => ({ ...f, interest_end_date: e.target.value }))} className={inputCls} />
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={form.capitalization} onChange={(e) => setForm((f) => ({ ...f, capitalization: e.target.checked }))} className="w-4 h-4 rounded accent-teal-500" />
            <span className="text-sm text-gray-300">Капитализация процентов</span>
          </label>

          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={submitting} className="flex-1 py-2 text-sm rounded-lg bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50 transition-colors">
              {submitting ? 'Сохранение…' : 'Сохранить'}
            </button>
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">Отмена</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Deposits section ──────────────────────────────────────────────────────────

function DepositsSection({
  deposits,
  confirmDeleteDepositId,
  depositDeleteError,
  deletingDeposit,
  onCloseDeposit,
  onEditDeposit,
  onDeleteDeposit,
  onConfirmDeleteDeposit,
  onCancelDeleteDeposit,
}: {
  deposits: DepositSummary[]
  confirmDeleteDepositId: string | null
  depositDeleteError: string | null
  deletingDeposit: boolean
  onCloseDeposit: (d: DepositSummary) => void
  onEditDeposit: (d: DepositSummary) => void
  onDeleteDeposit: (accountId: string) => void
  onConfirmDeleteDeposit: (accountId: string) => void
  onCancelDeleteDeposit: () => void
}) {
  const today = new Date().toISOString().slice(0, 10)
  const PAYOUT_LABELS: Record<string, string> = {
    daily: 'ежедневно',
    monthly: 'ежемесячно',
    at_maturity: 'в конце срока',
  }

  if (deposits.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Вклады</h2>
        </div>
        <p className="p-5 text-sm text-gray-500">Нет активных вкладов. Нажмите «Создать вклад» чтобы добавить.</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Вклады</h2>
        <span className="text-xs text-gray-500">{deposits.length} шт.</span>
      </div>
      <div className="divide-y divide-gray-800/60">
        {deposits.map((d) => {
          const isExpired = d.interest_end_date != null && d.interest_end_date < today
          return (
            <div key={d.account_id} className={`px-5 py-4 flex flex-wrap items-start gap-x-8 gap-y-3 transition-colors ${isExpired ? 'bg-amber-950/10 hover:bg-amber-950/20' : 'hover:bg-gray-800/20'}`}>
              <div className="min-w-[160px]">
                <p className="font-medium text-sm text-white">{d.name}</p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className="inline-block px-2 py-0.5 rounded text-xs font-medium text-sky-400 bg-sky-900/30">
                    {d.account_type === 'savings' ? 'Накопительный' : 'Вклад'}
                  </span>
                  {isExpired && (
                    <span className="inline-block px-2 py-0.5 rounded text-xs font-medium text-amber-400 bg-amber-900/30">Истёк</span>
                  )}
                </div>
              </div>
              <div className="min-w-[110px]">
                <p className="text-xs text-gray-500 mb-0.5">Сумма</p>
                <p className="text-sm font-bold tabular-nums text-white">{fmt(d.principal)}</p>
                <p className="text-xs text-gray-600">{d.currency}</p>
              </div>
              {d.has_settings && (
                <div className="min-w-[90px]">
                  <p className="text-xs text-gray-500 mb-0.5">Ставка</p>
                  <p className="text-sm font-semibold text-teal-400">{d.annual_rate_percent}%</p>
                  <p className="text-xs text-gray-600">годовых</p>
                </div>
              )}
              {d.has_settings && (
                <div className="min-w-[130px]">
                  <p className="text-xs text-gray-500 mb-0.5">Срок</p>
                  <p className="text-xs text-gray-300">{fmtDate(d.interest_start_date)}</p>
                  {d.interest_end_date && (
                    <p className={`text-xs ${isExpired ? 'text-amber-400' : 'text-gray-400'}`}>— {fmtDate(d.interest_end_date)}</p>
                  )}
                  {d.payout_frequency && (
                    <p className="text-xs text-gray-600 mt-0.5">{PAYOUT_LABELS[d.payout_frequency] ?? d.payout_frequency}</p>
                  )}
                </div>
              )}
              {d.has_settings && (
                <div className="min-w-[110px]">
                  <p className="text-xs text-gray-500 mb-0.5">Начислено</p>
                  <p className="text-sm font-bold tabular-nums text-teal-400">{fmt(d.accrued_interest)}</p>
                  <p className="text-xs text-gray-600">{d.currency} на {fmtDate(d.as_of)}</p>
                </div>
              )}
              {!d.has_settings && (
                <p className="text-xs text-amber-400/70 self-center">Ставка не настроена</p>
              )}
              <div className="self-center ml-auto flex items-center gap-2 flex-wrap">
                {isExpired && (
                  <button onClick={() => onCloseDeposit(d)} className="px-3 py-1.5 text-xs rounded-lg bg-amber-700 hover:bg-amber-600 text-white transition-colors whitespace-nowrap">
                    Закрыть вклад
                  </button>
                )}
                <button
                  onClick={() => onEditDeposit(d)}
                  className="px-2 py-1 text-xs rounded bg-teal-900/40 text-teal-400 hover:bg-teal-900/70 transition-colors whitespace-nowrap"
                >
                  Редактировать вклад
                </button>
                {depositDeleteError && confirmDeleteDepositId === d.account_id && (
                  <span className="text-xs text-red-400">{depositDeleteError}</span>
                )}
                {confirmDeleteDepositId === d.account_id ? (
                  <span className="flex items-center gap-1.5">
                    <span className="text-xs text-gray-400">Удалить?</span>
                    <button onClick={() => onConfirmDeleteDeposit(d.account_id)} disabled={deletingDeposit} className="px-2 py-1 text-xs rounded bg-red-800/60 text-red-300 hover:bg-red-700/70 disabled:opacity-50 transition-colors">
                      {deletingDeposit ? '…' : 'Да'}
                    </button>
                    <button onClick={onCancelDeleteDeposit} className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors">Нет</button>
                  </span>
                ) : (
                  <button onClick={() => onDeleteDeposit(d.account_id)} className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-500 hover:bg-red-900/40 hover:text-red-400 transition-colors" title="Удалить вклад (только если нет операций)">✕</button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [deposits, setDeposits] = useState<DepositSummary[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [showDepositModal, setShowDepositModal] = useState(false)
  const [closingDeposit, setClosingDeposit] = useState<DepositSummary | null>(null)
  const [showExcluded, setShowExcluded] = useState(false)
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null)

  const [form, setForm] = useState({
    ticker: '',
    name: '',
    asset_type: 'stock' as AssetType,
    currency: 'RUB',
    estimated_value: '',
    include_in_capital: true,
  })
  const isPhysical = PHYSICAL_ASSET_TYPES.has(form.asset_type)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [editingDeposit, setEditingDeposit] = useState<DepositSummary | null>(null)
  const [confirmDeleteDepositId, setConfirmDeleteDepositId] = useState<string | null>(null)
  const [depositDeleteError, setDepositDeleteError] = useState<string | null>(null)
  const [deletingDeposit, setDeletingDeposit] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [assetsData, depositsData, accountsData] = await Promise.all([
        api.assets.list(),
        api.portfolio.deposits(),
        api.accounts.list(),
      ])
      setAssets(assetsData)
      setDeposits(depositsData)
      setAccounts(accountsData)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    const _isPhysical = PHYSICAL_ASSET_TYPES.has(form.asset_type)
    if (!_isPhysical && !form.ticker.trim()) { setFormError('Тикер обязателен для рыночных активов'); return }
    if (!form.name.trim()) { setFormError('Укажите название актива'); return }
    if (!form.currency.trim()) { setFormError('Укажите валюту'); return }

    setSubmitting(true)
    try {
      await api.assets.create({
        ticker: _isPhysical ? undefined : form.ticker.trim().toUpperCase(),
        name: form.name.trim(),
        asset_type: form.asset_type,
        currency: form.currency.trim().toUpperCase(),
        estimated_value: form.estimated_value !== '' ? form.estimated_value : undefined,
        include_in_capital: form.include_in_capital,
      })
      setForm({ ticker: '', name: '', asset_type: 'stock', currency: 'RUB', estimated_value: '', include_in_capital: true })
      setShowForm(false)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Ошибка создания актива')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDeleteAsset(id: string) {
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.assets.delete(id)
      setConfirmDeleteId(null)
      await load()
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : 'Ошибка удаления')
    } finally {
      setDeleting(false)
    }
  }

  async function handleDeleteDeposit(accountId: string) {
    setDeletingDeposit(true)
    setDepositDeleteError(null)
    try {
      await api.accounts.delete(accountId)
      setConfirmDeleteDepositId(null)
      await load()
    } catch (e) {
      setDepositDeleteError(e instanceof Error ? e.message : 'Ошибка удаления')
    } finally {
      setDeletingDeposit(false)
    }
  }

  // Split assets: included vs excluded from capital
  const includedAssets = assets.filter((a) => a.include_in_capital)
  const excludedAssets = assets.filter((a) => !a.include_in_capital)
  const visibleAssets = showExcluded ? assets : includedAssets

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {showDepositModal && (
        <CreateDepositModal onClose={() => setShowDepositModal(false)} onCreated={load} />
      )}
      {closingDeposit && (
        <DepositCloseModal
          deposit={closingDeposit}
          accounts={accounts}
          onClose={() => setClosingDeposit(null)}
          onSuccess={() => { setClosingDeposit(null); load() }}
        />
      )}
      {editingDeposit && (
        <EditDepositModal
          deposit={editingDeposit}
          onClose={() => setEditingDeposit(null)}
          onSaved={() => { setEditingDeposit(null); load() }}
        />
      )}
      {editingAsset && (
        <EditAssetModal
          asset={editingAsset}
          onClose={() => setEditingAsset(null)}
          onSaved={() => { setEditingAsset(null); load() }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-2xl font-bold">Активы</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setShowDepositModal(true)}
            className="px-3 py-1.5 text-sm rounded-lg bg-sky-700 hover:bg-sky-600 text-white transition-colors"
          >
            + Создать вклад
          </button>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          >
            {showForm ? 'Отмена' : '+ Новый актив'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/50 bg-red-900/20 p-4 text-red-400 text-sm">{error}</div>
      )}

      {/* Create asset form */}
      {showForm && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Новый актив</h2>
          {formError && (
            <div className="mb-4 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">{formError}</div>
          )}
          {isPhysical && (
            <div className="mb-4 rounded-lg border border-orange-800/30 bg-orange-950/15 px-3 py-2 text-xs text-orange-300">
              Для физических активов тикер не нужен — он будет сгенерирован автоматически.
            </div>
          )}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Field label="Тип *">
              <select
                value={form.asset_type}
                onChange={(e) => setForm((f) => ({ ...f, asset_type: e.target.value as AssetType, ticker: '' }))}
                className={selectCls}
              >
                {ASSET_TYPES.map((t) => (
                  <option key={t} value={t}>{ASSET_TYPE_LABELS[t] ?? t}</option>
                ))}
              </select>
            </Field>
            {!isPhysical && (
              <Field label="Тикер *">
                <input type="text" placeholder="Например: SBER" value={form.ticker} onChange={(e) => setForm((f) => ({ ...f, ticker: e.target.value.toUpperCase() }))} className={inputCls} />
              </Field>
            )}
            <Field label="Название *">
              <input type="text" placeholder={isPhysical ? 'Например: Toyota Camry 2020' : 'Например: Сбербанк'} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className={inputCls} />
            </Field>
            <Field label="Валюта *">
              <input type="text" maxLength={10} placeholder="RUB" value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))} className={inputCls} />
            </Field>
            {isPhysical && (
              <Field label="Оценочная стоимость">
                <input type="number" step="any" min="0" placeholder="Необязательно" value={form.estimated_value} onChange={(e) => setForm((f) => ({ ...f, estimated_value: e.target.value }))} className={inputCls} />
              </Field>
            )}
            <div className="sm:col-span-2 lg:col-span-4 flex items-center gap-4 pt-1 flex-wrap">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.include_in_capital}
                  onChange={(e) => setForm((f) => ({ ...f, include_in_capital: e.target.checked }))}
                  className="w-4 h-4 rounded accent-blue-500"
                />
                <span className="text-sm text-gray-300">Учитывать в расчёте капитала</span>
              </label>
              <button type="submit" disabled={submitting} className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors">
                {submitting ? 'Создание…' : 'Создать актив'}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setFormError(null) }} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Deposits section */}
      {loading ? null : (
        <DepositsSection
          deposits={deposits}
          confirmDeleteDepositId={confirmDeleteDepositId}
          depositDeleteError={depositDeleteError}
          deletingDeposit={deletingDeposit}
          onCloseDeposit={setClosingDeposit}
          onEditDeposit={setEditingDeposit}
          onDeleteDeposit={(id) => { setConfirmDeleteDepositId(id); setDepositDeleteError(null) }}
          onConfirmDeleteDeposit={handleDeleteDeposit}
          onCancelDeleteDeposit={() => { setConfirmDeleteDepositId(null); setDepositDeleteError(null) }}
        />
      )}

      {/* Assets table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Активы</h2>
            <span className="text-xs text-gray-500">{assets.length} шт.</span>
          </div>
          {excludedAssets.length > 0 && (
            <button
              onClick={() => setShowExcluded((v) => !v)}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              {showExcluded ? 'Скрыть неучитываемые' : `Показать неучитываемые (${excludedAssets.length})`}
            </button>
          )}
        </div>
        {deleteError && (
          <div className="mx-5 mt-3 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
            {deleteError}
            <button onClick={() => setDeleteError(null)} className="ml-2 text-red-300 hover:text-red-100">×</button>
          </div>
        )}
        {loading ? (
          <p className="p-5 text-sm text-gray-500">Загрузка…</p>
        ) : assets.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">Нет активов. Создайте актив или загрузите тестовые данные.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                <th className="text-left px-5 py-2">Тикер</th>
                <th className="text-left px-3 py-2">Название</th>
                <th className="text-left px-3 py-2">Тип</th>
                <th className="text-left px-3 py-2">Стоимость</th>
                <th className="text-left px-5 py-2">Валюта</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {visibleAssets.map((a) => {
                const _isPhys = PHYSICAL_ASSET_TYPES.has(a.asset_type)
                return (
                  <tr key={a.id} className={`hover:bg-gray-800/30 transition-colors ${!a.include_in_capital ? 'opacity-60' : ''}`}>
                    <td className="px-5 py-3 font-mono font-bold text-blue-400">
                      {_isPhys ? <span className="text-gray-600 font-normal text-xs italic">авто</span> : a.ticker}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-gray-200">{a.name}</span>
                        {!a.include_in_capital && (
                          <span className="inline-block px-1.5 py-0.5 rounded text-xs font-medium text-gray-500 bg-gray-800 border border-gray-700">Не учитывается</span>
                        )}
                        {a.is_credit_linked && (
                          <span className="inline-block px-1.5 py-0.5 rounded text-xs font-medium text-orange-400 bg-orange-900/30">
                            {CREDIT_KIND_LABELS[a.credit_kind ?? 'other'] ?? 'Кредит'}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[a.asset_type] ?? 'text-gray-400 bg-gray-800'}`}>
                        {ASSET_TYPE_LABELS[a.asset_type] ?? a.asset_type}
                      </span>
                    </td>
                    <td className="px-3 py-3 tabular-nums text-gray-300 text-xs">
                      {_isPhys && a.estimated_value ? fmt(a.estimated_value) : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-5 py-3 font-mono text-gray-300">{a.currency}</td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setEditingAsset(a)}
                          className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
                          title="Редактировать"
                        >
                          ✏
                        </button>
                        {confirmDeleteId === a.id ? (
                          <span className="flex items-center justify-end gap-1.5">
                            <span className="text-xs text-gray-400">Удалить?</span>
                            <button onClick={() => handleDeleteAsset(a.id)} disabled={deleting} className="px-2 py-1 text-xs rounded bg-red-800/60 text-red-300 hover:bg-red-700/70 disabled:opacity-50 transition-colors">
                              {deleting ? '…' : 'Да'}
                            </button>
                            <button onClick={() => { setConfirmDeleteId(null); setDeleteError(null) }} className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors">Нет</button>
                          </span>
                        ) : (
                          <button onClick={() => { setConfirmDeleteId(a.id); setDeleteError(null) }} className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-500 hover:bg-red-900/40 hover:text-red-400 transition-colors">✕</button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
