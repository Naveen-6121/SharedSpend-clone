import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  users: vi.fn(),
  setUserActive: vi.fn(),
  database: vi.fn(),
}))

vi.mock('@/api', () => ({ adminApi: api }))

import { AdminPage } from '@/pages/AdminPage'

function renderAdminPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AdminPage />
    </QueryClientProvider>,
  )
}

describe('AdminPage', () => {
  afterEach(() => vi.clearAllMocks())

  it('shows user management and database migration status', async () => {
    api.users.mockResolvedValue([{
      id: 'u1', username: 'alice', display_name: 'Alice', is_active: true,
      is_admin: true, created_at: '2026-09-01T00:00:00Z',
    }])
    api.database.mockResolvedValue({
      database_connected: true,
      current_revisions: ['head-a'],
      head_revisions: ['head-a'],
      migrations_current: true,
    })

    renderAdminPage()

    expect(await screen.findByText('@alice')).toBeInTheDocument()
    expect(await screen.findByText('Up to date')).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Disable' })).toBeDisabled()
  })

  it('sends user enable/disable changes and refreshes the list', async () => {
    api.users.mockResolvedValue([{
      id: 'u2', username: 'bob', display_name: 'Bob', is_active: true,
      is_admin: false, created_at: '2026-09-01T00:00:00Z',
    }])
    api.database.mockResolvedValue({
      database_connected: true, current_revisions: [], head_revisions: [], migrations_current: false,
    })
    api.setUserActive.mockResolvedValue({ id: 'u2', is_active: false })

    renderAdminPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Disable' }))

    await waitFor(() => expect(api.setUserActive).toHaveBeenCalledWith('u2', false))
    await waitFor(() => expect(api.users).toHaveBeenCalledTimes(2))
  })
})
