import { beforeEach, describe, expect, it } from 'vitest'
import {
  budgetAlertsEnabled,
  setBudgetAlertsEnabled,
  takeNewBudgetThresholds,
} from '@/lib/budgetNotifications'

describe('budget threshold notifications', () => {
  beforeEach(() => localStorage.clear())

  it('is opt-in and emits each threshold once for a group and month', () => {
    expect(budgetAlertsEnabled()).toBe(false)
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 1000, 850)).toEqual([])

    setBudgetAlertsEnabled(true)
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 1000, 850)).toEqual([80])
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 1000, 900)).toEqual([])
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 1000, 1000)).toEqual([100])
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 1000, 1100)).toEqual([])
    expect(takeNewBudgetThresholds('user-a', 'group-b', 2026, 9, 1000, 850)).toEqual([80])
    expect(takeNewBudgetThresholds('user-b', 'group-a', 2026, 9, 1000, 850)).toEqual([80])
  })

  it('re-arms a threshold if spending drops below it and keeps disabled alerts silent', () => {
    setBudgetAlertsEnabled(true)
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 100, 85)).toEqual([80])
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 100, 70)).toEqual([])
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 100, 85)).toEqual([80])
    setBudgetAlertsEnabled(false)
    expect(takeNewBudgetThresholds('user-a', 'group-a', 2026, 9, 100, 100)).toEqual([])
  })
})
