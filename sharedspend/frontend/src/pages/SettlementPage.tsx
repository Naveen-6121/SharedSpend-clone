/**
 * SettlementPage — "Who owes whom?"
 *
 * Settlement is based exclusively on PERSONAL transactions that have
 * add_to_settlement=true. Minimum-transfer calculation is done by the backend.
 * Settlement records are persisted server-side (not localStorage).
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settlementsApi, groupsApi } from '@/api'
import { useGroup } from '@/context/GroupContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { formatINR, currentYear, currentMonth, monthName } from '@/lib/format'
import type { SettlementTransfer, SettlementRecordOut } from '@/types'

// ─── Component ────────────────────────────────────────────────────────────────
export function SettlementPage() {
  const { activeGroup } = useGroup()
  const [year, setYear] = useState(currentYear())
  const [month, setMonth] = useState(currentMonth())
  const queryClient = useQueryClient()

  const enabled = !!activeGroup

  // Calculated transfers from backend (based on add_to_settlement transactions)
  const { data: transfers = [], isLoading: calcLoading } = useQuery<SettlementTransfer[]>({
    queryKey: ['settlement-calculate', activeGroup?.id, year, month],
    queryFn: () => settlementsApi.calculate(activeGroup!.id, year, month),
    enabled,
  })

  // Persisted settlement records for this group
  const { data: records = [], isLoading: recordsLoading } = useQuery<SettlementRecordOut[]>({
    queryKey: ['settlement-records', activeGroup?.id],
    queryFn: () => settlementsApi.list(activeGroup!.id),
    enabled,
  })

  // Group members for display names
  const { data: groupMembers = [] } = useQuery({
    queryKey: ['group-members', activeGroup?.id],
    queryFn: () => groupsApi.members(activeGroup!.id),
    enabled,
  })

  const memberNames: Record<string, string> = {}
  groupMembers.forEach((m) => {
    memberNames[m.user_id] = m.display_name || m.username || m.user_id
  })

  // Create a settlement record (to persist it)
  const createRecord = useMutation({
    mutationFn: (t: SettlementTransfer) =>
      settlementsApi.create(activeGroup!.id, t.from_user_id, t.to_user_id, t.amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settlement-records', activeGroup?.id] })
    },
  })

  // Mark a record as settled
  const markSettled = useMutation({
    mutationFn: (id: string) => settlementsApi.settle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settlement-records', activeGroup?.id] })
    },
  })

  // Delete a settled record
  const deleteRecord = useMutation({
    mutationFn: (id: string) => settlementsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settlement-records', activeGroup?.id] })
    },
  })

  const loading = calcLoading || recordsLoading

  // Determine which calculated transfers already have a persisted PENDING record
  const pendingRecords = records.filter((r) => r.status === 'PENDING')
  const settledRecords = records.filter((r) => r.status === 'SETTLED')

  // Transfers that haven't been persisted yet
  const unpersisted = transfers.filter(
    (t) => !pendingRecords.some(
      (r) => r.from_user_id === t.from_user_id && r.to_user_id === t.to_user_id
    )
  )

  const years = Array.from({ length: 5 }, (_, i) => currentYear() - i)
  const months = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: monthName(i + 1) }))

  if (!activeGroup) {
    return <p className="text-muted-foreground text-center py-12">Select a group to view settlements</p>
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header + filters */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Settlement</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Based on personal expenses marked "Add to Settlement"
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
            <SelectContent>{years.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>{months.map((m) => <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      {/* How settlement works */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {monthName(month)} {year} — Settlement Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}
            </div>
          ) : transfers.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No personal expenses marked for settlement this period.
              <br />
              <span className="text-xs">Add a Personal transaction and check "Add to Settlement" to start tracking.</span>
            </p>
          ) : (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Transfers to settle</span>
                <span className="font-semibold">{transfers.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total to settle</span>
                <span className="font-semibold">
                  {formatINR(transfers.reduce((s, t) => s + t.amount, 0))}
                </span>
              </div>
              <Separator />
              <p className="text-xs text-muted-foreground">
                Amounts split equally among all group members who are part of the expense.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending settlements from calculation */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold flex items-center gap-2">
          Pending Settlements
          {(unpersisted.length + pendingRecords.length) > 0 && (
            <Badge variant="destructive" className="text-xs">
              {unpersisted.length + pendingRecords.length}
            </Badge>
          )}
        </h2>

        {loading ? (
          Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)
        ) : (unpersisted.length === 0 && pendingRecords.length === 0) ? (
          <Card>
            <CardContent className="py-6 text-center">
              <p className="text-2xl mb-1">🎉</p>
              <p className="text-sm font-medium">All settled up!</p>
              <p className="text-xs text-muted-foreground mt-1">
                {transfers.length === 0
                  ? 'No settlement transactions for this period.'
                  : 'All transfers have been marked as settled.'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Unpersisted calculated transfers — save + settle */}
            {unpersisted.map((t, i) => (
              <Card key={`calc-${i}`}>
                <CardContent className="py-4">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div>
                      <p className="text-sm font-medium">
                        <span className="text-destructive">{memberNames[t.from_user_id] ?? t.from_user_id}</span>
                        <span className="text-muted-foreground mx-2">owes</span>
                        <span className="text-green-600">{memberNames[t.to_user_id] ?? t.to_user_id}</span>
                      </p>
                      <p className="text-2xl font-bold tabular-nums mt-1">{formatINR(t.amount)}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => createRecord.mutate(t)}
                      disabled={createRecord.isPending}
                      className="shrink-0"
                    >
                      ✓ Mark as Settled
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}

            {/* Persisted PENDING records */}
            {pendingRecords.map((r) => (
              <Card key={r.id}>
                <CardContent className="py-4">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div>
                      <p className="text-sm font-medium">
                        <span className="text-destructive">{memberNames[r.from_user_id] ?? r.from_user_id}</span>
                        <span className="text-muted-foreground mx-2">owes</span>
                        <span className="text-green-600">{memberNames[r.to_user_id] ?? r.to_user_id}</span>
                      </p>
                      <p className="text-2xl font-bold tabular-nums mt-1">{formatINR(r.amount)}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => markSettled.mutate(r.id)}
                      disabled={markSettled.isPending}
                      className="shrink-0"
                    >
                      ✓ Mark as Settled
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </>
        )}
      </div>

      {/* Settlement history */}
      {settledRecords.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-muted-foreground">Settlement History</h2>
          <Card>
            <CardContent className="pt-4 divide-y">
              {settledRecords.map((r) => (
                <div key={r.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm">
                      <span className="font-medium">{memberNames[r.from_user_id] ?? r.from_user_id}</span>
                      <span className="text-muted-foreground mx-1">paid</span>
                      <span className="font-medium">{memberNames[r.to_user_id] ?? r.to_user_id}</span>
                    </p>
                    {r.settled_at && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {new Date(r.settled_at).toLocaleDateString('en-IN', {
                          day: 'numeric', month: 'short', year: 'numeric',
                        })}
                      </p>
                    )}
                  </div>
                  <div className="text-right flex items-center gap-2">
                    <div>
                      <p className="text-sm font-semibold tabular-nums">{formatINR(r.amount)}</p>
                      <Badge variant="secondary" className="text-xs mt-1">Settled</Badge>
                    </div>
                    <button
                      type="button"
                      aria-label="Delete record"
                      className="text-xs text-muted-foreground hover:text-destructive ml-1"
                      onClick={() => deleteRecord.mutate(r.id)}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
