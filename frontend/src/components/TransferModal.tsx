'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import type { Account, CashBalance } from '@/lib/types'
import { preferCashBankAccount } from '@/lib/types'

// ── shared styles ─────────────────────────────────────────────────────────────

const _inputCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors'
const _selectCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors'
const _labelCls = 'block text-xs text-gray-400 mb-1.5'

function fmt(value: string | number) {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function nowLocal() {
  const d = new Date()
  d.setSeconds(0, 0)
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

// ── types ─────────────────────────────────────────────────────────────────────

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

// ── component ─────────────────────────────────────────────────────────────────

interface TransferModalProps {
  accounts: Account[]
  cashBalances: CashBalance[]
  onClose: () => void
  onSuccess: () => void
}

export default function TransferModal({
  accounts,
  cashBalances,
  onClose,
  onSuccess,
}: TransferModalProps) {
  const firstId = preferCashBankAccount(accounts)
  const secondId = accounts.find((a) => a.id !== firstId)?.id ?? ''

  const [form, setForm] = useState<TransferFormState>({
    from_account_id: firstId,
    to_account_id: secondId,
    amount: '',
    currency: 'RUB',
    hasFee: false,
    fee: '',
    note: '',
    operated_at: nowLocal(),
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof TransferFormState>(key: K, value: TransferFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  // Available balance on source account
  const available = parseFloat(
    cashBalances.find(
      (cb) => cb.account_id === form.from_account_id && cb.currency === form.currency
    )?.balance ?? '0'
  )
  const amt = parseFloat(form.amount) || 0
  const feeAmt = form.hasFee ? (parseFloat(form.fee) || 0) : 0
  const required = amt + feeAmt
  const exceedsBalance = form.from_account_id !== '' && required > available && required > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!form.from_account_id) { setError('Выберите счёт-источник'); return }
    if (!form.to_account_id) { setError('Выберите счёт-получатель'); return }
    if (form.from_account_id === form.to_account_id) {
      setError('Откуда и куда должны быть разными счетами'); return
    }
    if (!form.amount || isNaN(amt) || amt <= 0) { setError('Введите положительную сумму'); return }
    if (form.hasFee && (!form.fee || isNaN(feeAmt) || feeAmt < 0)) {
      setError('Введите корректную комиссию'); return
    }
    if (exceedsBalance) {
      setError(`Недостаточно средств: доступно ${fmt(available)} ${form.currency}, нужно ${fmt(required)}`)
      return
    }

    setSubmitting(true)
    try {
      await api.operations.transfer({
        from_account_id: form.from_account_id,
        to_account_id: form.to_account_id,
        amount: form.amount,
        currency: form.currency,
        operated_at: new Date(form.operated_at).toISOString(),
        fee: form.hasFee && form.fee ? form.fee : null,
        note: form.note.trim() || null,
      })
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при сохранении')
    } finally {
      setSubmitting(false)
    }
  }

  function accountLabel(a: Account) {
    const bal = cashBalances.find((cb) => cb.account_id === a.id && cb.currency === form.currency)
    const balStr = bal ? fmt(bal.balance) : '—'
    return `${a.name} · ${balStr} ${form.currency}`
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-base font-semibold text-white">Перевод между счетами</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <p className="text-xs text-indigo-400/80 bg-indigo-950/20 border border-indigo-800/30 rounded-lg px-3 py-2">
            Перевод не является доходом или расходом. Только комиссия уменьшает общий капитал.
          </p>

          {/* Откуда */}
          <div>
            <label className={_labelCls}>Откуда *</label>
            <select
              value={form.from_account_id}
              onChange={(e) => {
                set('from_account_id', e.target.value)
                if (e.target.value === form.to_account_id) set('to_account_id', '')
              }}
              className={_selectCls}
            >
              <option value="">— выберите счёт —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{accountLabel(a)}</option>
              ))}
            </select>
            {form.from_account_id && (
              <p className={`text-xs mt-1 ${available <= 0 ? 'text-red-400' : 'text-gray-500'}`}>
                Доступно: {fmt(available)} {form.currency}
              </p>
            )}
          </div>

          {/* Куда */}
          <div>
            <label className={_labelCls}>Куда *</label>
            <select
              value={form.to_account_id}
              onChange={(e) => set('to_account_id', e.target.value)}
              className={_selectCls}
            >
              <option value="">— выберите счёт —</option>
              {accounts.filter((a) => a.id !== form.from_account_id).map((a) => (
                <option key={a.id} value={a.id}>{accountLabel(a)}</option>
              ))}
            </select>
          </div>

          {/* Сумма + Валюта */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className={_labelCls}>Сумма перевода *</label>
              <input
                type="number"
                step="any"
                min="0.01"
                placeholder="Например, 50 000"
                value={form.amount}
                onChange={(e) => set('amount', e.target.value)}
                className={`${_inputCls} ${exceedsBalance ? 'border-red-600' : ''}`}
              />
              {exceedsBalance && (
                <p className="text-xs text-red-400 mt-1">
                  Превышает доступный остаток ({fmt(available)} {form.currency})
                </p>
              )}
            </div>
            <div>
              <label className={_labelCls}>Валюта</label>
              <input
                type="text"
                maxLength={10}
                placeholder="RUB"
                value={form.currency}
                onChange={(e) => set('currency', e.target.value.toUpperCase())}
                className={_inputCls}
              />
            </div>
          </div>

          {/* Комиссия */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.hasFee}
                onChange={(e) => { set('hasFee', e.target.checked); if (!e.target.checked) set('fee', '') }}
                className="w-3.5 h-3.5 accent-indigo-500"
              />
              <span className="text-xs text-gray-300">Комиссия за перевод</span>
            </label>
            {form.hasFee && (
              <input
                type="number"
                step="any"
                min="0"
                placeholder="Например, 50"
                value={form.fee}
                onChange={(e) => set('fee', e.target.value)}
                className={_inputCls}
              />
            )}
          </div>

          {/* Комментарий */}
          <div>
            <label className={_labelCls}>Комментарий</label>
            <input
              type="text"
              placeholder="Необязательно"
              value={form.note}
              onChange={(e) => set('note', e.target.value)}
              className={_inputCls}
            />
          </div>

          {/* Дата */}
          <div>
            <label className={_labelCls}>Дата и время</label>
            <input
              type="datetime-local"
              value={form.operated_at}
              onChange={(e) => set('operated_at', e.target.value)}
              className={_inputCls}
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={submitting || exceedsBalance}
              className="flex-1 px-4 py-2 text-sm rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Сохраняю…' : 'Выполнить перевод'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
