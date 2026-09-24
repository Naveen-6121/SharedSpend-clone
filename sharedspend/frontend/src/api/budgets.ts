import apiClient from './client'
import type { BudgetPeriodCreate, BudgetPeriodOut } from '@/types'

export const budgetsApi = {
  /**
   * Get the budget for a specific year+month.
   * Backend has no single-budget GET endpoint — we list all budgets and find the match.
   * Returns null when no budget is set for that period so React Query can cache
   * the successful empty result instead of treating it as an invalid query value.
   */
  get: (groupId: string, year: number, month: number) =>
    apiClient
      .get<BudgetPeriodOut[]>(`/groups/${groupId}/budgets`)
      .then((r) => r.data.find((b) => b.year === year && b.month === month) ?? null),

  copyPrevious: (groupId: string, year: number, month: number) =>
    apiClient
      .get<BudgetPeriodOut | null>(`/groups/${groupId}/budgets/${year}/${month}/previous`)
      .then((r) => r.data),

  /**
   * Create or update a budget period.
   * Backend POST /groups/{id}/budgets acts as upsert (updates if period already exists).
   */
  upsert: (groupId: string, data: BudgetPeriodCreate) =>
    apiClient.post<BudgetPeriodOut>(`/groups/${groupId}/budgets`, data).then((r) => r.data),
}
