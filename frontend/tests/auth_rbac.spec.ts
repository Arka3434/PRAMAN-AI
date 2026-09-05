import { expect, test } from '@playwright/test'

test.describe('Phase 15: Authentication, RBAC & Officer Identity', () => {
  test.beforeEach(async ({ page }) => {
    // Explicitly enforce real authentication mode for all tests in this suite
    await page.addInitScript(() => {
      window.sessionStorage.setItem('praman_e2e_real_auth', 'true')
    })
  })

  test('unauthenticated visitor is redirected to official /login page', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: 'PRAMAN AI' })).toBeVisible()
    await expect(page.getByText('Legal Metrology Automated Enforcement Portal')).toBeVisible()
    await expect(page.getByLabel(/Official Email Address/i)).toBeVisible()
    await expect(page.getByLabel(/^Password$/i)).toBeVisible()
  })

  test('login rejection displays official error banner for invalid credentials', async ({ page }) => {
    await page.goto('/login')

    await page.getByLabel(/Official Email Address/i).fill('inspector1@praman.gov.in')
    await page.getByLabel(/^Password$/i).fill('WrongPassword123!')
    await page.getByRole('button', { name: /Sign In to Enforcement Console/i }).click()

    await expect(page.getByText(/Invalid officer email address or password/i)).toBeVisible()
    await expect(page).toHaveURL(/\/login/)
  })

  test('successful officer login redirects to command center and renders officer credentials in top bar', async ({ page }) => {
    await page.goto('/login')

    await page.getByLabel(/Official Email Address/i).fill('admin@praman.gov.in')
    await page.getByLabel(/^Password$/i).fill('ValidPass123!@#')
    await page.getByRole('button', { name: /Sign In to Enforcement Console/i }).click()

    // Navigates to dashboard
    await expect(page).toHaveURL('/')
    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()

    // TopBar displays authenticated officer details
    await expect(page.getByRole('banner').getByText('Admin Officer')).toBeVisible()
    await expect(page.locator('#officer-logout-btn')).toBeVisible()

    // Admin sidebar displays Users link
    await expect(page.getByRole('link', { name: 'Users' })).toBeVisible()
  })

  test('role-based visibility: Inspector cannot see Users management in sidebar', async ({ page }) => {
    await page.goto('/login')

    await page.getByLabel(/Official Email Address/i).fill('inspector1@praman.gov.in')
    await page.getByLabel(/^Password$/i).fill('ValidPass123!@#')
    await page.getByRole('button', { name: /Sign In to Enforcement Console/i }).click()

    await expect(page).toHaveURL('/')
    await expect(page.getByRole('banner').getByText('Inspector Rajesh Kumar')).toBeVisible()

    // Field inspector has inspections access but NOT user administration
    await expect(page.getByRole('link', { name: 'Inspections', exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Users' })).not.toBeVisible()

    // Direct navigation to /users is guarded and blocked with 403 screen
    await page.goto('/users')
    await expect(page.getByText('Designated Role Required')).toBeVisible()
  })

  test('officer logout terminates session and returns to login screen', async ({ page }) => {
    await page.goto('/login')

    await page.getByLabel(/Official Email Address/i).fill('supervisor@praman.gov.in')
    await page.getByLabel(/^Password$/i).fill('ValidPass123!@#')
    await page.getByRole('button', { name: /Sign In to Enforcement Console/i }).click()

    await expect(page).toHaveURL('/')
    await expect(page.getByRole('banner').getByText('Supervising Officer Sharma')).toBeVisible()

    // Click Sign Out
    await page.locator('#officer-logout-btn').click()

    // Redirected to login
    await expect(page).toHaveURL(/\/login/)

    // Navigating back to protected route redirects to login
    await page.goto('/inspections')
    await expect(page).toHaveURL(/\/login/)
  })

  test('public consumer packaging transparency route remains accessible without authentication', async ({ page }) => {
    await page.goto('/consumer')
    await expect(page).toHaveURL('/consumer')
    await expect(page.getByRole('heading', { name: 'Consumer Packaging Transparency' })).toBeVisible()
    await expect(page.getByText('Consumer Transparency & Packaging Verification')).toBeVisible()
  })
})
