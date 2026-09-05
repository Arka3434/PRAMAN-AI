import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('Phase 6H: Inspection History & Report Management workflow', async ({ page }) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  // 1. Create a new inspection through workflow
  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  // Upload and analyze
  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()
  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

  // Review and finalize
  await page.getByRole('button', { name: 'Confirm' }).click()
  await page.getByRole('button', { name: 'Finalize inspection' }).click()
  await expect(page.getByText('COMPLETED')).toBeVisible()

  // 2. Navigate to Inspections History Register (/inspections)
  await page.goto('/inspections')
  await expect(page.getByRole('heading', { name: 'Inspections' })).toBeVisible()

  // Verify table is populated
  const table = page.locator('[data-testid="inspections-table"]')
  await expect(table).toBeVisible()

  // Verify filter tabs exist and can be clicked
  const completedTab = page.locator('[data-testid="filter-tab-completed"]')
  await expect(completedTab).toBeVisible()
  await completedTab.click()

  // In completed filter, completed inspection row should have download report button
  const reportBtn = page.locator('[data-testid="download-report-button"]').first()
  await expect(reportBtn).toBeVisible()

  // 3. Test opening an existing inspection from history
  const openBtn = page.locator('[data-testid="open-inspection-button"]').first()
  await expect(openBtn).toBeVisible()
  await openBtn.click()

  // Should navigate back to the workflow page
  await expect(page).toHaveURL(/\/inspections\/[a-zA-Z0-9-]+/)
  await expect(page.getByTestId('compliance-summary-card')).toBeVisible()

  // 4. Navigate to Reports Register (/reports)
  await page.goto('/reports')
  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible()

  const reportsTable = page.locator('[data-testid="reports-table"]')
  await expect(reportsTable).toBeVisible()

  // Verify report download from reports register
  const reportDownloadBtn = page.locator('[data-testid="download-report-button"]').first()
  await expect(reportDownloadBtn).toBeVisible()

  const downloadPromise = page.waitForEvent('download')
  await reportDownloadBtn.click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^praman_inspection_report_.*\.pdf$/)
})
