import { expect, test } from '@playwright/test'

test('Phase 6I: Legal Rule Catalog Management & Traceability', async ({ page }) => {
  // 1. Navigate to the Rules Catalog page
  await page.goto('/rules')
  await expect(page.getByRole('heading', { name: 'Legal Rule Catalog' })).toBeVisible()

  // 2. Verify Cryptographic Integrity Hash & Version Badge
  const hashBadge = page.locator('[data-testid="catalog-hash-badge"]')
  await expect(hashBadge).toBeVisible()
  await expect(hashBadge).toContainText('b847e70c09bf2666cee117f0b800b8f26de5d5d86059d70966d794a5e6e13adc')

  // Verify Metrics Summary Cards
  await expect(page.locator('[data-testid="total-rules-count"]')).toHaveText('8')
  await expect(page.locator('[data-testid="safe-rules-count"]')).toHaveText('6')
  await expect(page.locator('[data-testid="needs-verification-count"]')).toHaveText('2')

  // 3. Verify All 8 Rules are Present in the List
  const rulesList = page.locator('[data-testid="rules-list"]')
  await expect(rulesList).toBeVisible()

  for (let i = 1; i <= 8; i++) {
    const ruleId = `PCR-00${i}`
    await expect(page.locator(`[data-testid="rule-card-${ruleId}"]`)).toBeVisible()
  }

  // 4. Test Filtering by SAFE (Automated)
  const safeTab = page.locator('[data-testid="filter-tab-safe"]')
  await safeTab.click()
  await expect(page.locator('[data-testid="rule-card-PCR-001"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-card-PCR-007"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-card-PCR-006"]')).not.toBeVisible()
  await expect(page.locator('[data-testid="rule-card-PCR-008"]')).not.toBeVisible()

  // 5. Test Filtering by Assisted Review (NEEDS_VERIFICATION)
  const nvTab = page.locator('[data-testid="filter-tab-needs-verification"]')
  await nvTab.click()
  await expect(page.locator('[data-testid="rule-card-PCR-006"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-card-PCR-008"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-card-PCR-001"]')).not.toBeVisible()
  await expect(page.locator('[data-testid="rule-card-PCR-007"]')).not.toBeVisible()

  // 6. Reset to All and Expand PCR-007 for Detailed Legal Traceability
  const allTab = page.locator('[data-testid="filter-tab-all"]')
  await allTab.click()

  const pcr007Header = page.locator('[data-testid="rule-header-PCR-007"]')
  await pcr007Header.click()

  // Verify statutory details are revealed
  const pcr007Card = page.locator('[data-testid="rule-card-PCR-007"]')
  await expect(pcr007Card).toContainText('Maximum Retail Price')
  await expect(pcr007Card).toContainText('Rule 6(1)(e)')
  await expect(pcr007Card).toContainText('Statutory Expected Condition')
  await expect(pcr007Card).toContainText('Statutory Exemptions')
  await expect(pcr007Card).toContainText('Evidence & Technical Verification Criteria')

  // 7. Verify Read-Only Integrity: No "New rule" or editing controls exist
  await expect(page.getByRole('button', { name: 'New rule' })).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Add rule' })).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Edit' })).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Delete' })).not.toBeVisible()
})
