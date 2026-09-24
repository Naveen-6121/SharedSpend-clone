import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PlusCircle, Search, ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useGroup } from '@/context/GroupContext'
import { useAuth } from '@/context/AuthContext'
import { useDeleteTransaction } from '@/hooks/useApi'
import { useCategories } from '@/hooks/useApi'
import { groupsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { currentYear, currentMonth } from '@/lib/format'
import { buildExportRows, exportXlsx } from '@/lib/export'
import { settlementsApi, transactionsApi } from '@/api'
import { TransactionSection } from '@/components/TransactionSection'
import { buildTransactionDisplayRows } from '@/lib/transactionPresentation'
import { toast } from 'sonner'
import type { TransactionType } from '@/types'

const PAGE_SIZE = 20

export function TransactionsPage() {
  const { activeGroup } = useGroup()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<TransactionType | 'ALL'>('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [payerFilter, setPayerFilter] = useState('ALL')
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
    payer_id: payerFilter === 'ALL' ? undefined : payerFilter,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    search: search || undefined,
  }

  const { data: transactions = [], isLoading: transactionsLoading } = useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => transactionsApi.listAll(filters),
    enabled: !!activeGroup,
  })
  const { data: settlementRecords = [], isLoading: settlementsLoading } = useQuery({
    queryKey: ['settlement-records', activeGroup?.id],
    queryFn: () => settlementsApi.list(activeGroup!.id),
    enabled: !!activeGroup,
  })
  const isLoading = transactionsLoading || settlementsLoading
  const deleteMutation = useDeleteTransaction()

  const resetFilters = () => {
    setSearch(''); setTypeFilter('ALL'); setCategoryFilter('ALL'); setPayerFilter('ALL')
    setDateFrom(''); setDateTo(''); setPage(1)
  }

  const hasFilters = search || typeFilter !== 'ALL' || categoryFilter !== 'ALL' || payerFilter !== 'ALL' || dateFrom || dateTo

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

  const rows = buildTransactionDisplayRows(transactions, settlementRecords, user?.id ?? '', memberMap, {
    type: typeFilter,
    categoryId: categoryFilter,
    payerId: payerFilter,
    search,
    dateFrom,
    dateTo,
  })
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const groupRows = pageRows.filter((row) => row.section === 'group')
  const personalRows = pageRows.filter((row) => row.section === 'personal')

  const handleExport = async (format: 'xlsx' | 'csv') => {
    if (!activeGroup) { toast.error('No active group selected'); return }
    setExporting(true)
    try {
      if (format === 'csv') {
        const blob = await transactionsApi.exportCsv({
          group_id: activeGroup.id,
          type: typeFilter === 'ALL' ? undefined : typeFilter,
          category_id: categoryFilter === 'ALL' ? undefined : categoryFilter,
          payer_id: payerFilter === 'ALL' ? undefined : payerFilter,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          search: search || undefined,
        })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `transactions-${currentYear()}-${String(currentMonth()).padStart(2, '0')}.csv`
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        toast.success('CSV export downloaded')
        return
      }

      // Fetch all matching transactions in pages supported by the backend.
      const exportFilters = {
        group_id: activeGroup.id,
        type: typeFilter === 'ALL' ? undefined : typeFilter,
        category_id: categoryFilter === 'ALL' ? undefined : categoryFilter,
        payer_id: payerFilter === 'ALL' ? undefined : payerFilter,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        search: search || undefined,
      }
      const transactions = await transactionsApi.listAll(exportFilters)
      const rows = buildExportRows(transactions, categoryMap, memberMap)
      const y = currentYear()
      const m = String(currentMonth()).padStart(2, '0')
      const groupSlug = activeGroup.name.replace(/[^a-z0-9]/gi, '_')
      const filename = `SharedSpend_${groupSlug}_${y}-${m}.${format}`
      await exportXlsx(rows, filename)
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
        <Select value={payerFilter} onValueChange={(v) => { setPayerFilter(v); setPage(1) }}>
          <SelectTrigger className="w-40" aria-label="Filter by payer"><SelectValue placeholder="All payers" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All payers</SelectItem>
            {members.map((m) => <SelectItem key={m.user_id} value={m.user_id}>{m.display_name || m.username || m.user_id}</SelectItem>)}
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
      {!isLoading && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
          {rows.length} transaction{rows.length !== 1 ? 's' : ''}
          {hasFilters ? ' matching filters' : ''}
          </p>
          {hasFilters && rows.length === 0 && (
            <Button variant="ghost" size="sm" onClick={resetFilters} className="text-muted-foreground">
              Clear filters
            </Button>
          )}
        </div>
      )}

      <TransactionSection
        title="GROUP TRANSACTIONS"
        rows={groupRows}
        isLoading={isLoading}
        onEdit={(id) => navigate(`/transactions/${id}/edit`)}
        onDelete={setDeleteId}
      />
      <TransactionSection
        title="PERSONAL TRANSACTIONS"
        rows={personalRows}
        isLoading={isLoading}
        onEdit={(id) => navigate(`/transactions/${id}/edit`)}
        onDelete={setDeleteId}
      />

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
