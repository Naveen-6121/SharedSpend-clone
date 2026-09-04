import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, tokenStorage, usersApi } from '@/api'
import type { LoginRequest, UserCreate, UserOut } from '@/types'

interface AuthState {
  user: UserOut | null
  isAuthenticated: boolean
  isLoading: boolean
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>
  register: (data: UserCreate) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
  })

  const loadUser = useCallback(async () => {
    const token = tokenStorage.getAccess()
    if (!token) {
      setState({ user: null, isAuthenticated: false, isLoading: false })
      return
    }
    try {
      const user = await usersApi.me()
      setState({ user, isAuthenticated: true, isLoading: false })
    } catch {
      tokenStorage.clear()
      setState({ user: null, isAuthenticated: false, isLoading: false })
    }
  }, [])

  useEffect(() => {
    loadUser()
  }, [loadUser])

  // Listen for forced logout from 401 interceptor
  useEffect(() => {
    const handler = () => setState({ user: null, isAuthenticated: false, isLoading: false })
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  const login = async (data: LoginRequest) => {
    const tokens = await authApi.login(data)
    tokenStorage.set(tokens.access_token, tokens.refresh_token)
    const user = await usersApi.me()
    setState({ user, isAuthenticated: true, isLoading: false })
  }

  const register = async (data: UserCreate) => {
    const tokens = await authApi.register(data)
    tokenStorage.set(tokens.access_token, tokens.refresh_token)
    const user = await usersApi.me()
    setState({ user, isAuthenticated: true, isLoading: false })
  }

  const logout = async () => {
    try { await authApi.logout() } catch { /* ignore */ }
    tokenStorage.clear()
    setState({ user: null, isAuthenticated: false, isLoading: false })
  }

  const refreshUser = async () => {
    const user = await usersApi.me()
    setState((s) => ({ ...s, user }))
  }

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
