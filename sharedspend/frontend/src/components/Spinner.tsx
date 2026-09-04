import { cn } from '@/lib/utils'

export function PageSpinner({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center justify-center py-16', className)}>
      <span className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

export function InlineSpinner({ className }: { className?: string }) {
  return <span className={cn('h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent inline-block', className)} />
}
