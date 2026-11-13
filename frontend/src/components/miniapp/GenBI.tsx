'use client'
import { useState } from 'react'
import { money, Report, ReportSpec } from '@/lib/miniapp-api'
type API = <T>(path: string, body?: unknown, method?: string) => Promise<T>
const presets = [{intent:'expenses_by_category',title:'Расходы по категориям'},{intent:'monthly_cashflow',title:'Денежный поток'},{intent:'dividends_over_time',title:'Дивиденды и купоны'},{intent:'allocation_by_account',title:'Портфель по счетам'},{intent:'allocation_by_asset_type',title:'Портфель по видам активов'}]

export default function GenBI({ api, filters }: { api: API; filters: Omit<ReportSpec,'intent'> }) {
  const [report,setReport]=useState<Report|null>(null)
  const [question,setQuestion]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [series,setSeries]=useState('')
  const [showTable,setShowTable]=useState(false)
  async function request(intent?:string) {
    if(busy || (!intent && question.trim().length<3)) return
    setBusy(true);setError('')
    try {
      const result=await api<Report>(intent?'/reports':'/query',intent?{...filters,intent}:{question,context:report?.spec||null})
      setReport(result);setSeries(result.series.find(s=>s.key==='free')?.key||result.series[0].key);setShowTable(false);setQuestion('')
    } catch(e) {setError(e instanceof Error?e.message:'Не удалось построить отчёт')}
    finally{setBusy(false)}
  }
  const selected=report?.series.find(s=>s.key===series)||report?.series[0]
  const maximum=report?Math.max(...report.rows.map(row=>Math.abs(Number(row[selected?.key||'value']))),1):1
  return <div><p className="mini-eyebrow">GenBI</p><h1>{report?'Разберите свои финансы':'Спросите о финансах'}</h1>
    {!report && <p className="mini-hint">Выберите готовый отчёт или задайте вопрос. Расчёты основаны на подтверждённых операциях.</p>}
    {report && <section aria-label="Результат отчёта"><h2>{report.title}</h2><p className="mini-filter-caption">{report.spec.date_from} - {report.spec.date_to} · {report.spec.account_name||'Все счета'}</p>
      {report.series.length>1 && <div className="mini-field"><label htmlFor="report-series">Показатель на графике</label><select id="report-series" value={series} onChange={e=>setSeries(e.target.value)}>{report.series.map(s=><option key={s.key} value={s.key}>{s.label}</option>)}</select></div>}
      {report.empty?<div className="mini-note"><h3>Нет данных за этот период</h3><p>Измените период или добавьте и подтвердите операцию.</p></div>:<>
        {report.totals?.[selected?.key||'value']!=null && <div className="mini-metric"><p>{selected?.label}</p><strong>{money(report.totals[selected?.key||'value'])}</strong></div>}
        <ul className="mini-chart" aria-label={`${report.title}: ${selected?.label}`}>{report.rows.map((row,i)=><li key={i}><div><span>{row.label}</span><strong>{money(row[selected?.key||'value'])}</strong></div><div className="mini-bar-track" aria-hidden="true"><div className={Number(row[selected?.key||'value'])<0?'negative':''} style={{width:`${Math.abs(Number(row[selected?.key||'value']))/maximum*100}%`}} /></div></li>)}</ul>
      </>}
      <button type="button" className="quiet" onClick={()=>setShowTable(!showTable)} aria-expanded={showTable}>{showTable?'Скрыть таблицу':'Точные значения'}</button>
      {showTable&&<div className="mini-table-scroll" tabIndex={0} role="region" aria-label="Точные значения отчёта"><table><caption>{report.title}, RUB</caption><thead><tr><th scope="col">Период / группа</th>{report.series.map(s=><th scope="col" key={s.key}>{s.label}</th>)}</tr></thead><tbody>{report.rows.map((row,i)=><tr key={i}><th scope="row">{row.label}</th>{report.series.map(s=><td key={s.key}>{money(row[s.key])}</td>)}</tr>)}</tbody></table></div>}
      <details><summary>Как рассчитано</summary><p>{report.explanation}</p></details>
    </section>}
    <form onSubmit={e=>{e.preventDefault();void request()}} className="mini-query"><div className="mini-field"><label htmlFor="genbi-question">{report?'Уточнить этот отчёт':'Вопрос по вашим данным'}</label><textarea id="genbi-question" value={question} onChange={e=>setQuestion(e.target.value)} rows={2} maxLength={2000} placeholder={report?'А за прошлый месяц?':'На что ушли деньги в этом месяце?'} /></div>
      {error&&<p className="mini-error" role="alert">{error}</p>}<button className="primary mini-keyboard-action" disabled={busy||question.trim().length<3}>{busy?'Строим отчёт…':report?'Уточнить отчёт':'Задать вопрос'}</button>{busy&&<p className="mini-hint" role="status">Строим отчёт. Текущий результат остаётся на экране со своими фильтрами.</p>}
    </form>
    {report&&<button type="button" className="quiet" disabled={busy} onClick={()=>{setReport(null);setQuestion('');setError('')}}>Новый вопрос без контекста</button>}
    <div className="mini-preset-list" aria-label="Готовые отчёты">{presets.map(p=><button type="button" key={p.intent} disabled={busy} onClick={()=>void request(p.intent)}><span>{p.title}</span><span aria-hidden="true">↗</span></button>)}</div>
  </div>
}
