import Link from 'next/link'

export default function AIAssistantBar() {
  return <div className="shrink-0 border-b border-gray-800 bg-gray-950 px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
    <span className="font-semibold text-gray-400">AI-помощник</span>
    <Link href="/" className="text-blue-400 hover:text-blue-300">Ввести операцию</Link>
    <Link href="/analytics" className="text-blue-400 hover:text-blue-300">Задать вопрос по данным</Link>
    <Link href="/telegram" className="text-gray-400 hover:text-white">Голосом в Telegram</Link>
  </div>
}
