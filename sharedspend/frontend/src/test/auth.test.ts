import { describe, it, expect, beforeEach } from 'vitest'
import { tokenStorage } from '@/api/client'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, val: string) => { store[key] = val },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

describe('tokenStorage', () => {
  beforeEach(() => localStorageMock.clear())

  it('returns null when no token stored', () => {
    expect(tokenStorage.getAccess()).toBeNull()
    expect(tokenStorage.getRefresh()).toBeNull()
  })

  it('stores and retrieves tokens', () => {
    tokenStorage.set('access-abc', 'refresh-xyz')
    expect(tokenStorage.getAccess()).toBe('access-abc')
    expect(tokenStorage.getRefresh()).toBe('refresh-xyz')
  })

  it('clears tokens', () => {
    tokenStorage.set('a', 'b')
    tokenStorage.clear()
    expect(tokenStorage.getAccess()).toBeNull()
    expect(tokenStorage.getRefresh()).toBeNull()
  })

  it('overwrites existing tokens', () => {
    tokenStorage.set('first', 'first-r')
    tokenStorage.set('second', 'second-r')
    expect(tokenStorage.getAccess()).toBe('second')
    expect(tokenStorage.getRefresh()).toBe('second-r')
  })
})
