import { describe, it, expect } from 'vitest'
import { formatINR, parseApiError, todayISO, toLocalDateString, utilizationColor, utilizationBarColor } from '@/lib/format'

describe('formatINR', () => {
  it('formats zero', () => expect(formatINR(0)).toContain('0'))
  it('formats thousands', () => { const r = formatINR(20000); expect(r).toContain('20,000') })
  it('formats decimals correctly', () => { const r = formatINR(1234.56); expect(r).toContain('1,234.56') })
  it('includes ₹ symbol', () => expect(formatINR(100)).toMatch(/₹/))
  it('handles large amounts without float errors', () => {
    // 1/3 of 100 should not produce repeating decimals in display
    const r = formatINR(100 / 3)
    expect(r).toBeTruthy()
    expect(r.split('.')[1]?.length ?? 0).toBeLessThanOrEqual(2)
  })
})

describe('parseApiError', () => {
  it('extracts string detail', () => {
    expect(parseApiError({ response: { data: { detail: 'Invalid credentials' } } })).toBe('Invalid credentials')
  })
  it('extracts array detail', () => {
    expect(parseApiError({ response: { data: { detail: [{ msg: 'Field required' }] } } })).toBe('Field required')
  })
  it('returns fallback for unknown error', () => {
    expect(parseApiError(null)).toBe('An unexpected error occurred')
  })
  it('returns fallback for empty object', () => {
    expect(parseApiError({})).toBe('An unexpected error occurred')
  })
})

describe('todayISO', () => {
  it('returns YYYY-MM-DD format', () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
  it('returns current date', () => {
    const d = new Date()
    const expected = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    expect(todayISO()).toBe(expected)
  })
})

describe('toLocalDateString', () => {
  it('formats a date string correctly', () => {
    const result = toLocalDateString('2025-01-15')
    expect(result).toContain('15')
    expect(result).toContain('Jan')
    expect(result).toContain('2025')
  })
})

describe('utilizationColor', () => {
  it('returns muted for null', () => expect(utilizationColor(null)).toContain('muted'))
  it('returns destructive for >= 100', () => expect(utilizationColor(100)).toContain('destructive'))
  it('returns yellow for >= 80', () => expect(utilizationColor(80)).toContain('yellow'))
  it('returns green for < 80', () => expect(utilizationColor(50)).toContain('green'))
})

describe('utilizationBarColor', () => {
  it('returns primary for null', () => expect(utilizationBarColor(null)).toContain('primary'))
  it('returns destructive for >= 100', () => expect(utilizationBarColor(105)).toContain('destructive'))
  it('returns yellow for >= 80', () => expect(utilizationBarColor(85)).toContain('yellow'))
  it('returns green for < 80', () => expect(utilizationBarColor(40)).toContain('green'))
})
