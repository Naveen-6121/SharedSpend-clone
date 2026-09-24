import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatINR, toLocalDateString } from '@/lib/format'
import type { TransactionDisplayRow } from '@/lib/transactionPresentation'

const columns = 'grid grid-cols-[minmax(0,1fr)_minmax(4rem,0.4fr)_6rem_3.5rem] items-center gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(8rem,0.48fr)_8rem_4rem] sm:gap-4'
const formatSettlementAmount = (amount: number) => new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2,
}).format(amount)

interface TransactionSectionProps {
  title: string
  rows: TransactionDisplayRow[]
  isLoading: boolean
  onEdit: (transactionId: string) => void
  onDelete: (transactionId: string) => void
}

export function TransactionSection({ title, rows, isLoading, onEdit, onDelete }: TransactionSectionProps) {
  return (
    <section className="space-y-2" aria-label={title}>
      <h2 className="text-base font-semibold">{title}</h2>
      <div className="overflow-hidden rounded-lg border border-border bg-card text-card-foreground">
        <div className={`${columns} border-b bg-muted px-3 py-2 text-xs font-medium text-muted-foreground sm:px-4`}>
          <span>Transaction</span>
          <span>Made By</span>
          <span className="text-right">Amount</span>
          <span aria-hidden="true" />
        </div>
        <div role="list" aria-label={`${title} list`}>
          {isLoading ? Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-16 w-full rounded-none border-b" />
          )) : rows.length ? rows.map((row) => {
            const isCredit = row.signedAmount > 0
            const formattedAmount = row.label.startsWith('Settlement')
              ? formatSettlementAmount(Math.abs(row.signedAmount))
              : formatINR(Math.abs(row.signedAmount))
            const amount = `${isCredit ? '+' : row.signedAmount < 0 ? '-' : ''}${formattedAmount}`
            return (
              <div key={row.key} className={`${columns} min-h-16 border-b px-3 py-3 last:border-0 hover:bg-muted/40 sm:px-4`} role="listitem">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium" title={row.description}>{row.description}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-xs text-muted-foreground">{toLocalDateString(row.date)}</span>
                    <span className="text-xs text-muted-foreground">{row.label}</span>
                  </div>
                </div>
                <span className="truncate text-sm text-muted-foreground" title={row.madeBy}>{row.madeBy}</span>
                <span
                  className={`whitespace-nowrap text-right text-sm font-semibold tabular-nums ${
                    isCredit ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'
                  }`}
                  aria-label={`${isCredit ? 'Credit' : 'Debit'} ${amount}`}
                >
                  {amount}
                </span>
                <div className="flex items-center justify-end">
                  {row.canEdit && row.transactionId && (
                    <>
                      <Button variant="ghost" size="icon" className="h-7 w-7 sm:h-8 sm:w-8" onClick={() => onEdit(row.transactionId!)}
                        aria-label={`Edit ${row.description}`}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 sm:h-8 sm:w-8 text-destructive" onClick={() => onDelete(row.transactionId!)}
                        aria-label={`Delete ${row.description}`}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            )
          }) : (
            <p className="px-4 py-6 text-sm text-muted-foreground">No transactions in this section.</p>
          )}
        </div>
      </div>
    </section>
  )
}
