'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface NavItem {
  href?: string
  label: string
  disabled?: boolean
  note?: string
}

const mainLinks: NavItem[] = [
  { href: '/', label: 'Dashboard' },
  { href: '/operations', label: 'Operations' },
  { href: '/accounts', label: 'Accounts' },
  { href: '/assets', label: 'Assets' },
]

const comingSoonLinks: NavItem[] = [
  { href: '/assets', label: 'Deposits', note: '↗ Assets' },
  { href: '/', label: 'Cash Balances', note: '↗ Dashboard' },
  { label: 'Income', disabled: true },
  { label: 'Settings', disabled: true },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="
      flex flex-row md:flex-col
      md:w-56 md:min-h-screen
      border-b md:border-b-0 md:border-r border-gray-800
      p-3 md:p-4
      gap-1
      overflow-x-auto md:overflow-visible
      shrink-0 bg-gray-950
    ">
      <div className="hidden md:block mb-5 px-1">
        <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">Finance AI</p>
      </div>

      {/* Main nav */}
      <div className="flex flex-row md:flex-col gap-0.5">
        {mainLinks.map(({ href, label }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href!}
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
      </div>

      {/* Coming soon — desktop only */}
      <div className="hidden md:block mt-5">
        <p className="px-3 mb-1.5 text-[10px] font-semibold text-gray-700 uppercase tracking-widest">
          Скоро
        </p>
        <div className="flex flex-col gap-0.5">
          {comingSoonLinks.map((item) =>
            item.disabled ? (
              <span
                key={item.label}
                className="px-3 py-2 rounded-lg text-sm text-gray-700 cursor-default"
              >
                {item.label}
              </span>
            ) : (
              <Link
                key={item.label}
                href={item.href!}
                className="px-3 py-2 rounded-lg text-sm text-gray-600 hover:text-gray-400 hover:bg-gray-800/40 transition-colors flex items-center justify-between"
              >
                {item.label}
                {item.note && (
                  <span className="text-[10px] text-gray-700 ml-1">{item.note}</span>
                )}
              </Link>
            )
          )}
        </div>
      </div>
    </aside>
  )
}
