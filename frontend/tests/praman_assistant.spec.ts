import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('Phase 14: Evidence-Grounded PRAMAN Inspection Assistant', async ({ page }) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  // 1. Create inspection and run analysis
  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()

  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

  // 2. Verify Assistant Header Button exists and open drawer
  const openAssistantBtn = page.locator('[data-testid="open-assistant-btn"]')
  await expect(openAssistantBtn).toBeVisible()
  await expect(openAssistantBtn).toContainText('PRAMAN Assistant')
  await openAssistantBtn.click()

  // 3. Verify Drawer, Title, and Mandatory Disclaimer
  const drawer = page.locator('[data-testid="praman-assistant-drawer"]')
  await expect(drawer).toBeVisible()
  await expect(drawer).toContainText('PRAMAN Assistant')
  await expect(drawer).toContainText('Evidence-Grounded')
  await expect(drawer).toContainText('Informational Assistance Only:')
  await expect(drawer).toContainText('Does not determine legal liability')

  // 4. Test Tab 1: Inspection Summary
  const summaryTab = page.locator('[data-testid="tab-summary"]')
  await expect(summaryTab).toBeVisible()
  await summaryTab.click()

  await expect(drawer).toContainText('Panels Analyzed')
  await expect(drawer).toContainText('Declarations Extracted')
  await expect(drawer).toContainText('Panel Image Quality Diagnostics (Raw Metrics)')

  // 5. Test Tab 2: Explain Finding
  const explainTab = page.locator('[data-testid="tab-explain"]')
  await expect(explainTab).toBeVisible()
  await explainTab.click()

  const findingSelect = page.locator('[data-testid="assistant-finding-select"]')
  await expect(findingSelect).toBeVisible()

  await expect(drawer).toContainText('Review Status:')
  await expect(drawer).toContainText('Expected Statutory Condition')
  await expect(drawer).toContainText('Detected Value on Packaging')
  await expect(drawer).toContainText('OCR Optical Evidence Snippet')
  await expect(drawer).toContainText('Statutory Mapping Status:')

  // 6. Test Tab 3: Evidence Trace
  const traceTab = page.locator('[data-testid="tab-trace"]')
  await expect(traceTab).toBeVisible()
  await traceTab.click()

  await expect(drawer).toContainText('Optical Provenance & Traceability')
  await expect(drawer).toContainText('Rule Check ID')
  await expect(drawer).toContainText('OCR Raw Text Snippet')

  // 7. Test Tab 4: Manual Review Guide
  const manualTab = page.locator('[data-testid="tab-manual"]')
  await expect(manualTab).toBeVisible()
  await manualTab.click()

  await expect(drawer).toContainText('Procedural Verification Protocol')

  // 8. Close Assistant Drawer
  const closeBtn = page.locator('[data-testid="close-assistant-drawer-btn"]')
  await expect(closeBtn).toBeVisible()
  await closeBtn.click()
  await expect(drawer).not.toBeVisible()

  // 9. Test direct Explain button on finding card
  const explainFindingBtn = page.locator('[data-testid^="explain-finding-"]').first()
  if (await explainFindingBtn.isVisible()) {
    await explainFindingBtn.click()
    await expect(drawer).toBeVisible()
    await expect(drawer).toContainText('Expected Statutory Condition')
    await closeBtn.click()
    await expect(drawer).not.toBeVisible()
  }
})
