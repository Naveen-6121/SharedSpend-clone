export const BUDGET_ALERTS_KEY = 'ss_budget_alerts_enabled'
const SENT_ALERTS_KEY = 'ss_budget_alerts_sent'
const THRESHOLDS = [80, 100] as const

export function budgetAlertsEnabled() {
  return localStorage.getItem(BUDGET_ALERTS_KEY) === 'true'
}

export function setBudgetAlertsEnabled(enabled: boolean) {
  localStorage.setItem(BUDGET_ALERTS_KEY, String(enabled))
}

/** Returns newly crossed thresholds once per group and month on this device. */
export function takeNewBudgetThresholds(
  userId: string,
  groupId: string,
  year: number,
  month: number,
  budget: number | null | undefined,
  spent: number,
): number[] {
  if (!budgetAlertsEnabled() || !budget || budget <= 0) return []

  const keyPrefix = `${userId}:${groupId}:${year}-${String(month).padStart(2, '0')}`
  const sent = new Set<string>(JSON.parse(localStorage.getItem(SENT_ALERTS_KEY) ?? '[]'))
  const ratio = (spent / budget) * 100
  const newlyReached: number[] = []

  for (const threshold of THRESHOLDS) {
    const key = `${keyPrefix}:${threshold}`
    if (ratio < threshold) {
      sent.delete(key)
    } else if (!sent.has(key)) {
      sent.add(key)
      newlyReached.push(threshold)
    }
  }

  localStorage.setItem(SENT_ALERTS_KEY, JSON.stringify([...sent]))
  return newlyReached
}
