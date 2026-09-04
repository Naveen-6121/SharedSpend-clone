import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PlusCircle, ArrowLeftRight, Users } from 'lucide-react'
import { useGroup } from '@/context/GroupContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import { EmptyState } from '@/components/EmptyState'
import { analyticsApi, transactionsApi } from '@/api'
import { formatINR, toLocalDateString, currentYear, currentMonth, utilizationColor } from '@/lib/format'
import type { TransactionOut, GroupMemberOut } from '@/types'
import { groupsApi } from '@/api'

// ─── Budget + Remaining combined card ────────────────────────────────────────
function BudgetCard({
  budget,
  spent,
  remaining,
  utilPct,
  loading,
  year,
  month,
}: {
  budget: number | null
  spent: number
  remaining: number | null
  utilPct: number | null
  loading: boolean
  year: number
  month: number
}) {
  const overBudget = utilPct != null && utilPct >= 100
  const colorClass = utilizationColor(utilPct)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">Budget</CardTitle>
          <span className="text-xs text-muted-foreground">{year}/{String(month).padStart(2, '0')}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-2 w-full" />
          </div>
        ) : (
          <>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Monthly Budget</span>
                <span className="font-semibold">{budget != null ? formatINR(budget) : 'Not set'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Shared Spent</span>
                <span className="font-semibold">{formatINR(spent)}</span>
              </div>
              <div className="flex justify-between border-t pt-1 mt-1">
                <span className="text-muted-foreground">Remaining</span>
                <span className={`font-bold tabular-nums ${colorClass}`}>
                  {remaining != null ? formatINR(remaining) : '—'}
                </span>
              </div>
            </div>
            {utilPct != null && (
              <div className="space-y-1">
                <Progress value={Math.min(utilPct, 100)} className="h-1.5"
                  aria-label={`Budget utilization ${Math.round(utilPct)}%`} />
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">
                    {overBudget ? '⚠ Over budget' : 'Used'}
                  </span>
                  <span className={colorClass}>{Math.round(utilPct)}%</span>
                </div>
              </div>
            )}
            {budget == null && (
              <Link to="/settings/group"
                className="text-xs text-primary underline-offset-2 hover:underline">
                Set monthly budget →
              </Link>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Personal spending breakdown by member ───────────────────────────────────
function PersonalSpendCard({
  personalByMember,
  members,
  loading,
}: {
  personalByMember: Array<{ user_id: string; display_name: string | null; personal_spent: number }>
  members: GroupMemberOut[]
  loading: boolean
}) {
  // Build display name from member list (enriched) or fall back to analytics name
  const nameFor = (userId: string, analyticsName: string | null): string => {
    const m = members.find((m) => m.user_id === userId)
    return m?.display_name || m?.username || analyticsName || userId
  }

  const total = personalByMember.reduce((s, m) => s + m.personal_spent, 0)
  const hasData = personalByMember.some((m) => m.personal_spent > 0)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">Personal Spending</CardTitle>
          <Users className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : !hasData ? (
          <p className="text-sm text-muted-foreground">No personal expenses this month</p>
        ) : (
          <div className="space-y-2">
            {personalByMember
              .filter((m) => m.personal_spent > 0)
              .sort((a, b) => b.personal_spent - a.personal_spent)
              .map((m) => (
                <div key={m.user_id} className="flex items-center justify-between text-sm">
                  <span className="text-foreground truncate max-w-[60%]">
                    {nameFor(m.user_id, m.display_name)}
                  </span>
                  <span className="font-semibold tabular-nums">{formatINR(m.personal_spent)}</span>
                </div>
              ))}
            {personalByMember.filter((m) => m.personal_spent > 0).length > 1 && (
              <div className="flex justify-between text-xs text-muted-foreground border-t pt-1 mt-1">
                <span>Total personal</span>
                <span className="font-medium tabular-nums">{formatINR(total)}</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Recent transaction row ───────────────────────────────────────────────────
function TxRow({ tx, members }: { tx: TransactionOut; members: GroupMemberOut[] }) {
  // For personal transactions, show the recorder's name instead of "Personal"
  const label = tx.type === 'SHARED'
    ? 'Shared'
    : (() => {
        const m = members.find((m) => m.user_id === tx.recorded_by_id)
        return m?.display_name || m?.username || 'Personal'
      })()

  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-8 w-8 rounded-full flex items-center justify-center shrink-0 text-sm bg-muted"
          aria-hidden="true">
          💸
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{tx.description}</p>
          <p className="text-xs text-muted-foreground">{toLocalDateString(tx.date)}</p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Badge variant={tx.type === 'SHARED' ? 'default' : 'secondary'} className="text-xs">
          {label}
        </Badge>
        <span className="text-sm font-semibold tabular-nums">{formatINR(tx.amount)}</span>
      </div>
    </div>
  )
}

// ─── Main dashboard ───────────────────────────────────────────────────────────
export function DashboardPage() {
  const { activeGroup } = useGroup()
  const year = currentYear()
  const month = currentMonth()

  const params = { group_id: activeGroup?.id ?? '', year, month }
  const enabled = !!activeGroup

  // Analytics summary: budget + shared_spent (current month, current group)
  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ['analytics', 'summary', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.summary(params),
    enabled,
  })

  // Analytics members: personal spending per member for current group+period
  const { data: memberStats = [] } = useQuery({
    queryKey: ['analytics', 'members', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.members(params),
    enabled,
  })

  // Recent transactions: current group, most recent 8
  const { data: recent, isLoading: txLoading } = useQuery({
    queryKey: ['transactions', 'recent', activeGroup?.id, year, month],
    queryFn: () => transactionsApi.list({ group_id: activeGroup?.id, year, month, page_size: 8, page: 1 }),
    enabled,
  })

  // Group members for display names
  const { data: members = [] } = useQuery({
    queryKey: ['group-members', activeGroup?.id],
    queryFn: () => groupsApi.members(activeGroup!.id),
    enabled,
  })

  if (!activeGroup) {
    return (
      <EmptyState
        icon="💰"
        title="No group yet"
        description="Create a group to start tracking shared and personal expenses."
        action={
          <Button asChild>
            <Link to="/groups/new"><PlusCircle className="mr-2 h-4 w-4" />Create Group</Link>
          </Button>
        }
      />
    )
  }

  const utilPct = summary?.utilization_pct ?? null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{activeGroup.name}</h1>
        <Button asChild size="sm">
          <Link to="/transactions/new"><PlusCircle className="mr-2 h-4 w-4" />Add</Link>
        </Button>
      </div>

      {/* Summary cards — 3 column grid */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {/* 1. Combined Budget card */}
        <BudgetCard
          budget={summary?.budget ?? null}
          spent={summary?.shared_spent ?? 0}
          remaining={summary?.remaining ?? null}
          utilPct={utilPct}
          loading={sumLoading}
          year={year}
          month={month}
        />

        {/* 2. Shared Spent card */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Shared Spent</CardTitle>
              <ArrowLeftRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            </div>
          </CardHeader>
          <CardContent>
            {sumLoading
              ? <Skeleton className="h-6 w-24" />
              : <>
                  <p className="text-xl font-bold tabular-nums">{formatINR(summary?.shared_spent ?? 0)}</p>
                  <p className="text-xs text-muted-foreground mt-1">Group expenses this month</p>
                </>
            }
          </CardContent>
        </Card>

        {/* 3. Personal spending breakdown by member — uses analytics/members for all-member view */}
        <PersonalSpendCard
          personalByMember={memberStats.map((m) => ({
            user_id: m.user_id,
            display_name: m.display_name,
            personal_spent: Number(m.personal_spent),
          }))}
          members={members}
          loading={sumLoading}
        />
      </div>

      {/* Recent transactions */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">Recent Transactions</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/transactions">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {txLoading
            ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full mb-2" />)
            : !recent?.items?.length
              ? <EmptyState icon="📋" title="No transactions yet" description="Add your first transaction to get started." className="py-8" />
              : recent.items.map((tx) => <TxRow key={tx.id} tx={tx} members={members} />)
          }
        </CardContent>
      </Card>
    </div>
  )
}
