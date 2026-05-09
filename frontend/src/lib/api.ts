import type {
  Account,
  AccountInterestSettings,
  Asset,
  BudgetSummary,
  CashBalance,
  ConfirmWithFundingResponse,
  DepositSummary,
  ExpensesByCategory,
  InterestAccrual,
  Operation,
  ParseResponse,
  Position,
  AllocationItem,
  PortfolioSummary,
  HealthStatus,
  RecurringIncome,
  SalaryDue,
  SeedResult,
} from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = (body as { detail?: string }).detail
    throw new Error(detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<HealthStatus>('/api/v1/health'),

  seed: () => request<SeedResult>('/api/v1/seed/dev-data', { method: 'POST' }),

  accounts: {
    list: () => request<Account[]>('/api/v1/accounts'),
    create: (data: { name: string; account_type: string; currency: string }) =>
      request<Account>('/api/v1/accounts', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: { name?: string }) =>
      request<Account>(`/api/v1/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/api/v1/accounts/${id}`, { method: 'DELETE' }),
    interestSettings: (id: string) =>
      request<AccountInterestSettings>(`/api/v1/accounts/${id}/interest-settings`),
    setInterestSettings: (id: string, data: Partial<AccountInterestSettings>) =>
      request<AccountInterestSettings>(`/api/v1/accounts/${id}/interest-settings`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
  },

  assets: {
    list: () => request<Asset[]>('/api/v1/assets'),
    create: (data: Record<string, unknown>) =>
      request<Asset>('/api/v1/assets', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      request<Asset>(`/api/v1/assets/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/api/v1/assets/${id}`, { method: 'DELETE' }),
  },

  operations: {
    list: () => request<Operation[]>('/api/v1/operations'),
    create: (data: Record<string, unknown>) =>
      request<Operation>('/api/v1/operations', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<void>(`/api/v1/operations/${id}`, { method: 'DELETE' }),
    transfer: (data: {
      from_account_id: string
      to_account_id: string
      amount: string
      currency: string
      operated_at: string
      fee?: string | null
      note?: string | null
    }) =>
      request<Operation>('/api/v1/operations/transfer', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Record<string, unknown>) =>
      request<Operation>(`/api/v1/operations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    updateTransfer: (id: string, data: Record<string, unknown>) =>
      request<Operation>(`/api/v1/operations/transfer/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    confirmWithFunding: (data: {
      operation: Record<string, unknown>
      force_funding: boolean
      deposit_fee?: string | null
    }) =>
      request<ConfirmWithFundingResponse>('/api/v1/operations/confirm-with-funding', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  portfolio: {
    summary: () => request<PortfolioSummary>('/api/v1/portfolio/summary'),
    positions: () => request<Position[]>('/api/v1/portfolio/positions'),
    allocation: () => request<AllocationItem[]>('/api/v1/portfolio/allocation'),
    cashBalances: () => request<CashBalance[]>('/api/v1/portfolio/cash-balances'),
    interestAccruals: (asOf?: string) =>
      request<InterestAccrual[]>(
        `/api/v1/portfolio/interest-accruals${asOf ? `?as_of=${asOf}` : ''}`
      ),
    deposits: (asOf?: string) =>
      request<DepositSummary[]>(
        `/api/v1/portfolio/deposits${asOf ? `?as_of=${asOf}` : ''}`
      ),
  },

  budget: {
    summary: (from: string, to: string) =>
      request<BudgetSummary>(`/api/v1/budget/summary?from=${from}&to=${to}`),
    expensesByCategory: (from: string, to: string) =>
      request<ExpensesByCategory>(`/api/v1/budget/expenses-by-category?from=${from}&to=${to}`),
    salaryDue: () => request<SalaryDue>('/api/v1/budget/salary-due'),
    setRecurringIncome: (data: {
      name: string
      account_id: string
      amount: string
      income_source: string
      day_of_month: number
      is_active: boolean
    }) =>
      request<RecurringIncome>('/api/v1/budget/recurring-income', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getRecurringIncome: () => request<RecurringIncome[]>('/api/v1/budget/recurring-income'),
  },

  ai: {
    parse: (text: string) =>
      request<ParseResponse>('/api/v1/ai/parse-operation', {
        method: 'POST',
        body: JSON.stringify({ text }),
      }),
  },
}
