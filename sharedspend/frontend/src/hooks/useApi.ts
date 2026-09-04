/**
 * Shared React Query hooks — single source of truth for every API call.
 * All cache keys are defined here so invalidation is consistent everywhere.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  analyticsApi, budgetsApi, categoriesApi, categorizerApi,
  groupsApi, transactionsApi, usersApi,
} from '@/api'
import { parseApiError } from '@/lib/format'
import type {
  AnalyticsFilters, BudgetPeriodCreate, CategoryCreate, CategoryDeleteRequest,
  CategoryUpdate, GroupCreate, GroupUpdate, InviteMember, PasswordChange,
  TransactionCreate, TransactionFilters, TransactionUpdate, UserUpdate,
  CategorizeRequest,
} from '@/types'

// ─── Query key factory ────────────────────────────────────────────────────────
export const QK = {
  me: () => ['me'] as const,
  groups: () => ['groups'] as const,
  group: (id: string) => ['groups', id] as const,
  members: (groupId: string) => ['group-members', groupId] as const,
  budget: (groupId: string, year: number, month: number) => ['budget', groupId, year, month] as const,
  categories: (groupId?: string) => ['categories', groupId ?? 'global'] as const,
  transactions: (filters?: TransactionFilters) => ['transactions', filters ?? {}] as const,
  transaction: (id: string) => ['transaction', id] as const,
  analytics: (type: string, params: AnalyticsFilters) => ['analytics', type, params] as const,
}

// ─── User ─────────────────────────────────────────────────────────────────────
export function useMe() {
  return useQuery({ queryKey: QK.me(), queryFn: usersApi.me })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UserUpdate) => usersApi.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QK.me() }); toast.success('Profile updated') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: PasswordChange) => usersApi.changePassword(data),
    onError: (e) => toast.error(parseApiError(e)),
  })
}

// ─── Groups ───────────────────────────────────────────────────────────────────
export function useGroups() {
  return useQuery({ queryKey: QK.groups(), queryFn: groupsApi.list })
}

export function useGroupMembers(groupId: string | undefined) {
  return useQuery({
    queryKey: QK.members(groupId ?? ''),
    queryFn: () => groupsApi.members(groupId!),
    enabled: !!groupId,
  })
}

export function useCreateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: GroupCreate) => groupsApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QK.groups() }); toast.success('Group created') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useUpdateGroup(groupId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: GroupUpdate) => groupsApi.update(groupId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QK.groups() }); toast.success('Group updated') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useInviteMember(groupId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: InviteMember) => groupsApi.invite(groupId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QK.members(groupId) }); toast.success('Member invited') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useRemoveMember(groupId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => groupsApi.removeMember(groupId, userId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QK.members(groupId) }); toast.success('Member removed') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

// ─── Budget ───────────────────────────────────────────────────────────────────
export function useBudget(groupId: string | undefined, year: number, month: number) {
  return useQuery({
    queryKey: QK.budget(groupId ?? '', year, month),
    queryFn: () => budgetsApi.get(groupId!, year, month),
    enabled: !!groupId,
    retry: false, // 404 means no budget set — don't retry
  })
}

export function useUpsertBudget(groupId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: BudgetPeriodCreate) => budgetsApi.upsert(groupId, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: QK.budget(groupId, vars.year, vars.month) })
      qc.invalidateQueries({ queryKey: ['analytics'] })
      toast.success('Budget saved')
    },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

// ─── Categories ───────────────────────────────────────────────────────────────
export function useCategories(groupId?: string) {
  return useQuery({
    queryKey: QK.categories(groupId),
    queryFn: () => categoriesApi.list(groupId),
  })
}

export function useCreateCategory(groupId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CategoryCreate) => categoriesApi.create(groupId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categories'] }); toast.success('Category created') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useUpdateCategory(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CategoryUpdate) => categoriesApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categories'] }); toast.success('Category updated') },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useDeleteCategory(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body?: CategoryDeleteRequest) => categoriesApi.delete(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
      qc.invalidateQueries({ queryKey: ['transactions'] })
      toast.success('Category deleted')
    },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

// ─── Categorizer ──────────────────────────────────────────────────────────────
export function useCategorize() {
  return useMutation({
    mutationFn: (data: CategorizeRequest) => categorizerApi.suggest(data),
  })
}

// ─── Transactions ─────────────────────────────────────────────────────────────
export function useTransactions(filters: TransactionFilters = {}) {
  return useQuery({
    queryKey: QK.transactions(filters),
    queryFn: () => transactionsApi.list(filters),
  })
}

export function useTransaction(id: string | undefined) {
  return useQuery({
    queryKey: QK.transaction(id ?? ''),
    queryFn: () => transactionsApi.get(id!),
    enabled: !!id,
  })
}

export function useCreateTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TransactionCreate) => transactionsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['analytics'] })
      toast.success('Transaction added')
    },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useUpdateTransaction(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TransactionUpdate) => transactionsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['analytics'] })
      toast.success('Transaction updated')
    },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

export function useDeleteTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => transactionsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['analytics'] })
      toast.success('Transaction deleted')
    },
    onError: (e) => toast.error(parseApiError(e)),
  })
}

// ─── Analytics ────────────────────────────────────────────────────────────────
export function useAnalyticsSummary(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('summary', params),
    queryFn: () => analyticsApi.summary(params),
    enabled: enabled && !!params.group_id,
  })
}

export function useAnalyticsByCategory(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('by-category', params),
    queryFn: () => analyticsApi.byCategory(params),
    enabled: enabled && !!params.group_id,
  })
}

export function useAnalyticsByDay(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('by-day', params),
    queryFn: () => analyticsApi.byDay(params),
    enabled: enabled && !!params.group_id,
  })
}

export function useAnalyticsByMonth(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('by-month', params),
    queryFn: () => analyticsApi.byMonth(params),
    enabled: enabled && !!params.group_id,
  })
}

export function useAnalyticsByYear(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('by-year', params),
    queryFn: () => analyticsApi.byYear(params),
    enabled: enabled && !!params.group_id,
  })
}

export function useAnalyticsMembers(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('members', params),
    queryFn: () => analyticsApi.members(params),
    enabled: enabled && !!params.group_id,
  })
}

export function useAnalyticsInsights(params: AnalyticsFilters, enabled = true) {
  return useQuery({
    queryKey: QK.analytics('insights', params),
    queryFn: () => analyticsApi.insights(params),
    enabled: enabled && !!params.group_id,
  })
}
