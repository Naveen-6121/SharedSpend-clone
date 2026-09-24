import type { SettlementRecordOut, TransactionOut, TransactionType } from '@/types'

export interface TransactionDisplayRow {
  key: string
  transactionId: string | null
  section: 'group' | 'personal'
  description: string
  date: string
  madeBy: string
  signedAmount: number
  label: string
  canEdit: boolean
}

export interface TransactionDisplayFilters {
  type: TransactionType | 'ALL'
  categoryId: string
  payerId: string
  search: string
  dateFrom: string
  dateTo: string
}

export function buildTransactionDisplayRows(
  transactions: TransactionOut[],
  settlements: SettlementRecordOut[],
  currentUserId: string,
  memberNames: Record<string, string>,
  filters: TransactionDisplayFilters,
): TransactionDisplayRow[] {
  const settlementById = new Map(settlements.map((settlement) => [settlement.id, settlement]))
  const rows: TransactionDisplayRow[] = transactions.map((transaction) => {
    const settlement = transaction.settlement_record_id
      ? settlementById.get(transaction.settlement_record_id)
      : undefined
    const isSettlement = Boolean(transaction.settlement_record_id)
    const isGroup = transaction.type === 'SHARED'
    const description = settlement
      ? `Payment to ${memberNames[settlement.to_user_id] ?? 'group member'} - ${settlement.original_description || transaction.description}`
      : transaction.description.replace(/\s*[·•]\s*/g, ' - ')

    return {
      key: transaction.id,
      transactionId: transaction.id,
      section: isGroup ? 'group' : 'personal',
      description,
      date: transaction.date,
      madeBy: memberNames[transaction.recorded_by_id] ?? 'Group member',
      signedAmount: -Math.abs(Number(transaction.amount)),
      label: isGroup ? 'Group Transaction' : isSettlement ? 'Settlement Payment' : 'Personal Expense',
      canEdit: !isSettlement && transaction.recorded_by_id === currentUserId,
    }
  })

  if (currentUserId && filters.type !== 'SHARED' && filters.categoryId === 'ALL') {
    settlements.forEach((settlement) => {
      if (
        settlement.status !== 'SETTLED' ||
        !settlement.payment_transaction_id ||
        settlement.to_user_id !== currentUserId ||
        !settlement.settled_at
      ) return

      const fromName = memberNames[settlement.from_user_id] ?? 'group member'
      const description = `Settlement received from ${fromName} - ${settlement.original_description ?? 'expense'}`
      const date = settlement.settled_at.slice(0, 10)
      const search = filters.search.trim().toLocaleLowerCase()
      if (filters.payerId !== 'ALL' && filters.payerId !== settlement.from_user_id) return
      if (filters.dateFrom && date < filters.dateFrom) return
      if (filters.dateTo && date > filters.dateTo) return
      if (search && !description.toLocaleLowerCase().includes(search)) return

      rows.push({
        key: `settlement-credit-${settlement.id}`,
        transactionId: null,
        section: 'personal',
        description,
        date,
        madeBy: fromName,
        signedAmount: Math.abs(Number(settlement.amount)),
        label: 'Settlement Credit',
        canEdit: false,
      })
    })
  }

  return rows.sort((a, b) => b.date.localeCompare(a.date) || a.key.localeCompare(b.key))
}
