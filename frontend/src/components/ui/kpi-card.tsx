import * as React from 'react'

import { Card, CardContent } from './card'
import { Badge } from './badge'

export interface KPICardProps {
  label: string
  value: string
  change?: string
  tone?: 'pass' | 'warning' | 'violation' | 'review' | 'neutral'
  icon?: React.ReactNode
}

export function KPICard({ label, value, change, tone = 'neutral', icon }: KPICardProps) {
  return (
    <Card className="overflow-hidden border-slate-200 bg-white">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-3 text-3xl font-bold tracking-tight text-slate-900">{value}</p>
          </div>
          {icon ? <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700">{icon}</div> : null}
        </div>
        {change ? (
          <div className="mt-4 flex items-center justify-between gap-3">
            <Badge variant={tone}>{change}</Badge>
            <span className="text-xs text-slate-500">vs last period</span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
