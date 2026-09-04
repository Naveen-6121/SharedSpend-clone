import apiClient from './client'
import type {
  TransactionCreate,
  TransactionFilters,
  TransactionListResponse,
  TransactionOut,
  TransactionUpdate,
} from '@/types'

export const transactionsApi = {
  /**
   * List transactions. Backend returns a flat list[TransactionOut].
   * We wrap it in a paginated envelope so the UI can show counts and paginate.
   * The 'search' filter is stripped since the backend does not support it.
   */
  list: async (filters: TransactionFilters = {}): Promise<TransactionListResponse> => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { search: _search, ...backendFilters } = filters
    const page = filters.page ?? 1
    const page_size = filters.page_size ?? 20
    const items = await apiClient
      .get<TransactionOut[]>('/transactions', { params: backendFilters })
      .then((r) => r.data)
    return {
      items,
      total: items.length,   // approximate: backend applies offset/limit, so count = page items
      page,
      page_size,
    }
  },

  get: (id: string) =>
    apiClient.get<TransactionOut>(`/transactions/${id}`).then((r) => r.data),

  create: (data: TransactionCreate) =>
    apiClient.post<TransactionOut>('/transactions', data).then((r) => r.data),

  update: (id: string, data: TransactionUpdate) =>
    apiClient.put<TransactionOut>(`/transactions/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/transactions/${id}`).then((r) => r.data),
}
