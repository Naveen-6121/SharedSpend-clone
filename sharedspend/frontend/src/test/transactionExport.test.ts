import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

import apiClient from '@/api/client'
import { transactionsApi } from '@/api/transactions'

describe('transactionsApi.exportCsv', () => {
  afterEach(() => vi.clearAllMocks())

  it('requests CSV using active filters and excludes list-only parameters', async () => {
    const blob = new Blob(['date,amount'])
    vi.mocked(apiClient.get).mockResolvedValue({ data: blob } as never)

    const result = await transactionsApi.exportCsv({
      group_id: 'group-1',
      type: 'SHARED',
      category_id: 'category-1',
      payer_id: 'payer-1',
      date_from: '2025-03-01',
      date_to: '2025-03-31',
      page: 3,
      page_size: 20,
      search: 'lunch',
    })

    expect(result).toBe(blob)
    expect(apiClient.get).toHaveBeenCalledWith('/transactions/export', {
      params: {
        group_id: 'group-1',
        type: 'SHARED',
        category_id: 'category-1',
        payer_id: 'payer-1',
        date_from: '2025-03-01',
        date_to: '2025-03-31',
        search: 'lunch',
      },
      responseType: 'blob',
    })
  })
})
