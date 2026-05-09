'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import TransferModal from '@/components/TransferModal'
import type { Account, Asset, CashBalance, Operation, OperationType } from '@/lib/types'
import { OPERATION_TYPES, incomeSourceLabel } from '@/lib/types'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(value: string | number) {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtQty(value: string | null) {
  if (!value) return '—'
  const n = parseFloat(value)
  if (isNaN(n)) return '—'
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 6 })
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function nowLocal() {
  const d = new Date()
  d.setSeconds(0, 0)
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

// ── label maps ────────────────────────────────────────────────────────────────

const OP_COLORS: Record<string, string> = {
  buy: 'text-green-400 bg-green-900/30',
  sell: 'text-red-400 bg-red-900/30',
  deposit: 'text-blue-400 bg-blue-900/30',
  withdraw: 'text-orange-400 bg-orange-900/30',
  dividend: 'text-emerald-400 bg-emerald-900/30',
  coupon: 'text-teal-400 bg-teal-900/30',
  fee: 'text-yellow-400 bg-yellow-900/30',
  tax: 'text-rose-400 bg-rose-900/30',
  manual_valuation: 'text-purple-400 bg-purple-900/30',
  expense: 'text-pink-400 bg-pink-900/30',
  transfer: 'text-indigo-400 bg-indigo-900/30',
}

const OP_LABELS: Record<string, string> = {
  buy: 'Покупка',
  sell: 'Продажа',
  deposit: 'Доход',
  withdraw: 'Вывод',
  dividend: 'Дивиденды',
  coupon: 'Купон',
  fee: 'Комиссия',
  tax: 'Налог',
  manual_valuation: 'Переоценка',
  expense: 'Расход',
  transfer: 'Перевод',
}

const EXPENSE_GROUP_LABELS: Record<string, string> = {
  living: 'На жизнь',
  investment: 'Инвест.',
  credit: 'Кредит',
}

// Editable operation types and their labels for the type dropdown
const OP_TYPE_DROPDOWN: OperationType[] = [
  'buy', 'sell', 'deposit', 'withdraw', 'dividend', 'coupon',
  'fee', 'tax', 'manual_valuation', 'expense', 'transfer',
]

function Badge({ type }: { type: string }) {
  const colors = OP_COLORS[type] ?? 'text-gray-400 bg-gray-800'
  const label = OP_LABELS[type] ?? type.replace('_', ' ')
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {label}
    </span>
  )
}

const REQUIRES_ASSET = new Set<OperationType>(['buy', 'sell', 'manual_valuation'])
const REQUIRES_QTY_PRICE = new Set<OperationType>(['buy', 'sell'])
const REQUIRES_PRICE = new Set<OperationType>(['buy', 'sell', 'manual_valuation'])
const IS_EXPENSE_TYPE = new Set<OperationType>(['expense'])

// ── form state ────────────────────────────────────────────────────────────────

interface GenericFormState {
  account_id: string
  asset_id: string
  operation_type: OperationType
  quantity: string
  price: string
  amount: string
  currency: string
  operated_at: string
  note: string
  // expense-specific
  expense_group: string
  expense_category: string
  merchant: string
}

const EMPTY_FORM: GenericFormState = {
  account_id: '',
  asset_id: '',
  operation_type: 'buy',
  quantity: '',
  price: '',
  amount: '',
  currency: 'RUB',
  operated_at: '',
  note: '',
  expense_group: 'living',
  expense_category: '',
  merchant: '',
}

interface TransferFormState {
  from_account_id: string
  to_account_id: string
  amount: string
  currency: string
  hasFee: boolean
  fee: string
  note: string
  operated_at: string
}

// ── main component ────────────────────────────────────────────────────────────

