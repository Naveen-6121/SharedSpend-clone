import apiClient from './client'
import type { AdminUserOut, DatabaseStatusOut } from '@/types'

export const adminApi = {
  users: () => apiClient.get<AdminUserOut[]>('/admin/users').then((r) => r.data),

  setUserActive: (userId: string, is_active: boolean) =>
    apiClient.patch<AdminUserOut>(`/admin/users/${userId}/status`, { is_active }).then((r) => r.data),

  database: () => apiClient.get<DatabaseStatusOut>('/admin/database').then((r) => r.data),
}
