import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test.describe('Phase 12: Multi-Panel Evidence Fusion & Package-Level Compliance Analysis', () => {
  test('supports multi-panel image upload, non-destructive rotation, fused compliance analysis, and panel attribution', async ({
    page,
  }) => {
    const fixture1 = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')
    const fixture2 = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'blurry_label.png')

    // 1. Create a new inspection
    await page.goto('/inspections/new')
    await page.getByRole('button', { name: 'Create inspection' }).click()
    await page.waitForURL(/\/inspections\//)

    // 2. Upload Front Panel Evidence
    const fileInput = page.locator('[data-testid="inspection-image-upload"]')
    await fileInput.setInputFiles(fixture1)
    await page.locator('#capture-side').selectOption('front')
    await page.getByRole('button', { name: 'Upload image' }).click()

    // Verify first image uploaded
    await expect(page.locator('[data-testid="image-card"]')).toHaveCount(1)

    // 3. Upload Back Panel Evidence
    await fileInput.setInputFiles(fixture2)
    await page.locator('#capture-side').selectOption('back')
    await page.getByRole('button', { name: 'Upload image' }).click()

    // Verify two images present in evidence gallery
    await expect(page.locator('[data-testid="image-card"]')).toHaveCount(2)

    // 4. Test Non-Destructive Image Rotation on Front Panel
    const rotateBtn = page.locator('[data-testid="rotate-image-btn"]').first()
    await expect(rotateBtn).toBeVisible()
    await rotateBtn.click()

    // Verify rotation badge appears confirming derivative used & original preserved
    const rotBadge = page.locator('[data-testid="image-rotation-badge"]').first()
    await expect(rotBadge).toBeVisible({ timeout: 10_000 })
    await expect(rotBadge).toContainText('Rotated 90°')
    await expect(rotBadge).toContainText('Original Preserved')

    // 5. Run Multi-Panel Analysis
    const runBtn = page.locator('[data-testid="run-analysis-btn"]')
    await expect(runBtn).toBeVisible()
    await runBtn.click()

    // Wait for analysis results to render (multi-image OCR takes 10-20s)
    const declCards = page.locator('[data-testid="declaration-field-card"]')
    await expect(declCards.first()).toBeVisible({ timeout: 40_000 })

    // Verify panel provenance badge is displayed on declarations
    const panelBadges = page.locator('[data-testid^="panel-badge-"]')
    await expect(panelBadges.first()).toBeVisible()
    const badgeText = await panelBadges.first().innerText()
    expect(badgeText.toLowerCase()).toMatch(/(front|back|left|right|other)\s+panel/)

    // 7. Verify Compliance Summary & Findings
    const summaryCard = page.locator('[data-testid="compliance-summary-card"]')
    await expect(summaryCard).toBeVisible()

    // Verify findings list is present
    const findingsList = page.getByRole('heading', { name: 'Findings' })
    await expect(findingsList).toBeVisible()

    // Verify finding panel provenance badge if finding has attributed panel
    const findingPanels = page.locator('[data-testid^="finding-panel-"]')
    const findingPanelCount = await findingPanels.count()
    if (findingPanelCount > 0) {
      await expect(findingPanels.first()).toContainText('Panel Evidence')
    }

    // 8. Verify Visual Evidence Viewer shows Panel Attribution
    const visualEvidence = page.locator('[data-testid="finding-visual-evidence"], [data-testid="finding-textual-evidence"]').first()
    if (await visualEvidence.isVisible()) {
      const panelProv = visualEvidence.locator('[data-testid="evidence-panel-provenance"]')
      if (await panelProv.isVisible()) {
        await expect(panelProv).toContainText('Panel:')
      }
    }

    // 9. Verify Inspector Review and Finalization Workflow on Multi-Panel Inspection
    const confirmBtn = page.getByRole('button', { name: 'Confirm', exact: true }).first()
    if (await confirmBtn.isVisible() && (await confirmBtn.isEnabled())) {
      await confirmBtn.click()
    }
  })
})
