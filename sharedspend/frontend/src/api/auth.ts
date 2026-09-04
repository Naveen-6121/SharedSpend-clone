import apiClient from './client'
import type { LoginRequest, TokenResponse, UserCreate } from '@/types'

export const authApi = {
  register: (data: UserCreate) =>
    apiClient.post<TokenResponse>('/auth/register', data).then((r) => r.data),

  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  refresh: (refresh_token: string) =>
    apiClient.post<TokenResponse>('/auth/refresh', { refresh_token }).then((r) => r.data),

  logout: () =>
    apiClient.post('/auth/logout').then((r) => r.data),
}
