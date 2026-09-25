import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from '@playwright/test'

const frontendDir = dirname(fileURLToPath(import.meta.url))
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    browserName: 'chromium',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
})
