import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TransactionSection } from '@/components/TransactionSection'
import { buildTransactionDisplayRows } from '@/lib/transactionPresentation'
import type { SettlementRecordOut, TransactionOut } from '@/types'

const groupExpense: TransactionOut = {
  id: 'group-expense', description: 'Movie Night', amount: 867, date: '2026-09-10', type: 'SHARED',
  category_id: null, group_id: 'home', payer_id: null, recorded_by_id: 'naveen',
  suggested_category_id: null, notes: null, add_to_settlement: false, settlement_group_id: null,
  settlement_participant_ids: null, settlement_record_id: null, is_deleted: false,
  created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-10T00:00:00Z',
}

const settlementPayment: TransactionOut = {
  ...groupExpense, id: 'payment', description: 'Payment to Alekhya · Movie', amount: 433.5,
  type: 'PERSONAL', group_id: null, payer_id: 'naveen', recorded_by_id: 'naveen',
  settlement_record_id: 'settlement-1',
}

const settledRecord: SettlementRecordOut = {
  id: 'settlement-1', group_id: 'home', from_user_id: 'naveen', to_user_id: 'alekhya',
  amount: 433.5, original_transaction_id: 'movie', original_description: 'Movie',
  original_amount: 867, original_transaction_date: '2026-09-08', payment_transaction_id: 'payment',
  status: 'SETTLED', settled_at: '2026-09-11T12:00:00Z', created_at: '2026-09-10T12:00:00Z',
}

const names = { naveen: 'Naveen', alekhya: 'Alekhya' }
const allFilters = { type: 'ALL' as const, categoryId: 'ALL', payerId: 'ALL', search: '', dateFrom: '', dateTo: '' }

describe('transaction presentation', () => {
  it('separates group and personal expenses and uses debit amounts', () => {
    const rows = buildTransactionDisplayRows([groupExpense], [], 'naveen', names, allFilters)
    expect(rows).toEqual([expect.objectContaining({
      section: 'group', description: 'Movie Night', label: 'Group Transaction',
      madeBy: 'Naveen', signedAmount: -867,
    })])
  })

  it('labels the debtor payment with the payee and original expense', () => {
    const rows = buildTransactionDisplayRows([settlementPayment], [settledRecord], 'naveen', names, allFilters)
    expect(rows[0]).toMatchObject({
      section: 'personal', description: 'Payment to Alekhya - Movie',
      label: 'Settlement Payment', madeBy: 'Naveen', signedAmount: -433.5, canEdit: false,
    })
  })

  it('shows a positive settlement credit only to the recipient, without exposing the source expense', () => {
    const rows = buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, allFilters)
    expect(rows).toEqual([expect.objectContaining({
      section: 'personal', description: 'Settlement received from Naveen - Movie',
      label: 'Settlement Credit', madeBy: 'Naveen', signedAmount: 433.5, canEdit: false,
    })])
  })

  it('respects transaction type, category, payer, search, and date filters for settlement credits', () => {
    expect(buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, {
      ...allFilters, type: 'SHARED',
    })).toHaveLength(0)
    expect(buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, {
      ...allFilters, categoryId: 'food',
    })).toHaveLength(0)
    expect(buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, {
      ...allFilters, payerId: 'alekhya',
    })).toHaveLength(0)
    expect(buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, {
      ...allFilters, search: 'rent',
    })).toHaveLength(0)
    expect(buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, {
      ...allFilters, dateFrom: '2026-09-12',
    })).toHaveLength(0)
  })
})

describe('transaction section layout', () => {
  it('renders aligned labels and distinct debit/credit colors', () => {
    const rows = buildTransactionDisplayRows([groupExpense], [], 'naveen', names, allFilters)
    const onEdit = vi.fn()
    const onDelete = vi.fn()
    render(<TransactionSection title="GROUP TRANSACTIONS" rows={rows} isLoading={false} onEdit={onEdit} onDelete={onDelete} />)

    expect(screen.getByText('Transaction')).toBeInTheDocument()
    expect(screen.getByText('Made By')).toBeInTheDocument()
    expect(screen.getByText('Amount')).toBeInTheDocument()
    expect(screen.getByText('Group Transaction')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit Movie Night' })).toBeInTheDocument()
    expect(screen.getByLabelText('Debit -₹867')).toHaveClass('text-red-700', 'dark:text-red-400')
    const item = within(screen.getByRole('list', { name: 'GROUP TRANSACTIONS list' })).getByRole('listitem')
    const header = screen.getByText('Amount').parentElement
    expect(header).toHaveClass('grid-cols-[minmax(0,1fr)_minmax(4rem,0.4fr)_6rem_3.5rem]')
    expect(header).toHaveClass('sm:grid-cols-[minmax(0,1fr)_minmax(8rem,0.48fr)_8rem_4rem]')
    expect(item).toHaveClass('grid-cols-[minmax(0,1fr)_minmax(4rem,0.4fr)_6rem_3.5rem]')
    expect(item).toHaveClass('sm:grid-cols-[minmax(0,1fr)_minmax(8rem,0.48fr)_8rem_4rem]')
  })

  it('renders credits with a positive sign and green color', () => {
    const rows = buildTransactionDisplayRows([], [settledRecord], 'alekhya', names, allFilters)
    render(<TransactionSection title="PERSONAL TRANSACTIONS" rows={rows} isLoading={false} onEdit={vi.fn()} onDelete={vi.fn()} />)

    expect(screen.getByText('Settlement received from Naveen - Movie')).toBeInTheDocument()
    expect(screen.getByLabelText('Credit +₹433.50')).toHaveClass('text-emerald-700', 'dark:text-emerald-400')
    expect(screen.queryByRole('button', { name: /Edit|Delete/ })).not.toBeInTheDocument()
    const header = screen.getByText('Amount').parentElement
    const item = within(screen.getByRole('list', { name: 'PERSONAL TRANSACTIONS list' })).getByRole('listitem')
    expect(item.className).toContain('grid-cols-[minmax(0,1fr)_minmax(4rem,0.4fr)_6rem_3.5rem]')
    expect(item.className).toContain('sm:grid-cols-[minmax(0,1fr)_minmax(8rem,0.48fr)_8rem_4rem]')
    expect(header?.className).toContain('grid-cols-[minmax(0,1fr)_minmax(4rem,0.4fr)_6rem_3.5rem]')
    expect(header?.className).toContain('sm:grid-cols-[minmax(0,1fr)_minmax(8rem,0.48fr)_8rem_4rem]')
  })
})
