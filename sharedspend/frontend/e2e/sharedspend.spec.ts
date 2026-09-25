import { randomBytes, randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { expect, request as playwrightRequest, test } from '@playwright/test'
import * as XLSX from 'xlsx'

const apiBase = 'http://127.0.0.1:8001/api/v1'

function credentials(label: string) {
  const id = randomUUID().replaceAll('-', '').slice(0, 10)
  return {
    username: `e2e_${label}_${id}`,
    email: `${label}_${id}@example.com`,
    displayName: `E2E ${label}`,
    password: `${randomBytes(24).toString('base64url')}A1!`,
  }
}

async function registerInBrowser(page: import('@playwright/test').Page, account: ReturnType<typeof credentials>) {
  await page.goto('/register')
  await page.getByLabel('Username').fill(account.username)
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Display Name').fill(account.displayName)
  await page.getByLabel('Password', { exact: true }).fill(account.password)
  await page.getByLabel('Confirm Password').fill(account.password)
  await page.getByRole('button', { name: 'Create Account' }).click()
  await page.locator('input[type="password"]').evaluateAll((inputs) => {
    inputs.forEach((input) => { (input as HTMLInputElement).value = '' })
  })
  await expect(page.getByText('No group yet')).toBeVisible()
}

test('two members complete budget, transactions, analytics, settlements, exports, alerts, and dark mode', async ({
  page,
  browser,
}) => {
  test.setTimeout(180_000)
  const owner = credentials('owner')
  const member = credentials('member')

  await registerInBrowser(page, owner)
  await page.getByRole('link', { name: 'Create Group' }).click()
  await page.getByLabel('Group Name').fill(`E2E Home ${owner.username.slice(-6)}`)
  await page.getByRole('button', { name: 'Create Group' }).click()
  await expect(page.getByRole('button', { name: /E2E Home/ })).toBeVisible()

  const memberContext = await browser.newContext()
  const memberPage = await memberContext.newPage()
  try {
    await registerInBrowser(memberPage, member)

    const api = await playwrightRequest.newContext({ baseURL: `${apiBase}/` })
    try {
      const ownerLogin = await api.post('auth/login', {
        data: { username: owner.username, password: owner.password },
      })
      expect(ownerLogin.ok()).toBeTruthy()
      const ownerTokens = await ownerLogin.json()
      const ownerApi = (path: string, method: 'get' | 'post' = 'get', data?: unknown) =>
        api[method](path.replace(/^\/+/, ''), {
          headers: { Authorization: `Bearer ${ownerTokens.access_token}` },
          ...(data === undefined ? {} : { data }),
        })

      const groupsResponse = await ownerApi('/groups')
      const groups = await groupsResponse.json()
      const group = groups.find((candidate: { name: string }) => candidate.name.startsWith('E2E Home'))
      expect(group).toBeTruthy()

      const ownerMe = await ownerApi('/users/me')
      const ownerId = (await ownerMe.json()).id as string

      await page.goto('/settings/group')
      await page.getByPlaceholder('Username to invite').fill(member.username)
      await page.getByRole('button', { name: 'Invite', exact: true }).click()
      await expect(page.getByText(member.displayName, { exact: true })).toBeVisible()

      const memberLogin = await api.post('auth/login', {
        data: { username: member.username, password: member.password },
      })
      expect(memberLogin.ok()).toBeTruthy()
      const memberTokens = await memberLogin.json()
      const memberApi = (path: string) => api.get(path.replace(/^\/+/, ''), {
        headers: { Authorization: `Bearer ${memberTokens.access_token}` },
      })
      const membersResponse = await ownerApi(`/groups/${group.id}`)
      const members = (await membersResponse.json()).members
      expect(members).toHaveLength(2)
      const memberId = members.find((row: { user_id: string }) => row.user_id !== ownerId).user_id as string

      const now = new Date()
      const year = now.getFullYear()
      const month = now.getMonth() + 1
      const previous = month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 }
      const previousBudget = await ownerApi(`/groups/${group.id}/budgets`, 'post', {
        year: previous.year, month: previous.month, amount: '800.00',
      })
      expect(previousBudget.ok()).toBeTruthy()

      await page.getByPlaceholder('Amount (₹)').fill('1000')
      await page.getByRole('button', { name: 'Set Budget' }).click()
      await expect(page.getByText('Current:')).toBeVisible()
      await page.getByRole('button', { name: 'Copy previous month' }).click()
      const amountInput = page.getByPlaceholder('Amount (₹)')
      await expect(amountInput).toHaveValue('800.00')
      const currentBeforeSave = await ownerApi(`/groups/${group.id}/budgets`)
      const beforeSaveRows = await currentBeforeSave.json()
      expect(Number(beforeSaveRows.find((row: { year: number; month: number }) =>
        row.year === year && row.month === month).amount)).toBe(1000)
      await page.getByRole('button', { name: 'Update' }).click()
      await expect(page.getByText('Budget saved!').first()).toBeVisible()
      await page.reload()
      await expect(page.getByPlaceholder('Amount (₹)')).toHaveValue('800.00')
      const savedResponse = await ownerApi(`/groups/${group.id}/budgets`)
      const savedRows = await savedResponse.json()
      expect(Number(savedRows.find((row: { year: number; month: number }) =>
        row.year === year && row.month === month).amount)).toBe(800)

      await page.context().grantPermissions(['notifications'])
      await page.getByRole('link', { name: 'Settings', exact: true }).click()
      await page.getByRole('button', { name: 'Alerts off' }).click()
      await expect(page.getByRole('button', { name: 'Alerts on' })).toBeVisible()

      const categoriesResponse = await ownerApi('/categories')
      const categories = await categoriesResponse.json()
      const category = categories[0] as { id: string; name: string }
      const today = new Date().toISOString().slice(0, 10)
      async function addSharedTransaction(description: string, amount: string) {
        await page.goto('/transactions/new')
        await page.getByLabel('Description').fill(description)
        await page.getByLabel(/Amount/).fill(amount)
        await page.getByLabel('Category').selectOption(category.id)
        await page.getByRole('button', { name: 'Add Transaction' }).click()
        await expect(page.getByRole('heading', { name: 'Transactions', exact: true })).toBeVisible()
        await expect(page.getByText(description, { exact: true })).toBeVisible()
      }

      await addSharedTransaction('E2E shared groceries', '650')
      await page.getByRole('link', { name: 'Dashboard', exact: true }).click()
      await expect(page.getByText(/used 80% of this month's shared budget/)).toBeVisible()
      await addSharedTransaction('E2E shared supplies', '150')
      await page.getByRole('link', { name: 'Dashboard', exact: true }).click()
      await expect(page.getByText(/used 100% of this month's shared budget/)).toBeVisible()
      await expect(page.getByText('Shared Spent')).toBeVisible()
      await expect(page.getByText('Shared Spent').locator('..').getByText('₹800', { exact: true })).toBeVisible()

      await page.getByRole('link', { name: 'Analytics', exact: true }).click()
      await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
      await expect(page.getByText(category.name, { exact: true }).first()).toBeVisible()
      await expect(page.locator('.recharts-pie-sector').first()).toBeVisible()
      await page.getByRole('tab', { name: 'Daily' }).click()
      await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible()
      await page.getByRole('tab', { name: 'Monthly' }).click()
      await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible()
      await page.getByRole('tab', { name: 'Yearly' }).click()
      await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible()
      await page.getByRole('tab', { name: 'Insights' }).click()
      await expect(page.getByText('Projected Spend')).toBeVisible()
      await expect(page.getByText(/₹800(?:\.00)?/).first()).toBeVisible()

      await page.setViewportSize({ width: 390, height: 844 })
      const horizontalOverflow = await page.evaluate(() =>
        document.documentElement.scrollWidth > window.innerWidth,
      )
      expect(horizontalOverflow).toBe(false)
      await page.setViewportSize({ width: 1280, height: 900 })

      await page.goto('/transactions')
      await page.getByRole('button', { name: 'Export' }).click()
      const csvDownloadPromise = page.waitForEvent('download')
      await page.getByRole('menuitem', { name: /CSV/ }).click()
      const csvDownload = await csvDownloadPromise
      const csv = await readFile((await csvDownload.path())!, 'utf8')
      expect(csv.split(/\r?\n/, 1)[0]).toBe(
        'id,date,amount,type,description,category,category_id,payer,payer_id,recorded_by,recorded_by_id,group_id,notes,add_to_settlement,created_at,updated_at',
      )
      expect(csv).toContain('E2E shared groceries')

      await page.getByRole('button', { name: 'Export' }).click()
      const xlsxDownloadPromise = page.waitForEvent('download')
      await page.getByRole('menuitem', { name: /Excel/ }).click()
      const xlsxDownload = await xlsxDownloadPromise
      const workbook = XLSX.read(await readFile((await xlsxDownload.path())!), { type: 'buffer' })
      const worksheet = workbook.Sheets[workbook.SheetNames[0]]
      expect(XLSX.utils.sheet_to_json(worksheet, { header: 1 })).toEqual(
        expect.arrayContaining([expect.arrayContaining(['E2E shared groceries'])]),
      )

      await page.getByRole('link', { name: 'Settings', exact: true }).click()
      await page.getByRole('button', { name: 'Light mode' }).click()
      await expect(page.locator('html')).toHaveClass(/dark/)
      await page.reload()
      await expect(page.getByRole('button', { name: 'Dark mode' })).toBeVisible()
      await expect(page.locator('html')).toHaveClass(/dark/)
      await page.getByRole('link', { name: 'Analytics', exact: true }).click()
      await expect(page.locator('.recharts-pie-sector').first()).toBeVisible()
      await page.getByRole('tab', { name: 'Daily' }).click()
      await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible()

      await page.goto('/transactions/new')
      await page.getByRole('button', { name: /Personal/ }).click()
      await page.getByLabel('Description').fill('E2E settlement lunch')
      await page.getByLabel(/Amount/).fill('200')
      await page.getByLabel('Paid by').selectOption(ownerId)
      await page.getByLabel('Add to Settlement').check()
      await page.getByLabel('Category').selectOption(category.id)
      await page.getByRole('button', { name: 'Add Transaction' }).click()
      await expect(page.getByRole('heading', { name: 'Transactions', exact: true })).toBeVisible()

      await page.getByRole('link', { name: 'Settlement', exact: true }).click()
      await expect(page.getByText(member.displayName, { exact: false })).toBeVisible()
      await expect(page.getByText(/₹100(?:\.00)?/).first()).toBeVisible()
      await page.getByRole('button', { name: 'Track payment' }).click()
      await expect(page.getByText('Awaiting payer')).toBeVisible()

      await memberPage.reload()
      await memberPage.goto('/settlement')
      await expect(memberPage.getByRole('button', { name: '✓ Mark as Paid' })).toBeVisible()
      await memberPage.getByRole('button', { name: '✓ Mark as Paid' }).click()
      await expect(memberPage.getByText('Settlement History')).toBeVisible()
      await memberPage.goto('/transactions')
      await expect(memberPage.getByText('E2E settlement lunch', { exact: true })).toHaveCount(0)
      await expect(memberPage.getByText(/settlement/i).first()).toBeVisible()

      // A group member and an invited member see the same shared total and budget.
      const memberSummary = await memberApi(
        `/analytics/summary?group_id=${group.id}&year=${year}&month=${month}`,
      )
      expect(memberSummary.ok()).toBeTruthy()
      const summary = await memberSummary.json()
      expect(Number(summary.shared_spent)).toBe(800)
      expect(Number(summary.budget)).toBe(800)
      expect(memberId).not.toBe(ownerId)
    } finally {
      await api.dispose()
    }
  } finally {
    await memberContext.close()
  }
})
