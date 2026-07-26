/**
 * Playwright E2E test: upload a real file and verify InteractiveViewer renders
 * backend diagnostic data.
 *
 * Prerequisites:
 *   1. Start the backend: cd backend && uv run uvicorn app.api:app --port 8000
 *   2. Start the frontend: cd frontend && npm run dev
 *   3. npm install -D @playwright/test
 *   4. npx playwright install chromium
 *
 * Run: npx playwright test --config=playwright.config.ts
 */

import { test, expect } from '@playwright/test';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const TEST_IMAGE = process.env.TEST_IMAGE || 'test_fixtures/sample.jpg';

test.describe('Real upload E2E', () => {
  test('upload a JPEG and verify InteractiveViewer shows diagnostic data', async ({ page }) => {
    await page.goto(FRONTEND_URL);

    // Navigate to the upload/test tab
    await page.click('text=Test Your Media');

    // Upload a real image file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(TEST_IMAGE);
    await page.click('text=Analyze');

    // Wait for the scan to complete
    await page.waitForSelector('text=Forensic Scanner Engaged', { timeout: 5000 });
    await page.waitForSelector('text=Digital Exhibit', { timeout: 120000 });

    // Verify the InteractiveViewer renders the uploaded media
    const viewer = page.locator('.rounded-xl.bg-black');
    await expect(viewer).toBeVisible();

    // Verify diagnostic controls are present
    await expect(page.locator('text=Interactive Diagnostics')).toBeVisible();
    await expect(page.locator('text=Error Level (ELA)')).toBeVisible();
    await expect(page.locator('text=FFT Spectrum')).toBeVisible();

    // Click ELA toggle and verify the diagnostic overlay label appears
    await page.click('text=Error Level (ELA)');
    await expect(page.locator('text=Viewing:')).toBeVisible();
    await expect(page.locator('text=Error Level Analysis')).toBeVisible();

    // Verify report pane shows real results (not sample data defaults)
    await expect(page.locator('text=Forensic Investigation Report')).toBeVisible();
    const verdictText = await page.locator('[class*="verdict"]').first().textContent();
    expect(['REAL', 'FAKE', 'INCONCLUSIVE']).toContain(verdictText?.trim());
  });

  test('upload a video and verify <video> element renders instead of <img>', async ({ page }) => {
    const testVideo = process.env.TEST_VIDEO || 'test_fixtures/sample.mp4';
    await page.goto(FRONTEND_URL);
    await page.click('text=Test Your Media');

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testVideo);
    await page.click('text=Analyze');

    await page.waitForSelector('text=Digital Exhibit', { timeout: 120000 });

    // The main media render should be a <video> element, not <img>
    const video = page.locator('.rounded-xl.bg-black video');
    await expect(video).toBeVisible({ timeout: 10000 });
    await expect(video).toHaveAttribute('controls');

    // Verify video is playing or can play
    await expect(video).toHaveJSProperty('paused', false, { timeout: 5000 });
  });
});
