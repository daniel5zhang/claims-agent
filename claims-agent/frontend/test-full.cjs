const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  const ctx = await b.newContext();
  const p = await ctx.newPage();
  
  console.log('1. Login page...');
  await p.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
  await p.fill('input[autocomplete="username"]', 'admin');
  await p.fill('input[autocomplete="current-password"]', 'admin123');
  await p.click('button[type="submit"]');
  await p.waitForTimeout(500);
  const url = p.url();
  console.log('   URL after login:', url);
  
  console.log('\n2. Dashboard...');
  await p.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
  const cards = await p.$$('.cards .card');
  console.log('   Stats cards:', cards.length);
  const dashText = await p.textContent('body');
  console.log('   Content:', dashText.slice(0, 150));
  
  console.log('\n3. Case List...');
  await p.goto('http://localhost:5173/cases', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1000);
  const rows = await p.$$('table tbody tr');
  console.log('   Table rows:', rows.length);
  const listText = await p.textContent('body');
  console.log('   Content:', listText.slice(0, 200));
  const links = await p.$$('a');
  console.log('   Links:', links.length);
  
  console.log('\n4. Case Create...');
  await p.goto('http://localhost:5173/cases/new', { waitUntil: 'networkidle' });
  const formInputs = await p.$$('input');
  console.log('   Form inputs:', formInputs.length);
  
  console.log('\n5. C-end (no auth)...');
  const ctx2 = await b.newContext();
  const p2 = await ctx2.newPage();
  await p2.goto('http://localhost:5173/c/', { waitUntil: 'networkidle' });
  const cText = await p2.textContent('body');
  console.log('   Content:', cText.slice(0, 150));
  
  await p.screenshot({ path: 'test-screenshots/dashboard.png' });
  console.log('\n✅ Full test complete');
  await b.close();
})();
