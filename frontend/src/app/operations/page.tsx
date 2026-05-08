'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Account, Asset, Operation, OperationType } from '@/lib/types'
import { OPERATION_TYPES } from '@/lib/types'

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
}

function Badge({ type }: { type: string }) {
  const colors = OP_COLORS[type] ?? 'text-gray-400 bg-gray-800'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {type.replace('_', ' ')}
    </span>
  )
}

const REQUIRES_ASSET = new Set<OperationType>(['buy', 'sell', 'manual_valuation'])
const REQUIRES_QTY_PRICE = new Set<OperationType>(['buy', 'sell'])
const REQUIRES_PRICE = new Set<OperationType>(['buy', 'sell', 'manual_valuation'])

// ── default form state ────────────────────────────────────────────────────────

function nowLocal() {
  const d = new Date()
  d.setSeconds(0, 0)
  // toISOString() gives UTC; subtract timezone offset to get local wall-clock time
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

interface FormState {
  account_id: string
  asset_id: string
  operation_type: OperationType
  quantity: string
  price: string
  amount: string
  currency: string
  operated_at: string
  note: string
}

const EMPTY_FORM: FormState = {
  account_id: '',
  asset_id: '',
  operation_type: 'buy',
  quantity: '',
  price: '',
  amount: '',
  currency: 'RUB',
  operated_at: nowLocal(),
  note: '',
}

// ── component ─────────────────────────────────────────────────────────────────

export default function OperationsPage() {
  const [operations, setOperations] = useState<Operation[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  // Lazy initializer so operated_at is current time at mount, not stale module-load time
  const [form, setForm] = useState<FormState>(() => ({ ...EMPTY_FORM, operated_at: nowLocal() }))
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [filterType, setFilterType] = useState('')
  const [filterAccount, setFilterAccount] = useState('')
  const [filterAsset, setFilterAsset] = useState('')

  const [deletingId, setDeletingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ops, accs, asss] = await Promise.all([
        api.operations.list(),
        api.accounts.list(),
        api.assets.list(),
      ])
      setOperations(ops)
      setAccounts(accs)
      setAssets(asss)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data')
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

  // ── account/asset name lookups ───────────────────────────────────────────
  const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a.name]))
  const assetMap = Object.fromEntries(assets.map((a) => [a.id, a.ticker]))

  // ── form submit ──────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)

    const op = form.operation_type
    if (!form.account_id) { setFormError('Account is required'); return }
    if (REQUIRES_ASSET.has(op) && !form.asset_id) { setFormError('Asset is required for ' + op); return }
    if (REQUIRES_QTY_PRICE.has(op)) {
      if (!form.quantity || parseFloat(form.quantity) <= 0) { setFormError('Quantity must be positive'); return }
      if (!form.price || parseFloat(form.price) <= 0) { setFormError('Price must be positive'); return }
    }
    if (REQUIRES_PRICE.has(op) && !REQUIRES_QTY_PRICE.has(op)) {
      if (!form.price || parseFloat(form.price) <= 0) { setFormError('Price must be positive'); return }
    }
    if (!REQUIRES_QTY_PRICE.has(op) && !REQUIRES_PRICE.has(op)) {
      if (!form.amount) { setFormError('Amount is required'); return }
    }

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

    setSubmitting(true)
    try {
      await api.operations.create(payload)
      setForm({ ...EMPTY_FORM, operated_at: nowLocal() })
      setShowForm(false)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Failed to create operation')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this operation? Portfolio will be recalculated.')) return
    setDeletingId(id)
    try {
      await api.operations.delete(id)
      await load()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setDeletingId(null)
    }
  }

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">Operations</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          >
            {showForm ? 'Cancel' : '+ New Operation'}
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
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            New Operation
          </h2>
          {formError && (
            <div className="mb-4 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {formError}
            </div>
          )}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Operation type */}
            <Field label="Operation type *">
              <select
                value={form.operation_type}
                onChange={(e) => setForm((f) => ({ ...f, operation_type: e.target.value as OperationType, asset_id: '', quantity: '', price: '', amount: '' }))}
                className={selectCls}
              >
                {OPERATION_TYPES.map((t) => (
                  <option key={t} value={t}>{t.replace('_', ' ')}</option>
                ))}
              </select>
            </Field>

            {/* Account */}
            <Field label="Account *">
              <select
                value={form.account_id}
                onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))}
                className={selectCls}
              >
                <option value="">— select account —</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </Field>

            {/* Asset */}
            <Field label={`Asset${REQUIRES_ASSET.has(form.operation_type) ? ' *' : ''}`}>
              <select
                value={form.asset_id}
                onChange={(e) => setForm((f) => ({ ...f, asset_id: e.target.value }))}
                className={selectCls}
              >
                <option value="">— none —</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>{a.ticker} — {a.name}</option>
                ))}
              </select>
            </Field>

            {/* Quantity (buy/sell only) */}
            {REQUIRES_QTY_PRICE.has(form.operation_type) && (
              <Field label="Quantity *">
                <input
                  type="number"
                  step="any"
                  min="0"
                  placeholder="e.g. 10"
                  value={form.quantity}
                  onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                  className={inputCls}
                />
              </Field>
            )}

            {/* Price (buy/sell/manual_valuation) */}
            {REQUIRES_PRICE.has(form.operation_type) && (
              <Field label="Price *">
                <input
                  type="number"
                  step="any"
                  min="0"
                  placeholder="e.g. 280.50"
                  value={form.price}
                  onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                  className={inputCls}
                />
              </Field>
            )}

            {/* Amount */}
            {REQUIRES_QTY_PRICE.has(form.operation_type) ? (
              <Field label="Amount (computed)">
                <input
                  type="text"
                  readOnly
                  value={computedAmount ?? ''}
                  className={`${inputCls} opacity-50 cursor-default`}
                />
              </Field>
            ) : (
              <Field label={`Amount${!REQUIRES_PRICE.has(form.operation_type) ? ' *' : ''}`}>
                <input
                  type="number"
                  step="any"
                  min="0"
                  placeholder="e.g. 1000"
                  value={form.amount}
                  onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                  className={inputCls}
                />
              </Field>
            )}

            {/* Currency */}
            <Field label="Currency">
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
            <Field label="Date & time *">
              <input
                type="datetime-local"
                value={form.operated_at}
                onChange={(e) => setForm((f) => ({ ...f, operated_at: e.target.value }))}
                className={inputCls}
              />
            </Field>

            {/* Note */}
            <Field label="Note">
              <input
                type="text"
                placeholder="Optional note"
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
                {submitting ? 'Saving…' : 'Create operation'}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setFormError(null) }}
                className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className={labelCls}>Type</label>
            <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className={selectCls}>
              <option value="">All types</option>
              {OPERATION_TYPES.map((t) => (
                <option key={t} value={t}>{t.replace('_', ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Account</label>
            <select value={filterAccount} onChange={(e) => setFilterAccount(e.target.value)} className={selectCls}>
              <option value="">All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Asset</label>
            <select value={filterAsset} onChange={(e) => setFilterAsset(e.target.value)} className={selectCls}>
              <option value="">All assets</option>
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
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
            Operations
          </h2>
          <span className="text-xs text-gray-500">{filtered.length} shown</span>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-gray-500">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">No operations found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                  <th className="text-left px-5 py-2">Date</th>
                  <th className="text-left px-3 py-2">Type</th>
                  <th className="text-left px-3 py-2">Account</th>
                  <th className="text-left px-3 py-2">Asset</th>
                  <th className="text-right px-3 py-2">Qty</th>
                  <th className="text-right px-3 py-2">Price</th>
                  <th className="text-right px-3 py-2">Amount</th>
                  <th className="text-right px-5 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {filtered.map((op) => (
                  <tr key={op.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-5 py-2.5 text-gray-400 whitespace-nowrap text-xs">{fmtDate(op.operated_at)}</td>
                    <td className="px-3 py-2.5"><Badge type={op.operation_type} /></td>
                    <td className="px-3 py-2.5 text-gray-300 text-xs">{accountMap[op.account_id] ?? '—'}</td>
                    <td className="px-3 py-2.5 font-mono text-blue-400 text-xs">{op.asset_id ? (assetMap[op.asset_id] ?? '—') : '—'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-gray-300">{fmtQty(op.quantity)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-gray-300">{op.price ? fmt(op.price) : '—'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-medium">{fmt(op.amount)}</td>
                    <td className="px-5 py-2.5 text-right">
                      <button
                        onClick={() => handleDelete(op.id)}
                        disabled={deletingId === op.id}
                        className="text-xs text-gray-500 hover:text-red-400 disabled:opacity-40 transition-colors"
                      >
                        {deletingId === op.id ? '…' : 'Delete'}
                      </button>
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
