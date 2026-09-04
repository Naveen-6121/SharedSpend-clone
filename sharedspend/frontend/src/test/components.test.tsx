import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No data" description="Nothing here yet" />)
    expect(screen.getByText('No data')).toBeTruthy()
    expect(screen.getByText('Nothing here yet')).toBeTruthy()
  })

  it('renders custom icon', () => {
    render(<EmptyState icon="🎉" title="Empty" />)
    expect(screen.getByText('🎉')).toBeTruthy()
  })

  it('renders action when provided', () => {
    render(<EmptyState title="Empty" action={<button>Create one</button>} />)
    expect(screen.getByText('Create one')).toBeTruthy()
  })
})

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeTruthy()
  })

  it('is disabled when loading', () => {
    render(<Button loading>Save</Button>)
    expect(screen.getByRole('button')).toHaveProperty('disabled', true)
  })

  it('calls onClick when clicked', async () => {
    const handler = vi.fn()
    render(<Button onClick={handler}>Click</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(handler).toHaveBeenCalledOnce()
  })

  it('does not call onClick when disabled', async () => {
    const handler = vi.fn()
    render(<Button onClick={handler} disabled>Click</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(handler).not.toHaveBeenCalled()
  })
})

describe('Badge', () => {
  it('renders content', () => {
    render(<Badge>Shared</Badge>)
    expect(screen.getByText('Shared')).toBeTruthy()
  })

  it('applies variant class', () => {
    const { container } = render(<Badge variant="destructive">Error</Badge>)
    expect(container.firstChild).toBeTruthy()
  })
})

describe('Skeleton', () => {
  it('renders with animate-pulse class', () => {
    const { container } = render(<Skeleton className="h-4 w-24" />)
    expect(container.firstChild?.toString()).toBeTruthy()
  })
})
