import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { groupState, userState, apiMocks } = vi.hoisted(() => ({
  groupState: {
    activeGroup: { id: 'family-group', name: 'Family' },
    isOwner: true,
    reloadGroups: vi.fn(),
  },
  userState: { user: { id: 'owner-1' } },
  apiMocks: {
    getBudget: vi.fn(),
    copyPrevious: vi.fn(),
    upsertBudget: vi.fn(),
    members: vi.fn(),
    invite: vi.fn(),
    updateGroup: vi.fn(),
    removeMember: vi.fn(),
  },
}))

vi.mock('@/context/GroupContext', () => ({ useGroup: () => groupState }))
vi.mock('@/context/AuthContext', () => ({ useAuth: () => userState }))
vi.mock('@/api', () => ({
  budgetsApi: {
    get: apiMocks.getBudget,
    copyPrevious: apiMocks.copyPrevious,
    upsert: apiMocks.upsertBudget,
  },
  groupsApi: {
    members: apiMocks.members,
    invite: apiMocks.invite,
    update: apiMocks.updateGroup,
    removeMember: apiMocks.removeMember,
  },
}))

import { GroupSettingsPage } from '@/pages/GroupPages'

describe('budget copy and save flow', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('copies into the editable field without saving, then saves through the current-period upsert', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    apiMocks.getBudget.mockResolvedValue({ amount: 1000 })
    apiMocks.copyPrevious.mockResolvedValue({ amount: 800 })
    apiMocks.upsertBudget.mockResolvedValue({ amount: 800 })
    apiMocks.members.mockResolvedValue([
      { id: 'membership-1', user_id: 'owner-1', role: 'OWNER', display_name: 'Naveen', joined_at: '2026-01-01T00:00:00Z' },
      { id: 'membership-2', user_id: 'member-1', role: 'MEMBER', display_name: 'Alekhya', joined_at: '2026-01-01T00:00:00Z' },
    ])

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><GroupSettingsPage /></MemoryRouter>
      </QueryClientProvider>,
    )

    const amount = await screen.findByPlaceholderText('Amount (₹)') as HTMLInputElement
    await waitFor(() => expect(amount).toHaveValue(1000))
    await user.click(screen.getByRole('button', { name: 'Copy previous month' }))
    await waitFor(() => expect(amount).toHaveValue(800))
    expect(apiMocks.copyPrevious).toHaveBeenCalledWith(
      'family-group', expect.any(Number), expect.any(Number),
    )
    expect(apiMocks.upsertBudget).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Update' }))
    await waitFor(() => expect(apiMocks.upsertBudget).toHaveBeenCalledOnce())
    expect(apiMocks.upsertBudget).toHaveBeenCalledWith('family-group', {
      year: expect.any(Number),
      month: expect.any(Number),
      amount: 800,
    })
    queryClient.clear()
  })
})
