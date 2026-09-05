import { defineConfig, devices } from '@playwright/test'
import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

function getDynamicTestAuth(): { token: string; storagePath: string } {
  let token = process.env.TEST_AUTH_TOKEN || ''
  let adminUser: Record<string, unknown> = {
    id: '15851906-e313-4a9c-84a2-4c662fdf26d2',
    email: 'admin@praman.gov.in',
    full_name: 'Admin Officer',
    role: 'ADMIN',
    designation: 'Chief Administrator',
    badge_number: null,
    jurisdiction_office: 'Central HQ',
    is_active: true,
  }

  try {
    const backendDir = path.resolve(__dirname, '..', 'backend')
    const pythonExe =
      process.platform === 'win32'
        ? path.resolve(__dirname, '..', '.venv', 'Scripts', 'python.exe')
        : path.resolve(__dirname, '..', '.venv', 'bin', 'python')

    const script = [
      'from app.db.session import SessionLocal',
      'from app.models.user import User',
      'from app.core.security import create_access_token',
      'import json',
      'db = SessionLocal()',
      "u = db.query(User).filter(User.email == 'admin@praman.gov.in').first()",
      'token = create_access_token(str(u.id), role=u.role, email=u.email)',
      "print(json.dumps({'token': token, 'user': {'id': str(u.id), 'email': u.email, 'full_name': u.full_name, 'role': u.role, 'designation': u.designation, 'badge_number': u.badge_number, 'jurisdiction_office': u.jurisdiction_office, 'is_active': u.is_active}}))",
    ].join('; ')

    const out = execSync(`"${pythonExe}" -c "${script}"`, {
      cwd: backendDir,
      encoding: 'utf-8',
    }).trim()

    const parsed = JSON.parse(out)
    if (!token && parsed.token) {
      token = parsed.token
    }
    if (parsed.user) {
      adminUser = parsed.user
    }
  } catch (err) {
    console.warn('Could not generate dynamic E2E auth token:', err)
  }

  const authDir = path.resolve(__dirname, '.playwright', 'auth')
  fs.mkdirSync(authDir, { recursive: true })
  const storagePath = path.join(authDir, 'admin_auth.json')

  const storageState = {
    cookies: [],
    origins: [
      {
        origin: 'http://127.0.0.1:5173',
        localStorage: [
          { name: 'praman_token', value: token },
          { name: 'praman_user', value: JSON.stringify(adminUser) },
        ],
      },
      {
        origin: 'http://localhost:5173',
        localStorage: [
          { name: 'praman_token', value: token },
          { name: 'praman_user', value: JSON.stringify(adminUser) },
        ],
      },
      {
        origin: 'http://127.0.0.1:5174',
        localStorage: [
          { name: 'praman_token', value: token },
          { name: 'praman_user', value: JSON.stringify(adminUser) },
        ],
      },
      {
        origin: 'http://localhost:5174',
        localStorage: [
          { name: 'praman_token', value: token },
          { name: 'praman_user', value: JSON.stringify(adminUser) },
        ],
      },
    ],
  }

  fs.writeFileSync(storagePath, JSON.stringify(storageState, null, 2), 'utf-8')
  return { token, storagePath }
}

const dynamicAuth = getDynamicTestAuth()

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    headless: true,
  },
  projects: [
    {
      name: 'auth',
      testMatch: /auth_rbac\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
      },
    },
    {
      name: 'chromium',
      testIgnore: /auth_rbac\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: dynamicAuth.storagePath,
        extraHTTPHeaders: dynamicAuth.token
          ? {
              Authorization: `Bearer ${dynamicAuth.token}`,
            }
          : undefined,
      },
    },
  ],
})
