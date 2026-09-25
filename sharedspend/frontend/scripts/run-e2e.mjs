import { randomBytes } from 'node:crypto'
import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoDir = resolve(frontendDir, '..')
const backendDir = resolve(repoDir, 'backend')
const python = process.env.SHAREDSPEND_E2E_PYTHON ?? resolve(
  backendDir,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
)
const viteCli = resolve(frontendDir, 'node_modules/vite/bin/vite.js')
const playwrightCli = resolve(frontendDir, 'node_modules/@playwright/test/cli.js')
const baseEnv = { ...process.env }

function start(command, args, cwd, env) {
  const child = spawn(command, args, { cwd, env, stdio: 'inherit', windowsHide: true })
  child.once('error', (error) => {
    console.error(`Could not start the E2E process (${command}): ${error.message}`)
  })
  return child
}

async function waitFor(url, child, label) {
  const deadline = Date.now() + 120_000
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`${label} exited before becoming ready`)
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // The process is still starting.
    }
    await delay(250)
  }
  throw new Error(`${label} did not become ready within two minutes`)
}

async function stop(child) {
  if (child.exitCode !== null) return
  child.kill('SIGTERM')
  await Promise.race([
    new Promise((resolveExit) => child.once('exit', resolveExit)),
    delay(3000).then(() => child.kill('SIGKILL')),
  ])
}

const backendEnv = {
  ...baseEnv,
  APP_ENV: 'development',
  DATABASE_URL: 'sqlite+aiosqlite://',
  SECRET_KEY: randomBytes(32).toString('hex'),
  CORS_ORIGINS: 'http://127.0.0.1:5174',
}
// The E2E backend is intentionally isolated on in-memory SQLite. Explicitly
// blank any inherited staging URL so it cannot trip selection or reach this app.
backendEnv.TEST_DATABASE_URL = ''
const frontendEnv = {
  ...baseEnv,
  VITE_API_BASE_URL: 'http://127.0.0.1:8001',
}

let backend
let vite
let exitCode = 1
try {
  backend = start(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001'], backendDir, backendEnv)
  await waitFor('http://127.0.0.1:8001/health', backend, 'Test backend')
  vite = start(process.execPath, [viteCli, '--host', '127.0.0.1', '--port', '5174', '--strictPort'], frontendDir, frontendEnv)
  await waitFor('http://127.0.0.1:5174/login', vite, 'Test frontend')
  const tests = start(process.execPath, [playwrightCli, 'test'], frontendDir, baseEnv)
  exitCode = await new Promise((resolveExit, reject) => {
    tests.once('error', reject)
    tests.once('exit', (code, signal) => resolveExit(code ?? (signal ? 1 : 0)))
  })
} catch (error) {
  console.error(error instanceof Error ? error.message : 'E2E setup failed')
} finally {
  if (vite) await stop(vite)
  if (backend) await stop(backend)
}

process.exitCode = Number(exitCode)
