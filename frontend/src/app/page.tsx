'use client'

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Account, Asset, BudgetSummary, CashBalance, HealthStatus, InterestAccrual, ParseResponse, PortfolioSummary, Operation, SalaryDue } from '@/lib/types'
import { INCOME_SOURCES, PHYSICAL_ASSET_TYPES, incomeSourceLabel, preferCashBankAccount } from '@/lib/types'
import TransferModal from '@/components/TransferModal'

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
  const [assetsList, setAssetsList] = useState<Asset[]>([])
  const [cashBalances, setCashBalances] = useState<CashBalance[]>([])
  const [interestAccruals, setInterestAccruals] = useState<InterestAccrual[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [showIncomeModal, setShowIncomeModal] = useState(false)
  const [incomeSuccessMsg, setIncomeSuccessMsg] = useState<string | null>(null)
  const [showExpenseModal, setShowExpenseModal] = useState(false)
  const [expenseSuccessMsg, setExpenseSuccessMsg] = useState<string | null>(null)
  const [showTransferModal, setShowTransferModal] = useState(false)
  const [transferSuccessMsg, setTransferSuccessMsg] = useState<string | null>(null)
  const [salaryDue, setSalaryDue] = useState<SalaryDue | null>(null)
  const [budgetSummary, setBudgetSummary] = useState<BudgetSummary | null>(null)
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
  // funding flow state
  const [fundingRequired, setFundingRequired] = useState<{ missingCash: string; currency: string } | null>(null)
  const [depositFee, setDepositFee] = useState('')
  const [hasFee, setHasFee] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setErrors([])
    const errs: string[] = []

    const now = new Date()
    const monthFrom = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    const monthTo = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`

    const [healthRes, summaryRes, opsRes, assetsRes, cashRes, accsRes, interestRes, budgetRes, salaryDueRes] = await Promise.allSettled([
      api.health(),
      api.portfolio.summary(),
      api.operations.list(),
      api.assets.list(),
      api.portfolio.cashBalances(),
      api.accounts.list(),
      api.portfolio.interestAccruals(),
      api.budget.summary(monthFrom, monthTo),
      api.budget.salaryDue(),
    ])

    if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
    else errs.push(`Health: ${healthRes.reason instanceof Error ? healthRes.reason.message : 'error'}`)

    if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value)
    else errs.push(`Portfolio: ${summaryRes.reason instanceof Error ? summaryRes.reason.message : 'error'}`)

    if (opsRes.status === 'fulfilled') setRecentOps(opsRes.value.slice(0, 5))
    else errs.push(`Operations: ${opsRes.reason instanceof Error ? opsRes.reason.message : 'error'}`)

    if (assetsRes.status === 'fulfilled') {
      setAssetMap(Object.fromEntries((assetsRes.value as Asset[]).map((a) => [a.id, a.ticker])))
      setAssetsList(assetsRes.value as Asset[])
    }

    if (cashRes.status === 'fulfilled') setCashBalances(cashRes.value)
    else setCashBalances([])

    if (accsRes.status === 'fulfilled') setAccounts(accsRes.value)

    if (interestRes.status === 'fulfilled') setInterestAccruals(interestRes.value)
    else setInterestAccruals([])

    if (budgetRes.status === 'fulfilled') setBudgetSummary(budgetRes.value)
    else setBudgetSummary(null)

    if (salaryDueRes.status === 'fulfilled') setSalaryDue(salaryDueRes.value)
    else setSalaryDue(null)

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
    setFundingRequired(null)
    setDepositFee('')
    setHasFee(false)
    try {
      setAiResult(await api.ai.parse(aiText.trim()))
    } catch (e) {
      setAiError(e instanceof Error ? e.message : 'Parse error')
    } finally {
      setAiParsing(false)
    }
  }

  async function handleAiConfirm(forceFunding = false) {
    if (!aiResult || aiResult.status !== 'parsed' || !aiResult.operation || !aiResult.account_id) return
    const op = aiResult.operation
    const isBuySell = op.operation_type === 'buy' || op.operation_type === 'sell'
    const amount = isBuySell && op.quantity && op.price
      ? String(parseFloat(op.quantity) * parseFloat(op.price))
      : (op.amount ?? '0')

    setAiConfirming(true)
    setAiConfirmMsg(null)
    try {
      const operationPayload: Record<string, unknown> = {
        account_id: aiResult.account_id,
        ...(aiResult.asset_id ? { asset_id: aiResult.asset_id } : {}),
        ...(aiResult.to_account_id ? { to_account_id: aiResult.to_account_id } : {}),
        operation_type: op.operation_type,
        ...(op.quantity ? { quantity: op.quantity } : {}),
        ...(op.price ? { price: op.price } : {}),
        amount,
        ...(op.fee ? { fee: op.fee } : {}),
        currency: op.currency,
        operated_at: op.operated_at,
        ...(op.expense_group ? { expense_group: op.expense_group } : {}),
        ...(op.expense_category ? { expense_category: op.expense_category } : {}),
        ...(op.merchant ? { merchant: op.merchant } : {}),
        ...(op.income_source ? { income_source: op.income_source } : {}),
        ...(op.principal_amount ? { principal_amount: op.principal_amount } : {}),
        ...(op.interest_amount ? { interest_amount: op.interest_amount } : {}),
        ...(op.note ? { note: op.note } : {}),
      }

      const result = await api.operations.confirmWithFunding({
        operation: operationPayload,
        force_funding: forceFunding,
        deposit_fee: depositFee || null,
      })

      if (result.status === 'funding_required' && result.funding_required) {
        const fr = result.funding_required
        setFundingRequired({
          missingCash: fr.missing_cash,
          currency: fr.currency,
        })
        setAiConfirmMsg(null)
        return
      }

      const parts: string[] = []
      if (result.deposit) parts.push(`Пополнение: ${fmt(result.deposit.amount)} ${result.deposit.currency}`)
      parts.push('Операция сохранена.')
      setAiConfirmMsg(parts.join(' '))
      setAiResult(null)
      setAiText('')
      setFundingRequired(null)
      setDepositFee('')
      setHasFee(false)
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setAiConfirmMsg(`Ошибка: ${e instanceof Error ? e.message : 'unknown'}`)
    } finally {
      setAiConfirming(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl">
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
          {incomeSuccessMsg && (
            <span className="text-xs text-green-400 bg-green-900/20 border border-green-800/40 px-3 py-1.5 rounded-lg">
              {incomeSuccessMsg}
            </span>
          )}
          {expenseSuccessMsg && (
            <span className="text-xs text-pink-400 bg-pink-900/20 border border-pink-800/40 px-3 py-1.5 rounded-lg">
              {expenseSuccessMsg}
            </span>
          )}
          {transferSuccessMsg && (
            <span className="text-xs text-blue-400 bg-blue-900/20 border border-blue-800/40 px-3 py-1.5 rounded-lg">
              {transferSuccessMsg}
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
            onClick={() => { setShowIncomeModal(true); setIncomeSuccessMsg(null) }}
            className="px-3 py-1.5 text-sm rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white transition-colors"
          >
            Ввести доход
          </button>
          <button
            onClick={() => { setShowExpenseModal(true); setExpenseSuccessMsg(null) }}
            className="px-3 py-1.5 text-sm rounded-lg bg-pink-800 hover:bg-pink-700 text-white transition-colors"
          >
            Ввести расход
          </button>
          <button
            onClick={() => { setShowTransferModal(true); setTransferSuccessMsg(null) }}
            className="px-3 py-1.5 text-sm rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white transition-colors"
          >
            Перевод
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
          AI-ввод операции
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
          <p className="text-xs text-gray-600">
            AI заполнит черновик. Сохранение только после подтверждения.
          </p>

          {aiError && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {aiError}
            </div>
          )}

          {/* Provider-level error (key missing, API down, etc.) */}
          {aiResult?.provider_error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              ⚠ {aiResult.provider_error}
            </div>
          )}

          {/* Rate limit message */}
          {aiResult?.rate_limited && (
            <div className="rounded-lg border border-orange-800/50 bg-orange-900/20 p-3 space-y-1">
              <p className="text-orange-400 text-sm font-medium">Лимит запросов</p>
              <p className="text-orange-300 text-xs">{aiResult.message}</p>
              {aiResult.cooldown_seconds_remaining && (
                <p className="text-orange-400 text-xs">
                  Подождите {aiResult.cooldown_seconds_remaining} сек.
                </p>
              )}
            </div>
          )}

          {aiConfirmMsg && !aiResult && (
            <p className="text-sm text-green-400">{aiConfirmMsg}</p>
          )}

          {aiResult?.status === 'not_operation' && !aiResult.provider_error && !aiResult.rate_limited && (
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
                <p className={`text-sm ${aiConfirmMsg.startsWith('Ошибка') ? 'text-red-400' : 'text-green-400'}`}>
                  {aiConfirmMsg}
                </p>
              )}

              {fundingRequired ? (
                <div className="flex justify-end">
                  <div className="w-full max-w-xs rounded-lg border border-amber-800/40 bg-amber-950/20 p-3 space-y-2">
                    <div>
                      <p className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
                        Недостаточно средств
                      </p>
                      <p className="text-sm font-bold text-white tabular-nums mt-0.5">
                        +{fmt(fundingRequired.missingCash)}&nbsp;{fundingRequired.currency}
                      </p>
                    </div>
                    <p className="text-xs text-gray-400 leading-relaxed">
                      Можно автоматически создать пополнение и провести операцию.
                    </p>
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={hasFee}
                        onChange={(e) => { setHasFee(e.target.checked); if (!e.target.checked) setDepositFee('') }}
                        className="w-3.5 h-3.5 accent-amber-500"
                      />
                      <span className="text-xs text-gray-300">Есть комиссия за пополнение</span>
                    </label>
                    {hasFee && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Комиссия пополнения</p>
                        <input
                          type="number"
                          value={depositFee}
                          onChange={(e) => setDepositFee(e.target.value)}
                          placeholder="Например, 50"
                          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-amber-600 transition-colors"
                        />
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 pt-0.5">
                      <button
                        onClick={() => handleAiConfirm(true)}
                        disabled={aiConfirming}
                        className="px-3 py-1.5 text-xs rounded bg-amber-700 hover:bg-amber-600 text-white disabled:opacity-50 transition-colors whitespace-nowrap"
                      >
                        {aiConfirming ? 'Сохраняю…' : 'Пополнить и провести'}
                      </button>
                      <button
                        onClick={() => { setFundingRequired(null); setDepositFee(''); setHasFee(false) }}
                        className="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-400 transition-colors"
                      >
                        Отмена
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAiConfirm(false)}
                    disabled={aiConfirming || !aiResult.account_id}
                    className="px-3 py-1.5 text-sm rounded-lg bg-green-700 hover:bg-green-600 text-white disabled:opacity-50 transition-colors"
                  >
                    {aiConfirming ? 'Сохраняю…' : 'Подтвердить операцию'}
                  </button>
                  <button
                    onClick={() => { setAiResult(null); setAiText(''); setAiConfirmMsg(null); setFundingRequired(null); setDepositFee(''); setHasFee(false) }}
                    className="px-3 py-1.5 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
                  >
                    Отмена
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* KPI cards */}
      {(() => {
        // total_capital = cash + positions (at cost) + physical assets estimated value (RUB only).
        // No double counting: cashBalances = uninvested cash; portfolio.total_cost = invested money at cost.
        // Physical assets are tracked separately via estimated_value (not in cash, not in positions).
        // TODO: subtract liabilities when the liabilities module is implemented.
        const totalCash = cashBalances.reduce((s, cb) => s + parseFloat(cb.balance), 0)
        const portfolioValue = summary ? parseFloat(summary.total_cost) : 0
        const physicalAssets = assetsList.filter(
          (a) => PHYSICAL_ASSET_TYPES.has(a.asset_type) && a.include_in_capital && a.currency === 'RUB' && a.estimated_value
        )
        const physicalValue = physicalAssets.reduce((s, a) => s + parseFloat(a.estimated_value!), 0)
        const totalCapital = totalCash + portfolioValue + physicalValue
        const nonRubPhysical = assetsList.filter(
          (a) => PHYSICAL_ASSET_TYPES.has(a.asset_type) && a.include_in_capital && a.currency !== 'RUB' && a.estimated_value
        )

        return (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <Card className="flex flex-col gap-1">
                <p className="text-xs text-gray-400 uppercase tracking-wider">API</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <StatusDot ok={health?.status === 'ok'} />
                  <span className="text-sm font-medium">{health?.status ?? '—'}</span>
                </div>
              </Card>
              <Card className="flex flex-col gap-1">
                <p className="text-xs text-gray-400 uppercase tracking-wider">База данных</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <StatusDot ok={health?.database === 'ok'} />
                  <span className="text-sm font-medium">{health?.database ?? '—'}</span>
                </div>
              </Card>
              <Card className="flex flex-col gap-1 lg:col-span-2">
                <p className="text-xs text-gray-400 uppercase tracking-wider">Итоговый капитал</p>
                <p className="text-xl font-bold tabular-nums mt-1">
                  {cashBalances.length > 0 || summary || physicalValue > 0 ? fmt(totalCapital) : '—'}
                </p>
                <div className="text-xs text-gray-600 space-y-0.5 mt-0.5">
                  <p>Деньги: {fmt(totalCash)}</p>
                  <p>Портфель: {fmt(portfolioValue)}</p>
                  {physicalValue > 0 && <p>Физ. активы: {fmt(physicalValue)}</p>}
                </div>
              </Card>
              <Card className="flex flex-col gap-1">
                <p className="text-xs text-gray-400 uppercase tracking-wider">Деньги</p>
                <p className={`text-xl font-bold tabular-nums mt-1 ${totalCash < 0 ? 'text-red-400' : ''}`}>
                  {cashBalances.length > 0 ? fmt(totalCash) : '—'}
                </p>
                <p className="text-xs text-gray-500">RUB · сумма по счетам</p>
              </Card>
              <Card className="flex flex-col gap-1">
                <p className="text-xs text-gray-400 uppercase tracking-wider">Инвестпортфель</p>
                <p className="text-xl font-bold tabular-nums mt-1">
                  {summary ? fmt(summary.total_cost) : '—'}
                </p>
                <p className="text-xs text-gray-500">RUB · по себестоимости</p>
              </Card>
            </div>
            {nonRubPhysical.length > 0 && (
              <div className="rounded-lg border border-amber-800/30 bg-amber-950/15 px-4 py-2.5 text-xs text-amber-400/80">
                Физические активы в иностранной валюте ({nonRubPhysical.map((a) => `${a.name} (${a.currency})`).join(', ')}) не включены в расчёт капитала — конвертация валют не поддерживается.
              </div>
            )}
          </>
        )
      })()}

      {/* Cash Balances */}
      {!loading && (
        <Card>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Остатки по счетам
          </h2>
          {cashBalances.length === 0 ? (
            <p className="text-sm text-gray-500">Нет остатков. Создайте счёт и добавьте операцию пополнения.</p>
          ) : (
            <div className="flex flex-wrap gap-x-6 gap-y-4">
              {cashBalances.map((cb) => {
                const accName = accounts.find((a) => a.id === cb.account_id)?.name ?? cb.account_id.slice(0, 8)
                return (
                  <div key={`${cb.account_id}-${cb.currency}`} className="min-w-[120px]">
                    <p className="text-xs font-medium text-gray-300 truncate max-w-[160px]">{accName}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{cb.currency}</p>
                    <p className={`text-lg font-bold tabular-nums mt-0.5 ${parseFloat(cb.balance) < 0 ? 'text-red-400' : 'text-white'}`}>
                      {fmt(cb.balance)}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {/* Interest Accruals */}
      {interestAccruals.length > 0 && (
        <Card>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Начисленные проценты
          </h2>
          <div className="flex flex-wrap gap-6">
            {interestAccruals.map((ia) => (
              <div key={ia.account_id} className="min-w-[160px]">
                <p className="text-xs text-gray-500 mb-0.5">{ia.account_name}</p>
                <p className="text-lg font-bold tabular-nums text-teal-400">
                  {fmt(ia.accrued_interest)}&nbsp;<span className="text-sm text-gray-400">{ia.currency}</span>
                </p>
                <p className="text-xs text-gray-600 mt-0.5">{ia.annual_rate_percent}% годовых</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Salary widget — shown when salary is due and not yet received */}
      {salaryDue?.is_due && !salaryDue.already_received && salaryDue.template && (
        <SalaryWidget
          template={salaryDue.template}
          accounts={accounts}
          onSuccess={() => {
            setRefreshKey((k) => k + 1)
            setSalaryDue((s) => s ? { ...s, already_received: true } : s)
          }}
        />
      )}

      {/* Budget summary for current month */}
      {budgetSummary && (
        <Card>
          <div className="flex items-baseline gap-2 mb-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
              Денежный поток месяца
            </h2>
            <span className="text-xs text-gray-600">
              {new Date().toLocaleString('ru-RU', { month: 'long', year: 'numeric' })}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            <BudgetLine label="Доход" value={budgetSummary.income_total} color="text-emerald-400" />
            <BudgetLine label="Расходы на жизнь" value={budgetSummary.living_expense_total} color="text-pink-400" negative />
            <BudgetLine label="Кредитные платежи" value={budgetSummary.credit_payment_total} color="text-orange-400" negative />
            <BudgetLine
              label="Свободный денежный поток"
              value={budgetSummary.free_cashflow}
              color={parseFloat(budgetSummary.free_cashflow) >= 0 ? 'text-emerald-400' : 'text-red-400'}
            />
            <BudgetLine label="Инвест. расходы" value={budgetSummary.investment_expense_total} color="text-yellow-400" negative />
            <BudgetLine label="Куплено активов" value={budgetSummary.invested_total} color="text-blue-400" negative />
            <BudgetLine label="Остаток на конец" value={budgetSummary.cash_end} color={parseFloat(budgetSummary.cash_end) < 0 ? 'text-red-400' : 'text-white'} />
            {budgetSummary.credit_principal_total !== '0.00' && (
              <BudgetLine label="из кредита: тело" value={budgetSummary.credit_principal_total} color="text-gray-400" />
            )}
          </div>
          {budgetSummary.has_reconciliation_warning && (
            <p className="mt-3 text-xs text-amber-400 bg-amber-950/20 border border-amber-800/30 rounded-lg px-3 py-2">
              Остаток отрицательный — возможно, не все операции введены.
            </p>
          )}
        </Card>
      )}

      {/* Chart + Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Структура портфеля
          </h2>
          {loading ? (
            <div className="h-52 flex items-center justify-center text-gray-500 text-sm">Loading…</div>
          ) : (
            <AllocationChart data={summary?.allocation ?? []} />
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Позиции
          </h2>
          {loading ? (
            <p className="text-sm text-gray-500">Загрузка…</p>
          ) : (summary?.positions ?? []).length === 0 ? (
            <p className="text-sm text-gray-500">Нет позиций. Создайте счёт, актив и добавьте операцию покупки.</p>
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

      {/* Income Modal */}
      {showIncomeModal && (
        <IncomeModal
          accounts={accounts}
          onClose={() => setShowIncomeModal(false)}
          onSuccess={() => {
            setShowIncomeModal(false)
            setIncomeSuccessMsg('Доход добавлен.')
            setRefreshKey((k) => k + 1)
            setTimeout(() => setIncomeSuccessMsg(null), 4000)
          }}
        />
      )}

      {/* Expense Modal */}
      {showExpenseModal && (
        <ExpenseModal
          accounts={accounts}
          assets={assetsList}
          onClose={() => setShowExpenseModal(false)}
          onSuccess={() => {
            setShowExpenseModal(false)
            setExpenseSuccessMsg('Расход добавлен.')
            setRefreshKey((k) => k + 1)
            setTimeout(() => setExpenseSuccessMsg(null), 4000)
          }}
        />
      )}

      {/* Transfer Modal */}
      {showTransferModal && (
        <TransferModal
          accounts={accounts}
          cashBalances={cashBalances}
          onClose={() => setShowTransferModal(false)}
          onSuccess={() => {
            setShowTransferModal(false)
            setTransferSuccessMsg('Перевод сохранён.')
            setRefreshKey((k) => k + 1)
            setTimeout(() => setTransferSuccessMsg(null), 4000)
          }}
        />
      )}

      {/* Recent Operations */}
      <Card>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Последние операции
        </h2>
        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : recentOps.length === 0 ? (
          <p className="text-sm text-gray-500">Операций пока нет.</p>
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
                  <th className="text-right pb-2">Fee</th>
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
                    <td className="py-2 font-mono text-xs text-blue-400">
                      {op.operation_type === 'deposit'
                        ? <span className="text-gray-400 not-italic">{incomeSourceLabel(op.income_source)}{op.income_source === 'other' && op.note ? `: ${op.note}` : ''}</span>
                        : (op.asset_id ? (assetMap[op.asset_id] ?? '—') : '—')}
                    </td>
                    <td className="py-2 text-right tabular-nums text-gray-300">
                      {op.quantity ? parseFloat(op.quantity).toLocaleString('ru-RU', { maximumFractionDigits: 4 }) : '—'}
                    </td>
                    <td className="py-2 text-right tabular-nums text-gray-300">
                      {op.price ? fmt(op.price) : '—'}
                    </td>
                    <td className="py-2 text-right tabular-nums text-gray-500">
                      {op.fee ? fmt(op.fee) : '—'}
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

import type { ExpenseGroup, OperationDraft, RecurringIncome } from '@/lib/types'

function BudgetLine({ label, value, color, negative }: { label: string; value: string; color: string; negative?: boolean }) {
  const n = parseFloat(value)
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-lg font-bold tabular-nums ${color}`}>
        {negative && n > 0 ? '−' : ''}{fmt(Math.abs(n))}
      </p>
    </div>
  )
}

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
      <PreviewField label="Тип" value={op.operation_type.replace(/_/g, ' ')} />
      {op.asset_ticker && (
        <PreviewField label="Актив" value={op.asset_name ? `${op.asset_ticker} · ${op.asset_name}` : op.asset_ticker} />
      )}
      {op.account_name && <PreviewField label="Счёт" value={op.account_name} />}
      {op.to_account_name && <PreviewField label="Счёт назначения" value={op.to_account_name} />}
      {op.quantity && <PreviewField label="Кол-во" value={op.quantity} />}
      {op.price && <PreviewField label="Цена" value={op.price} />}
      {op.amount && <PreviewField label="Сумма" value={op.amount} />}
      {op.fee && <PreviewField label="Комиссия" value={op.fee} />}
      <PreviewField label="Валюта" value={op.currency} />
      {op.expense_group && <PreviewField label="Группа расхода" value={op.expense_group} />}
      {op.expense_category && <PreviewField label="Категория" value={op.expense_category} />}
      {op.merchant && <PreviewField label="Получатель" value={op.merchant} />}
      {op.income_source && <PreviewField label="Источник дохода" value={op.income_source} />}
      {op.principal_amount && <PreviewField label="Тело долга" value={op.principal_amount} />}
      {op.interest_amount && <PreviewField label="Проценты" value={op.interest_amount} />}
      {op.linked_asset_text && <PreviewField label="Кредит/актив" value={op.linked_asset_text} />}
      {op.note && <PreviewField label="Заметка" value={op.note} />}
    </div>
  )
}

