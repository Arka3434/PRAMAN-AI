import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('Phase 6G: Report Generation & Evidence-Backed Inspection Report download after finalization', async ({ page }) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  // 1. Upload image
  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()

  // 2. Run analysis
  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

  // 3. Before finalization: inspection report card should not be visible
  await expect(page.locator('[data-testid="inspection-report-card"]')).not.toBeVisible()

  // 4. Batch confirm all findings to satisfy review guardrails
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.locator('[data-testid="summary-inspector-result"]')).toContainText('Review: COMPLETE')

  // 5. Finalize inspection
  const finalizeBtn = page.getByRole('button', { name: 'Finalize inspection' })
  await expect(finalizeBtn).toBeEnabled()
  await finalizeBtn.click()

  await expect(page.getByText('COMPLETED')).toBeVisible()

  // 6. Inspection report card and download button are now visible
  const reportCard = page.locator('[data-testid="inspection-report-card"]')
  await expect(reportCard).toBeVisible()

  const downloadBtn = page.locator('[data-testid="download-report-button"]')
  await expect(downloadBtn).toBeVisible()
  await expect(downloadBtn).toHaveText(/Download inspection report/i)

  // 7. Verify downloading the report PDF
  const downloadPromise = page.waitForEvent('download')
  await downloadBtn.click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toMatch(/^praman_inspection_report_.*\.pdf$/)

  const downloadPath = await download.path()
  expect(downloadPath).toBeTruthy()
})
