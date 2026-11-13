'use client'

import { useCallback, useEffect, useState } from 'react'
import { request } from '@/lib/api'

type Status = { configured: boolean; linked: boolean; bot_username: string }
export default function Telegram() {
  const [status, setStatus] = useState<Status | null>(null)
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = useCallback(async () => {
    try { setStatus(await request<Status>('/api/v1/telegram/status')) }
    catch { setError('Не удалось проверить подключение. Убедитесь, что сервис запущен.') }
  }, [])
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 5000); return () => clearInterval(timer) }, [refresh])
  async function connect() {
    setBusy(true); setError('')
    try { const result = await request<{ url: string }>('/api/v1/telegram/pairing', { method: 'POST' }); setUrl(result.url) }
    catch (e) { setError(e instanceof Error ? e.message : 'Не удалось подключить Telegram') }
    finally { setBusy(false) }
  }
  async function disconnect() {
    if (!window.confirm('Отключить Telegram от ваших финансовых данных?')) return
    setBusy(true); setError('')
    try { await request('/api/v1/telegram/link', { method: 'DELETE' }); setUrl(''); await refresh() }
    catch { setError('Не удалось отключить Telegram') }
    finally { setBusy(false) }
  }
  return <div className="max-w-3xl space-y-6 p-4 sm:p-6">
    <div><h1 className="text-2xl font-semibold">Операции через Telegram</h1><p className="text-gray-400 mt-2">Отправляйте расходы, доходы и переводы текстом или голосом. Проверьте черновик и подтвердите запись кнопкой в боте.</p></div>
    {error && <p role="alert" className="text-red-300">{error}</p>}
    <section className="p-6 border border-gray-800 rounded-xl space-y-4">
      <p>{status ? (status.linked ? 'Telegram подключён' : status.configured ? 'Бот готов к подключению' : 'Бот пока не настроен') : 'Проверяю подключение...'}</p>
      {status?.linked ? <div className="flex gap-4 items-center"><a href={`https://t.me/${status.bot_username}`} target="_blank" rel="noreferrer" className="text-blue-400">Открыть бота</a><button disabled={busy} onClick={() => void disconnect()} className="text-gray-400">Отключить</button></div> : <>
        <button disabled={busy || !status?.configured} onClick={() => void connect()} className="bg-blue-600 rounded-lg px-4 py-2 disabled:opacity-50">{busy ? 'Создаю ссылку...' : url ? 'Создать новую ссылку' : 'Подключить Telegram'}</button>
        {url && <div><a href={url} target="_blank" rel="noreferrer" className="text-blue-400 underline">Открыть Telegram и нажать «Запустить»</a><p className="text-sm text-gray-400 mt-2">Ссылка одноразовая и действует 10 минут. После запуска бот получит доступ к вашему локальному учёту.</p></div>}
      </>}
    </section>
    <section className="space-y-3"><h2 className="font-semibold">Как вводить операции</h2>
      <p className="text-gray-400">Сначала создайте счёт в разделе Accounts. Затем отправьте боту, например: «Потратил 450 рублей на продукты со счёта Наличные». Используйте точное название своего счёта.</p>
      <p className="text-gray-400">Голосовое сообщение - до 2 минут и 5 МБ. Распознанный текст появится перед черновиком. Если данные неверны, отмените черновик и отправьте исправленный текст.</p>
      <p className="text-gray-400">/accounts - названия счетов · /pending - черновики · /summary - деньги на счетах. Черновики действуют 24 часа. Для работы бота компьютер и Docker должны быть включены.</p>
    </section>
  </div>
}
