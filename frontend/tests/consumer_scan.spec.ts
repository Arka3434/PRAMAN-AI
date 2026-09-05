import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('Phase 11: Consumer Transparency Scan & Citizen Verification Portal', async ({ page }) => {
  const normalFixture = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  // 1. Navigate to Consumer Mode via sidebar or direct URL
  await page.goto('/')
  const consumerNavLink = page.getByRole('link', { name: 'Consumer Scan' })
  await expect(consumerNavLink).toBeVisible()
  await consumerNavLink.click()

  await expect(page).toHaveURL('/consumer')
  await expect(page.getByRole('heading', { name: 'Consumer Packaging Transparency' })).toBeVisible()

  // Verify prominent statutory disclaimer banner
  await expect(page.getByText('Consumer Transparency & Packaging Verification')).toBeVisible()

  // 2. Test Scan Package Photo flow
  const fileInput = page.locator('[data-testid="consumer-file-input"]')
  await fileInput.setInputFiles(normalFixture)

  const scanBtn = page.locator('[data-testid="consumer-scan-button"]')
  await expect(scanBtn).toBeVisible()
  await scanBtn.click()

  // Wait for scan results
  const resultsContainer = page.locator('[data-testid="consumer-scan-results"]')
  await expect(resultsContainer).toBeVisible({ timeout: 25_000 })

  // Verify diagnostic quality badge
  await expect(page.getByText('Image Diagnostic Quality')).toBeVisible()

  // Verify mandatory packaging declarations checklist items
  await expect(page.locator('[data-testid="declaration-item-commodity_name"]')).toBeVisible()
  await expect(page.locator('[data-testid="declaration-item-retail_sale_price"]')).toBeVisible()
  await expect(page.locator('[data-testid="declaration-item-net_quantity"]')).toBeVisible()
  await expect(page.locator('[data-testid="declaration-item-consumer_contact"]')).toBeVisible()
  await expect(page.locator('[data-testid="declaration-item-country_of_origin"]')).toBeVisible()

  // Verify semantic neutrality: must NOT contain punitive words
  const pageContent = await resultsContainer.innerText()
  expect(pageContent).not.toMatch(/\bviolation\b/i)
  expect(pageContent).not.toMatch(/\boffense\b/i)
  expect(pageContent).not.toMatch(/\billegal package\b/i)
  expect(pageContent).not.toMatch(/\bnon-compliant product\b/i)

  // 3. Test Search Product Catalog flow
  const catalogTab = page.locator('[data-testid="tab-search-catalog"]')
  await expect(catalogTab).toBeVisible()
  await catalogTab.click()

  const catalogSearch = page.locator('[data-testid="consumer-catalog-search"]')
  await expect(catalogSearch).toBeVisible()

  // Search for any existing products
  await catalogSearch.fill('Rice')
  await page.waitForTimeout(400) // debounce wait

  const productCards = page.locator('[data-testid^="consumer-product-card-"]')
  const count = await productCards.count()
  if (count > 0) {
    // Open product details modal
    const viewBtn = page.locator('[data-testid^="view-declarations-btn-"]').first()
    await viewBtn.click()

    const modal = page.locator('[data-testid="product-detail-modal"]')
    await expect(modal).toBeVisible()
    await expect(modal.getByText('Known Mandatory Packaging Declarations')).toBeVisible()

    // Close modal
    await page.locator('[data-testid="close-detail-modal"]').click()
    await expect(modal).not.toBeVisible()
  }
})
