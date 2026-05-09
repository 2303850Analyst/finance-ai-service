'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Account, AccountInterestSettings, AccountType } from '@/lib/types'
import { ACCOUNT_TYPES } from '@/lib/types'

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

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU')
}

const TYPE_COLORS: Record<AccountType, string> = {
  broker: 'text-blue-400 bg-blue-900/30',
  bank: 'text-green-400 bg-green-900/30',
  crypto: 'text-amber-400 bg-amber-900/30',
  cash: 'text-gray-300 bg-gray-700/50',
  deposit: 'text-sky-400 bg-sky-900/30',
  savings: 'text-teal-400 bg-teal-900/30',
  other: 'text-gray-400 bg-gray-800',
}

const TYPE_LABELS: Record<AccountType, string> = {
  broker: 'Брокер',
  bank: 'Банк',
  crypto: 'Крипто',
  cash: 'Наличные',
  deposit: 'Вклад',
  savings: 'Накопительный',
  other: 'Другое',
}

const INTEREST_ACCOUNT_TYPES: AccountType[] = ['savings']

const INTEREST_PAYOUT_LABELS: Record<string, string> = {
  daily: 'Ежедневно',
  monthly: 'Ежемесячно',
  at_maturity: 'В конце срока',
}

// ── Edit Account Modal ────────────────────────────────────────────────────────

interface EditAccountModalProps {
  account: Account
  onClose: () => void
  onSaved: () => void
}

