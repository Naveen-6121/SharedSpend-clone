import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '@/api'
import { useGroup } from '@/context/GroupContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { formatINR, currentYear, currentMonth, monthName } from '@/lib/format'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import type { DailySpend, MonthlySpend, YearlySpend } from '@/types'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899']

function NoData() {
  return (
    <p className="text-sm text-muted-foreground py-8 text-center">
      No data for this period
    </p>
  )
}

function normDaily(data: DailySpend[]) {
  return data.map((d) => ({ ...d, label: d.date.slice(5) })) // show MM-DD
}
function normMonthly(data: MonthlySpend[]) {
  return data.map((d) => ({ ...d, label: monthName(d.month).slice(0, 3) }))
}
function normYearly(data: YearlySpend[]) {
  return data.map((d) => ({ ...d, label: String(d.year) }))
}

export function AnalyticsPage() {
  const { activeGroup } = useGroup()
  const [year, setYear] = useState(currentYear())
  const [month, setMonth] = useState(currentMonth())

  const enabled = !!activeGroup
  const base = { group_id: activeGroup?.id ?? '', year }

  const { data: byCategory, isLoading: catLoading } = useQuery({
    queryKey: ['analytics', 'by-category', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.byCategory({ ...base, month }),
    enabled,
  })

  const { data: byDay, isLoading: dayLoading } = useQuery({
    queryKey: ['analytics', 'by-day', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.byDay({ ...base, month }),
    enabled,
  })

  const { data: byMonth, isLoading: monthLoading } = useQuery({
    queryKey: ['analytics', 'by-month', activeGroup?.id, year],
    queryFn: () => analyticsApi.byMonth(base),
    enabled,
  })

  const { data: byYear, isLoading: yearLoading } = useQuery({
    queryKey: ['analytics', 'by-year', activeGroup?.id],
    queryFn: () => analyticsApi.byYear({ group_id: activeGroup?.id ?? '' }),
    enabled,
  })

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ['analytics', 'members', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.members({ ...base, month }),
    enabled,
  })

  const { data: insights } = useQuery({
    queryKey: ['analytics', 'insights', activeGroup?.id, year, month],
    queryFn: () => analyticsApi.insights({ ...base, month }),
    enabled,
  })

  const years = Array.from({ length: 5 }, (_, i) => currentYear() - i)
  const months = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: monthName(i + 1) }))

  if (!activeGroup) {
    return <p className="text-muted-foreground text-center py-12">Select a group to view analytics</p>
  }

  return (
    <div className="space-y-6">
      {/* Header + date filters */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-semibold">Analytics</h1>
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

      <Tabs defaultValue="category">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="category">By Category</TabsTrigger>
          <TabsTrigger value="daily">Daily</TabsTrigger>
          <TabsTrigger value="monthly">Monthly</TabsTrigger>
          <TabsTrigger value="yearly">Yearly</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
        </TabsList>

        {/* ── By Category ─────────────────────────────────────────── */}
        <TabsContent value="category" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Spending by Category — {monthName(month)} {year}</CardTitle></CardHeader>
            <CardContent>
              {catLoading
                ? <Skeleton className="h-48 w-full" />
                : !byCategory?.length
                  ? <NoData />
                  : (
                    <div className="grid md:grid-cols-2 gap-6 items-start">
                      {/* Pie chart — only rendered when there is data */}
                      <div style={{ width: '100%', height: 260 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={byCategory}
                              dataKey="amount"
                              nameKey="category_name"
                              cx="50%" cy="50%"
                              outerRadius={90}
                              label={({ percent }: { percent?: number }) =>
                                percent && percent > 0.04 ? `${((percent) * 100).toFixed(0)}%` : ''}
                            >
                              {byCategory.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                            </Pie>
                            <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      {/* Legend table */}
                      <div className="space-y-2">
                        {byCategory.map((c, i) => (
                          <div key={c.category_id ?? 'none'} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <span className="h-3 w-3 rounded-full shrink-0"
                                style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                              <span>{c.category_name ?? 'Uncategorized'}</span>
                            </div>
                            <div className="text-right">
                              <span className="font-medium">{formatINR(c.amount)}</span>
                              <span className="text-xs text-muted-foreground ml-2">({c.count})</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Daily ─────────────────────────────────────────────────── */}
        <TabsContent value="daily" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Daily Spending — {monthName(month)} {year}</CardTitle></CardHeader>
            <CardContent>
              {dayLoading
                ? <Skeleton className="h-48 w-full" />
                : !byDay?.length
                  ? <NoData />
                  : (
                    <div style={{ width: '100%', height: 260 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={normDaily(byDay)} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} width={40} />
                          <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                          <Bar dataKey="shared" name="Shared" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                          <Bar dataKey="personal" name="Personal" fill="#22c55e" radius={[2, 2, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Monthly ───────────────────────────────────────────────── */}
        <TabsContent value="monthly" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Monthly Spending — {year}</CardTitle></CardHeader>
            <CardContent>
              {monthLoading
                ? <Skeleton className="h-48 w-full" />
                : !byMonth?.length
                  ? <NoData />
                  : (
                    <div style={{ width: '100%', height: 260 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={normMonthly(byMonth)} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} width={40} />
                          <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                          <Bar dataKey="shared" name="Shared" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                          <Bar dataKey="personal" name="Personal" fill="#22c55e" radius={[2, 2, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Yearly ────────────────────────────────────────────────── */}
        <TabsContent value="yearly" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Yearly Overview</CardTitle></CardHeader>
            <CardContent>
              {yearLoading
                ? <Skeleton className="h-48 w-full" />
                : !byYear?.length
                  ? <NoData />
                  : (
                    <div style={{ width: '100%', height: 260 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={normYearly(byYear)} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} width={40} />
                          <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                          <Bar dataKey="shared" name="Shared" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                          <Bar dataKey="personal" name="Personal" fill="#22c55e" radius={[2, 2, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Members breakdown table ───────────────────────────────── */}
        <TabsContent value="members" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Spending by Member — {monthName(month)} {year}</CardTitle></CardHeader>
            <CardContent>
              {membersLoading
                ? <Skeleton className="h-32 w-full" />
                : !members?.length
                  ? <NoData />
                  : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-muted-foreground text-xs">
                            <th className="text-left py-2 pr-4 font-medium">Member</th>
                            <th className="text-right py-2 px-4 font-medium">Shared Paid</th>
                            <th className="text-right py-2 px-4 font-medium">Personal</th>
                            <th className="text-right py-2 pl-4 font-medium">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {members.map((m) => {
                            const total = m.paid + m.personal_spent
                            return (
                              <tr key={m.user_id} className="border-b last:border-0">
                                <td className="py-2.5 pr-4 font-medium">
                                  {m.display_name ?? m.user_id}
                                </td>
                                <td className="py-2.5 px-4 text-right tabular-nums">{formatINR(m.paid)}</td>
                                <td className="py-2.5 px-4 text-right tabular-nums text-muted-foreground">{formatINR(m.personal_spent)}</td>
                                <td className="py-2.5 pl-4 text-right tabular-nums font-semibold">{formatINR(total)}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                        <tfoot>
                          <tr className="border-t text-xs text-muted-foreground">
                            <td className="py-2 pr-4">Total</td>
                            <td className="py-2 px-4 text-right tabular-nums font-medium">
                              {formatINR(members.reduce((s, m) => s + m.paid, 0))}
                            </td>
                            <td className="py-2 px-4 text-right tabular-nums font-medium">
                              {formatINR(members.reduce((s, m) => s + m.personal_spent, 0))}
                            </td>
                            <td className="py-2 pl-4 text-right tabular-nums font-semibold">
                              {formatINR(members.reduce((s, m) => s + m.paid + m.personal_spent, 0))}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Insights ──────────────────────────────────────────────── */}
        <TabsContent value="insights" forceMount className="data-[state=inactive]:hidden">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Highest Category</CardTitle></CardHeader>
              <CardContent>
                {insights?.highest_category
                  ? <>
                      <p className="text-xl font-bold">{insights.highest_category.name ?? '—'}</p>
                      <p className="text-muted-foreground text-sm">{formatINR(insights.highest_category.amount)}</p>
                    </>
                  : <p className="text-sm text-muted-foreground">No data</p>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Highest Day</CardTitle></CardHeader>
              <CardContent>
                {insights?.highest_day
                  ? <>
                      <p className="text-xl font-bold">{insights.highest_day.date ?? '—'}</p>
                      <p className="text-muted-foreground text-sm">{formatINR(insights.highest_day.amount)}</p>
                    </>
                  : <p className="text-sm text-muted-foreground">No data</p>}
              </CardContent>
            </Card>
            <Card className="sm:col-span-2">
              <CardHeader><CardTitle className="text-base">Top 5 Transactions</CardTitle></CardHeader>
              <CardContent>
                {!insights?.largest_transactions?.length
                  ? <p className="text-sm text-muted-foreground">No data</p>
                  : (
                    <div className="space-y-2">
                      {insights.largest_transactions.map((tx) => (
                        <div key={tx.id} className="flex justify-between text-sm">
                          <span className="truncate max-w-[60%]">{tx.description}</span>
                          <span className="font-medium">{formatINR(tx.amount)}</span>
                        </div>
                      ))}
                    </div>
                  )}
              </CardContent>
            </Card>
            {insights?.trend && (
              <Card className="sm:col-span-2">
                <CardHeader><CardTitle className="text-base">Spending Trend</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-base font-medium capitalize">{insights.trend}</p>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
