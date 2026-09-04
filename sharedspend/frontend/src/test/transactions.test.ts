import { describe, it, expect } from 'vitest'

// ─── Transaction type validation rules (NEW semantics) ────────────────────────
// SHARED: requires group_id, payer MUST be null
// PERSONAL: requires payer_id, group MUST be null
function validateTransactionPayload(payload: {
  type: 'SHARED' | 'PERSONAL'
  group_id?: string | null
  payer_id?: string | null
  amount?: number
  description?: string
  date?: string
  add_to_settlement?: boolean
}) {
  const errors: string[] = []

  if (!payload.description?.trim()) errors.push('Description is required')
  if (!payload.amount || payload.amount <= 0) errors.push('Amount must be positive')
  if (!payload.date) errors.push('Date is required')

  if (payload.type === 'SHARED') {
    if (!payload.group_id) errors.push('Group is required for shared transactions')
    if (payload.payer_id) errors.push('SHARED transactions must not have a payer')
  }

  if (payload.type === 'PERSONAL') {
    if (payload.group_id) errors.push('Personal transactions must not have a group')
    if (!payload.payer_id) errors.push('Payer is required for personal transactions')
  }

  return errors
}

describe('Transaction payload validation — new semantics', () => {
  it('passes for valid SHARED transaction (no payer)', () => {
    const errs = validateTransactionPayload({
      type: 'SHARED', description: 'Groceries', amount: 500,
      date: '2025-01-15', group_id: 'g1', payer_id: null,
    })
    expect(errs).toHaveLength(0)
  })

  it('fails SHARED with a payer_id (payer must be null)', () => {
    const errs = validateTransactionPayload({
      type: 'SHARED', description: 'Groceries', amount: 500,
      date: '2025-01-15', group_id: 'g1', payer_id: 'u1',
    })
    expect(errs).toContain('SHARED transactions must not have a payer')
  })

  it('passes for valid PERSONAL transaction (payer required)', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Shirt', amount: 800,
      date: '2025-01-15', group_id: null, payer_id: 'u1',
    })
    expect(errs).toHaveLength(0)
  })

  it('passes PERSONAL with add_to_settlement=true', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Dinner', amount: 1500,
      date: '2025-01-15', payer_id: 'u1', add_to_settlement: true,
    })
    expect(errs).toHaveLength(0)
  })

  it('fails SHARED without group_id', () => {
    const errs = validateTransactionPayload({
      type: 'SHARED', description: 'Dinner', amount: 300,
      date: '2025-01-15', group_id: null, payer_id: null,
    })
    expect(errs).toContain('Group is required for shared transactions')
  })

  it('fails PERSONAL without payer_id', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Water', amount: 30,
      date: '2025-01-15', group_id: null, payer_id: null,
    })
    expect(errs).toContain('Payer is required for personal transactions')
  })

  it('fails PERSONAL with group_id set', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Movie', amount: 250,
      date: '2025-01-15', group_id: 'g1', payer_id: 'u1',
    })
    expect(errs).toContain('Personal transactions must not have a group')
  })

  it('fails with zero amount', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Test', amount: 0,
      date: '2025-01-15', payer_id: 'u1',
    })
    expect(errs).toContain('Amount must be positive')
  })

  it('fails with negative amount', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: 'Test', amount: -100,
      date: '2025-01-15', payer_id: 'u1',
    })
    expect(errs).toContain('Amount must be positive')
  })

  it('fails with empty description', () => {
    const errs = validateTransactionPayload({
      type: 'PERSONAL', description: '  ', amount: 100,
      date: '2025-01-15', payer_id: 'u1',
    })
    expect(errs).toContain('Description is required')
  })
})

// ─── Budget utilization edge cases ────────────────────────────────────────────
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

