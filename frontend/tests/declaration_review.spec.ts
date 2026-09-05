import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test.describe('Phase 9: Human-in-the-Loop Declaration Review & Field Correction', () => {
  test('allows inspector to review and correct extracted declarations with audit trail and re-evaluation', async ({ page }) => {
    const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

    // 1. Create inspection and upload package evidence
    await page.goto('/inspections/new')
    await page.getByRole('button', { name: 'Create inspection' }).click()
    await page.waitForURL(/\/inspections\//)

    await page.locator('input[type="file"]').setInputFiles(fixturePath)
    await page.getByRole('button', { name: 'Upload image' }).click()
    await expect(page.locator('[data-testid="image-card"]')).toBeVisible()

    // 2. Run initial analysis
    const runBtn = page.getByRole('button', { name: 'Run DEMO Analysis' })
    await runBtn.click()
    await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

    // 3. Verify extracted declarations appear in Extraction Review UI
    const ocrCard = page.locator('[data-testid="ocr-analysis-card"]')
    await expect(ocrCard).toBeVisible()
    await expect(ocrCard.getByText('OCR Analysis & Extraction Review')).toBeVisible()
    await expect(page.locator('[data-testid="declaration-field-card"]').first()).toBeVisible()

    // 4. Verify raw OCR text toggle is available
    const toggleOcrBtn = page.locator('[data-testid="toggle-raw-ocr-btn"]')
    await expect(toggleOcrBtn).toBeVisible()
    await toggleOcrBtn.click()
    const rawOcrPanel = page.locator('[data-testid="raw-ocr-text-panel"]')
    await expect(rawOcrPanel).toBeVisible()
    await expect(rawOcrPanel).toContainText('Immutable Raw OCR Text Stream')

    // 5. Open Extraction Review edit mode
    const editBtn = page.locator('[data-testid="edit-declarations-btn"]')
    await expect(editBtn).toBeVisible()
    await editBtn.click()

    const editor = page.locator('[data-testid="extraction-review-editor"]')
    await expect(editor).toBeVisible()

    // 6. Correct a declaration (e.g. retail_sale_price)
    const priceInput = page.locator('[data-testid="input-retail_sale_price"]')
    await expect(priceInput).toBeVisible()
    await priceInput.fill('₹ 299.00 (Incl. of all taxes)')

    const notesInput = page.locator('[data-testid="input-correction-notes"]')
    await expect(notesInput).toBeVisible()
    await notesInput.fill('Inspector confirmed valid MRP on bottom fold under magnifying lens')

    // 7. Save & Re-evaluate Compliance
    const saveBtn = page.locator('[data-testid="save-declarations-btn"]')
    await expect(saveBtn).toBeVisible()
    await saveBtn.click()

    // 8. Editor closes, updated declaration displays with "Inspector Verified" badge
    await expect(editor).not.toBeVisible()
    const verifiedBadge = page.locator('[data-testid="inspector-verified-badge"]')
    await expect(verifiedBadge).toBeVisible()
    await expect(verifiedBadge).toContainText('Inspector Verified')

    const updatedPrice = page.locator('[data-testid="declaration-value-retail_sale_price"]')
    await expect(updatedPrice).toContainText('₹ 299.00')

    // Original OCR value remains visible for audit context
    const origOcrAudit = page.locator('[data-testid="original-ocr-retail_sale_price"]')
    await expect(origOcrAudit).toBeVisible()
    await expect(origOcrAudit).toContainText('Original OCR:')

    // 9. Verify compliance summary card and findings are refreshed
    const summaryCard = page.locator('[data-testid="compliance-summary-card"]')
    await expect(summaryCard).toBeVisible()
    await expect(page.locator('[data-testid="summary-engine-result"]')).toBeVisible()

    // 10. Verify inspector review and finalization workflow still functions
    const reviewCards = page.locator('[data-testid="finding-review-card"]')
    const count = await reviewCards.count()
    if (count > 0) {
      // Review the first finding
      const firstCard = reviewCards.first()
      const confirmBtn = firstCard.getByRole('button', { name: /confirm/i })
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click()
        await expect(firstCard.getByText('CONFIRMED')).toBeVisible()
      }
    }
  })
})
