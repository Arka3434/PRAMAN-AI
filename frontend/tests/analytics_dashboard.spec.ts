import { test, expect } from '@playwright/test'

test.describe('Phase 7: Live Operational Dashboard & Enforcement Analytics', () => {
  test('Overview dashboard renders live KPIs, charts, and navigates to review queue', async ({ page }) => {
    // 1. Navigate to Overview (home)
    await page.goto('http://localhost:5174/')

    // 2. Wait for dashboard headline to load
    const headline = page.locator('[data-testid="dashboard-headline"]')
    await expect(headline).toBeVisible()
    await expect(headline).toContainText('Operational review is')

    // 3. Verify KPI cards are visible and populated
    await expect(page.getByText('Inspections this month')).toBeVisible()
    await expect(page.getByText('Manual review queue')).toBeVisible()
    await expect(page.getByText('Statutory violations', { exact: true })).toBeVisible()
    await expect(page.getByText('Average compliance score')).toBeVisible()

    // 4. Verify Trend and Breakdown containers render
    await expect(page.locator('[data-testid="compliance-trend-container"]')).toBeVisible()
    await expect(page.locator('[data-testid="violation-breakdown-container"]')).toBeVisible()

    // 5. Test Review Queue button navigation
    const reviewQueueBtn = page.locator('[data-testid="dashboard-review-queue-btn"]')
    await expect(reviewQueueBtn).toBeVisible()
    await reviewQueueBtn.click()
    await page.waitForURL(/.*status=review_required/)
    expect(page.url()).toContain('status=review_required')
  })

  test('Analytics page renders live operational trends and rule performance table', async ({ page }) => {
    await page.goto('http://localhost:5174/analytics')

    // Verify header
    await expect(page.getByRole('heading', { name: 'Analytics', exact: true })).toBeVisible()

    // Verify 4 KPI cards
    await expect(page.getByText('Total inspections')).toBeVisible()
    await expect(page.getByText('Completed inspections')).toBeVisible()
    await expect(page.getByText('In review queue')).toBeVisible()
    await expect(page.getByText('Adjudication yield rate')).toBeVisible()

    // Verify monthly trend container and review efficiency
    await expect(page.locator('[data-testid="analytics-monthly-trend"]')).toBeVisible()
    await expect(page.getByText('Inspector review efficiency')).toBeVisible()
    await expect(page.getByText('Confirmed Violations:')).toBeVisible()
    await expect(page.getByText('Overruled / Rejected in Field:')).toBeVisible()

    // Verify statutory rule performance section
    await expect(page.getByText('Statutory rule performance')).toBeVisible()
  })

  test('Violations register displays live findings, filters, and escalation summary', async ({ page }) => {
    await page.goto('http://localhost:5174/violations')

    // Verify header
    await expect(page.getByRole('heading', { name: 'Violations', exact: true })).toBeVisible()

    // Verify filters
    const searchInput = page.locator('[data-testid="violations-search-input"]')
    await expect(searchInput).toBeVisible()

    const severityFilter = page.locator('[data-testid="violations-severity-filter"]')
    await expect(severityFilter).toBeVisible()

    const ruleStatusFilter = page.locator('[data-testid="violations-rulestatus-filter"]')
    await expect(ruleStatusFilter).toBeVisible()

    const reviewDecisionFilter = page.locator('[data-testid="violations-reviewdecision-filter"]')
    await expect(reviewDecisionFilter).toBeVisible()

    // Verify Escalation Summary cards
    await expect(page.getByText('Statutory escalation summary')).toBeVisible()
    await expect(page.getByText('Critical Violations')).toBeVisible()
    await expect(page.getByText('Major Violations')).toBeVisible()
    await expect(page.getByText('Field adjudication status')).toBeVisible()

    // Test filter interaction
    await severityFilter.selectOption('critical')
    await page.waitForTimeout(300)
  })
})
