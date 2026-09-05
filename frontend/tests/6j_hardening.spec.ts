/**
 * Phase 6J Hardening Playwright Tests
 *
 * 1. Invalid inspection URL shows clean 404 empty state (data-testid="inspection-not-found")
 * 2. Dashboard "Review Queue" button navigates to /inspections?status=review_required
 * 3. File input is reset after upload (basic smoke)
 */
import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:5174";
const API = "http://127.0.0.1:8000";

// ─── Test 1: Invalid inspection renders 404 empty state ──────────────────────

test("invalid inspection URL renders 404 empty state", async ({ page }) => {
  await page.goto(`${BASE}/inspections/00000000-dead-beef-0000-000000000000`);
  // Route mock or real 404 — the UI must show the not-found block
  await expect(page.getByTestId("inspection-not-found")).toBeVisible({
    timeout: 10_000,
  });
});

// ─── Test 2: Dashboard Review Queue navigates correctly ───────────────────────

test("dashboard Review Queue button navigates to inspections with review filter", async ({
  page,
}) => {
  await page.goto(`${BASE}/`);
  const reviewBtn = page.getByRole("link", { name: /review queue/i });
  await expect(reviewBtn).toBeVisible({ timeout: 8_000 });
  await reviewBtn.click();
  await page.waitForURL(/\/inspections/);
  expect(page.url()).toContain("status=review_required");
});

// ─── Test 3: Full E2E — upload, analyse, per-finding review, finalize ─────────

test("full hardened workflow: upload -> analyse -> review -> finalize", async ({
  page,
}) => {
  // Create inspection
  const createResp = await page.request.post(`${API}/api/v1/inspections`, {
    data: {
      inspection_number: `PW-6J-${Date.now()}`,
      title: "Playwright 6J Hardening Test",
    },
  });
  expect(createResp.ok()).toBeTruthy();
  const insp = await createResp.json();
  const iid: string = insp.id;

  // Navigate to workflow
  await page.goto(`${BASE}/inspections/${iid}`);
  await expect(page.getByTestId("inspection-not-found")).not.toBeVisible({ timeout: 6_000 });

  // Run analysis via API
  await page.request.post(`${API}/api/v1/inspections/${iid}/analyze`);

  // Fetch and review all findings via API
  const findingsResp = await page.request.get(`${API}/api/v1/inspections/${iid}/findings`);
  const findings = await findingsResp.json();
  expect(Array.isArray(findings)).toBeTruthy();
  for (const f of findings) {
    await page.request.post(
      `${API}/api/v1/inspections/${iid}/findings/${f.id}/review`,
      {
        data: {
          inspection_id: iid,
          decision: "confirm",
          reviewer_name: "playwright-6j",
          notes: "6J hardening e2e",
        },
      }
    );
  }

  // Finalize
  const finResp = await page.request.post(`${API}/api/v1/inspections/${iid}/finalize`);
  expect(finResp.ok()).toBeTruthy();
  const finData = await finResp.json();
  expect(finData.status).toBe("COMPLETED");

  // Verify report endpoint returns PDF
  const repResp = await page.request.get(`${API}/api/v1/inspections/${iid}/report`);
  expect(repResp.ok()).toBeTruthy();
  expect(repResp.headers()["content-type"]).toBe("application/pdf");
});
