import { describe, it, expect } from 'vitest'

// Transaction type validation rules (mirrors backend logic)
function validateTransactionPayload(payload: {
  type: 'SHARED' | 'PERSONAL'
  group_id?: string | null
  payer_id?: string | null
  amount?: number
  description?: string
  date?: string
}) {
  const errors: string[] = []

  if (!payload.description?.trim()) errors.push('Description is required')
  if (!payload.amount || payload.amount <= 0) errors.push('Amount must be positive')
  if (!payload.date) errors.push('Date is required')

  if (payload.type === 'SHARED') {
    if (!payload.group_id) errors.push('Group is required for shared transactions')
    if (!payload.payer_id) errors.push('Payer is required for shared transactions')
  }

  if (payload.type === 'PERSONAL') {
    if (payload.group_id) errors.push('Personal transactions must not have a group')
    if (payload.payer_id) errors.push('Personal transactions must not have a payer')
  }

  return errors
}

describe('Transaction payload validation', () => {
  it('passes for valid SHARED transaction', () => {
    const errs = validateTransactionPayload({
      type: 'SHARED', description: 'Groceries', amount: 500,
      date: '2025-01-15', group_id: 'g1', payer_id: 'u1',
    })
    expect(errs).toHaveLength(0)
  })

  it('passes for valid PERSONAL transaction', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Shirt', amount: 800,
      date: '2025-01-15', group_id: null, payer_id: null,
    })
    expect(errs).toHaveLength(0)
  })

  it('fails SHARED without group_id', () => {
    const errs = validateTransactionPayload({
      type: 'SHARED', description: 'Dinner', amount: 300,
      date: '2025-01-15', group_id: null, payer_id: 'u1',
    })
    expect(errs).toContain('Group is required for shared transactions')
  })

  it('fails SHARED without payer_id', () => {
    const errs = validateTransactionPayload({
      type: 'SHARED', description: 'Water', amount: 30,
      date: '2025-01-15', group_id: 'g1', payer_id: null,
    })
    expect(errs).toContain('Payer is required for shared transactions')
  })

  it('fails PERSONAL with group_id set', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Movie', amount: 250,
      date: '2025-01-15', group_id: 'g1', payer_id: null,
    })
    expect(errs).toContain('Personal transactions must not have a group')
  })

  it('fails with zero amount', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Test', amount: 0,
      date: '2025-01-15',
    })
    expect(errs).toContain('Amount must be positive')
  })

  it('fails with negative amount', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Test', amount: -100,
      date: '2025-01-15',
    })
    expect(errs).toContain('Amount must be positive')
  })

  it('fails with empty description', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: '  ', amount: 100,
      date: '2025-01-15',
    })
    expect(errs).toContain('Description is required')
  })
})

// Budget utilization edge cases
describe('Budget utilization calculation', () => {
  function calcUtilization(spent: number, budget: number | null) {
    if (budget == null || budget === 0) return null
    return (spent / budget) * 100
  }

  it('returns null when no budget set', () => {
    expect(calcUtilization(500, null)).toBeNull()
  })

  it('returns 0 when nothing spent', () => {
    expect(calcUtilization(0, 10000)).toBe(0)
  })

  it('returns 50 at half budget', () => {
    expect(calcUtilization(5000, 10000)).toBe(50)
  })

  it('returns 100 at full budget', () => {
    expect(calcUtilization(10000, 10000)).toBe(100)
  })

  it('exceeds 100 when over budget', () => {
    expect(calcUtilization(12000, 10000)).toBe(120)
  })

  it('handles decimal amounts correctly', () => {
    const result = calcUtilization(333.33, 1000)
    expect(result).toBeCloseTo(33.333)
  })
})
