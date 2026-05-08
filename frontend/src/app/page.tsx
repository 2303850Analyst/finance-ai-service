'use client'

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Asset, HealthStatus, ParseResponse, PortfolioSummary, Operation } from '@/lib/types'

const AllocationChart = dynamic(() => import('@/components/AllocationChart'), { ssr: false })

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
  )
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-gray-800 bg-gray-900 p-5 ${className}`}>
      {children}
    </div>
  )
}

function fmt(value: string | number) {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [recentOps, setRecentOps] = useState<Operation[]>([])
  const [assetMap, setAssetMap] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState<string[]>([])
  const [seeding, setSeeding] = useState(false)
  const [seedMsg, setSeedMsg] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  // AI command bar state
  const [aiText, setAiText] = useState('')
  const [aiParsing, setAiParsing] = useState(false)
  const [aiResult, setAiResult] = useState<ParseResponse | null>(null)
  const [aiError, setAiError] = useState<string | null>(null)
  const [aiConfirming, setAiConfirming] = useState(false)
  const [aiConfirmMsg, setAiConfirmMsg] = useState<string | null>(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setErrors([])
    const errs: string[] = []

    const [healthRes, summaryRes, opsRes, assetsRes] = await Promise.allSettled([
      api.health(),
      api.portfolio.summary(),
      api.operations.list(),
      api.assets.list(),
    ])

    if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
    else errs.push(`Health: ${healthRes.reason instanceof Error ? healthRes.reason.message : 'error'}`)

    if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value)
    else errs.push(`Portfolio: ${summaryRes.reason instanceof Error ? summaryRes.reason.message : 'error'}`)

    if (opsRes.status === 'fulfilled') setRecentOps(opsRes.value.slice(0, 5))
    else errs.push(`Operations: ${opsRes.reason instanceof Error ? opsRes.reason.message : 'error'}`)

    if (assetsRes.status === 'fulfilled') {
      setAssetMap(Object.fromEntries((assetsRes.value as Asset[]).map((a) => [a.id, a.ticker])))
    }

    if (errs.length > 0) setErrors(errs)
    setLoading(false)
  }, [])

  useEffect(() => { loadAll() }, [loadAll, refreshKey])

  async function handleSeed() {
    setSeeding(true)
    setSeedMsg(null)
    try {
      const result = await api.seed()
      const newAccs = result.accounts_created.length
      const newAssets = result.assets_created.length
      setSeedMsg(
        newAccs === 0 && newAssets === 0
          ? 'Already seeded — no changes.'
          : `Seeded: ${newAccs} account(s), ${newAssets} asset(s).`
      )
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setSeedMsg(`Error: ${e instanceof Error ? e.message : 'unknown'}`)
    } finally {
      setSeeding(false)
    }
  }

  async function handleAiParse() {
    if (!aiText.trim()) return
    setAiParsing(true)
    setAiError(null)
    setAiResult(null)
    setAiConfirmMsg(null)
    try {
      setAiResult(await api.ai.parse(aiText.trim()))
    } catch (e) {
      setAiError(e instanceof Error ? e.message : 'Parse error')
    } finally {
      setAiParsing(false)
    }
  }

  async function handleAiConfirm() {
    if (!aiResult || aiResult.status !== 'parsed' || !aiResult.operation || !aiResult.account_id) return
    const op = aiResult.operation
    const isBuySell = op.operation_type === 'buy' || op.operation_type === 'sell'
    const amount = isBuySell && op.quantity && op.price
      ? String(parseFloat(op.quantity) * parseFloat(op.price))
      : (op.amount ?? '0')

    setAiConfirming(true)
    setAiConfirmMsg(null)
    try {
      await api.operations.create({
        account_id: aiResult.account_id,
        ...(aiResult.asset_id ? { asset_id: aiResult.asset_id } : {}),
        operation_type: op.operation_type,
        ...(op.quantity ? { quantity: op.quantity } : {}),
        ...(op.price ? { price: op.price } : {}),
        amount,
        currency: op.currency,
        operated_at: op.operated_at,
      })
      setAiConfirmMsg('Операция сохранена.')
      setAiResult(null)
      setAiText('')
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setAiConfirmMsg(`Ошибка: ${e instanceof Error ? e.message : 'unknown'}`)
    } finally {
      setAiConfirming(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">Finance AI Service</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {seedMsg && (
            <span className="text-xs text-gray-400 bg-gray-800 px-3 py-1.5 rounded-lg">
              {seedMsg}
            </span>
          )}
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="px-3 py-1.5 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-50 transition-colors"
          >
            {seeding ? 'Seeding…' : 'Seed dev data'}
          </button>
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={loading}
            className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
          >
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="rounded-xl border border-red-800/50 bg-red-900/20 p-4 space-y-1">
          {errors.map((e, i) => (
            <p key={i} className="text-sm text-red-400">{e}</p>
          ))}
        </div>
      )}

      {/* AI Command Bar */}
      <Card>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          AI Command Bar
        </h2>
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={aiText}
              onChange={(e) => setAiText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !aiParsing) handleAiParse() }}
              placeholder="Купил 10 акций Сбера по 280 рублей, счет Т-Инвестиции"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              onClick={handleAiParse}
              disabled={aiParsing || !aiText.trim()}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {aiParsing ? 'Разбираю…' : 'Разобрать'}
            </button>
          </div>

          {aiError && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {aiError}
            </div>
          )}

          {aiConfirmMsg && !aiResult && (
            <p className="text-sm text-green-400">{aiConfirmMsg}</p>
          )}

          {aiResult?.status === 'not_operation' && (
            <div className="rounded-lg border border-yellow-800/50 bg-yellow-900/20 p-3 text-yellow-400 text-sm">
              {aiResult.message || 'Не распознано как финансовая операция.'}
            </div>
          )}

          {aiResult?.status === 'need_clarification' && (
            <div className="rounded-lg border border-orange-800/50 bg-orange-900/20 p-3 space-y-1">
              <p className="text-orange-400 text-sm font-medium">Нужно уточнение</p>
              {aiResult.message && <p className="text-orange-300 text-xs">{aiResult.message}</p>}
              {aiResult.missing_fields.length > 0 && (
                <p className="text-orange-400 text-xs">
                  Не найдено: {aiResult.missing_fields.join(', ')}
                </p>
              )}
              {aiResult.operation && (
                <AiDraftPreview op={aiResult.operation} />
              )}
            </div>
          )}

          {aiResult?.status === 'parsed' && aiResult.operation && (
            <div className="rounded-xl border border-blue-800/40 bg-blue-950/30 p-4 space-y-3">
              <div className="space-y-0.5">
                <p className="text-xs text-yellow-400">
                  ⚠ AI разобрал операцию. Проверьте данные перед подтверждением.
                </p>
                <p className="text-xs text-gray-500">
                  AI не изменяет портфель до вашего подтверждения.
                </p>
              </div>

              <AiDraftPreview op={aiResult.operation} />

              {!aiResult.account_id && (
                <p className="text-xs text-orange-400">
                  ⚠ Счёт не определён. Укажите счёт в тексте или создайте операцию вручную.
                </p>
              )}

              {aiConfirmMsg && (
                <p className="text-sm text-red-400">{aiConfirmMsg}</p>
              )}

              <div className="flex gap-2">
                <button
                  onClick={handleAiConfirm}
                  disabled={aiConfirming || !aiResult.account_id}
                  className="px-4 py-2 text-sm rounded-lg bg-green-700 hover:bg-green-600 text-white disabled:opacity-50 transition-colors"
                >
                  {aiConfirming ? 'Сохраняю…' : 'Подтвердить операцию'}
                </button>
                <button
                  onClick={() => { setAiResult(null); setAiText(''); setAiConfirmMsg(null) }}
                  className="px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                >
                  Отмена
                </button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Status + Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">API</p>
          <div className="flex items-center gap-2">
            <StatusDot ok={health?.status === 'ok'} />
            <span className="text-sm font-medium">{health?.status ?? '—'}</span>
          </div>
        </Card>
        <Card>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Database</p>
          <div className="flex items-center gap-2">
            <StatusDot ok={health?.database === 'ok'} />
            <span className="text-sm font-medium">{health?.database ?? '—'}</span>
          </div>
        </Card>
        <Card>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Total Value</p>
          <p className="text-xl font-bold">
            {summary ? fmt(summary.total_cost) : '—'}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">RUB</p>
        </Card>
        <Card>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Positions</p>
          <p className="text-xl font-bold">{summary?.positions_count ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-0.5">assets held</p>
        </Card>
      </div>

      {/* Chart + Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Allocation by Type
          </h2>
          {loading ? (
            <div className="h-52 flex items-center justify-center text-gray-500 text-sm">Loading…</div>
          ) : (
            <AllocationChart data={summary?.allocation ?? []} />
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Positions
          </h2>
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : (summary?.positions ?? []).length === 0 ? (
            <p className="text-sm text-gray-500">No positions. Seed dev data and add operations.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider">
                    <th className="text-left pb-2">Ticker</th>
                    <th className="text-right pb-2">Qty</th>
                    <th className="text-right pb-2">Avg Price</th>
                    <th className="text-right pb-2">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {(summary?.positions ?? []).map((pos) => (
                    <tr key={pos.id}>
                      <td className="py-2">
                        <span className="font-mono font-medium text-blue-400">{pos.ticker}</span>
                        <span className="text-gray-500 text-xs ml-2">{pos.asset_type}</span>
                      </td>
                      <td className="py-2 text-right tabular-nums">{parseFloat(pos.quantity).toLocaleString('ru-RU', { maximumFractionDigits: 4 })}</td>
                      <td className="py-2 text-right tabular-nums text-gray-300">{fmt(pos.average_price)}</td>
                      <td className="py-2 text-right tabular-nums font-medium">{fmt(pos.total_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Recent Operations */}
      <Card>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Recent Operations
        </h2>
        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : recentOps.length === 0 ? (
          <p className="text-sm text-gray-500">No operations yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider">
                  <th className="text-left pb-2">Date</th>
                  <th className="text-left pb-2">Type</th>
                  <th className="text-left pb-2">Asset</th>
                  <th className="text-right pb-2">Qty</th>
                  <th className="text-right pb-2">Price</th>
                  <th className="text-right pb-2">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {recentOps.map((op) => (
                  <tr key={op.id}>
                    <td className="py-2 text-gray-400 whitespace-nowrap">{fmtDate(op.operated_at)}</td>
                    <td className="py-2">
                      <OpTypeBadge type={op.operation_type} />
                    </td>
                    <td className="py-2 font-mono text-xs text-blue-400">{op.asset_id ? (assetMap[op.asset_id] ?? '—') : '—'}</td>
                    <td className="py-2 text-right tabular-nums text-gray-300">
                      {op.quantity ? parseFloat(op.quantity).toLocaleString('ru-RU', { maximumFractionDigits: 4 }) : '—'}
                    </td>
                    <td className="py-2 text-right tabular-nums text-gray-300">
                      {op.price ? fmt(op.price) : '—'}
                    </td>
                    <td className="py-2 text-right tabular-nums font-medium">{fmt(op.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

import type { OperationDraft } from '@/lib/types'

function PreviewField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className="text-sm font-medium text-white">{value}</p>
    </div>
  )
}

function AiDraftPreview({ op }: { op: OperationDraft }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 pt-1">
      <PreviewField label="Тип" value={op.operation_type.replace('_', ' ')} />
      {op.asset_ticker && (
        <PreviewField label="Актив" value={op.asset_name ? `${op.asset_ticker} · ${op.asset_name}` : op.asset_ticker} />
      )}
      {op.account_name && <PreviewField label="Счёт" value={op.account_name} />}
      {op.quantity && <PreviewField label="Кол-во" value={op.quantity} />}
      {op.price && <PreviewField label="Цена" value={op.price} />}
      {op.amount && <PreviewField label="Сумма" value={op.amount} />}
      {op.fee && <PreviewField label="Комиссия" value={op.fee} />}
      <PreviewField label="Валюта" value={op.currency} />
    </div>
  )
}

const OP_TYPE_COLORS: Record<string, string> = {
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

function OpTypeBadge({ type }: { type: string }) {
  const colors = OP_TYPE_COLORS[type] ?? 'text-gray-400 bg-gray-800'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {type.replace('_', ' ')}
    </span>
  )
}
