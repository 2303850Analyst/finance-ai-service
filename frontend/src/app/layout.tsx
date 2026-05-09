import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/Sidebar'
import AIAssistantBar from '@/components/AIAssistantBar'

export const metadata: Metadata = {
  title: 'Finance AI Service',
  description: 'Personal finance and investment portfolio tracker',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white">
        <div className="flex flex-col md:flex-row min-h-screen">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <AIAssistantBar />
            <main className="flex-1 min-w-0 overflow-auto">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  )
}