const OP_TYPE_COLORS: Record<string, string> = {
  buy: 'text-green-400 bg-green-900/30',
  sell: 'text-red-400 bg-red-900/30',
  deposit: 'text-emerald-400 bg-emerald-900/30',
  withdraw: 'text-orange-400 bg-orange-900/30',
  dividend: 'text-teal-400 bg-teal-900/30',
  coupon: 'text-teal-400 bg-teal-900/30',
  fee: 'text-yellow-400 bg-yellow-900/30',
  tax: 'text-rose-400 bg-rose-900/30',
  manual_valuation: 'text-purple-400 bg-purple-900/30',
  expense: 'text-pink-400 bg-pink-900/30',
  transfer: 'text-indigo-400 bg-indigo-900/30',
}

const OP_TYPE_LABELS: Record<string, string> = {
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

function OpTypeBadge({ type }: { type: string }) {
  const colors = OP_TYPE_COLORS[type] ?? 'text-gray-400 bg-gray-800'
  const label = OP_TYPE_LABELS[type] ?? type.replace('_', ' ')
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {label}
    </span>
  )
}

// ── Income Modal ──────────────────────────────────────────────────────────────

const _inputCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors'
const _selectCls =
  'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors'
const _labelCls = 'block text-xs text-gray-400 mb-1.5'

