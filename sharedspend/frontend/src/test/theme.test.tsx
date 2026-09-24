import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { ThemeProvider, useTheme } from '@/context/ThemeContext'

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return <button onClick={toggleTheme}>{theme}</button>
}

describe('theme preference', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => {
    cleanup()
    document.documentElement.classList.remove('dark')
  })

  it('toggles, applies, and persists dark mode', () => {
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'light' }))

    expect(screen.getByRole('button', { name: 'dark' })).toBeTruthy()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('ss_theme')).toBe('dark')
  })

  it('restores the saved preference', () => {
    localStorage.setItem('ss_theme', 'dark')
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    expect(screen.getByRole('button', { name: 'dark' })).toBeTruthy()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
