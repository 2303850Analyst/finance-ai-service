"use client"

import { useEffect, useState } from "react"

interface HealthStatus {
  status: string
  database: string
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
    />
  )
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    fetch(`${apiUrl}/api/v1/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<HealthStatus>
      })
      .then((data) => {
        setHealth(data)
        setLoading(false)
      })
      .catch((err: Error) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Finance AI Service</h1>
          <p className="text-gray-400 mt-1">Personal finance &amp; investment portfolio tracker</p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            System Status
          </h2>

          {loading && <p className="text-gray-500 text-sm">Checking…</p>}

          {error && (
            <div className="flex items-center gap-3 text-sm">
              <StatusDot ok={false} />
              <span className="text-red-400">Backend unreachable — {error}</span>
            </div>
          )}

          {health && (
            <ul className="space-y-3 text-sm">
              <li className="flex items-center gap-3">
                <StatusDot ok={health.status === "ok"} />
                <span className="text-gray-300">
                  API{" "}
                  <span className="font-mono text-gray-400">{health.status}</span>
                </span>
              </li>
              <li className="flex items-center gap-3">
                <StatusDot ok={health.database === "ok"} />
                <span className="text-gray-300">
                  Database{" "}
                  <span className="font-mono text-gray-400">{health.database}</span>
                </span>
              </li>
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Stage 1 — Foundation
          </h2>
          <ul className="space-y-2 text-sm text-gray-400">
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span> Monorepo structure
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span> FastAPI + PostgreSQL + SQLAlchemy 2
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span> Base models: users, accounts, assets, operations, positions, audit_logs
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span> Alembic migrations
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span> Next.js 14 frontend
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span> Docker Compose
            </li>
          </ul>
        </div>
      </div>
    </main>
  )
}
