import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test.describe('Phase 8: Computer Vision Image Quality Assessment', () => {
  test('evaluates and displays quality diagnostics per uploaded image and warns on unreadable images', async ({ page }) => {
    const normalFixture = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')
    const blurryFixture = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'blurry_label.png')

    // 1. Create a new inspection
    await page.goto('/inspections/new')
    await page.getByRole('button', { name: 'Create inspection' }).click()
    await page.waitForURL(/\/inspections\//)

    // 2. Upload the normal packaging image
    await page.locator('input[type="file"]').setInputFiles(normalFixture)
    await page.getByRole('button', { name: 'Upload image' }).click()

    // 3. Verify quality information appears on the uploaded image card
    const imageCard = page.locator('[data-testid="image-card"]').first()
    await expect(imageCard).toBeVisible()

    const qualityBadge = imageCard.locator('[data-testid="image-quality-badge"]')
    await expect(qualityBadge).toBeVisible()
    await expect(qualityBadge).toContainText(/Optimal Quality|Acceptable/i)

    const qualityMetrics = imageCard.locator('[data-testid="quality-metrics"]')
    await expect(qualityMetrics).toBeVisible()
    await expect(qualityMetrics).toContainText('Sharpness:')
    await expect(qualityMetrics).toContainText('Glare:')
    await expect(qualityMetrics).toContainText('Dimensions:')

    // 4. Upload a degraded/unreadable blurry image
    await page.locator('input[type="file"]').setInputFiles(blurryFixture)
    await page.getByRole('button', { name: 'Upload image' }).click()

    // 5. Verify degraded/unreadable warning banner appears prominently
    const warningBanner = page.locator('[data-testid="quality-warning-banner"]')
    await expect(warningBanner).toBeVisible()
    await expect(warningBanner).toContainText('UNREADABLE')
    await expect(warningBanner).toContainText('Recommendation:')

    // Verify the unreadable image card has an unreadable quality badge
    const blurryCard = page.locator('[data-testid="image-card"]').filter({ hasText: 'blurry_label.png' })
    await expect(blurryCard).toBeVisible()
    await expect(blurryCard.locator('[data-testid="image-quality-badge"]')).toContainText(/Unreadable Quality|Degraded Quality/i)

    // 6. Verify existing workflow remains completely functional (OCR is not blocked)
    const runAnalysisBtn = page.getByRole('button', { name: 'Run Demo Analysis' })
    await expect(runAnalysisBtn).not.toBeDisabled()

    await runAnalysisBtn.click()
    await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

    // Verify compliance summary card and findings are generated as normal
    await expect(page.locator('[data-testid="compliance-summary-card"]')).toBeVisible()
    await expect(page.locator('[data-testid="summary-engine-result"]')).toBeVisible()
  })
})
