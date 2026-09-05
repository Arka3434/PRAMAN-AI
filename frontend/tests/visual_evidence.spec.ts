import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('visual evidence renders source image with bounding box overlay and fallback for missing declarations', async ({ page }) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()

  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible()

  // Verify that findings with bounding box render visual evidence with SVG polygon overlay
  const visualEvidenceBlocks = page.locator('[data-testid="finding-visual-evidence"]')
  await expect(visualEvidenceBlocks.first()).toBeVisible({ timeout: 15_000 })

  // Check the expand / fit toggle
  const expandBtn = visualEvidenceBlocks.first().getByRole('button', { name: /Expand full image|Fit preview/i })
  await expect(expandBtn).toBeVisible()
  await expandBtn.click()
  await expect(visualEvidenceBlocks.first().getByRole('button', { name: 'Fit preview' })).toBeVisible()

  // Verify that missing declarations render textual evidence without inventing a bounding box
  const textualEvidenceBlocks = page.locator('[data-testid="finding-textual-evidence"]')
  await expect(textualEvidenceBlocks.first()).toBeVisible()
  await expect(textualEvidenceBlocks.first()).toContainText('Spatial bounding box unavailable (declaration not detected in image text)')

  // Complete review and finalization to ensure workflow remains fully functional
  await page.getByRole('button', { name: 'Confirm' }).click()
  await page.getByRole('button', { name: 'Finalize inspection' }).click()
  await expect(page.getByText('COMPLETED')).toBeVisible()
})
