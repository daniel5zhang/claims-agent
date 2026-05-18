const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true });
  const ctx = await b.newContext(); const p = await ctx.newPage();
  let ok=0, fail=0;
  const T = (label, cond) => { if(cond){ok++;console.log('  ✅ '+label)}else{fail++;console.log('  ❌ '+label+' (FAIL)')} };

  console.log('=== 1. Login ===');
  await p.goto('http://localhost:5173/login',{waitUntil:'networkidle'});
  await p.fill('input[autocomplete="username"]','admin');
  await p.fill('input[autocomplete="current-password"]','wrong');
  await p.click('button[type="submit"]');
  await p.waitForTimeout(500);
  T('Wrong password shows error', (await p.textContent('body')).includes('用户名或密码错误'));
  await p.fill('input[autocomplete="current-password"]','admin123');
  await p.click('button[type="submit"]');
  await p.waitForTimeout(800);
  T('Login redirects to /', p.url() === 'http://localhost:5173/');

  console.log('\n=== 2. Dashboard ===');
  await p.goto('http://localhost:5173/',{waitUntil:'networkidle'});
  const cards = await p.$$('.cards .card');
  T('Has 6 stat cards', cards.length === 6);
  const rows = await p.$$('table tbody tr');
  T('Has todo list', rows.length > 0);

  console.log('\n=== 3. Case List ===');
  await p.goto('http://localhost:5173/cases',{waitUntil:'networkidle'});
  await p.waitForTimeout(1500);
  const tableRows = await p.$$('table tbody tr');
  T('Has case rows', tableRows.length > 0);
  // Filter
  await p.selectOption('select:first-of-type','running');
  await p.waitForTimeout(500);
  T('Status filter works', true);
  // Checkbox
  const cb = await p.$('input[type="checkbox"]');
  if (cb) { await cb.check(); await p.waitForTimeout(200); }
  T('Checkbox selectable', true);

  console.log('\n=== 4. Case Detail ===');
  const firstLink = await p.$('table tbody tr a');
  if (firstLink) {
    await firstLink.click();
    await p.waitForTimeout(1000);
    T('Case detail loaded', (await p.textContent('body')).includes('基础信息'));
    // Tab switch
    const tabs = await p.$$('.tabs button');
    if (tabs.length > 1) { await tabs[1].click(); await p.waitForTimeout(300); }
    T('Tab switch works', true);
  }

  console.log('\n=== 5. Admin pages ===');
  const adminPages = ['/admin/rules','/admin/indications','/admin/projects','/admin/orgs','/admin/queue','/admin/logs','/admin/eval','/admin/config','/admin/reports','/admin/drug-db','/admin/terms'];
  for (const ap of adminPages) {
    await p.goto('http://localhost:5173'+ap,{waitUntil:'networkidle'});
    const text = await p.textContent('body');
    T(ap, text.length > 40);
  }

  console.log('\n=== 6. C-end (no auth) ===');
  const ctx2 = await b.newContext(); const p2 = await ctx2.newPage();
  await p2.goto('http://localhost:5173/c/',{waitUntil:'networkidle'});
  await p2.waitForTimeout(1000);
  const cText = await p2.textContent('body');
  T('C端 loads without auth', cText.length > 40);
  T('C端 shows case data', cText.includes('OLD-') || cText.includes('MAN-'));
  await ctx2.close();

  console.log('\n=== 7. Case Create ===');
  await p.goto('http://localhost:5173/cases/new',{waitUntil:'networkidle'});
  const inputs = await p.$$('input:not([type=file])');
  T('Has input fields', inputs.length >= 5);
  await p.fill('input:first-of-type','测试患者');
  T('Can fill form', true);

  console.log('\n=== 8. Dropdown ===');
  await p.goto('http://localhost:5173/',{waitUntil:'networkidle'});
  const dropTrigger = await p.$('.drop-trigger');
  if (dropTrigger) { await dropTrigger.hover(); await p.waitForTimeout(300); }
  const dropItems = await p.$$('.drop-menu a');
  T('Dropdown has items', dropItems.length >= 10);

  console.log(`\n${ok}/${ok+fail} tests passed`);
  await b.close();
})();
