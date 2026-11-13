'use client'
import { useEffect, useRef, useState } from 'react'
import { openBot } from './telegram'

export default function VoiceInput({ disabled, bot, onAudio }: { disabled: boolean; bot: string; onAudio: (audio: string) => Promise<void> }) {
  const [recording, setRecording] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const cancelled = useRef(false)
  const mounted = useRef(true)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  function release() { stream.current?.getTracks().forEach(track => track.stop()); stream.current = null; if (timer.current) clearInterval(timer.current); timer.current = null }
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; cancelled.current = true; if (recorder.current?.state === 'recording') recorder.current.stop(); release() } }, [])
  async function start() {
    if (recording || requesting || disabled) return
    setError(''); setRequesting(true); cancelled.current = false
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('unsupported')
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current || cancelled.current) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type))
      const device = new MediaRecorder(media, { ...(mimeType ? { mimeType } : {}), audioBitsPerSecond: 64000 })
      recorder.current = device
      const chunks: Blob[] = []; let size = 0; const started = Date.now()
      device.ondataavailable = event => { if (event.data.size) { chunks.push(event.data); size += event.data.size; if (size > 5000000) { cancelled.current = true; setError('Запись больше 5 МБ. Запишите более короткое сообщение.'); if (device.state === 'recording') device.stop() } } }
      device.onerror = () => { cancelled.current = true; if (mounted.current) { setError('Запись прервана. Можно повторить или отправить голос боту.'); setRecording(false) }; release() }
      device.onstop = async () => {
        release(); if (!mounted.current) return; setRecording(false)
        if (cancelled.current) return
        const blob = new Blob(chunks, { type: device.mimeType })
        if (!blob.size) { setError('Запись пустая. Попробуйте ещё раз.'); return }
        const reader = new FileReader()
        reader.onload = async () => { if (mounted.current) await onAudio(String(reader.result).split(',')[1]) }
        reader.onerror = () => setError('Не удалось прочитать запись. Попробуйте ещё раз.')
        reader.readAsDataURL(blob)
      }
      device.start(1000); setRecording(true); setSeconds(0)
      timer.current = setInterval(() => { const elapsed = Math.floor((Date.now() - started) / 1000); setSeconds(elapsed); if (elapsed >= 120 && device.state === 'recording') device.stop() }, 250)
    } catch { release(); if (mounted.current) setError('Микрофон недоступен. Разрешите доступ или отправьте голосовое сообщение боту.') }
    finally { if (mounted.current) setRequesting(false) }
  }
  return <section className="mini-voice" aria-label="Голосовой ввод">
    {recording ? <><p role="status">Запись идёт · {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</p><div className="mini-actions"><button className="primary" type="button" onClick={() => recorder.current?.stop()}>Остановить и распознать</button><button className="secondary" type="button" onClick={() => { cancelled.current = true; recorder.current?.stop() }}>Отменить запись</button></div></> : <button type="button" className="secondary mini-wide" onClick={start} disabled={disabled || requesting}>{requesting ? 'Ожидаем доступ к микрофону…' : 'Записать голос'}</button>}
    {error && <div className="mini-error" role="alert"><p>{error}</p><button type="button" className="secondary" onClick={() => openBot(bot)}>Открыть бота</button><p>После отправки голоса вернитесь сюда - черновик появится в списке.</p></div>}
    <p className="mini-hint">До 2 минут. Сначала покажем текст и черновик.</p>
  </section>
}
