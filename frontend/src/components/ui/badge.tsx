import * as React from 'react'

import { cn } from '../../lib/utils'

const badgeVariants = {
  default: 'border border-slate-200 bg-slate-100 text-slate-700',
  pass: 'border border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border border-amber-200 bg-amber-50 text-amber-700',
  violation: 'border border-rose-200 bg-rose-50 text-rose-700',
  review: 'border border-violet-200 bg-violet-50 text-violet-700',
  neutral: 'border border-sky-200 bg-sky-50 text-sky-700',
} as const

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof badgeVariants
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return <div className={cn('inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em]', badgeVariants[variant], className)} {...props} />
}

export { Badge, badgeVariants }
