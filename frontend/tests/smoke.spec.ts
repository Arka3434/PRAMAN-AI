import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const routes = [
  { path: '/', heading: 'Overview' },
  { path: '/inspections', heading: 'Inspections' },
  { path: '/inspections/new', heading: 'New Inspection' },
  { path: '/products', heading: 'Products' },
  { path: '/violations', heading: 'Violations' },
  { path: '/reports', heading: 'Reports' },
  { path: '/analytics', heading: 'Analytics' },
  { path: '/rules', heading: 'Rules' },
  { path: '/users', heading: 'Users' },
  { path: '/settings', heading: 'Settings' },
]

function createPngFixture() {
  const fixturesDir = join(process.cwd(), 'tests', 'fixtures')
  mkdirSync(fixturesDir, { recursive: true })

  const buffer = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAF' +
      'c1TgAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJ0UkG' +
      'AAAAAAgIYy9lAAAAAElFTkSuQmCC',
    'base64',
  )

  const filePath = join(fixturesDir, 'package-sample.png')
  writeFileSync(filePath, buffer)
  return filePath
}

test('frontend app loads and runs route checks', async ({ page }) => {
  for (const route of routes) {
    await page.goto(route.path)
    await expect(page.getByRole('heading', { name: route.heading })).toBeVisible()
  }
})

test('new inspection actions navigate to the new inspection page', async ({ page }) => {
  for (let index = 0; index < 3; index += 1) {
    await page.goto('/')
    await page.locator('a[href="/inspections/new"]').nth(index).click()
    await expect(page).toHaveURL(/\/inspections\/new$/)
    await expect(page.getByRole('heading', { name: 'New Inspection' })).toBeVisible()
  }
})

test('end-to-end inspection workflow creates, uploads, analyzes, reviews, and finalizes', async ({ page }) => {
  const fixturePath = createPngFixture()

  await page.goto('/inspections/new')
  await page.getByRole('button', { name: 'Create inspection' }).click()
  await page.waitForURL(/\/inspections\//)

  await page.locator('input[type="file"]').setInputFiles(fixturePath)
  await page.getByRole('button', { name: 'Upload image' }).click()
  await expect(page.getByRole('button', { name: 'Run Demo Analysis' })).not.toBeDisabled()

  await page.getByRole('button', { name: 'Run Demo Analysis' }).click()
  await expect(page.getByText('Demo confidence:')).toBeVisible()
  await expect(page.getByText('commodity_name')).toBeVisible()
  await expect(page.getByText(/(DEMO: required declaration|PCR-00\d)/).first()).toBeVisible()

  await page.getByRole('button', { name: 'Confirm' }).click()
  await page.getByRole('button', { name: 'Finalize inspection' }).click()
  await expect(page.getByText('COMPLETED')).toBeVisible()
})
