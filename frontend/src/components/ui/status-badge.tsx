import { Badge } from './badge'

export type StatusBadgeVariant = 'pass' | 'warning' | 'violation' | 'review' | 'neutral'

export function StatusBadge({ status, className }: { status: StatusBadgeVariant; className?: string }) {
  const labelMap: Record<StatusBadgeVariant, string> = {
    pass: 'PASS',
    warning: 'WARNING',
    violation: 'POTENTIAL VIOLATION',
    review: 'MANUAL REVIEW',
    neutral: 'ACTIVE',
  }

  return (
    <Badge variant={status} className={className}>
      {labelMap[status]}
    </Badge>
  )
}
