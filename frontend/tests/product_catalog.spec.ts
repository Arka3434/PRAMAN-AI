import { expect, test } from '@playwright/test'

test('Phase 10: Product Master Catalog & Multi-Inspection Compliance Portfolio', async ({ page }) => {
  const uniqueProductName = `PW Organic Tea ${Date.now().toString().slice(-4)}`
  const uniqueBrand = 'Himalayan Harvest'

  // 1. Navigate to Products Portfolio page
  await page.goto('/products')
  await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible()

  // 2. Open Register Product modal and register a new commodity
  const registerBtn = page.locator('[data-testid="register-product-button"]')
  await expect(registerBtn).toBeVisible()
  await registerBtn.click()

  const registerModal = page.locator('[data-testid="register-modal"]')
  await expect(registerModal).toBeVisible()

  await page.locator('[data-testid="new-product-name-input"]').fill(uniqueProductName)
  await page.locator('[data-testid="new-product-brand-input"]').fill(uniqueBrand)
  await page.locator('[data-testid="new-product-manufacturer-input"]').fill('Himalayan Agro Ltd')

  await page.locator('[data-testid="register-submit-btn"]').click()
  await expect(registerModal).not.toBeVisible()

  // 3. Search for the newly registered product
  const searchInput = page.locator('[data-testid="products-search-input"]')
  await searchInput.fill(uniqueProductName)
  await expect(page.getByText(uniqueProductName)).toBeVisible()

  // 4. Open product detail drawer
  const detailsBtn = page.getByRole('button', { name: 'Details' }).first()
  await detailsBtn.click()

  const drawer = page.locator('[data-testid="product-detail-drawer"]')
  await expect(drawer).toBeVisible()
  await expect(drawer.getByText(uniqueProductName)).toBeVisible()
  await expect(drawer.getByText(uniqueBrand)).toBeVisible()
  await expect(drawer.getByText('Total Inspections')).toBeVisible()

  // 5. Click "Inspect Product" from drawer to initiate inspection linked to this product
  const inspectBtn = page.locator('[data-testid="inspect-product-drawer-btn"]')
  await expect(inspectBtn).toBeVisible()
  await inspectBtn.click()

  // Verify navigation to /inspections/new with pre-selected product
  await expect(page).toHaveURL(/\/inspections\/new\?productId=/)
  await expect(page.locator('[data-testid="product-select"]')).toBeVisible()

  // Create the inspection linked to this existing product
  await page.locator('[data-testid="create-inspection-submit-btn"]').click()
  await page.waitForURL(/\/inspections\/[a-zA-Z0-9-]+/)

  // 6. Return to /products and verify inspection association
  await page.goto('/products')
  await searchInput.fill(uniqueProductName)
  await expect(page.getByText(uniqueProductName)).toBeVisible()

  // Open details drawer again
  await page.getByRole('button', { name: 'Details' }).first().click()
  await expect(drawer).toBeVisible()

  // Verify that the historical inspection is listed in the product's inspection history
  await expect(drawer.getByText('INSP-')).toBeVisible()

  // 7. Inline metadata editing test: update brand
  const editBtn = page.locator('[data-testid="edit-product-btn"]')
  await expect(editBtn).toBeVisible()
  await editBtn.click()

  const brandInput = drawer.locator('input').nth(1)
  await brandInput.fill(`${uniqueBrand} Reserve`)

  const saveBtn = page.locator('[data-testid="save-product-btn"]')
  await saveBtn.click()

  await expect(drawer.getByText(`${uniqueBrand} Reserve`)).toBeVisible()
  // Historical inspection remains intact
  await expect(drawer.getByText('INSP-')).toBeVisible()
})
