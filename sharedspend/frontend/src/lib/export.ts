/**
 * Client-side export utilities — no third-party dependencies.
 * Produces a real .xlsx file using the SpreadsheetML (OOXML) format,
 * which is the same format Excel and Google Sheets use natively.
 */
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

/** Escape XML entities */
function xmlEsc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

/** Excel-safe string cell */
function strCell(col: string, row: number, value: string): string {
  return `<c r="${col}${row}" t="inlineStr"><is><t>${xmlEsc(String(value ?? ''))}</t></is></c>`
}

/** Number cell */
function numCell(col: string, row: number, value: number): string {
  return `<c r="${col}${row}"><v>${value}</v></c>`
}

/** Map column index (0-based) to Excel column letter(s) */
function colLetter(idx: number): string {
  let s = ''
  let n = idx
  while (n >= 0) {
    s = String.fromCharCode((n % 26) + 65) + s
    n = Math.floor(n / 26) - 1
  }
  return s
}

// ─── XLSX builder ─────────────────────────────────────────────────────────────

function buildXlsx(rows: ExportRow[], sheetName = 'Transactions'): Blob {
  const headers = ['Date', 'Description', 'Amount (₹)', 'Type', 'Payer', 'Category', 'Notes']

  const sheetRows: string[] = []

  // Header row
  const headerCells = headers.map((h, ci) => strCell(colLetter(ci), 1, h)).join('')
  sheetRows.push(`<row r="1">${headerCells}</row>`)

  // Data rows
  rows.forEach((r, ri) => {
    const rowIdx = ri + 2
    const cells = [
      strCell('A', rowIdx, r.date),
      strCell('B', rowIdx, r.description),
      numCell('C', rowIdx, r.amount),
      strCell('D', rowIdx, r.type),
      strCell('E', rowIdx, r.payer),
      strCell('F', rowIdx, r.category),
      strCell('G', rowIdx, r.notes),
    ].join('')
    sheetRows.push(`<row r="${rowIdx}">${cells}</row>`)
  })

  const sheetXml = `<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>${sheetRows.join('')}</sheetData>
</worksheet>`

  const workbookXml = `<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="${xmlEsc(sheetName)}" sheetId="1" r:id="rId1"/></sheets>
</workbook>`

  const relsXml = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="xl/worksheets/sheet1.xml"/>
</Relationships>`

  const contentTypesXml = `<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`

  // Build ZIP using fflate-style manual approach (use JSZip-compatible parts)
  // Since we cannot guarantee a zip library, use the CSV fallback for now
  // but trigger as .xlsx with BOM for Excel compatibility.
  // NOTE: For a proper XLSX, use the exported file parts as a ZIP.
  // We use a trick: encode as base64 in data URI and trigger download.
  const encoder = new TextEncoder()
  const parts: Record<string, Uint8Array> = {
    '[Content_Types].xml': encoder.encode(contentTypesXml),
    '_rels/.rels': encoder.encode(relsXml),
    'xl/workbook.xml': encoder.encode(workbookXml),
    'xl/worksheets/sheet1.xml': encoder.encode(sheetXml),
  }
  // Build a minimal ZIP manually
  return buildZip(parts)
}

/** Minimal ZIP builder — handles small files without compression */
function buildZip(files: Record<string, Uint8Array>): Blob {
  const chunks: Uint8Array[] = []
  const localOffsets: Record<string, number> = {}
  let offset = 0

  const enc = new TextEncoder()

  function u16le(n: number): Uint8Array {
    return new Uint8Array([n & 0xff, (n >> 8) & 0xff])
  }
  function u32le(n: number): Uint8Array {
    return new Uint8Array([n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >> 24) & 0xff])
  }
  function crc32(data: Uint8Array): number {
    const table = new Uint32Array(256)
    for (let i = 0; i < 256; i++) {
      let c = i
      for (let j = 0; j < 8; j++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1
      table[i] = c
    }
    let crc = 0xffffffff
    for (const byte of data) crc = table[(crc ^ byte) & 0xff] ^ (crc >>> 8)
    return (crc ^ 0xffffffff) >>> 0
  }
  function concat(...arrs: Uint8Array[]): Uint8Array {
    const len = arrs.reduce((s, a) => s + a.byteLength, 0)
    const out = new Uint8Array(len)
    let pos = 0
    for (const a of arrs) { out.set(a, pos); pos += a.byteLength }
    return out
  }

  const centralDir: Uint8Array[] = []

  for (const [name, data] of Object.entries(files)) {
    const nameBytes = enc.encode(name)
    const crc = crc32(data)
    const localHeader = concat(
      new Uint8Array([0x50, 0x4b, 0x03, 0x04]), // local file sig
      u16le(20),           // version needed
      u16le(0),            // flags
      u16le(0),            // no compression
      u16le(0), u16le(0),  // mod time/date
      u32le(crc),
      u32le(data.byteLength),
      u32le(data.byteLength),
      u16le(nameBytes.byteLength),
      u16le(0),            // extra field length
      nameBytes,
    )
    localOffsets[name] = offset
    chunks.push(localHeader, data)
    offset += localHeader.byteLength + data.byteLength

    const centralEntry = concat(
      new Uint8Array([0x50, 0x4b, 0x01, 0x02]), // central dir sig
      u16le(20), u16le(20), u16le(0), u16le(0),
      u16le(0), u16le(0),
      u32le(crc),
      u32le(data.byteLength), u32le(data.byteLength),
      u16le(nameBytes.byteLength), u16le(0), u16le(0), u16le(0), u16le(0),
      u32le(0),
      u32le(localOffsets[name]),
      nameBytes,
    )
    centralDir.push(centralEntry)
  }

  const centralDirBytes = concat(...centralDir)
  const eocd = concat(
    new Uint8Array([0x50, 0x4b, 0x05, 0x06]), // end of central dir
    u16le(0), u16le(0),
    u16le(centralDir.length), u16le(centralDir.length),
    u32le(centralDirBytes.byteLength),
    u32le(offset),
    u16le(0),
  )

  const allParts = [...chunks, centralDirBytes, eocd].map((u) => u.buffer as ArrayBuffer)
  return new Blob(allParts,
    { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
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
export function exportXlsx(rows: ExportRow[], filename: string) {
  const blob = buildXlsx(rows)
  triggerDownload(blob, filename)
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

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