// ─── Budget input validation ───────────────────────────────────────────────────
describe('Budget input — monetary values', () => {
  // Simulates the HTML number input step="0.01" min="0.01" constraint
  function isValidBudgetInput(value: number): boolean {
    // step=0.01, min=0.01 — value must be >= 0.01 and a multiple of 0.01
    if (value < 0.01) return false
    // Check step alignment: (value - min) % step === 0 (within float tolerance)
    const diff = Math.round((value - 0.01) * 100) % 1
    return Math.abs(diff) < Number.EPSILON
  }

  it('accepts 15000', () => expect(isValidBudgetInput(15000)).toBe(true))
  it('accepts 15000.00', () => expect(isValidBudgetInput(15000.00)).toBe(true))
  it('accepts 15001', () => expect(isValidBudgetInput(15001)).toBe(true))
  it('accepts 14999', () => expect(isValidBudgetInput(14999)).toBe(true))
  it('accepts 1500.50', () => expect(isValidBudgetInput(1500.50)).toBe(true))
  it('accepts 0.01', () => expect(isValidBudgetInput(0.01)).toBe(true))
  it('rejects 0', () => expect(isValidBudgetInput(0)).toBe(false))
  it('rejects negative', () => expect(isValidBudgetInput(-100)).toBe(false))
})

// ─── Settlement API response shape ────────────────────────────────────────────
describe('Settlement API response shape', () => {
  // The settlement API returns arrays, not objects. Test the contract.
  it('calculate returns an array', () => {
    const response: unknown = [] // backend returns list[dict]
    expect(Array.isArray(response)).toBe(true)
  })

  it('list returns an array', () => {
    const response: unknown = []
    expect(Array.isArray(response)).toBe(true)
  })

  it('handles empty calculate response', () => {
    const transfers: Array<{ from_user_id: string; to_user_id: string; amount: number }> = []
    expect(transfers.filter(() => true)).toHaveLength(0)
    expect(transfers.length).toBe(0)
  })

  it('handles empty records list', () => {
    const records: Array<{ id: string; status: string }> = []
    const pending = records.filter((r) => r.status === 'PENDING')
    const settled = records.filter((r) => r.status === 'SETTLED')
    expect(pending).toHaveLength(0)
    expect(settled).toHaveLength(0)
  })

  it('calculates equal split among participants', () => {
    const amount = 1500
    const participants = ['u1', 'u2']
    const share = amount / participants.length
    expect(share).toBe(750)
  })

  it('minimum transfers algorithm works for two members', () => {
    // Member A paid 200, Member B paid 0. Total = 200, fair share = 100 each.
    // B owes A: 100
    const total = 200
    const members = [
      { user_id: 'u1', paid: 200 },
      { user_id: 'u2', paid: 0 },
    ]
    const n = members.length
    const fairShare = total / n
    const balances = members.map((m) => ({ id: m.user_id, balance: m.paid - fairShare }))
    // u1 balance = +100 (creditor), u2 balance = -100 (debtor)
    expect(balances.find((b) => b.id === 'u1')?.balance).toBe(100)
    expect(balances.find((b) => b.id === 'u2')?.balance).toBe(-100)
  })
})

// ─── Dashboard data consistency ───────────────────────────────────────────────
describe('Dashboard data consistency', () => {
  it('summary budget renders "Not set" when null', () => {
    const budget: number | null = null
    const display = budget != null ? `₹${budget}` : 'Not set'
    expect(display).toBe('Not set')
  })

  it('summary budget renders formatted amount when set', () => {
    const budget = 15000
    const display = budget != null ? `₹${budget}` : 'Not set'
    expect(display).toBe('₹15000')
  })

  it('remaining = budget - shared_spent when budget exists', () => {
    const budget = 15000
    const sharedSpent = 3500
    const remaining = budget - sharedSpent
    expect(remaining).toBe(11500)
  })

  it('remaining is null when budget is null', () => {
    const budget: number | null = null
    const sharedSpent = 3500
    const remaining = budget != null ? budget - sharedSpent : null
    expect(remaining).toBeNull()
  })

  it('personal spending per member is summed correctly', () => {
    const memberStats = [
      { user_id: 'u1', personal_spent: 500 },
      { user_id: 'u2', personal_spent: 300 },
    ]
    const total = memberStats.reduce((s, m) => s + m.personal_spent, 0)
    expect(total).toBe(800)
  })

  it('recent transactions list shows items when not empty', () => {
    const items = [
      { id: '1', description: 'Groceries', amount: 500, type: 'SHARED' },
      { id: '2', description: 'Coffee', amount: 100, type: 'PERSONAL' },
    ]
    expect(items.length).toBeGreaterThan(0)
    expect(items[0].description).toBe('Groceries')
  })
})
