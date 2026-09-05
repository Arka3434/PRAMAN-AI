import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('Phase 6F: Compliance summary displays engine evaluation, inspector progress, filtering, and finalization', async ({ page }) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  // 1. Upload image
  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  const uploadResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/upload-images') && resp.status() === 201
  )
  await page.getByRole('button', { name: 'Upload image' }).click()
  await uploadResponsePromise
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).toBeEnabled()

  // 2. Run analysis
  const analyzeResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/analyze') && resp.status() === 201
  )
  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await analyzeResponsePromise
  await expect(page.getByText('Demo confidence:')).toBeVisible()

  // 3. Compliance Summary Card renders
  const summaryCard = page.locator('[data-testid="compliance-summary-card"]')
  await expect(summaryCard).toBeVisible()

  // Verify Engine Evaluation & Review status badges
  const engineResultBadge = page.locator('[data-testid="summary-engine-result"]')
  await expect(engineResultBadge).toBeVisible()
  await expect(engineResultBadge).toContainText('Engine:')

  const inspectorResultBadge = page.locator('[data-testid="summary-inspector-result"]')
  await expect(inspectorResultBadge).toBeVisible()
  await expect(inspectorResultBadge).toContainText('Review: PENDING')

  // Verify summary count pills
  await expect(page.locator('[data-testid="summary-passed-count"]')).toBeVisible()
  await expect(page.locator('[data-testid="summary-violations-count"]')).toBeVisible()
  await expect(page.locator('[data-testid="summary-manual-review-count"]')).toBeVisible()
  await expect(page.locator('[data-testid="summary-review-progress"]')).toBeVisible()

  // 4. Test interactive filter (click Passed Checks)
  await page.getByRole('button', { name: /Passed Checks/i }).click()
  await expect(page.getByText(/Filtered: passed/i)).toBeVisible()

  // Reset filter
  await page.getByRole('button', { name: /Reset Filter|Clear filter/i }).first().click()
  await expect(page.getByText(/Filtered: passed/i)).not.toBeVisible()

  // 5. Individual inspector review: confirm finding 1
  const firstFindingActions = page.locator('[data-testid^="finding-actions-"]').first()
  await firstFindingActions.locator('button', { hasText: 'Confirm' }).click()
  await expect(page.locator('[data-testid="inspector-decision-badge"]').first()).toHaveText('Inspector: CONFIRMED')

  // 6. Complete review with batch confirm
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.locator('[data-testid="summary-inspector-result"]')).toContainText('Review: COMPLETE')

  // 7. Finalize inspection
  const finalizeBtn = page.getByRole('button', { name: 'Finalize inspection' })
  await expect(finalizeBtn).toBeEnabled()
  await finalizeBtn.click()

  await expect(page.getByText('COMPLETED')).toBeVisible()
})
