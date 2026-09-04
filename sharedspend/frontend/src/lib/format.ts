// ─── INR currency formatting ──────────────────────────────────────────────────
const inrFmt = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

export function formatINR(amount: number): string {
  return inrFmt.format(amount)
}

// ─── Date helpers ─────────────────────────────────────────────────────────────
export function toLocalDateString(isoDate: string): string {
  // isoDate = 'YYYY-MM-DD' — display as "12 Jan 2025"
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function todayISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function currentYear(): number {
  return new Date().getFullYear()
}

export function currentMonth(): number {
  return new Date().getMonth() + 1
}

export function monthName(month: number): string {
  return new Date(2000, month - 1, 1).toLocaleDateString('en-IN', { month: 'long' })
}

// ─── Error parsing ────────────────────────────────────────────────────────────
export function parseApiError(err: unknown): string {
  if (typeof err === 'object' && err !== null) {
    const e = err as { response?: { data?: { detail?: string | { msg: string }[] } } }
    const detail = e.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  }
  return 'An unexpected error occurred'
}

// ─── Budget utilization color ──────────────────────────────────────────────────
export function utilizationColor(pct: number | null): string {
  if (pct === null) return 'text-muted-foreground'
  if (pct >= 100) return 'text-destructive'
  if (pct >= 80) return 'text-yellow-600'
  return 'text-green-600'
}

export function utilizationBarColor(pct: number | null): string {
  if (pct === null) return 'bg-primary'
  if (pct >= 100) return 'bg-destructive'
  if (pct >= 80) return 'bg-yellow-500'
  return 'bg-green-500'
}
