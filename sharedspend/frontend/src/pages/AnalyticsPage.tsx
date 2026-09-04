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
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import type { DailySpend, MonthlySpend, YearlySpend } from '@/types'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899']

function EmptyChart() {
  return <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">No data for this period</div>
}

/** Format DailySpend for the bar chart (XAxis needs a string key) */
function normDaily(data: DailySpend[]) {
  return data.map((d) => ({ ...d, label: d.date }))
}

/** Format MonthlySpend for the bar chart */
function normMonthly(data: MonthlySpend[]) {
  return data.map((d) => ({ ...d, label: monthName(d.month) }))
}

/** Format YearlySpend for the bar chart */
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

  const { data: members } = useQuery({
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

        {/* Category */}
        <TabsContent value="category" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Spending by Category — {monthName(month)} {year}</CardTitle></CardHeader>
            <CardContent>
              {catLoading ? <Skeleton className="h-64 w-full" />
                : !byCategory?.length ? <EmptyChart />
                : (
                  <div className="grid md:grid-cols-2 gap-6">
                    <div style={{ width: '100%', height: 260 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={byCategory} dataKey="amount" nameKey="category_name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }: { name?: string; percent?: number }) => `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                            {byCategory.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                          </Pie>
                          <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="space-y-2">
                      {byCategory.map((c, i) => (
                        <div key={c.category_id ?? 'none'} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                            <span className="text-sm">{c.category_name ?? 'Uncategorized'}</span>
                          </div>
                          <span className="text-sm font-medium">{formatINR(c.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Daily */}
        <TabsContent value="daily" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Daily Spending — {monthName(month)} {year}</CardTitle></CardHeader>
            <CardContent>
              {dayLoading ? <Skeleton className="h-64 w-full" />
                : !byDay?.length ? <EmptyChart />
                : (
                  <div style={{ width: '100%', height: 260 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={normDaily(byDay)}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                        <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                        <Legend />
                        <Bar dataKey="shared" name="Shared" fill="#3b82f6" />
                        <Bar dataKey="personal" name="Personal" fill="#22c55e" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Monthly */}
        <TabsContent value="monthly" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Monthly Spending — {year}</CardTitle></CardHeader>
            <CardContent>
              {monthLoading ? <Skeleton className="h-64 w-full" />
                : !byMonth?.length ? <EmptyChart />
                : (
                  <div style={{ width: '100%', height: 260 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={normMonthly(byMonth)}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                        <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                        <Legend />
                        <Bar dataKey="shared" name="Shared" fill="#3b82f6" />
                        <Bar dataKey="personal" name="Personal" fill="#22c55e" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Yearly */}
        <TabsContent value="yearly" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Yearly Overview</CardTitle></CardHeader>
            <CardContent>
              {yearLoading ? <Skeleton className="h-64 w-full" />
                : !byYear?.length ? <EmptyChart />
                : (
                  <div style={{ width: '100%', height: 260 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={normYearly(byYear)}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                        <Tooltip formatter={(v: unknown) => formatINR(v as number)} />
                        <Legend />
                        <Bar dataKey="shared" name="Shared" fill="#3b82f6" />
                        <Bar dataKey="personal" name="Personal" fill="#22c55e" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Members */}
        <TabsContent value="members" forceMount className="data-[state=inactive]:hidden">
          <Card>
            <CardHeader><CardTitle>Member Contributions — {monthName(month)} {year}</CardTitle></CardHeader>
            <CardContent>
              {!members?.length
                ? <EmptyChart />
                : (
                  <div className="space-y-4">
                    {members.map((m) => (
                      <div key={m.user_id} className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="font-medium">{m.display_name ?? m.user_id}</span>
                        </div>
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>Shared paid: {formatINR(m.paid)}</span>
                          <span>Personal total: {formatINR(m.personal_spent)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Insights */}
        <TabsContent value="insights" forceMount className="data-[state=inactive]:hidden">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Highest Category</CardTitle></CardHeader>
              <CardContent>
                {insights?.highest_category
                  ? <><p className="text-xl font-bold">{insights.highest_category.name ?? '—'}</p><p className="text-muted-foreground text-sm">{formatINR(insights.highest_category.amount)}</p></>
                  : <p className="text-sm text-muted-foreground">No data</p>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Highest Day</CardTitle></CardHeader>
              <CardContent>
                {insights?.highest_day
                  ? <><p className="text-xl font-bold">{insights.highest_day.date ?? '—'}</p><p className="text-muted-foreground text-sm">{formatINR(insights.highest_day.amount)}</p></>
                  : <p className="text-sm text-muted-foreground">No data</p>}
              </CardContent>
            </Card>
            <Card className="sm:col-span-2">
              <CardHeader><CardTitle className="text-base">Top 5 Transactions</CardTitle></CardHeader>
              <CardContent>
                {!insights?.largest_transactions.length
                  ? <p className="text-sm text-muted-foreground">No data</p>
                  : <div className="space-y-2">
                    {insights.largest_transactions.map((tx) => (
                      <div key={tx.id} className="flex justify-between text-sm">
                        <span className="truncate max-w-[60%]">{tx.description}</span>
                        <span className="font-medium">{formatINR(tx.amount)}</span>
                      </div>
                    ))}
                  </div>}
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
