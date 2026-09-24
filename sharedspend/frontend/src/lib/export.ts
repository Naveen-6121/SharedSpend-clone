/** Client-side transaction exports. */
import type { TransactionOut } from '@/types'
import { toLocalDateString } from './format'

// ─── Types ────────────────────────────────────────────────────────────────────
interface ExportRow {
  date: string
  description: string
  amount: number
  type: string
  payer: string
  category: string
  notes: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// ─── XLSX builder ─────────────────────────────────────────────────────────────

async function buildXlsx(rows: ExportRow[], sheetName = 'Transactions'): Promise<Blob> {
  const XLSX = await import('xlsx')
  const headers = ['Date', 'Description', 'Amount (₹)', 'Type', 'Payer', 'Category', 'Notes']
  const data = [headers, ...rows.map((row) => [
    row.date,
    row.description,
    row.amount,
    row.type,
    row.payer,
    row.category,
    row.notes,
  ])]
  const worksheet = XLSX.utils.aoa_to_sheet(data)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
  const file = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
  return new Blob([file], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Build export rows from transactions.
 * categoryMap: id → name, memberMap: user_id → display name
 */
export function buildExportRows(
  transactions: TransactionOut[],
  categoryMap: Record<string, string>,
  memberMap: Record<string, string>,
): ExportRow[] {
  return transactions.map((tx) => ({
    date: toLocalDateString(tx.date),
    description: tx.description,
    amount: tx.amount,
    type: tx.type,
    payer: tx.payer_id ? (memberMap[tx.payer_id] ?? tx.payer_id) : '—',
    category: tx.category_id ? (categoryMap[tx.category_id] ?? '') : '',
    notes: tx.notes ?? '',
  }))
}

/** Download transactions as XLSX */
export async function exportXlsx(rows: ExportRow[], filename: string) {
  const blob = await buildXlsx(rows)
  triggerDownload(blob, filename, true)
}

/** Download transactions as CSV */
export function exportCsv(rows: ExportRow[], filename: string) {
  const headers = ['Date', 'Description', 'Amount', 'Type', 'Payer', 'Category', 'Notes']
  const escape = (s: string | number) => {
    const str = String(s ?? '')
    if (str.includes(',') || str.includes('"') || str.includes('\n'))
      return `"${str.replace(/"/g, '""')}"`
    return str
  }
  const lines = [
    headers.join(','),
    ...rows.map((r) => [r.date, r.description, r.amount, r.type, r.payer, r.category, r.notes].map(escape).join(',')),
  ]
  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' })
  triggerDownload(blob, filename)
}

function triggerDownload(blob: Blob, filename: string, deferUrlRevoke = false) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  if (deferUrlRevoke) {
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } else {
    URL.revokeObjectURL(url)
  }
}
