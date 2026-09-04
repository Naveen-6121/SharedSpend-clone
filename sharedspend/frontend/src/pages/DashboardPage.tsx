import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PlusCircle, TrendingUp, Wallet, ArrowLeftRight, User } from 'lucide-react'
import { useGroup } from '@/context/GroupContext'
import { useAuth } from '@/context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import { EmptyState } from '@/components/EmptyState'
import { analyticsApi, transactionsApi } from '@/api'
import { formatINR, toLocalDateString, currentYear, currentMonth, utilizationColor } from '@/lib/format'
import type { TransactionOut } from '@/types'

function BudgetRing({ pct, budget, spent }: { pct: number | null; budget: number | null; spent: number }) {
  const radius = 54
  const circ = 2 * Math.PI * radius
  const fill = pct != null ? Math.min(pct, 100) : 0
  const offset = circ - (fill / 100) * circ
  const color = pct == null ? '#94a3b8' : pct >= 100 ? '#ef4444' : pct >= 80 ? '#eab308' : '#22c55e'

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={128} height={128} viewBox="0 0 128 128" role="img" aria-label={pct != null ? `${Math.round(pct)}% of budget used` : 'No budget set'}>
        <circle cx={64} cy={64} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={12} />
        <circle cx={64} cy={64} r={radius} fill="none" stroke={color} strokeWidth={12}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 64 64)" style={{ transition: 'stroke-dashoffset 0.5s' }} />
        <text x={64} y={60} textAnchor="middle" fontSize={14} fill="#1f2328" fontWeight={600}>
          {pct != null ? `${Math.round(pct)}%` : '—'}
        </text>
        <text x={64} y={78} textAnchor="middle" fontSize={10} fill="#57606a">used</text>
      </svg>
      {budget == null
        ? <p className="text-sm text-muted-foreground">No budget set</p>
        : <p className="text-sm text-muted-foreground">{formatINR(spent)} of {formatINR(budget)}</p>
      }
    </div>
  )
}

function TxRow({ tx }: { tx: TransactionOut }) {
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
          {tx.type === 'SHARED' ? 'Shared' : 'Personal'}
        </Badge>
        <span className="text-sm font-semibold tabular-nums">{formatINR(tx.amount)}</span>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { activeGroup } = useGroup()
  const { user } = useAuth()
  const year = currentYear()
  const month = currentMonth()

  const params = { group_id: activeGroup?.id ?? '', year, month }
  const enabled = !!activeGroup

  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ['analytics', 'summary', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.summary(params),
    enabled,
  })

  const { data: recent, isLoading: txLoading } = useQuery({
    queryKey: ['transactions', 'recent', activeGroup?.id, user?.id],
    queryFn: () => transactionsApi.list({ group_id: activeGroup?.id, page_size: 8, page: 1 }),
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
  const overBudget = utilPct != null && utilPct >= 100

  // Personal spending for the current user from summary data
  const myPersonalSpent = user && summary?.personal_by_member
    ? (summary.personal_by_member.find((m) => m.user_id === user.id)?.personal_spent ?? 0)
    : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{activeGroup.name}</h1>
        <Button asChild size="sm">
          <Link to="/transactions/new"><PlusCircle className="mr-2 h-4 w-4" />Add</Link>
        </Button>
      </div>

      {/* Budget + summary cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
        <Card className="sm:col-span-2 lg:col-span-1">
          <CardContent className="pt-6 flex flex-col items-center">
            {sumLoading
              ? <Skeleton className="h-32 w-32 rounded-full" />
              : <BudgetRing
                  pct={utilPct}
                  budget={summary?.budget ?? null}
                  spent={summary?.shared_spent ?? 0}
                />
            }
          </CardContent>
        </Card>

        {[
          {
            label: 'Monthly Budget',
            icon: Wallet,
            value: summary?.budget != null ? formatINR(summary.budget) : 'Not set',
            sub: `${year} / ${String(month).padStart(2, '0')}`,
            colorClass: '',
          },
          {
            label: 'Shared Spent',
            icon: ArrowLeftRight,
            value: formatINR(summary?.shared_spent ?? 0),
            sub: 'Group expenses this month',
            colorClass: '',
          },
          {
            label: 'Personal Spent',
            icon: User,
            value: formatINR(myPersonalSpent),
            sub: 'My personal expenses',
            colorClass: '',
          },
          {
            label: 'Remaining',
            icon: TrendingUp,
            value: summary?.remaining != null ? formatINR(summary.remaining) : '—',
            sub: overBudget ? 'Over budget!' : 'Shared budget left',
            colorClass: utilizationColor(utilPct),
          },
        ].map(({ label, icon: Icon, value, sub, colorClass }) => (
          <Card key={label}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </div>
            </CardHeader>
            <CardContent>
              {sumLoading
                ? <Skeleton className="h-6 w-24" />
                : <>
                    <p className={`text-xl font-bold tabular-nums ${colorClass}`}>{value}</p>
                    <p className="text-xs text-muted-foreground mt-1">{sub}</p>
                  </>
              }
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Budget progress bar */}
      {!sumLoading && summary?.budget == null && (
        <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
          No budget set for this month.{' '}
          <Link to="/settings/group" className="text-primary underline-offset-2 hover:underline">
            Set budget →
          </Link>
        </div>
      )}
      {utilPct != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Budget utilization</span>
            <span className={utilizationColor(utilPct)}>{Math.round(utilPct)}%</span>
          </div>
          <Progress value={Math.min(utilPct, 100)} className="h-2"
            aria-label={`Budget utilization ${Math.round(utilPct)}%`} />
          {overBudget && (
            <p className="text-xs text-destructive font-medium">⚠ You have exceeded this month's budget</p>
          )}
        </div>
      )}

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
              : recent.items.map((tx) => <TxRow key={tx.id} tx={tx} />)
          }
        </CardContent>
      </Card>
    </div>
  )
}