function nowLocal() {
  const d = new Date()
  d.setSeconds(0, 0)
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

interface IncomeFormState {
  account_id: string
  amount: string
  currency: string
  income_source: string
  note: string
  hasFee: boolean
  fee: string
  operated_at: string
}

function IncomeModal({
  accounts,
  onClose,
  onSuccess,
}: {
  accounts: Account[]
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState<IncomeFormState>({
    account_id: preferCashBankAccount(accounts),
    amount: '',
    currency: 'RUB',
    income_source: 'salary',
    note: '',
    hasFee: false,
    fee: '',
    operated_at: nowLocal(),
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof IncomeFormState>(key: K, value: IncomeFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!form.account_id) { setError('Выберите счёт'); return }
    const amt = parseFloat(form.amount)
    if (!form.amount || isNaN(amt) || amt <= 0) { setError('Введите положительную сумму'); return }
    if (!form.income_source) { setError('Выберите источник дохода'); return }
    if (form.income_source === 'other' && !form.note.trim()) { setError('Укажите источник дохода'); return }
    if (form.hasFee) {
      const feeAmt = parseFloat(form.fee)
      if (!form.fee || isNaN(feeAmt) || feeAmt < 0) { setError('Введите корректную комиссию'); return }
    }

    const payload: Record<string, unknown> = {
      account_id: form.account_id,
      operation_type: 'deposit',
      amount: form.amount,
      currency: form.currency,
      income_source: form.income_source,
      note: form.note.trim() || null,
      operated_at: new Date(form.operated_at).toISOString(),
    }
    if (form.hasFee && form.fee) payload.fee = form.fee

    setSubmitting(true)
    try {
      await api.operations.create(payload)
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при сохранении')
    } finally {
      setSubmitting(false)
    }
  }

  const isOther = form.income_source === 'other'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-base font-semibold text-white">Ввести доход</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Account */}
          <div>
            <label className={_labelCls}>Счёт *</label>
            <select
              value={form.account_id}
              onChange={(e) => set('account_id', e.target.value)}
              className={_selectCls}
            >
              <option value="">— выберите счёт —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
              ))}
            </select>
          </div>

          {/* Amount + Currency */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className={_labelCls}>Сумма *</label>
              <input
                type="number"
                step="any"
                min="0.01"
                placeholder="Например, 100 000"
                value={form.amount}
                onChange={(e) => set('amount', e.target.value)}
                className={_inputCls}
              />
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

          {/* Income source */}
          <div>
            <label className={_labelCls}>Источник дохода *</label>
            <select
              value={form.income_source}
              onChange={(e) => { set('income_source', e.target.value); set('note', '') }}
              className={_selectCls}
            >
              {INCOME_SOURCES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Sale helper */}
          {form.income_source === 'sale' && (
            <p className="text-xs text-amber-400/80 leading-relaxed bg-amber-950/20 border border-amber-800/30 rounded-lg px-3 py-2">
              Если это имущество уже добавлено как актив, оформите продажу через операцию продажи актива, а не как доход.
            </p>
          )}

          {/* Interest helper */}
          {form.income_source === 'interest' && (
            <p className="text-xs text-teal-400/80 leading-relaxed bg-teal-950/20 border border-teal-800/30 rounded-lg px-3 py-2">
              Для автоматического расчёта процентов по вкладам и накопительным счетам настройте ставку на странице Счетов.
            </p>
          )}

          {/* Custom source (other) or general note */}
          <div>
            <label className={_labelCls}>
              {isOther ? 'Укажите источник *' : 'Комментарий'}
            </label>
            <input
              type="text"
              placeholder={isOther ? 'Например: продал велосипед' : 'Необязательно'}
              value={form.note}
              onChange={(e) => set('note', e.target.value)}
              className={_inputCls}
            />
          </div>

          {/* Fee checkbox + input */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.hasFee}
                onChange={(e) => { set('hasFee', e.target.checked); if (!e.target.checked) set('fee', '') }}
                className="w-3.5 h-3.5 accent-blue-500"
              />
              <span className="text-xs text-gray-300">Есть комиссия</span>
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

          {/* Date */}
          <div>
            <label className={_labelCls}>Дата и время</label>
            <input
              type="datetime-local"
              value={form.operated_at}
              onChange={(e) => set('operated_at', e.target.value)}
              className={_inputCls}
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 text-sm rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Сохраняю…' : 'Добавить'}
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

// ── Expense Modal ─────────────────────────────────────────────────────────────

const EXPENSE_GROUPS: { value: ExpenseGroup; label: string }[] = [
  { value: 'living', label: 'Повседневные расходы' },
  { value: 'investment', label: 'Инвестиционные расходы' },
  { value: 'credit', label: 'Кредитный платёж' },
]

interface ExpenseFormState {
  account_id: string
  amount: string
  currency: string
  expense_group: ExpenseGroup
  expense_category: string
  merchant: string
  hasFee: boolean
  fee: string
  principal_amount: string
  interest_amount: string
  liability_name: string
  linked_asset_id: string
  note: string
  operated_at: string
}

function ExpenseModal({
  accounts,
  assets,
  onClose,
  onSuccess,
}: {
  accounts: Account[]
  assets: Asset[]
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState<ExpenseFormState>({
    account_id: preferCashBankAccount(accounts),
    amount: '',
    currency: 'RUB',
    expense_group: 'living',
    expense_category: '',
    merchant: '',
    hasFee: false,
    fee: '',
    principal_amount: '',
    interest_amount: '',
    liability_name: '',
    linked_asset_id: '',
    note: '',
    operated_at: nowLocal(),
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [breakdownWarning, setBreakdownWarning] = useState<string | null>(null)

  function set<K extends keyof ExpenseFormState>(key: K, value: ExpenseFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  const isCredit = form.expense_group === 'credit'
  const hasBreakdown = isCredit && (form.principal_amount || form.interest_amount)

  function checkBreakdown(f: ExpenseFormState) {
    if (!isCredit || (!f.principal_amount && !f.interest_amount)) {
      setBreakdownWarning(null)
      return
    }
    const amount = parseFloat(f.amount) || 0
    const principal = parseFloat(f.principal_amount) || 0
    const interest = parseFloat(f.interest_amount) || 0
    const fee = f.hasFee ? (parseFloat(f.fee) || 0) : 0
    const diff = Math.abs(amount - principal - interest - fee)
    if (diff > 0.01) {
      setBreakdownWarning(`Не сходится: ${principal.toFixed(2)} + ${interest.toFixed(2)} + ${fee.toFixed(2)} = ${(principal + interest + fee).toFixed(2)}, сумма = ${amount.toFixed(2)}`)
    } else {
      setBreakdownWarning(null)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!form.account_id) { setError('Выберите счёт'); return }
    const amt = parseFloat(form.amount)
    if (!form.amount || isNaN(amt) || amt <= 0) { setError('Введите положительную сумму'); return }
    if (form.hasFee) {
      const feeAmt = parseFloat(form.fee)
      if (!form.fee || isNaN(feeAmt) || feeAmt < 0) { setError('Введите корректную комиссию'); return }
    }
    if (breakdownWarning) { setError('Исправьте разбивку кредитного платежа'); return }

    const payload: Record<string, unknown> = {
      account_id: form.account_id,
      operation_type: 'expense',
      amount: form.amount,
      currency: form.currency,
      expense_group: form.expense_group,
      expense_category: form.expense_category.trim() || null,
      merchant: form.merchant.trim() || null,
      note: form.note.trim() || null,
      operated_at: new Date(form.operated_at).toISOString(),
    }
    if (form.hasFee && form.fee) payload.fee = form.fee
    if (isCredit) {
      if (form.principal_amount) payload.principal_amount = form.principal_amount
      if (form.interest_amount) payload.interest_amount = form.interest_amount
      if (form.liability_name) payload.liability_name = form.liability_name.trim()
      if (form.linked_asset_id) payload.linked_asset_id = form.linked_asset_id
    }

    setSubmitting(true)
    try {
      await api.operations.create(payload)
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
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 sticky top-0 bg-gray-900">
          <h2 className="text-base font-semibold text-white">Ввести расход</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-3 text-red-400 text-sm">{error}</div>
          )}

          {/* Account */}
          <div>
            <label className={_labelCls}>Счёт *</label>
            <select value={form.account_id} onChange={(e) => set('account_id', e.target.value)} className={_selectCls}>
              <option value="">— выберите счёт —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
              ))}
            </select>
          </div>

          {/* Expense group */}
          <div>
            <label className={_labelCls}>Тип расхода *</label>
            <select
              value={form.expense_group}
              onChange={(e) => { set('expense_group', e.target.value as ExpenseGroup); setBreakdownWarning(null) }}
              className={_selectCls}
            >
              {EXPENSE_GROUPS.map((g) => (
                <option key={g.value} value={g.value}>{g.label}</option>
              ))}
            </select>
          </div>

          {/* Amount + Currency */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className={_labelCls}>Сумма *</label>
              <input
                type="number"
                step="any"
                min="0.01"
                placeholder="Например, 3 500"
                value={form.amount}
                onChange={(e) => { set('amount', e.target.value); checkBreakdown({ ...form, amount: e.target.value }) }}
                className={_inputCls}
              />
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

          {/* Credit breakdown */}
          {isCredit && (
            <div className="space-y-3 rounded-lg border border-orange-800/30 bg-orange-950/10 p-3">
              <p className="text-xs text-orange-400/80">Разбивка кредитного платежа (необязательно)</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={_labelCls}>Тело долга</label>
                  <input
                    type="number"
                    step="any"
                    min="0"
                    placeholder="Например, 4 500"
                    value={form.principal_amount}
                    onChange={(e) => { set('principal_amount', e.target.value); checkBreakdown({ ...form, principal_amount: e.target.value }) }}
                    className={_inputCls}
                  />
                </div>
                <div>
                  <label className={_labelCls}>Проценты</label>
                  <input
                    type="number"
                    step="any"
                    min="0"
                    placeholder="Например, 500"
                    value={form.interest_amount}
                    onChange={(e) => { set('interest_amount', e.target.value); checkBreakdown({ ...form, interest_amount: e.target.value }) }}
                    className={_inputCls}
                  />
                </div>
              </div>
              <div>
                <label className={_labelCls}>Название кредита</label>
                <input
                  type="text"
                  placeholder="Например, Ипотека Сбер"
                  value={form.liability_name}
                  onChange={(e) => set('liability_name', e.target.value)}
                  className={_inputCls}
                />
              </div>
              {/* Linked asset (optional) — show credit-linked and physical assets first */}
              {(() => {
                const creditAssets = assets.filter((a) => a.is_credit_linked || PHYSICAL_ASSET_TYPES.has(a.asset_type))
                const otherAssets = assets.filter((a) => !a.is_credit_linked && !PHYSICAL_ASSET_TYPES.has(a.asset_type))
                return (
                  <div>
                    <label className={_labelCls}>За что платёж?</label>
                    <select
                      value={form.linked_asset_id}
                      onChange={(e) => set('linked_asset_id', e.target.value)}
                      className={_selectCls}
                    >
                      <option value="">— Продолжить без привязки —</option>
                      {creditAssets.length > 0 && (
                        <optgroup label="Кредитные / физические активы">
                          {creditAssets.map((a) => (
                            <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
                          ))}
                        </optgroup>
                      )}
                      {otherAssets.length > 0 && (
                        <optgroup label="Прочие активы">
                          {otherAssets.map((a) => (
                            <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
                          ))}
                        </optgroup>
                      )}
                    </select>
                    {!form.linked_asset_id && (
                      <p className="text-xs text-gray-600 mt-1">
                        Необязательно. Привяжите к активу (напр., ипотека → квартира).
                      </p>
                    )}
                  </div>
                )
              })()}
              {breakdownWarning && (
                <p className="text-xs text-amber-400">{breakdownWarning}</p>
              )}
              {hasBreakdown && !breakdownWarning && (
                <p className="text-xs text-gray-500">
                  Тело долга не считается расходом — только проценты и комиссии.
                </p>
              )}
            </div>
          )}

          {/* Category + Merchant */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={_labelCls}>Категория</label>
              <input
                type="text"
                placeholder={isCredit ? 'Напр., ипотека' : 'Напр., продукты'}
                value={form.expense_category}
                onChange={(e) => set('expense_category', e.target.value)}
                className={_inputCls}
              />
            </div>
            <div>
              <label className={_labelCls}>Магазин / получатель</label>
              <input
                type="text"
                placeholder="Необязательно"
                value={form.merchant}
                onChange={(e) => set('merchant', e.target.value)}
                className={_inputCls}
              />
            </div>
          </div>

          {/* Fee */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.hasFee}
                onChange={(e) => { set('hasFee', e.target.checked); if (!e.target.checked) set('fee', '') }}
                className="w-3.5 h-3.5 accent-blue-500"
              />
              <span className="text-xs text-gray-300">Есть комиссия</span>
            </label>
            {form.hasFee && (
              <input
                type="number"
                step="any"
                min="0"
                placeholder="Например, 50"
                value={form.fee}
                onChange={(e) => { set('fee', e.target.value); checkBreakdown({ ...form, fee: e.target.value }) }}
                className={_inputCls}
              />
            )}
          </div>

          {/* Note */}
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

          {/* Date */}
          <div>
            <label className={_labelCls}>Дата и время</label>
            <input
              type="datetime-local"
              value={form.operated_at}
              onChange={(e) => set('operated_at', e.target.value)}
              className={_inputCls}
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={submitting || !!breakdownWarning}
              className="flex-1 px-4 py-2 text-sm rounded-lg bg-pink-800 hover:bg-pink-700 text-white disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Сохраняю…' : 'Добавить расход'}
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

// ── Salary Widget ─────────────────────────────────────────────────────────────

function SalaryWidget({
  template,
  accounts,
  onSuccess,
}: {
  template: RecurringIncome
  accounts: Account[]
  onSuccess: () => void
}) {
  const [amount, setAmount] = useState(template.amount)
  const [accountId, setAccountId] = useState(template.account_id)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  const accountName = accounts.find((a) => a.id === accountId)?.name ?? '—'

  async function handleConfirm() {
    setError(null)
    const amt = parseFloat(amount)
    if (isNaN(amt) || amt <= 0) { setError('Введите положительную сумму'); return }

    setSubmitting(true)
    try {
      await api.operations.create({
        account_id: accountId,
        operation_type: 'deposit',
        amount,
        currency: 'RUB',
        income_source: template.income_source,
        note: template.name,
        operated_at: new Date().toISOString(),
      })
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка при сохранении')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-xl border border-emerald-800/50 bg-emerald-950/20 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-emerald-400 text-lg">💰</span>
            <p className="text-sm font-semibold text-emerald-300">
              Подтвердить получение: {template.name}
            </p>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            Ожидается {new Date().toLocaleString('ru-RU', { month: 'long' })}. Подтвердите сумму и счёт.
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Сумма</label>
              <input
                type="number"
                step="any"
                min="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white w-36 focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Счёт</label>
              <select
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-emerald-500 transition-colors"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleConfirm}
              disabled={submitting}
              className="px-4 py-1.5 text-sm rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Сохраняю…' : 'Подтвердить'}
            </button>
          </div>

          {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-gray-600 hover:text-gray-400 text-xl leading-none shrink-0"
          title="Скрыть"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
