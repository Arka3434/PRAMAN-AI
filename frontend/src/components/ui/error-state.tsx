import { cn } from '../../lib/utils'

export function ErrorState({ className, message = 'Something went wrong while loading this dashboard section.' }: { className?: string; message?: string }) {
  return (
    <div className={cn('rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800', className)}>
      <p className="font-semibold">Unable to load content</p>
      <p className="mt-1">{message}</p>
    </div>
  )
}
