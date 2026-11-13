'use client'
import { usePathname } from 'next/navigation'
import Sidebar from './Sidebar'
import AIAssistantBar from './AIAssistantBar'

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname()
  if (path === '/miniapp' || path.startsWith('/miniapp/')) return <>{children}</>
  return <div className="flex flex-col md:flex-row min-h-screen"><Sidebar /><div className="flex-1 flex flex-col min-w-0 overflow-hidden"><AIAssistantBar /><main className="flex-1 min-w-0 overflow-auto">{children}</main></div></div>
}
