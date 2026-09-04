import apiClient from './client'
import type {
  AnalyticsFilters,
  BudgetSummary,
  CategorySpend,
  DailySpend,
  WeeklySpend,
  MonthlySpend,
  YearlySpend,
  MemberContribution,
  InsightsOut,
} from '@/types'

function clean(p: AnalyticsFilters): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(p).filter(([, v]) => v !== undefined && v !== null)
  ) as Record<string, string | number>
}

export const analyticsApi = {
  summary: (params: AnalyticsFilters) =>
    apiClient.get<BudgetSummary>('/analytics/summary', { params: clean(params) }).then((r) => r.data),

  byCategory: (params: AnalyticsFilters) =>
    apiClient.get<CategorySpend[]>('/analytics/by-category', { params: clean(params) }).then((r) => r.data),

  byDay: (params: AnalyticsFilters) =>
    apiClient.get<DailySpend[]>('/analytics/by-day', { params: clean(params) }).then((r) => r.data),

  byWeek: (params: AnalyticsFilters) =>
    apiClient.get<WeeklySpend[]>('/analytics/by-week', { params: clean(params) }).then((r) => r.data),

  byMonth: (params: AnalyticsFilters) =>
    apiClient.get<MonthlySpend[]>('/analytics/by-month', { params: clean(params) }).then((r) => r.data),

  byYear: (params: AnalyticsFilters) =>
    apiClient.get<YearlySpend[]>('/analytics/by-year', { params: clean(params) }).then((r) => r.data),

  members: (params: AnalyticsFilters) =>
    apiClient.get<MemberContribution[]>('/analytics/members', { params: clean(params) }).then((r) => r.data),

  insights: (params: AnalyticsFilters) =>
    apiClient.get<InsightsOut>('/analytics/insights', { params: clean(params) }).then((r) => r.data),
}
