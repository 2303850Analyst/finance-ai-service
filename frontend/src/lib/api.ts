import type {
  Account,
  Asset,
  Operation,
  Position,
  AllocationItem,
  PortfolioSummary,
  HealthStatus,
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
  },

  assets: {
    list: () => request<Asset[]>('/api/v1/assets'),
    create: (data: { ticker: string; name: string; asset_type: string; currency: string }) =>
      request<Asset>('/api/v1/assets', { method: 'POST', body: JSON.stringify(data) }),
  },

  operations: {
    list: () => request<Operation[]>('/api/v1/operations'),
    create: (data: Record<string, unknown>) =>
      request<Operation>('/api/v1/operations', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<void>(`/api/v1/operations/${id}`, { method: 'DELETE' }),
  },

  portfolio: {
    summary: () => request<PortfolioSummary>('/api/v1/portfolio/summary'),
    positions: () => request<Position[]>('/api/v1/portfolio/positions'),
    allocation: () => request<AllocationItem[]>('/api/v1/portfolio/allocation'),
  },
}
