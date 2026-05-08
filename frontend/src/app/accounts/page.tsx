'use client'

import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Account, AccountType } from '@/lib/types'
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
  other: 'text-gray-400 bg-gray-800',
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const [form, setForm] = useState({ name: '', account_type: 'broker' as AccountType, currency: 'RUB' })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setAccounts(await api.accounts.list())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (!form.name.trim()) { setFormError('Name is required'); return }
    if (!form.currency.trim()) { setFormError('Currency is required'); return }

    setSubmitting(true)
    try {
      await api.accounts.create({ ...form, name: form.name.trim() })
      setForm({ name: '', account_type: 'broker', currency: 'RUB' })
      setShowForm(false)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Failed to create')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">Accounts</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
        >
          {showForm ? 'Cancel' : '+ New Account'}
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
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">New Account</h2>
          {formError && (
            <div className="mb-4 rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {formError}
            </div>
          )}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="Name *">
              <input
                type="text"
                placeholder="e.g. Т-Инвестиции"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className={inputCls}
              />
            </Field>
            <Field label="Type *">
              <select
                value={form.account_type}
                onChange={(e) => setForm((f) => ({ ...f, account_type: e.target.value as AccountType }))}
                className={selectCls}
              >
                {ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="Currency *">
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
                {submitting ? 'Creating…' : 'Create account'}
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

      {/* Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Accounts</h2>
        </div>
        {loading ? (
          <p className="p-5 text-sm text-gray-500">Loading…</p>
        ) : accounts.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">No accounts. Create one or seed dev data.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                <th className="text-left px-5 py-2">Name</th>
                <th className="text-left px-3 py-2">Type</th>
                <th className="text-left px-3 py-2">Currency</th>
                <th className="text-left px-5 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {accounts.map((a) => (
                <tr key={a.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="px-5 py-3 font-medium">{a.name}</td>
                  <td className="px-3 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[a.account_type] ?? 'text-gray-400 bg-gray-800'}`}>
                      {a.account_type}
                    </span>
                  </td>
                  <td className="px-3 py-3 font-mono text-gray-300">{a.currency}</td>
                  <td className="px-5 py-3 text-gray-400 text-xs">{fmtDate(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
