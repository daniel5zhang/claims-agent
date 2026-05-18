const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT = path.join(__dirname, 'test-screenshots');
fs.mkdirSync(OUT, { recursive: true });

const TEST_PAGES = [
  { path: '/login', name: '01-login', guest: true },
  { path: '/', name: '02-dashboard' },
  { path: '/cases', name: '03-case-list' },
  { path: '/cases/new', name: '04-case-create' },
  { path: '/admin/rules', name: '05-rules' },
  { path: '/admin/config', name: '06-config' },
  { path: '/c/', name: '07-c-home', guest: true },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
  });
  const results = [];

  for (const page of TEST_PAGES) {
    const ctx = await browser.newContext();
    const tab = await ctx.newPage();

    try {
      // Login first for protected pages
      if (!page.guest) {
        await tab.goto('http://localhost:5173/login');
        await tab.fill('input[autocomplete="username"]', 'admin');
        await tab.fill('input[autocomplete="current-password"]', 'admin123');
        await tab.click('button[type="submit"]');
        await tab.waitForTimeout(500);
      }

      await tab.goto(`http://localhost:5173${page.path}`);
      await tab.waitForTimeout(300);
      const title = await tab.title();
      const bodyText = await tab.textContent('body');
      const contentLen = bodyText.length;
      const hasContent = contentLen > 50;

      await tab.screenshot({ path: path.join(OUT, `${page.name}.png`), fullPage: true });
      console.log(`${hasContent ? '✅' : '⚠️'} ${page.name}: ${page.path} — ${contentLen} chars — ${title}`);

      results.push({ page: page.name, ok: hasContent, contentLen });
    } catch (e) {
      console.log(`❌ ${page.name}: ${e.message.slice(0, 80)}`);
      results.push({ page: page.name, ok: false, error: e.message });
    } finally {
      await ctx.close();
    }
  }

  await browser.close();

  const ok = results.filter(r => r.ok).length;
  console.log(`\n${'='.repeat(50)}`);
  console.log(`${ok}/${results.length} pages OK`);
  console.log(`Screenshots: ${OUT}/`);
})();
