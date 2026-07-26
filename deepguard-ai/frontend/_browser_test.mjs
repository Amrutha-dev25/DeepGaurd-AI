import playwright from 'playwright';
import fs from 'fs';
import path from 'path';

const FRONTEND_URL = 'http://127.0.0.1:3000';
const IMAGE_PATH = 'D:\\adk-workspace\\deepguard-ai\\backend\\tests\\test_diag.png';
const SCREENSHOTS_DIR = 'D:\\adk-workspace\\deepguard-ai\\backend\\_debug_logs';

async function run() {
  // Use system-installed Chrome via channel
  const browser = await playwright.chromium.launch({
    headless: true,
    channel: 'chrome',
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  const apiResponses = [];
  page.on('response', r => {
    if (r.url().includes('/api/')) apiResponses.push({ url: r.url(), status: r.status() });
  });

  console.log('Navigating...');
  await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 30000 });
  console.log('Loaded:', await page.title());

  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '01_initial_page.png'), fullPage: true });
  console.log('Screenshot 1 saved');

  // Find file input
  for (const sel of ['input[type="file"]', '[data-testid="file-input"]', 'input[accept]', 'form input', 'label input']) {
    const el = await page.$(sel);
    if (el) {
      console.log('Found:', sel);
      await el.setInputFiles(IMAGE_PATH);
      console.log('File uploaded — waiting 45s for pipeline...');
      await page.waitForTimeout(45000);

      await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '02_after_upload.png'), fullPage: true });
      console.log('Screenshot 2 saved');

      const text = await page.evaluate(() => document.body.innerText);
      fs.writeFileSync(path.join(SCREENSHOTS_DIR, 'page_text.txt'), text);
      console.log('Page text saved, len=' + text.length);

      console.log('\nAPI responses:');
      for (const r of apiResponses) console.log(r.status, r.url);

      await browser.close();
      return;
    }
  }

  // Dump page for analysis
  const html = await page.content();
  fs.writeFileSync(path.join(SCREENSHOTS_DIR, 'page.html'), html);
  console.log('No file input — see page.html');
  await browser.close();
}

run().catch(e => { console.error('Error:', e.message); process.exit(1); });