function EditAccountModal({ account, onClose, onSaved }: EditAccountModalProps) {
  const [name, setName] = useState(account.name)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) { setError('Укажите название'); return }
    setError(null)
    setSubmitting(true)
    try {
      await api.accounts.update(account.id, { name: name.trim() })
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
      <div className="w-full max-w-sm rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Редактировать счёт</h2>
            <p className="text-xs text-gray-500 mt-0.5">{TYPE_LABELS[account.account_type]} · {account.currency}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg leading-none">×</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <Field label="Название *">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              className={inputCls}
            />
          </Field>

          <p className="text-xs text-gray-600">
            {/* TODO: Allow account_type and currency edits with history-compatibility validation */}
            Тип и валюта не редактируются — они привязаны к истории операций.
          </p>

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

// ── Interest Settings Modal ───────────────────────────────────────────────────

interface InterestModalProps {
  account: Account
  onClose: () => void
  onSaved: () => void
}

function InterestModal({ account, onClose, onSaved }: InterestModalProps) {
  const isDeposit = account.account_type === 'deposit'
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    is_interest_enabled: true,
    annual_rate_percent: '',
    interest_start_date: new Date().toISOString().slice(0, 10),
    interest_end_date: '',
    payout_frequency: 'monthly',
    capitalization: !isDeposit,  // savings: true, deposit: false
    payout_day: '',
  })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api.accounts.interestSettings(account.id)
      .then((s) => {
        setForm({
          is_interest_enabled: s.is_interest_enabled,
          annual_rate_percent: parseFloat(String(s.annual_rate_percent)).toString(),
          interest_start_date: s.interest_start_date,
          interest_end_date: s.interest_end_date ?? '',
          payout_frequency: s.payout_frequency,
          capitalization: s.capitalization,
          payout_day: s.payout_day?.toString() ?? '',
        })
      })
      .catch(() => {/* 404 = not configured yet, keep defaults */})
      .finally(() => setLoading(false))
  }, [account.id])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.annual_rate_percent) { setError('Укажите ставку'); return }
    if (!form.interest_start_date) { setError('Укажите дату начала'); return }
    if (isDeposit && !form.interest_end_date) { setError('Для вклада укажите дату окончания'); return }
    setError(null)
    setSubmitting(true)
    try {
      await api.accounts.setInterestSettings(account.id, {
        is_interest_enabled: form.is_interest_enabled,
        annual_rate_percent: form.annual_rate_percent,
        interest_start_date: form.interest_start_date,
        interest_end_date: form.interest_end_date || null,
        payout_frequency: form.payout_frequency,
        capitalization: form.capitalization,
        payout_day: form.payout_day ? Number(form.payout_day) : null,
      } as Partial<AccountInterestSettings>)
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
      <div className="w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Настройки процентов</h2>
            <p className="text-xs text-gray-500 mt-0.5">{account.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg leading-none">×</button>
        </div>

        {loading ? (
          <p className="p-5 text-sm text-gray-500">Загрузка…</p>
        ) : (
          <form onSubmit={handleSubmit} className="p-5 space-y-4">
            {error && (
              <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_interest_enabled}
                onChange={(e) => setForm((f) => ({ ...f, is_interest_enabled: e.target.checked }))}
                className="w-4 h-4 rounded accent-teal-500"
              />
              <span className="text-sm text-gray-300">Начислять проценты</span>
            </label>

            <div className="px-3 py-2 rounded-lg bg-teal-950/40 border-l-2 border-teal-700/60">
              <p className="text-xs text-gray-500 mb-0.5">Период выплаты процентов</p>
              <p className="text-xs font-medium text-teal-400">
                {INTEREST_PAYOUT_LABELS[form.payout_frequency] ?? form.payout_frequency}
              </p>
              <p className="text-xs text-gray-600 mt-0.5 leading-relaxed">
                Расчётная база: ежедневный остаток. Период выплаты определяет, когда проценты зачисляются.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Ставка, % годовых *">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="18.5"
                  value={form.annual_rate_percent}
                  onChange={(e) => setForm((f) => ({ ...f, annual_rate_percent: e.target.value }))}
                  className={inputCls}
                />
              </Field>
              <div>
                <label className={labelCls}>Период выплаты процентов</label>
                <select
                  value={form.payout_frequency}
                  onChange={(e) => setForm((f) => ({ ...f, payout_frequency: e.target.value }))}
                  className={selectCls}
                >
                  <option value="daily">Ежедневно</option>
                  <option value="monthly">Ежемесячно</option>
                  <option value="at_maturity">В конце срока</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Дата начала *">
                <input
                  type="date"
                  value={form.interest_start_date}
                  onChange={(e) => setForm((f) => ({ ...f, interest_start_date: e.target.value }))}
                  className={inputCls}
                />
              </Field>
              <Field label={isDeposit ? 'Дата окончания *' : 'Дата окончания'}>
                <input
                  type="date"
                  value={form.interest_end_date}
                  onChange={(e) => setForm((f) => ({ ...f, interest_end_date: e.target.value }))}
                  className={inputCls}
                />
              </Field>
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.capitalization}
                onChange={(e) => setForm((f) => ({ ...f, capitalization: e.target.checked }))}
                className="w-4 h-4 rounded accent-teal-500"
              />
              <span className="text-sm text-gray-300">Капитализация процентов</span>
            </label>

            <div className="flex gap-3 pt-1">
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 py-2 text-sm rounded-lg bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50 transition-colors"
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
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [interestAccount, setInterestAccount] = useState<Account | null>(null)
  const [editAccount, setEditAccount] = useState<Account | null>(null)

  const [form, setForm] = useState({ name: '', account_type: 'broker' as AccountType, currency: 'RUB' })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setAccounts(await api.accounts.list())
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
    if (!form.name.trim()) { setFormError('Укажите название'); return }
    if (!form.currency.trim()) { setFormError('Укажите валюту'); return }

    setSubmitting(true)
    try {
      await api.accounts.create({ ...form, name: form.name.trim() })
      setForm({ name: '', account_type: 'broker', currency: 'RUB' })
      setShowForm(false)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Ошибка создания')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: string) {
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.accounts.delete(id)
      setConfirmDeleteId(null)
      await load()
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : 'Ошибка удаления')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {interestAccount && (
        <InterestModal
          account={interestAccount}
          onClose={() => setInterestAccount(null)}
          onSaved={load}
        />
      )}
      {editAccount && (
        <EditAccountModal
          account={editAccount}
          onClose={() => setEditAccount(null)}
          onSaved={load}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">Счета</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
        >
          {showForm ? 'Отмена' : '+ Новый счёт'}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/50 bg-red-900/20 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Create form */}
      {showForm && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Новый счёт</h2>
          {formError && (
            <div className="mb-4 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {formError}
            </div>
          )}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="Название *">
              <input
                type="text"
                placeholder="напр. Т-Инвестиции"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className={inputCls}
              />
            </Field>
            <Field label="Тип *">
              <select
                value={form.account_type}
                onChange={(e) => setForm((f) => ({ ...f, account_type: e.target.value as AccountType }))}
                className={selectCls}
              >
                {ACCOUNT_TYPES.filter((t) => t !== 'deposit').map((t) => (
                  <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                ))}
              </select>
            </Field>
            <Field label="Валюта *">
              <input
                type="text"
                maxLength={10}
                placeholder="RUB"
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                className={inputCls}
              />
            </Field>
            <div className="sm:col-span-3 flex gap-3 pt-1">
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
              >
                {submitting ? 'Создание…' : 'Создать счёт'}
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
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Счета</h2>
        </div>
        {deleteError && (
          <div className="mx-5 mt-3 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
            {deleteError}
            <button onClick={() => setDeleteError(null)} className="ml-2 text-red-300 hover:text-red-100">×</button>
          </div>
        )}
        {loading ? (
          <p className="p-5 text-sm text-gray-500">Загрузка…</p>
        ) : accounts.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">Нет счетов. Создайте или загрузите тестовые данные.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                <th className="text-left px-5 py-2">Счёт</th>
                <th className="text-left px-3 py-2">Тип</th>
                <th className="text-left px-3 py-2">Валюта</th>
                <th className="text-left px-5 py-2">Создан</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {accounts.map((a) => (
                <tr key={a.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="px-5 py-3 font-medium">
                    {a.name}
                    {a.account_type === 'deposit' && (
                      <span className="ml-2 text-xs text-sky-500/70">управляется на странице Активы</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[a.account_type] ?? 'text-gray-400 bg-gray-800'}`}>
                      {TYPE_LABELS[a.account_type] ?? a.account_type}
                    </span>
                  </td>
                  <td className="px-3 py-3 font-mono text-gray-300">{a.currency}</td>
                  <td className="px-5 py-3 text-gray-400 text-xs">{fmtDate(a.created_at)}</td>
                  <td className="px-3 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {INTEREST_ACCOUNT_TYPES.includes(a.account_type) && (
                        <button
                          onClick={() => setInterestAccount(a)}
                          className="px-2 py-1 text-xs rounded bg-teal-900/40 text-teal-400 hover:bg-teal-900/70 transition-colors"
                        >
                          % ставка
                        </button>
                      )}
                      <button
                        onClick={() => setEditAccount(a)}
                        className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white transition-colors"
                        title="Редактировать"
                      >
                        ✏
                      </button>
                      {confirmDeleteId === a.id ? (
                        <span className="flex items-center gap-1.5">
                          <span className="text-xs text-gray-400">Удалить?</span>
                          <button
                            onClick={() => handleDelete(a.id)}
                            disabled={deleting}
                            className="px-2 py-1 text-xs rounded bg-red-800/60 text-red-300 hover:bg-red-700/70 disabled:opacity-50 transition-colors"
                          >
                            {deleting ? '…' : 'Да'}
                          </button>
                          <button
                            onClick={() => { setConfirmDeleteId(null); setDeleteError(null) }}
                            className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors"
                          >
                            Нет
                          </button>
                        </span>
                      ) : (
                        <button
                          onClick={() => { setConfirmDeleteId(a.id); setDeleteError(null) }}
                          className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-500 hover:bg-red-900/40 hover:text-red-400 transition-colors"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
