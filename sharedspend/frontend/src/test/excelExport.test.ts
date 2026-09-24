import { afterEach, describe, expect, it, vi } from 'vitest'
import * as XLSX from 'xlsx'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

import apiClient from '@/api/client'
import { transactionsApi } from '@/api/transactions'
import { exportXlsx } from '@/lib/export'

describe('Excel transaction export', () => {
  afterEach(() => vi.clearAllMocks())

  it('fetches all transactions in backend-supported pages', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: `tx-${index}` }))
    const secondPage = [{ id: 'tx-100' }]
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: firstPage, headers: { 'x-total-count': '101' } } as never)
      .mockResolvedValueOnce({ data: secondPage, headers: { 'x-total-count': '101' } } as never)

    const filters = {
      group_id: 'group-1',
      type: 'SHARED' as const,
      category_id: 'category-1',
      payer_id: 'payer-1',
      date_from: '2025-03-01',
      date_to: '2025-03-31',
      search: 'lunch',
    }
    const transactions = await transactionsApi.listAll(filters)

    expect(transactions).toHaveLength(101)
    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/transactions', {
      params: {
        group_id: 'group-1', type: 'SHARED', category_id: 'category-1',
        payer_id: 'payer-1',
        date_from: '2025-03-01', date_to: '2025-03-31', search: 'lunch', page: 1, page_size: 100,
      },
    })
    expect(apiClient.get).toHaveBeenNthCalledWith(2, '/transactions', {
      params: {
        group_id: 'group-1', type: 'SHARED', category_id: 'category-1',
        payer_id: 'payer-1',
        date_from: '2025-03-01', date_to: '2025-03-31', search: 'lunch', page: 2, page_size: 100,
      },
    })
  })

  it('downloads a readable XLSX workbook', async () => {
    let downloadedBlob: Blob | undefined
    const originalCreateObjectURL = URL.createObjectURL
    const originalRevokeObjectURL = URL.revokeObjectURL
    vi.useFakeTimers()
    const createObjectURL = vi.fn((blob: Blob) => {
      downloadedBlob = blob
      return 'blob:excel-export-test'
    })
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    })
    const clickedLinks: HTMLAnchorElement[] = []
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clickedLinks.push(this)
    })

    try {
      await exportXlsx([{
        date: '12 Jan 2025',
        description: 'Lunch & dinner',
        amount: 125.5,
        type: 'SHARED',
        payer: 'Alice',
        category: 'Food',
        notes: 'team meal',
      }], 'transactions.xlsx')

      expect(click).toHaveBeenCalledOnce()
      expect(clickedLinks[0].download).toBe('transactions.xlsx')
      expect(clickedLinks[0].href).toBe('blob:excel-export-test')
      expect(createObjectURL).toHaveBeenCalledOnce()
      expect(downloadedBlob?.type).toBe(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      )
      const bytes = new Uint8Array(await downloadedBlob!.arrayBuffer())
      expect(Array.from(bytes.slice(0, 4))).toEqual([0x50, 0x4b, 0x03, 0x04])
      expect(Array.from(bytes.slice(-22, -18))).toEqual([0x50, 0x4b, 0x05, 0x06])
      const workbook = XLSX.read(bytes, { type: 'array' })
      expect(workbook.SheetNames).toEqual(['Transactions'])
      expect(XLSX.utils.sheet_to_json(workbook.Sheets.Transactions, { header: 1 })).toEqual([
        ['Date', 'Description', 'Amount (₹)', 'Type', 'Payer', 'Category', 'Notes'],
        ['12 Jan 2025', 'Lunch & dinner', 125.5, 'SHARED', 'Alice', 'Food', 'team meal'],
      ])
      expect(revokeObjectURL).not.toHaveBeenCalled()
      vi.advanceTimersByTime(1000)
      expect(revokeObjectURL).toHaveBeenCalledOnce()
    } finally {
      Object.defineProperty(URL, 'createObjectURL', {
        configurable: true,
        value: originalCreateObjectURL,
      })
      Object.defineProperty(URL, 'revokeObjectURL', {
        configurable: true,
        value: originalRevokeObjectURL,
      })
      click.mockRestore()
      vi.useRealTimers()
    }
  })
})
