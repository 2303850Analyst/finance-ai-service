export type AccountType = 'broker' | 'bank' | 'crypto' | 'cash' | 'deposit' | 'other'
export type AssetType =
  | 'stock'
  | 'bond'
  | 'etf'
  | 'currency'
  | 'cash'
  | 'deposit'
  | 'crypto'
  | 'real_estate'
  | 'other'
export type OperationType =
  | 'buy'
  | 'sell'
  | 'deposit'
  | 'withdraw'
  | 'dividend'
  | 'coupon'
  | 'fee'
  | 'tax'
  | 'manual_valuation'
export type OperationStatus = 'pending' | 'confirmed' | 'cancelled' | 'rejected'

export interface Account {
  id: string
  name: string
  account_type: AccountType
  currency: string
  created_at: string
}

export interface Asset {
  id: string
  ticker: string
  name: string
  asset_type: AssetType
  currency: string
}

export interface Operation {
  id: string
  account_id: string
  asset_id: string | null
  operation_type: OperationType
  status: OperationStatus
  quantity: string | null
  price: string | null
  amount: string
  currency: string
  operated_at: string
  note: string | null
  created_at: string
}

export interface Position {
  id: string
  account_id: string
  asset_id: string
  ticker: string
  asset_name: string
  asset_type: AssetType
  quantity: string
  average_price: string
  total_cost: string
}

export interface AllocationItem {
  asset_type: AssetType
  total_cost: string
  percentage: number
}

export interface PortfolioSummary {
  total_cost: string
  positions_count: number
  positions: Position[]
  allocation: AllocationItem[]
}

export interface HealthStatus {
  status: string
  database: string
}

export interface SeedResult {
  user: string
  accounts_created: string[]
  assets_created: string[]
}

export interface OperationDraft {
  operation_type: string
  account_name: string | null
  asset_ticker: string | null
  asset_name: string | null
  quantity: string | null
  price: string | null
  amount: string | null
  fee: string | null
  currency: string
  operated_at: string
}

export interface ParseResponse {
  status: 'parsed' | 'need_clarification' | 'not_operation'
  raw_text: string
  operation: OperationDraft | null
  account_id: string | null
  asset_id: string | null
  warnings: string[]
  missing_fields: string[]
  message: string | null
}

export const ACCOUNT_TYPES: AccountType[] = ['broker', 'bank', 'crypto', 'cash', 'deposit', 'other']
export const ASSET_TYPES: AssetType[] = [
  'stock', 'bond', 'etf', 'currency', 'cash', 'deposit', 'crypto', 'real_estate', 'other',
]
export const OPERATION_TYPES: OperationType[] = [
  'buy', 'sell', 'deposit', 'withdraw', 'dividend', 'coupon', 'fee', 'tax', 'manual_valuation',
]
