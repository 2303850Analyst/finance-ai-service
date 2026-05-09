'use client'

export default function AIAssistantBar() {
  return (
    <div className="shrink-0 border-b border-gray-800 bg-gray-950 px-4 py-2.5 flex items-center gap-3">
      {/* Label */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-gray-600 text-base leading-none select-none">✦</span>
        <span className="text-xs font-semibold text-gray-500 whitespace-nowrap">AI‑помощник</span>
      </div>

      {/* Divider */}
      <div className="hidden sm:block w-px h-5 bg-gray-800 shrink-0" />

      {/* Input area */}
      <div className="flex-1 flex items-center gap-2 min-w-0">
        <input
          type="text"
          disabled
          placeholder="Спросите по сервису или финансам…"
          className="flex-1 min-w-0 bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-gray-400 placeholder-gray-600 disabled:cursor-not-allowed focus:outline-none"
        />
        <button
          disabled
          className="shrink-0 px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-600 disabled:cursor-not-allowed"
          aria-label="Отправить"
        >
          →
        </button>
      </div>

      {/* Hint — hidden on very small screens */}
      <p className="hidden lg:block shrink-0 text-[10px] text-gray-700 whitespace-nowrap">
        AI‑навигация будет добавлена позже
      </p>
    </div>
  )
}
