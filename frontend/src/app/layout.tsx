import type { Metadata } from 'next'
import './globals.css'
import AppShell from '@/components/AppShell'

export const metadata: Metadata = {
  title: 'Finance AI Service',
  description: 'Personal finance and investment portfolio tracker',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="bg-gray-950 text-white">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
