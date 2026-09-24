import { cleanup, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { groupState, userState, apiMocks } = vi.hoisted(() => ({
  groupState: { activeGroup: null as null | { id: string; name: string } },
  userState: { user: { id: 'user-1' } },
  apiMocks: {
    summary: vi.fn(), forecast: vi.fn(), members: vi.fn(),
    list: vi.fn(), groupMembers: vi.fn(),
  },
}))

vi.mock('@/context/GroupContext', () => ({ useGroup: () => groupState }))
vi.mock('@/context/AuthContext', () => ({ useAuth: () => userState }))
vi.mock('@/api', () => ({
  analyticsApi: {
    summary: apiMocks.summary,
    forecast: apiMocks.forecast,
    members: apiMocks.members,
  },
  transactionsApi: { list: apiMocks.list },
  groupsApi: { members: apiMocks.groupMembers },
}))

import { DashboardPage } from '@/pages/DashboardPage'

describe('dashboard group and budget consistency', () => {
  afterEach(() => {
    cleanup()
    groupState.activeGroup = null
    vi.clearAllMocks()
  })

  it('survives the no-group to active-group transition and renders API budget values', async () => {
    apiMocks.summary.mockResolvedValue({
      budget: 1000, shared_spent: 0, remaining: 1000, utilization_pct: 0,
      personal_by_member: [], paid_by_member: [],
    })
    apiMocks.forecast.mockResolvedValue({
      projected_spend: 0, budget: 1000, on_track: true, days_elapsed: 1, days_in_month: 30,
    })
    apiMocks.members.mockResolvedValue([])
    apiMocks.list.mockResolvedValue({ items: [], total: 0 })
    apiMocks.groupMembers.mockResolvedValue([])

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const view = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><DashboardPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(view.getByText('No group yet')).toBeTruthy()

    groupState.activeGroup = { id: 'group-1', name: 'Home' }
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><DashboardPage /></MemoryRouter>
      </QueryClientProvider>,
    )

    await waitFor(() => expect(view.getAllByText('₹1,000').length).toBeGreaterThanOrEqual(2))
    expect(apiMocks.summary).toHaveBeenCalledOnce()
    expect(view.getByText('Home')).toBeTruthy()
    queryClient.clear()
  })
})
