import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PlusCircle, Pencil, Trash2, Search, ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useGroup } from '@/context/GroupContext'
import { useAuth } from '@/context/AuthContext'
import { useDeleteTransaction, useTransactions } from '@/hooks/useApi'
import { useCategories } from '@/hooks/useApi'
import { groupsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { EmptyState } from '@/components/EmptyState'
import { formatINR, toLocalDateString, currentYear, currentMonth } from '@/lib/format'
import { buildExportRows, exportXlsx, exportCsv } from '@/lib/export'
import { transactionsApi } from '@/api'
import { toast } from 'sonner'
import type { TransactionOut, TransactionType } from '@/types'

const PAGE_SIZE = 20

export function TransactionsPage() {
  const { activeGroup } = useGroup()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<TransactionType | 'ALL'>('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const { data: categories } = useCategories(activeGroup?.id)

  const filters = {
    group_id: activeGroup?.id,
    type: typeFilter === 'ALL' ? undefined : typeFilter,
    category_id: categoryFilter === 'ALL' ? undefined : categoryFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    search: search || undefined,
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading } = useTransactions(filters)
  const deleteMutation = useDeleteTransaction()

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  const resetFilters = () => {
    setSearch(''); setTypeFilter('ALL'); setCategoryFilter('ALL')
    setDateFrom(''); setDateTo(''); setPage(1)
  }

  const hasFilters = search || typeFilter !== 'ALL' || categoryFilter !== 'ALL' || dateFrom || dateTo

  // Build category lookup map for export
  const categoryMap: Record<string, string> = {}
  categories?.forEach((c) => { categoryMap[c.id] = c.name })

  // Fetch group members to resolve user IDs → display names
  const { data: members = [] } = useQuery({
    queryKey: ['group-members', activeGroup?.id],
    queryFn: () => groupsApi.members(activeGroup!.id),
    enabled: !!activeGroup,
  })
  // user_id → display name map for badge labels
  const memberMap: Record<string, string> = {}
  members.forEach((m) => { memberMap[m.user_id] = m.display_name || m.username || m.user_id })

  const handleExport = async (format: 'xlsx' | 'csv') => {
    if (!activeGroup) { toast.error('No active group selected'); return }
    setExporting(true)
    try {
      // Fetch all matching transactions (no pagination)
      const exportFilters = {
        group_id: activeGroup.id,
        type: typeFilter === 'ALL' ? undefined : typeFilter,
        category_id: categoryFilter === 'ALL' ? undefined : categoryFilter,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        search: search || undefined,
        page: 1,
        page_size: 5000,
      }
      const result = await transactionsApi.list(exportFilters)
      const memberMap: Record<string, string> = {}
      const rows = buildExportRows(result.items, categoryMap, memberMap)
      const y = currentYear()
      const m = String(currentMonth()).padStart(2, '0')
      const groupSlug = activeGroup.name.replace(/[^a-z0-9]/gi, '_')
      const filename = `SharedSpend_${groupSlug}_${y}-${m}.${format}`
      if (format === 'xlsx') exportXlsx(rows, filename)
      else exportCsv(rows, filename)
      toast.success(`Exported ${rows.length} transactions`)
    } catch {
      toast.error('Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={exporting}>
                <Download className="mr-2 h-4 w-4" />{exporting ? 'Exporting…' : 'Export'}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport('xlsx')}>
                📊 Excel (.xlsx)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('csv')}>
                📄 CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button asChild size="sm">
            <Link to="/transactions/new"><PlusCircle className="mr-2 h-4 w-4" />Add</Link>
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <Input
            placeholder="Search transactions…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="pl-9"
            aria-label="Search transactions"
          />
        </div>
        <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v as TransactionType | 'ALL'); setPage(1) }}>
          <SelectTrigger className="w-36" aria-label="Filter by type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All types</SelectItem>
            <SelectItem value="SHARED">Shared</SelectItem>
            <SelectItem value="PERSONAL">Personal</SelectItem>
          </SelectContent>
        </Select>
        <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setPage(1) }}>
          <SelectTrigger className="w-40" aria-label="Filter by category"><SelectValue placeholder="All categories" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All categories</SelectItem>
            {categories?.map((c) => <SelectItem key={c.id} value={c.id}>{c.icon} {c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
          className="w-36" aria-label="From date" />
        <Input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
          className="w-36" aria-label="To date" />
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={resetFilters} className="text-muted-foreground">
            Clear filters
          </Button>
        )}
      </div>

      {/* Total count */}
      {!isLoading && data && (
        <p className="text-sm text-muted-foreground">
          {data.total} transaction{data.total !== 1 ? 's' : ''}
          {hasFilters ? ' matching filters' : ''}
        </p>
      )}

      {/* List */}
      <div className="rounded-lg border bg-card overflow-hidden" role="list" aria-label="Transactions">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16 w-full border-b" />)
          : !data?.items.length
            ? <EmptyState
                icon={hasFilters ? '🔍' : '📋'}
                title={hasFilters ? 'No transactions match your filters' : 'No transactions yet'}
                description={hasFilters ? 'Try clearing some filters.' : 'Add your first transaction to get started.'}
                action={hasFilters
                  ? <Button variant="outline" size="sm" onClick={resetFilters}>Clear filters</Button>
                  : <Button asChild size="sm"><Link to="/transactions/new">Add transaction</Link></Button>
                }
                className="py-12"
              />
            : data.items.map((tx) => (
              <TransactionRow
                key={tx.id}
                tx={tx}
                isOwn={tx.recorded_by_id === user?.id}
                memberMap={memberMap}
                onEdit={() => navigate(`/transactions/${tx.id}/edit`)}
                onDelete={() => setDeleteId(tx.id)}
              />
            ))
        }
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-3" role="navigation" aria-label="Pagination">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}
            aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
            aria-label="Next page">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Delete confirm */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete transaction?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The transaction will be permanently removed and all analytics will update automatically.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteId) {
                  deleteMutation.mutate(deleteId, { onSuccess: () => setDeleteId(null) })
                }
              }}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function TransactionRow({
  tx, isOwn, onEdit, onDelete, memberMap,
}: {
  tx: TransactionOut
  isOwn: boolean
  memberMap: Record<string, string>
  onEdit: () => void
  onDelete: () => void
}) {
  // Personal transactions: show who recorded it; Shared: show "Shared"
  const typeLabel = tx.type === 'SHARED'
    ? 'Shared'
    : (memberMap[tx.recorded_by_id] ?? 'Personal')

  return (
    <div className="flex items-center justify-between px-4 py-3 border-b last:border-0 hover:bg-muted/30 transition-colors"
      role="listitem">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-9 w-9 rounded-full flex items-center justify-center shrink-0 text-sm bg-muted"
          aria-hidden="true">
          💸
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{tx.description}</p>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">{toLocalDateString(tx.date)}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <Badge variant={tx.type === 'SHARED' ? 'default' : 'secondary'}>
          {typeLabel}
        </Badge>
        <span className="text-sm font-semibold w-24 text-right tabular-nums">{formatINR(tx.amount)}</span>
        {isOwn && (
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}
              aria-label={`Edit ${tx.description}`}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={onDelete}
              aria-label={`Delete ${tx.description}`}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
