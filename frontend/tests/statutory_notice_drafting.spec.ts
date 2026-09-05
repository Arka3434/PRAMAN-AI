import { expect, test } from '@playwright/test'
import { join } from 'node:path'

test('Phase 13: Evidence-Backed Statutory Notice & Inspection Memo Drafting with Human Officer Review', async ({
  page,
}) => {
  const fixturePath = join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'package_label_ocr.png')

  // 1. Navigate and create inspection
  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  // 2. Upload image and run analysis
  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()

  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible({ timeout: 25_000 })

  // 3. Confirm all findings and finalize inspection
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.locator('[data-testid="summary-inspector-result"]')).toContainText('Review: COMPLETE')

  const finalizeBtn = page.getByRole('button', { name: 'Finalize inspection' })
  await expect(finalizeBtn).toBeEnabled()
  await finalizeBtn.click()
  await expect(page.getByText('COMPLETED')).toBeVisible()

  // 4. Statutory Notice Card is displayed
  const noticeCard = page.locator('[data-testid="statutory-notice-action-card"]')
  await expect(noticeCard).toBeVisible()
  await expect(noticeCard).toContainText('Statutory Notice & Memo')

  // 5. Select recipient role and addressee name
  await page.locator('[data-testid="recipient-role-select"]').selectOption('MANUFACTURER')
  await page.locator('[data-testid="recipient-name-input"]').fill('Patanjali Foods Limited')

  // 6. Click Draft Statutory Notice
  const draftBtn = page.locator('[data-testid="draft-notice-button"]')
  await expect(draftBtn).toBeVisible()
  await draftBtn.click()

  // 7. Verify Draft Status and Notice Reference
  const statusBadge = page.locator('[data-testid="notice-status-badge"]')
  await expect(statusBadge).toBeVisible()
  await expect(statusBadge).toHaveText('DRAFT')

  const noticeRef = page.locator('[data-testid="notice-reference"]')
  await expect(noticeRef).toBeVisible()
  await expect(noticeRef).toContainText('SCN-')

  // 8. Open Notice Workspace
  const toggleBtn = page.locator('[data-testid="toggle-notice-workspace"]')
  await expect(toggleBtn).toBeVisible()
  // The workspace is opened automatically after drafting, or toggle can open it
  const workspace = page.locator('[data-testid="notice-workspace"]')
  await expect(workspace).toBeVisible()

  // 9. Verify procedural response period disclaimer
  const periodInput = page.locator('[data-testid="response-period-input"]')
  await expect(periodInput).toHaveValue('15')

  const periodNote = page.locator('[data-testid="response-period-note"]')
  await expect(periodNote).toBeVisible()
  await expect(periodNote).toContainText('administrative convenience')
  await expect(periodNote).toContainText('Not a legally mandated universal timeframe')

  // 10. Edit response period and officer notes
  await periodInput.fill('21')
  const notesInput = page.locator('[data-testid="officer-notes-input"]')
  await notesInput.fill('Preliminary inspection memo drafted. Section 36(1) liability noted for manufacturer.')

  // Save Draft
  const saveBtn = page.locator('[data-testid="save-notice-draft-button"]')
  await saveBtn.click()
  await expect(page.getByText('Notice draft updated successfully.')).toBeVisible()

  // 11. Mark as Reviewed
  const reviewBtn = page.locator('[data-testid="mark-notice-reviewed-button"]')
  await reviewBtn.click()

  await expect(statusBadge).toHaveText('REVIEWED')

  // 12. Verify Authenticated Issuing Officer Credentials
  const officerNameDisplay = page.locator('[data-testid="issuing-officer-name-display"]')
  await expect(officerNameDisplay).toBeVisible()
  await expect(officerNameDisplay).toContainText('Admin Officer')

  const confirmCheckbox = page.locator('[data-testid="confirm-issuance-checkbox"]')
  await confirmCheckbox.check()

  // 13. Formally Issue Notice
  const issueBtn = page.locator('[data-testid="issue-notice-button"]')
  await expect(issueBtn).toBeEnabled()
  await issueBtn.click()

  // 14. Verify ISSUED_BY_OFFICER and Immutability
  await expect(statusBadge).toHaveText('ISSUED BY OFFICER')

  const immutableBanner = page.locator('[data-testid="notice-immutable-banner"]')
  await expect(immutableBanner).toBeVisible()
  await expect(immutableBanner).toContainText('permanently immutable')
  await expect(immutableBanner).toContainText('Admin Officer')

  // 15. Verify PDF Download
  const downloadPdfBtn = page.locator('[data-testid="download-notice-pdf-button"]')
  await expect(downloadPdfBtn).toBeVisible()
  await expect(downloadPdfBtn).toContainText('Download Formal Notice')

  const downloadPromise = page.waitForEvent('download')
  await downloadPdfBtn.click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toMatch(/.*scn.*\.pdf$/i)
  const downloadPath = await download.path()
  expect(downloadPath).toBeTruthy()
})
