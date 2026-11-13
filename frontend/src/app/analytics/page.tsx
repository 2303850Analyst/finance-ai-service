'use client'

import { FormEvent, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import { request } from '@/lib/api'

type Report = {
  title: string; explanation: string; empty: boolean
  spec: { date_from: string; date_to: string; account_name: string | null }
  series: { key: string; label: string }[]
  rows: Record<string, string>[]
}
const examples = ['Расходы по категориям за этот месяц', 'Денежный поток за последние 6 месяцев', 'Дивиденды за этот год', 'Структура портфеля по счетам']
const colors = ['#38bdf8', '#fb923c', '#c084fc', '#f87171', '#34d399']
const fmt = (v: string | number) => Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 2 })

export default function Analytics() {
  const [question, setQuestion] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function run(text: string) {
    if (busy || !text.trim()) return
    setQuestion(text); setBusy(true); setError(''); setReport(null)
    try { setReport(await request<Report>('/api/v1/analytics/query', { method: 'POST', body: JSON.stringify({ question: text }) })) }
    catch (e) { setError(e instanceof Error ? e.message : 'Не удалось построить отчёт') }
    finally { setBusy(false) }
  }
  function submit(e: FormEvent) { e.preventDefault(); void run(question) }
  return <div className="max-w-6xl space-y-6 p-4 sm:p-6">
    <div><h1 className="text-2xl font-semibold">Аналитика по вашему вопросу</h1>
      <p className="mt-2 text-gray-400">Спросите о расходах, денежном потоке, дивидендах или структуре портфеля. Суммы рассчитает сервис по подтверждённым операциям.</p></div>
    <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3">
      <input aria-label="Вопрос для аналитики" value={question} onChange={e => setQuestion(e.target.value)} maxLength={2000}
        placeholder="Например: расходы по категориям за прошлый месяц" className="flex-1 min-w-0 bg-gray-900 border border-gray-700 rounded-lg p-3" />
      <button disabled={busy || question.trim().length < 3} className="bg-blue-600 rounded-lg px-5 py-3 disabled:opacity-50">{busy ? 'Строю отчёт...' : 'Построить отчёт'}</button>
    </form>
    <div className="flex flex-wrap gap-2">{examples.map(q => <button key={q} disabled={busy} onClick={() => void run(q)} className="text-sm border border-gray-700 rounded-full px-3 py-2 hover:bg-gray-800 disabled:opacity-50">{q}</button>)}</div>
    {error && <p role="alert" className="bg-red-950/40 text-red-300 rounded-lg p-4">{error}</p>}
    {busy && <p role="status" className="text-gray-400">Уточняю параметры вопроса и считаю данные...</p>}
    {report && <section className="space-y-5 border border-gray-800 rounded-xl p-4 sm:p-6">
      <div><h2 className="text-xl font-semibold">{report.title}</h2><p className="text-sm text-gray-400 mt-1">{report.spec.date_from} - {report.spec.date_to} · {report.spec.account_name || 'Все счета'} · RUB</p></div>
      {report.empty ? <p className="py-8 text-gray-400">За выбранный период нет данных для этого отчёта. Добавьте операции или измените период.</p> : <>
        <div className="h-80 w-full" aria-label="Диаграмма отчёта">
          <ResponsiveContainer width="100%" height="100%"><BarChart data={report.rows.map(row => Object.fromEntries(Object.entries(row).map(([k, v]) => [k, k === 'label' ? v : Number(v)])))}>
            <CartesianGrid stroke="#374151" vertical={false}/><XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 11 }}/><YAxis stroke="#9ca3af"/>
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} formatter={(value: number) => `${fmt(value)} RUB`} /><Legend/>
            {report.series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.label} fill={colors[i % colors.length]} radius={[3, 3, 0, 0]}/>)}
          </BarChart></ResponsiveContainer>
        </div>
        <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Точные значения отчёта в рублях</caption><thead><tr className="border-b border-gray-700"><th className="text-left py-3">Период / категория</th>{report.series.map(s => <th key={s.key} className="text-right px-3">{s.label}</th>)}</tr></thead>
          <tbody>{report.rows.map((row, i) => <tr key={i} className="border-b border-gray-800"><td className="py-3">{row.label}</td>{report.series.map(s => <td key={s.key} className="text-right px-3 tabular-nums">{fmt(row[s.key])}</td>)}</tr>)}</tbody></table></div>
      </>}
      <p className="text-sm text-gray-400">{report.explanation}</p>
    </section>}
    <p className="text-xs text-gray-500">Первая версия: период до года, рубли, фильтр по точному названию счёта. Рыночные котировки, прогнозы и инвестиционные рекомендации не поддерживаются.</p>
  </div>
}
