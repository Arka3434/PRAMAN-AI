import { cn } from '../../lib/utils'

export function LoadingState({ className, label = 'Loading dashboard…' }: { className?: string; label?: string }) {
  return (
    <div className={cn('flex min-h-[220px] items-center justify-center rounded-2xl border border-slate-200 bg-white', className)}>
      <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-[#263FE0]" />
        {label}
      </div>
    </div>
  )
}
