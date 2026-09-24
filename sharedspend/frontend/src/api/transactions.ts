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
   * Search and all supported date/category filters are handled by the backend.
   */
  list: async (filters: TransactionFilters = {}): Promise<TransactionListResponse> => {
    const page = filters.page ?? 1
    const page_size = filters.page_size ?? 20
    const response = await apiClient.get<TransactionOut[]>('/transactions', { params: filters })
    const items = response.data
    return {
      items,
      total: Number(response.headers['x-total-count'] ?? items.length),
      page,
      page_size,
    }
  },

  /** Fetch every matching transaction using the backend's 100-row page limit. */
  listAll: async (filters: TransactionFilters = {}): Promise<TransactionOut[]> => {
    const pageSize = 100
    const items: TransactionOut[] = []
    let page = 1

    while (true) {
      const result = await transactionsApi.list({ ...filters, page, page_size: pageSize })
      items.push(...result.items)
      if (result.items.length < pageSize) return items
      page += 1
    }
  },

  exportCsv: (filters: TransactionFilters = {}) => {
    const { page: _page, page_size: _pageSize, ...backendFilters } = filters
    return apiClient.get<Blob>('/transactions/export', {
      params: backendFilters,
      responseType: 'blob',
    }).then((r) => r.data)
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
