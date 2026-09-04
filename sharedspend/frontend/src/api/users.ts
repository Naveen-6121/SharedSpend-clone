import apiClient from './client'
import type { UserOut, UserUpdate, PasswordChange } from '@/types'

export const usersApi = {
  me: () =>
    apiClient.get<UserOut>('/users/me').then((r) => r.data),

  update: (data: UserUpdate) =>
    apiClient.put<UserOut>('/users/me', data).then((r) => r.data),

  changePassword: (data: PasswordChange) =>
    apiClient.put('/users/me/password', data).then((r) => r.data),
}
