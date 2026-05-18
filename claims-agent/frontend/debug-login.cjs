const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  const p = await b.newPage();
  await p.goto('http://localhost:5173/login', { waitUntil: 'networkidle', timeout: 10000 });
  await p.waitForTimeout(500);
  const text = await p.textContent('body');
  console.log('Body text:', text.slice(0, 300));
  console.log('Content length:', text.length);
  const inputs = await p.$$('input');
  console.log('Inputs:', inputs.length);
  const buttons = await p.$$('button');
  console.log('Buttons:', buttons.length);
  const h1 = await p.$('h1');
  console.log('h1 text:', h1 ? await h1.textContent() : 'missing');
  await p.screenshot({ path: 'test-screenshots/01-login-v2.png' });
  await b.close();
})();
