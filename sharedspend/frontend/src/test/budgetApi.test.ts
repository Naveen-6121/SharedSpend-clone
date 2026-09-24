import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({ default: { get: vi.fn() } }))

import apiClient from '@/api/client'
import { budgetsApi } from '@/api/budgets'

describe('budget copy API', () => {
  afterEach(() => vi.clearAllMocks())

  it('loads the prior calendar month for review before saving', async () => {
    const previous = { group_id: 'group-1', year: 2025, month: 12, amount: 800 }
    vi.mocked(apiClient.get).mockResolvedValue({ data: previous } as never)

    await expect(budgetsApi.copyPrevious('group-1', 2026, 1)).resolves.toEqual(previous)
    expect(apiClient.get).toHaveBeenCalledWith('/groups/group-1/budgets/2026/1/previous')
  })

  it('keeps an unset prior period empty', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: null } as never)
    await expect(budgetsApi.copyPrevious('group-1', 2026, 2)).resolves.toBeNull()
  })

  it('returns null for a missing current budget so the query cache accepts it', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] } as never)
    await expect(budgetsApi.get('group-1', 2026, 2)).resolves.toBeNull()
  })
})
