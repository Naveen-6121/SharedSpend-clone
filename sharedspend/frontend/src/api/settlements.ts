import apiClient from './client'
import type { SettlementTransfer, SettlementRecordOut } from '@/types'

export const settlementsApi = {
  /** Calculate minimum transfers needed for the group settlement. */
  calculate(groupId: string, year?: number, month?: number): Promise<SettlementTransfer[]> {
    const params: Record<string, string> = {}
    if (year !== undefined) params.year = String(year)
    if (month !== undefined) params.month = String(month)
    return apiClient
      .get<SettlementTransfer[]>(`/settlements/groups/${groupId}/calculate`, { params })
      .then((r) => r.data)
  },

  /** List all persisted settlement records for the group. */
  list(groupId: string): Promise<SettlementRecordOut[]> {
    return apiClient
      .get<SettlementRecordOut[]>(`/settlements/groups/${groupId}`)
      .then((r) => r.data)
  },

  /** Persist a new PENDING settlement record. */
  create(
    groupId: string,
    fromUserId: string,
    originalTransactionId: string,
  ): Promise<SettlementRecordOut> {
    return apiClient
      .post<SettlementRecordOut>(`/settlements/groups/${groupId}`, {
        from_user_id: fromUserId,
        original_transaction_id: originalTransactionId,
      })
      .then((r) => r.data)
  },

  /** Mark a settlement record as SETTLED. */
  settle(settlementId: string): Promise<SettlementRecordOut> {
    return apiClient
      .put<SettlementRecordOut>(`/settlements/${settlementId}/settle`, {})
      .then((r) => r.data)
  },

  /** Delete a settlement record. */
  delete(settlementId: string): Promise<void> {
    return apiClient.delete(`/settlements/${settlementId}`).then(() => undefined)
  },
}
