export type Account = { id: string; name: string; account_type: string; currency: string; cash_balance?: string }
export type Asset = { id: string; name: string; ticker: string | null }
export type Operation = {
  account_id: string; operation_type: string; amount: string; operated_at: string;
  [key: string]: string | boolean | null
}
export type Draft = { id: string; state: string; revision: number; operation: Operation; raw_text: string; warnings: string[]; expires_at: string; operation_id: string | null }
export type ReportSpec = { intent: string; date_from: string; date_to: string; account_name: string | null }
export type Report = { spec: ReportSpec; title: string; currency: string; rows: Record<string, string>[]; series: { key: string; label: string }[]; totals?: Record<string,string>; explanation: string; empty: boolean }
export type Overview = { cash: string; cash_as_of: string; income: string; living: string; credit: string; investment: string; free: string; count: number; recent: Operation[] }
export type Bootstrap = { accounts: Account[]; assets: Asset[]; bot_username: string }

export class MiniApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

export async function miniRequest<T>(initData: string, path: string, body?: unknown, method?: string): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), body && path === '/drafts/parse' ? 150000 : 65000)
  try {
    const response = await fetch('/api/v1/miniapp' + path, { method: method || (body ? 'POST' : 'GET'),
      headers: { Authorization: 'tma ' + initData, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined, cache: 'no-store', signal: controller.signal })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = data.detail
      const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x: { loc?: string[]; msg?: string }) => `${x.loc?.slice(1).join('.') || 'Поле'}: ${x.msg || 'Проверьте значение'}`).join('; ') : 'Не удалось выполнить запрос. Попробуйте ещё раз.'
      throw new MiniApiError(message, response.status)
    }
    return data as T
  } catch (error) {
    if (error instanceof MiniApiError) throw error
    throw new MiniApiError('Нет ответа от сервиса. Проверьте связь и повторите попытку.', 0)
  } finally { clearTimeout(timeout) }
}

export function moscowDate(value = new Date()): string {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(value)
  return ['year', 'month', 'day'].map(key => parts.find(p => p.type === key)?.value).join('-')
}
export function money(value: string | number) { return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value)) + ' ₽' }
export const operationLabels: Record<string, string> = { expense: 'Расход', deposit: 'Пополнение', withdraw: 'Снятие', buy: 'Покупка', sell: 'Продажа', dividend: 'Дивиденды', coupon: 'Купон', fee: 'Комиссия', tax: 'Налог', transfer: 'Перевод', manual_valuation: 'Переоценка' }
export function operationLabel(operation: Operation) { return operation.operation_type === 'deposit' && operation.income_source ? 'Доход' : operationLabels[operation.operation_type] || operation.operation_type }
