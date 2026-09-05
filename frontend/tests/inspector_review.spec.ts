import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('inspector review workflow verifies individual decisions, badge updates, and finalization integrity', async ({ page }) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  // Upload image
  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()

  // Run analysis
  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

  // Verify findings exist and initially display "Pending Inspector Review"
  const pendingBadges = page.locator('[data-testid="inspector-decision-badge"]')
  await expect(pendingBadges.first()).toBeVisible({ timeout: 15_000 })
  await expect(pendingBadges.first()).toHaveText('Pending Inspector Review')

  // Verify Finalize button is disabled when findings are unreviewed
  const finalizeBtn = page.getByRole('button', { name: 'Finalize inspection' })
  await expect(finalizeBtn).toBeDisabled()
  await expect(page.getByText('All statutory findings must be reviewed before finalization.')).toBeVisible()

  // Review first finding individually via Confirm
  const firstFindingActions = page.locator('[data-testid^="finding-actions-"]').first()
  await firstFindingActions.locator('button', { hasText: 'Confirm' }).click()
  await expect(pendingBadges.first()).toHaveText('Inspector: CONFIRMED')

  // Review second finding individually via Reject
  const secondFindingActions = page.locator('[data-testid^="finding-actions-"]').nth(1)
  await secondFindingActions.locator('button', { hasText: 'Reject' }).click()
  await expect(page.locator('[data-testid="inspector-decision-badge"]').nth(1)).toHaveText('Inspector: REJECTED')

  // Use batch Confirm in Inspector Review card to review all remaining findings
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.locator('[data-testid="review-progress"]')).toContainText('Reviewed')

  // Now Finalize button must be enabled
  await expect(finalizeBtn).toBeEnabled()
  await finalizeBtn.click()

  // Inspection transitions to COMPLETED
  await expect(page.getByText('COMPLETED')).toBeVisible()
})