export default function OperationsPage() {
  const [operations, setOperations] = useState<Operation[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [cashBalances, setCashBalances] = useState<CashBalance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<GenericFormState>(() => ({ ...EMPTY_FORM, operated_at: nowLocal() }))
  const [transferForm, setTransferForm] = useState<TransferFormState>({
    from_account_id: '',
    to_account_id: '',
    amount: '',
    currency: 'RUB',
    hasFee: false,
    fee: '',
    note: '',
    operated_at: nowLocal(),
  })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [filterType, setFilterType] = useState('')
  const [filterAccount, setFilterAccount] = useState('')
  const [filterAsset, setFilterAsset] = useState('')

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [ndflOp, setNdflOp] = useState<Operation | null>(null)

  // Transfer modal (opened via "+ Перевод" button)
  const [showTransferModal, setShowTransferModal] = useState(false)
  const [transferSuccessMsg, setTransferSuccessMsg] = useState<string | null>(null)

  // Edit
  const [editOp, setEditOp] = useState<Operation | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ops, accs, asss, cash] = await Promise.all([
        api.operations.list(),
        api.accounts.list(),
        api.assets.list(),
        api.portfolio.cashBalances().catch(() => []),
      ])
      setOperations(ops)
      setAccounts(accs)
      setAssets(asss)
      setCashBalances(cash)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить данные')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // ── derived: computed amount for buy/sell ────────────────────────────────
  const computedAmount =
    REQUIRES_QTY_PRICE.has(form.operation_type) && form.quantity && form.price
      ? (parseFloat(form.quantity) * parseFloat(form.price)).toFixed(2)
      : null

  // ── filtering ────────────────────────────────────────────────────────────
  const filtered = operations.filter((op) => {
    if (filterType && op.operation_type !== filterType) return false
    if (filterAccount && op.account_id !== filterAccount) return false
    if (filterAsset && op.asset_id !== filterAsset) return false
    return true
  })

  // ── lookup maps ──────────────────────────────────────────────────────────
  const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a.name]))
  const assetMap = Object.fromEntries(assets.map((a) => [a.id, a.ticker]))
  const assetNameMap = Object.fromEntries(assets.map((a) => [a.id, a.name]))

  // ── transfer form helpers ────────────────────────────────────────────────
  const transferAvailable = parseFloat(
    cashBalances.find(
      (cb) => cb.account_id === transferForm.from_account_id && cb.currency === transferForm.currency
    )?.balance ?? '0'
  )
  const transferAmt = parseFloat(transferForm.amount) || 0
  const transferFeeAmt = transferForm.hasFee ? (parseFloat(transferForm.fee) || 0) : 0
  const transferRequired = transferAmt + transferFeeAmt
  const transferExceeds =
    transferForm.from_account_id !== '' &&
    transferRequired > transferAvailable &&
    transferRequired > 0

  // ── generic form submit ──────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)

    const op = form.operation_type
    if (!form.account_id) { setFormError('Выберите счёт'); return }
    if (REQUIRES_ASSET.has(op) && !form.asset_id) { setFormError('Выберите актив для ' + op); return }
    if (REQUIRES_QTY_PRICE.has(op)) {
      if (!form.quantity || parseFloat(form.quantity) <= 0) { setFormError('Введите количество'); return }
      if (!form.price || parseFloat(form.price) <= 0) { setFormError('Введите цену'); return }
    }
    if (REQUIRES_PRICE.has(op) && !REQUIRES_QTY_PRICE.has(op)) {
      if (!form.price || parseFloat(form.price) <= 0) { setFormError('Введите цену'); return }
    }
    if (!REQUIRES_QTY_PRICE.has(op) && !REQUIRES_PRICE.has(op)) {
      if (!form.amount) { setFormError('Введите сумму'); return }
    }
    if (op === 'expense' && !form.expense_group) { setFormError('Выберите тип расхода'); return }

    const operated_at = new Date(form.operated_at).toISOString()
    const payload: Record<string, unknown> = {
      account_id: form.account_id,
      operation_type: op,
      currency: form.currency,
      operated_at,
      note: form.note || null,
    }

    if (form.asset_id) payload.asset_id = form.asset_id

    if (REQUIRES_QTY_PRICE.has(op)) {
      payload.quantity = form.quantity
      payload.price = form.price
      payload.amount = computedAmount ?? '0'
    } else if (op === 'manual_valuation') {
      payload.price = form.price
      payload.amount = form.amount || form.price || '0'
    } else {
      payload.amount = form.amount || '0'
    }

    if (op === 'expense') {
      payload.expense_group = form.expense_group
      if (form.expense_category) payload.expense_category = form.expense_category
      if (form.merchant) payload.merchant = form.merchant
    }

    setSubmitting(true)
    try {
      const created = await api.operations.create(payload)
      setForm({ ...EMPTY_FORM, operated_at: nowLocal() })
      setShowForm(false)
      await load()
      if (op === 'sell') setNdflOp(created)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Ошибка при создании операции')
    } finally {
      setSubmitting(false)
    }
  }

  // ── inline transfer submit ────────────────────────────────────────────────
  async function handleTransferSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)

    if (!transferForm.from_account_id) { setFormError('Выберите счёт-источник'); return }
    if (!transferForm.to_account_id) { setFormError('Выберите счёт-получатель'); return }
    if (transferForm.from_account_id === transferForm.to_account_id) {
      setFormError('Откуда и куда должны быть разными счетами'); return
    }
    if (!transferForm.amount || transferAmt <= 0) { setFormError('Введите положительную сумму'); return }
    if (transferExceeds) {
      setFormError(`Недостаточно средств: доступно ${fmt(transferAvailable)} ${transferForm.currency}, нужно ${fmt(transferRequired)}`)
      return
    }

    setSubmitting(true)
    try {
      await api.operations.transfer({
        from_account_id: transferForm.from_account_id,
        to_account_id: transferForm.to_account_id,
        amount: transferForm.amount,
        currency: transferForm.currency,
        operated_at: new Date(transferForm.operated_at).toISOString(),
        fee: transferForm.hasFee && transferForm.fee ? transferForm.fee : null,
        note: transferForm.note.trim() || null,
      })
      setShowForm(false)
      setTransferForm({ from_account_id: '', to_account_id: '', amount: '', currency: 'RUB', hasFee: false, fee: '', note: '', operated_at: nowLocal() })
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Ошибка при создании перевода')
    } finally {
      setSubmitting(false)
    }
  }

  function setTf<K extends keyof TransferFormState>(key: K, value: TransferFormState[K]) {
    setTransferForm((f) => ({ ...f, [key]: value }))
  }

  function transferAccountLabel(a: Account) {
    const bal = cashBalances.find((cb) => cb.account_id === a.id && cb.currency === transferForm.currency)
    return `${a.name} · ${bal ? fmt(bal.balance) : '—'} ${transferForm.currency}`
  }

  // ── delete ───────────────────────────────────────────────────────────────
  async function handleDelete(id: string) {
    if (!confirm('Удалить операцию? Портфель будет пересчитан.')) return
    setDeletingId(id)
    try {
      await api.operations.delete(id)
      await load()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Ошибка удаления')
    } finally {
      setDeletingId(null)
    }
  }

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-6 max-w-6xl">
      {/* NDFL prompt */}
      {ndflOp && (
        <NdflModal
          sellOp={ndflOp}
          operations={operations}
          accounts={accounts}
          onClose={() => setNdflOp(null)}
          onSuccess={async () => { setNdflOp(null); await load() }}
        />
      )}

      {/* Edit modal */}
      {editOp && (
        <EditOperationModal
          op={editOp}
          accounts={accounts}
          assets={assets}
          cashBalances={cashBalances}
          onClose={() => setEditOp(null)}
          onSuccess={async () => { setEditOp(null); await load() }}
        />
      )}

      {/* Transfer modal (from "+ Перевод" button) */}
      {showTransferModal && (
        <TransferModal
          accounts={accounts}
          cashBalances={cashBalances}
          onClose={() => setShowTransferModal(false)}
          onSuccess={() => {
            setShowTransferModal(false)
            setTransferSuccessMsg('Перевод сохранён.')
            load()
            setTimeout(() => setTransferSuccessMsg(null), 4000)
          }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">Операции</h1>
        <div className="flex gap-2 flex-wrap items-center">
          {transferSuccessMsg && (
            <span className="text-xs text-indigo-400 bg-indigo-900/20 border border-indigo-800/40 px-3 py-1.5 rounded-lg">
              {transferSuccessMsg}
            </span>
          )}
          <button
            onClick={() => { setShowTransferModal(true) }}
            className="px-3 py-1.5 text-sm rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white transition-colors"
          >
            + Перевод
          </button>
          <button
            onClick={() => { setShowForm((v) => !v); setFormError(null) }}
            className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          >
            {showForm ? 'Отмена' : '+ Новая операция'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/50 bg-red-900/20 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Create form */}
      {showForm && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
              Новая операция
            </h2>
            {/* Type selector always visible */}
            <select
              value={form.operation_type}
              onChange={(e) => setForm((f) => ({
                ...EMPTY_FORM,
                operated_at: f.operated_at,
                account_id: f.account_id,
                currency: f.currency,
                operation_type: e.target.value as OperationType,
              }))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
            >
              {OP_TYPE_DROPDOWN.map((t) => (
                <option key={t} value={t}>{OP_LABELS[t] ?? t}</option>
              ))}
            </select>
          </div>

          {formError && (
            <div className="mb-4 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {formError}
            </div>
          )}

          {/* Transfer inline form */}
          {form.operation_type === 'transfer' ? (
            <form onSubmit={handleTransferSubmit} className="space-y-4">
              <p className="text-xs text-indigo-400/80 bg-indigo-950/20 border border-indigo-800/30 rounded-lg px-3 py-2">
                Перевод не является доходом или расходом. Только комиссия уменьшает общий капитал.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Откуда *">
                  <select
                    value={transferForm.from_account_id}
                    onChange={(e) => {
                      setTf('from_account_id', e.target.value)
                      if (e.target.value === transferForm.to_account_id) setTf('to_account_id', '')
                    }}
                    className={selectCls}
                  >
                    <option value="">— выберите счёт —</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>{transferAccountLabel(a)}</option>
                    ))}
                  </select>
                  {transferForm.from_account_id && (
                    <p className={`text-xs mt-1 ${transferAvailable <= 0 ? 'text-red-400' : 'text-gray-500'}`}>
                      Доступно: {fmt(transferAvailable)} {transferForm.currency}
                    </p>
                  )}
                </Field>
                <Field label="Куда *">
                  <select
                    value={transferForm.to_account_id}
                    onChange={(e) => setTf('to_account_id', e.target.value)}
                    className={selectCls}
                  >
                    <option value="">— выберите счёт —</option>
                    {accounts.filter((a) => a.id !== transferForm.from_account_id).map((a) => (
                      <option key={a.id} value={a.id}>{transferAccountLabel(a)}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Сумма *">
                  <input
                    type="number"
                    step="any"
                    min="0.01"
                    placeholder="Например, 50 000"
                    value={transferForm.amount}
                    onChange={(e) => setTf('amount', e.target.value)}
                    className={`${inputCls} ${transferExceeds ? 'border-red-600' : ''}`}
                  />
                  {transferExceeds && (
                    <p className="text-xs text-red-400 mt-1">Превышает доступный остаток</p>
                  )}
                </Field>
                <Field label="Валюта">
                  <input
                    type="text"
                    maxLength={10}
                    placeholder="RUB"
                    value={transferForm.currency}
                    onChange={(e) => setTf('currency', e.target.value.toUpperCase())}
                    className={inputCls}
                  />
                </Field>
                <Field label="Дата и время *">
                  <input
                    type="datetime-local"
                    value={transferForm.operated_at}
                    onChange={(e) => setTf('operated_at', e.target.value)}
                    className={inputCls}
                  />
                </Field>
                <Field label="Комментарий">
                  <input
                    type="text"
                    placeholder="Необязательно"
                    value={transferForm.note}
                    onChange={(e) => setTf('note', e.target.value)}
                    className={inputCls}
                  />
                </Field>
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={transferForm.hasFee}
                    onChange={(e) => { setTf('hasFee', e.target.checked); if (!e.target.checked) setTf('fee', '') }}
                    className="w-3.5 h-3.5 accent-indigo-500"
                  />
                  <span className="text-xs text-gray-300">Есть комиссия за перевод</span>
                </label>
                {transferForm.hasFee && (
                  <input
                    type="number"
                    step="any"
                    min="0"
                    placeholder="Например, 50"
                    value={transferForm.fee}
                    onChange={(e) => setTf('fee', e.target.value)}
                    className={inputCls}
                  />
                )}
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={submitting || transferExceeds}
                  className="px-4 py-2 text-sm rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white disabled:opacity-50 transition-colors"
                >
                  {submitting ? 'Сохраняю…' : 'Создать перевод'}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setFormError(null) }}
                  className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                >
                  Отмена
                </button>
              </div>
            </form>
          ) : (
            /* Generic form for all other operation types */
            <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Account */}
              <Field label="Счёт *">
                <select
                  value={form.account_id}
                  onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))}
                  className={selectCls}
                >
                  <option value="">— выберите счёт —</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </Field>

              {/* Asset */}
              <Field label={`Актив${REQUIRES_ASSET.has(form.operation_type) ? ' *' : ''}`}>
                <select
                  value={form.asset_id}
                  onChange={(e) => setForm((f) => ({ ...f, asset_id: e.target.value }))}
                  className={selectCls}
                >
                  <option value="">— нет —</option>
                  {assets.map((a) => (
                    <option key={a.id} value={a.id}>{a.ticker} — {a.name}</option>
                  ))}
                </select>
              </Field>

              {/* Expense group (for expense type) */}
              {IS_EXPENSE_TYPE.has(form.operation_type) && (
                <Field label="Тип расхода *">
                  <select
                    value={form.expense_group}
                    onChange={(e) => setForm((f) => ({ ...f, expense_group: e.target.value }))}
                    className={selectCls}
                  >
                    <option value="living">Повседневные расходы</option>
                    <option value="investment">Инвестиционные расходы</option>
                    <option value="credit">Кредитный платёж</option>
                  </select>
                </Field>
              )}

              {/* Quantity (buy/sell only) */}
              {REQUIRES_QTY_PRICE.has(form.operation_type) && (
                <Field label="Количество *">
                  <input
                    type="number"
                    step="any"
                    min="0"
                    placeholder="Например, 10"
                    value={form.quantity}
                    onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                    className={inputCls}
                  />
                </Field>
              )}

              {/* Price (buy/sell/manual_valuation) */}
              {REQUIRES_PRICE.has(form.operation_type) && (
                <Field label="Цена *">
                  <input
                    type="number"
                    step="any"
                    min="0"
                    placeholder="Например, 280.50"
                    value={form.price}
                    onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                    className={inputCls}
                  />
                </Field>
              )}

              {/* Amount */}
              {REQUIRES_QTY_PRICE.has(form.operation_type) ? (
                <Field label="Сумма (вычислено)">
                  <input
                    type="text"
                    readOnly
                    value={computedAmount ?? ''}
                    className={`${inputCls} opacity-50 cursor-default`}
                  />
                </Field>
              ) : (
                <Field label={`Сумма${!REQUIRES_PRICE.has(form.operation_type) ? ' *' : ''}`}>
                  <input
                    type="number"
                    step="any"
                    min="0"
                    placeholder="Например, 1000"
                    value={form.amount}
                    onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                    className={inputCls}
                  />
                </Field>
              )}

              {/* Expense category + merchant */}
              {IS_EXPENSE_TYPE.has(form.operation_type) && (
                <>
                  <Field label="Категория">
                    <input
                      type="text"
                      placeholder="Напр., продукты"
                      value={form.expense_category}
                      onChange={(e) => setForm((f) => ({ ...f, expense_category: e.target.value }))}
                      className={inputCls}
                    />
                  </Field>
                  <Field label="Магазин / получатель">
                    <input
                      type="text"
                      placeholder="Необязательно"
                      value={form.merchant}
                      onChange={(e) => setForm((f) => ({ ...f, merchant: e.target.value }))}
                      className={inputCls}
                    />
                  </Field>
                </>
              )}

              {/* Currency */}
              <Field label="Валюта">
                <input
                  type="text"
                  maxLength={10}
                  placeholder="RUB"
                  value={form.currency}
                  onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                  className={inputCls}
                />
              </Field>

              {/* Date/time */}
              <Field label="Дата и время *">
                <input
                  type="datetime-local"
                  value={form.operated_at}
                  onChange={(e) => setForm((f) => ({ ...f, operated_at: e.target.value }))}
                  className={inputCls}
                />
              </Field>

              {/* Note */}
              <Field label="Комментарий">
                <input
                  type="text"
                  placeholder="Необязательно"
                  value={form.note}
                  onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                  className={inputCls}
                />
              </Field>

              {/* Submit */}
              <div className="sm:col-span-2 lg:col-span-3 flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
                >
                  {submitting ? 'Сохраняю…' : 'Создать операцию'}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setFormError(null) }}
                  className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                >
                  Отмена
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className={labelCls}>Тип операции</label>
            <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className={selectCls}>
              <option value="">Все типы</option>
              {OPERATION_TYPES.map((t) => (
                <option key={t} value={t}>{OP_LABELS[t] ?? t.replace('_', ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Счёт</label>
            <select value={filterAccount} onChange={(e) => setFilterAccount(e.target.value)} className={selectCls}>
              <option value="">Все счета</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Актив</label>
            <select value={filterAsset} onChange={(e) => setFilterAsset(e.target.value)} className={selectCls}>
              <option value="">Все активы</option>
              {assets.map((a) => (
                <option key={a.id} value={a.id}>{a.ticker}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Операции</h2>
          <span className="text-xs text-gray-500">{filtered.length} шт.</span>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-gray-500">Загрузка…</p>
        ) : filtered.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">Операций не найдено. Создайте первую операцию или загрузите тестовые данные.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                  <th className="text-left px-5 py-2">Дата</th>
                  <th className="text-left px-3 py-2">Тип</th>
                  <th className="text-left px-3 py-2">Счёт / откуда→куда</th>
                  <th className="text-left px-3 py-2">Актив / детали</th>
                  <th className="text-right px-3 py-2">Кол-во</th>
                  <th className="text-right px-3 py-2">Цена</th>
                  <th className="text-right px-3 py-2">Комис.</th>
                  <th className="text-right px-3 py-2">Сумма</th>
                  <th className="text-right px-5 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {filtered.map((op) => (
                  <tr key={op.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-5 py-2.5 text-gray-400 whitespace-nowrap text-xs">{fmtDate(op.operated_at)}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Badge type={op.operation_type} />
                        {op.operation_type === 'expense' && op.expense_group && (
                          <span className="text-xs text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">
                            {EXPENSE_GROUP_LABELS[op.expense_group] ?? op.expense_group}
                          </span>
                        )}
                      </div>
                      {op.operation_type === 'deposit' && op.income_source && (
                        <p className="text-xs text-gray-500 mt-0.5 leading-none">
                          {incomeSourceLabel(op.income_source)}
                          {op.income_source === 'other' && op.note ? `: ${op.note}` : ''}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-gray-300 text-xs">
                      {op.operation_type === 'transfer' ? (
                        <span className="text-indigo-300 whitespace-nowrap">
                          {accountMap[op.account_id] ?? '…'}
                          <span className="text-gray-500"> → </span>
                          {op.to_account_id ? (accountMap[op.to_account_id] ?? op.to_account_id.slice(0, 8)) : '—'}
                        </span>
                      ) : (
                        accountMap[op.account_id] ?? '—'
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs">
                      {op.operation_type === 'transfer' ? (
                        <span className="text-gray-600">—</span>
                      ) : op.operation_type === 'expense' ? (
                        <span className="text-gray-300">
                          {op.expense_category || '—'}
                          {op.merchant ? <span className="text-gray-500"> · {op.merchant}</span> : null}
                          {/* Credit payment linked asset */}
                          {op.expense_group === 'credit' && op.linked_asset_id && (
                            <span className="block text-orange-400 mt-0.5">
                              🔗 {assetNameMap[op.linked_asset_id] ?? '…'}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="font-mono text-blue-400">
                          {op.asset_id ? (assetMap[op.asset_id] ?? '—') : '—'}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-gray-300">{fmtQty(op.quantity)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-gray-300">{op.price ? fmt(op.price) : '—'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{op.fee ? fmt(op.fee) : '—'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-medium">{fmt(op.amount)}</td>
                    <td className="px-5 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setEditOp(op)}
                          className="text-xs text-gray-500 hover:text-blue-400 transition-colors"
                        >
                          Изм.
                        </button>
                        <button
                          onClick={() => handleDelete(op.id)}
                          disabled={deletingId === op.id}
                          className="text-xs text-gray-500 hover:text-red-400 disabled:opacity-40 transition-colors"
                        >
                          {deletingId === op.id ? '…' : 'Удал.'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── small shared styles ───────────────────────────────────────────────────────

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

// ── EditOperationModal ────────────────────────────────────────────────────────

function EditOperationModal({
  op,
  accounts,
  assets,
  cashBalances,
  onClose,
  onSuccess,
}: {
  op: Operation
  accounts: Account[]
  assets: Asset[]
  cashBalances: CashBalance[]
  onClose: () => void
  onSuccess: () => void
}) {
  const isBuySell = op.operation_type === 'buy' || op.operation_type === 'sell'

  // Physical assets for credit payment link selector
  const PHYSICAL_TYPES = new Set(['real_estate', 'vehicle', 'other_physical', 'other'])
  const physicalAssets = assets.filter((a) => PHYSICAL_TYPES.has(a.asset_type))

  function toLocalDT(iso: string) {
    const d = new Date(iso)
    const offset = d.getTimezoneOffset() * 60000
    return new Date(d.getTime() - offset).toISOString().slice(0, 16)
  }

  // ── transfer edit state ──
  const [tAmount, setTAmount] = useState(String(op.amount))
  const [tFee, setTFee] = useState(op.fee ? String(op.fee) : '')
  const [tHasFee, setTHasFee] = useState(!!op.fee)
  const [tNote, setTNote] = useState(op.note ?? '')
  const [tDate, setTDate] = useState(toLocalDT(op.operated_at))

  // Transfer: compute available after reversing current effect
  const oldFee = parseFloat(op.fee ?? '0')
  const sourceKey = cashBalances.find(
    (cb) => cb.account_id === op.account_id && cb.currency === op.currency
  )
  const rawAvailable = parseFloat(sourceKey?.balance ?? '0')
  const tAvailable = rawAvailable + parseFloat(op.amount) + oldFee
  const tAmt = parseFloat(tAmount) || 0
  const tFeeAmt = tHasFee ? (parseFloat(tFee) || 0) : 0
  const tExceeds = tAmt + tFeeAmt > tAvailable && tAmt + tFeeAmt > 0

  // ── generic/expense edit state ──
  const [amount, setAmount] = useState(String(op.amount))
  const [fee, setFee] = useState(op.fee ? String(op.fee) : '')
  const [hasFee, setHasFee] = useState(!!op.fee)
  const [note, setNote] = useState(op.note ?? '')
  const [date, setDate] = useState(toLocalDT(op.operated_at))
  const [currency, setCurrency] = useState(op.currency)
  // expense-specific
  const [expenseGroup, setExpenseGroup] = useState(op.expense_group ?? 'living')
  const [expenseCategory, setExpenseCategory] = useState(op.expense_category ?? '')
  const [merchant, setMerchant] = useState(op.merchant ?? '')
  const [principalAmount, setPrincipalAmount] = useState(op.principal_amount ? String(op.principal_amount) : '')
  const [interestAmount, setInterestAmount] = useState(op.interest_amount ? String(op.interest_amount) : '')
  const [liabilityName, setLiabilityName] = useState(op.liability_name ?? '')
  const [linkedAssetId, setLinkedAssetId] = useState(op.linked_asset_id ?? '')
  const [incomeSource, setIncomeSource] = useState(op.income_source ?? '')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleTransferUpdate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!tAmount || parseFloat(tAmount) <= 0) { setError('Введите положительную сумму'); return }
    if (tExceeds) { setError('Недостаточно средств на счёте-источнике'); return }

    const payload: Record<string, unknown> = {
      amount: tAmount,
      operated_at: new Date(tDate).toISOString(),
      note: tNote.trim() || null,
    }
    if (tHasFee && tFee) payload.fee = tFee
    else if (!tHasFee) payload.fee = null

    setSubmitting(true)
    try {
      await api.operations.updateTransfer(op.id, payload)
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при сохранении')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleGenericUpdate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!amount || parseFloat(amount) <= 0) { setError('Введите положительную сумму'); return }

    const payload: Record<string, unknown> = {
      amount,
      currency,
      operated_at: new Date(date).toISOString(),
      note: note.trim() || null,
    }
    if (hasFee && fee) payload.fee = fee
    else if (!hasFee) payload.fee = null

    if (op.operation_type === 'deposit') {
      payload.income_source = incomeSource || null
    }

    if (op.operation_type === 'expense') {
      payload.expense_group = expenseGroup
      payload.expense_category = expenseCategory.trim() || null
      payload.merchant = merchant.trim() || null
      if (principalAmount) payload.principal_amount = principalAmount
      if (interestAmount) payload.interest_amount = interestAmount
      payload.liability_name = liabilityName.trim() || null
      payload.linked_asset_id = linkedAssetId || null
    }

    setSubmitting(true)
    try {
      await api.operations.update(op.id, payload)
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при сохранении')
    } finally {
      setSubmitting(false)
    }
  }

  const title = OP_LABELS[op.operation_type] ?? op.operation_type
  const accountName = accounts.find((a) => a.id === op.account_id)?.name ?? '—'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 sticky top-0 bg-gray-900">
          <div>
            <h2 className="text-base font-semibold text-white">Изменить операцию</h2>
            <p className="text-xs text-gray-500 mt-0.5">{title} · {accountName}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        <div className="p-5">
          {error && (
            <div className="mb-4 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* buy/sell: not editable */}
          {isBuySell && (
            <div className="space-y-4">
              <div className="rounded-lg border border-amber-800/30 bg-amber-950/20 p-3">
                <p className="text-sm text-amber-400 font-medium mb-1">Редактирование недоступно</p>
                <p className="text-xs text-gray-400 leading-relaxed">
                  Покупки и продажи нельзя редактировать напрямую — это затрагивает FIFO-себестоимость и НДФЛ.
                  Удалите операцию и создайте заново.
                </p>
              </div>
              {/* TODO: buy/sell edit — implement when cost basis recalculation is designed */}
              <button
                onClick={onClose}
                className="w-full px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
              >
                Закрыть
              </button>
            </div>
          )}

          {/* transfer: edit amount, fee, date, note */}
          {op.operation_type === 'transfer' && (
            <form onSubmit={handleTransferUpdate} className="space-y-4">
              <p className="text-xs text-gray-500 bg-gray-800/50 rounded-lg px-3 py-2">
                Счета перевода нельзя изменить. Удалите и создайте заново для смены счетов.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Счёт-источник">
                  <input
                    type="text"
                    readOnly
                    value={accounts.find((a) => a.id === op.account_id)?.name ?? '—'}
                    className={`${inputCls} opacity-50 cursor-default`}
                  />
                </Field>
                <Field label="Счёт-получатель">
                  <input
                    type="text"
                    readOnly
                    value={accounts.find((a) => a.id === op.to_account_id)?.name ?? '—'}
                    className={`${inputCls} opacity-50 cursor-default`}
                  />
                </Field>
              </div>
              <Field label="Сумма *">
                <input
                  type="number"
                  step="any"
                  min="0.01"
                  value={tAmount}
                  onChange={(e) => setTAmount(e.target.value)}
                  className={`${inputCls} ${tExceeds ? 'border-red-600' : ''}`}
                />
                {tExceeds && <p className="text-xs text-red-400 mt-1">Превышает доступный остаток</p>}
                <p className="text-xs text-gray-600 mt-1">Доступно (после отмены текущего перевода): {fmt(tAvailable)} {op.currency}</p>
              </Field>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={tHasFee}
                    onChange={(e) => { setTHasFee(e.target.checked); if (!e.target.checked) setTFee('') }}
                    className="w-3.5 h-3.5 accent-indigo-500"
                  />
                  <span className="text-xs text-gray-300">Есть комиссия</span>
                </label>
                {tHasFee && (
                  <input type="number" step="any" min="0" placeholder="Комиссия" value={tFee} onChange={(e) => setTFee(e.target.value)} className={inputCls} />
                )}
              </div>
              <Field label="Дата и время">
                <input type="datetime-local" value={tDate} onChange={(e) => setTDate(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Комментарий">
                <input type="text" placeholder="Необязательно" value={tNote} onChange={(e) => setTNote(e.target.value)} className={inputCls} />
              </Field>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={submitting || tExceeds} className="flex-1 px-4 py-2 text-sm rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white disabled:opacity-50 transition-colors">
                  {submitting ? 'Сохраняю…' : 'Сохранить'}
                </button>
                <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">Отмена</button>
              </div>
            </form>
          )}

          {/* expense: full expense edit */}
          {op.operation_type === 'expense' && (
            <form onSubmit={handleGenericUpdate} className="space-y-4">
              <Field label="Тип расхода *">
                <select value={expenseGroup} onChange={(e) => setExpenseGroup(e.target.value as 'living' | 'investment' | 'credit')} className={selectCls}>
                  <option value="living">Повседневные расходы</option>
                  <option value="investment">Инвестиционные расходы</option>
                  <option value="credit">Кредитный платёж</option>
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Сумма *">
                  <input type="number" step="any" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputCls} />
                </Field>
                <Field label="Валюта">
                  <input type="text" maxLength={10} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} className={inputCls} />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Категория">
                  <input type="text" placeholder="Напр., продукты" value={expenseCategory} onChange={(e) => setExpenseCategory(e.target.value)} className={inputCls} />
                </Field>
                <Field label="Магазин / получатель">
                  <input type="text" placeholder="Необязательно" value={merchant} onChange={(e) => setMerchant(e.target.value)} className={inputCls} />
                </Field>
              </div>
              {expenseGroup === 'credit' && (
                <div className="space-y-3 rounded-lg border border-orange-800/30 bg-orange-950/10 p-3">
                  <p className="text-xs text-orange-400/80">Разбивка и связь с активом (кредит)</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Тело долга">
                      <input type="number" step="any" min="0" placeholder="Необязательно" value={principalAmount} onChange={(e) => setPrincipalAmount(e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Проценты">
                      <input type="number" step="any" min="0" placeholder="Необязательно" value={interestAmount} onChange={(e) => setInterestAmount(e.target.value)} className={inputCls} />
                    </Field>
                  </div>
                  <Field label="Название кредита">
                    <input type="text" placeholder="Напр., Ипотека Сбер" value={liabilityName} onChange={(e) => setLiabilityName(e.target.value)} className={inputCls} />
                  </Field>
                  <Field label="Связанный актив (необязательно)">
                    <select value={linkedAssetId} onChange={(e) => setLinkedAssetId(e.target.value)} className={selectCls}>
                      <option value="">— нет —</option>
                      {physicalAssets.map((a) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                      ))}
                    </select>
                  </Field>
                </div>
              )}
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input type="checkbox" checked={hasFee} onChange={(e) => { setHasFee(e.target.checked); if (!e.target.checked) setFee('') }} className="w-3.5 h-3.5 accent-blue-500" />
                  <span className="text-xs text-gray-300">Есть комиссия</span>
                </label>
                {hasFee && <input type="number" step="any" min="0" placeholder="Комиссия" value={fee} onChange={(e) => setFee(e.target.value)} className={inputCls} />}
              </div>
              <Field label="Комментарий">
                <input type="text" placeholder="Необязательно" value={note} onChange={(e) => setNote(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Дата и время">
                <input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
              </Field>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={submitting} className="flex-1 px-4 py-2 text-sm rounded-lg bg-pink-800 hover:bg-pink-700 text-white disabled:opacity-50 transition-colors">
                  {submitting ? 'Сохраняю…' : 'Сохранить'}
                </button>
                <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">Отмена</button>
              </div>
            </form>
          )}

          {/* other non-buy/sell/transfer/expense: simple edit */}
          {!isBuySell && op.operation_type !== 'transfer' && op.operation_type !== 'expense' && (
            <form onSubmit={handleGenericUpdate} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Сумма *">
                  <input type="number" step="any" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputCls} />
                </Field>
                <Field label="Валюта">
                  <input type="text" maxLength={10} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} className={inputCls} />
                </Field>
              </div>
              {op.operation_type === 'deposit' && (
                <Field label="Источник дохода">
                  <input type="text" placeholder="salary, bonus, interest…" value={incomeSource} onChange={(e) => setIncomeSource(e.target.value)} className={inputCls} />
                </Field>
              )}
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input type="checkbox" checked={hasFee} onChange={(e) => { setHasFee(e.target.checked); if (!e.target.checked) setFee('') }} className="w-3.5 h-3.5 accent-blue-500" />
                  <span className="text-xs text-gray-300">Есть комиссия</span>
                </label>
                {hasFee && <input type="number" step="any" min="0" value={fee} onChange={(e) => setFee(e.target.value)} className={inputCls} />}
              </div>
              <Field label="Дата и время">
                <input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Комментарий">
                <input type="text" placeholder="Необязательно" value={note} onChange={(e) => setNote(e.target.value)} className={inputCls} />
              </Field>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={submitting} className="flex-1 px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors">
                  {submitting ? 'Сохраняю…' : 'Сохранить'}
                </button>
                <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">Отмена</button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

// ── NDFL helpers ─────────────────────────────────────────────────────────────

function computeFifoCostBasis(ops: Operation[], sellOp: Operation): number | null {
  const assetId = sellOp.asset_id
  const sellQty = parseFloat(sellOp.quantity ?? '0')
  if (!assetId || sellQty <= 0) return null

  const relevant = ops
    .filter((op) =>
      op.asset_id === assetId &&
      op.status === 'confirmed' &&
      (op.operation_type === 'buy' || op.operation_type === 'sell')
    )
    .sort((a, b) => {
      const ta = new Date(a.operated_at).getTime()
      const tb = new Date(b.operated_at).getTime()
      if (ta !== tb) return ta - tb
      return a.created_at < b.created_at ? -1 : 1
    })

  const fifo: { qty: number; price: number }[] = []
  for (const op of relevant) {
    if (op.id === sellOp.id) break
    const qty = parseFloat(op.quantity ?? '0')
    const price = parseFloat(op.price ?? '0')
    if (qty <= 0) continue
    if (op.operation_type === 'buy' && price > 0) {
      fifo.push({ qty, price })
    } else if (op.operation_type === 'sell') {
      let rem = qty
      while (rem > 1e-9 && fifo.length > 0) {
        if (fifo[0].qty <= rem + 1e-9) {
          rem -= fifo[0].qty
          fifo.shift()
        } else {
          fifo[0].qty -= rem
          rem = 0
        }
      }
    }
  }

  let costBasis = 0
  let rem = sellQty
  for (const lot of fifo) {
    if (rem <= 1e-9) break
    const take = Math.min(lot.qty, rem)
    costBasis += take * lot.price
    rem -= take
  }

  if (rem > 1e-9) return null
  return costBasis
}

// ── NDFL Modal ────────────────────────────────────────────────────────────────

function NdflModal({
  sellOp,
  operations,
  accounts,
  onClose,
  onSuccess,
}: {
  sellOp: Operation
  operations: Operation[]
  accounts: Account[]
  onClose: () => void
  onSuccess: () => void
}) {
  const costBasis = computeFifoCostBasis(operations, sellOp)
  const proceeds = parseFloat(sellOp.amount)
  const sellFee = parseFloat(sellOp.fee ?? '0')
  const costBasisAvailable = costBasis !== null
  const defaultNdfl = costBasisAvailable
    ? (Math.max(proceeds - costBasis! - sellFee, 0) * 0.13).toFixed(2)
    : '0'

  const [amount, setAmount] = useState(defaultNdfl)
  const [accountId, setAccountId] = useState(sellOp.account_id)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setError(null)
    const amt = parseFloat(amount)
    if (isNaN(amt) || amt <= 0) { setError('Введите положительную сумму'); return }

    setSubmitting(true)
    try {
      await api.operations.create({
        account_id: accountId,
        operation_type: 'tax',
        amount,
        currency: sellOp.currency,
        operated_at: sellOp.operated_at,
        note: 'НДФЛ с продажи',
      })
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при сохранении')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-white">Записать НДФЛ?</h2>
            <p className="text-xs text-gray-400 mt-1">
              Продажа на {parseFloat(sellOp.amount).toLocaleString('ru-RU', { minimumFractionDigits: 2 })} {sellOp.currency}.
              {costBasisAvailable && costBasis !== null && (
                <> Себестоимость FIFO: {costBasis.toLocaleString('ru-RU', { minimumFractionDigits: 2 })}.</>
              )}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none shrink-0">✕</button>
        </div>

        {costBasisAvailable ? (
          <div className="rounded-lg bg-gray-800/50 p-3 space-y-1 text-xs text-gray-400">
            <div className="flex justify-between">
              <span>Выручка</span>
              <span className="tabular-nums text-white">{fmt(proceeds)}</span>
            </div>
            <div className="flex justify-between">
              <span>Себестоимость (FIFO)</span>
              <span className="tabular-nums text-gray-300">− {fmt(costBasis!)}</span>
            </div>
            {sellFee > 0 && (
              <div className="flex justify-between">
                <span>Комиссия продажи</span>
                <span className="tabular-nums text-gray-300">− {fmt(sellFee)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-gray-700 pt-1 font-medium">
              <span>НДФЛ (13%)</span>
              <span className="tabular-nums text-rose-400">{defaultNdfl}</span>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-amber-800/30 bg-amber-950/20 p-3">
            <p className="text-xs text-amber-400 leading-relaxed">
              НДФЛ считается с прибыли, а не со всей суммы продажи. Введите сумму вручную.
            </p>
          </div>
        )}

        <div className="space-y-3">
          <Field label="Сумма НДФЛ">
            <input
              type="number"
              step="any"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Счёт списания">
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)} className={selectCls}>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </Field>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex gap-2">
          <button
            onClick={handleConfirm}
            disabled={submitting}
            className="flex-1 px-4 py-2 text-sm rounded-lg bg-rose-700 hover:bg-rose-600 text-white disabled:opacity-50 transition-colors"
          >
            {submitting ? 'Сохраняю…' : 'Записать НДФЛ'}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
          >
            Пропустить
          </button>
        </div>
      </div>
    </div>
  )
}
