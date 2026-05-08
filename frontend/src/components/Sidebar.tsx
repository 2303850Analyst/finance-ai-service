'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/operations', label: 'Operations' },
  { href: '/accounts', label: 'Accounts' },
  { href: '/assets', label: 'Assets' },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="
      flex flex-row md:flex-col
      md:w-52 md:min-h-screen
      border-b md:border-b-0 md:border-r border-gray-800
      p-3 md:p-4
      gap-1
      overflow-x-auto md:overflow-visible
      shrink-0 bg-gray-950
    ">
      <div className="hidden md:block mb-6 px-1">
        <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">Finance AI</p>
      </div>
      {links.map(({ href, label }) => {
        const active = pathname === href
        return (
          <Link
            key={href}
            href={href}
            className={`
              px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-colors
              ${active
                ? 'bg-gray-800 text-white font-medium'
                : 'text-gray-400 hover:text-white hover:bg-gray-800/60'}
            `}
          >
            {label}
          </Link>
        )
      })}
    </aside>
  )
}
