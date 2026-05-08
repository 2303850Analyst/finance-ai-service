'use client'

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { AllocationItem } from '@/lib/types'

const COLORS: Record<string, string> = {
  stock: '#3b82f6',
  bond: '#10b981',
  etf: '#8b5cf6',
  crypto: '#f59e0b',
  currency: '#6b7280',
  cash: '#64748b',
  deposit: '#0ea5e9',
  real_estate: '#ef4444',
  other: '#9ca3af',
}

interface Props {
  data: AllocationItem[]
}

export default function AllocationChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-52 text-gray-500 text-sm">
        No positions
      </div>
    )
  }

  const chartData = data.map((item) => ({
    name: item.asset_type,
    value: item.percentage,
    total_cost: parseFloat(item.total_cost),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={88}
          paddingAngle={2}
          dataKey="value"
        >
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={COLORS[entry.name] ?? '#9ca3af'} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number) => [`${value.toFixed(1)}%`]}
          contentStyle={{
            background: '#111827',
            border: '1px solid #374151',
            borderRadius: '8px',
            color: '#f9fafb',
            fontSize: '12px',
          }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span style={{ color: '#9ca3af', fontSize: '12px' }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
