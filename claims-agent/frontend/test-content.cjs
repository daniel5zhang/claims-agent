const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch({ executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true });
  const ctx = await b.newContext(); const p = await ctx.newPage();
  
  // Login
  await p.goto('http://localhost:5173/login',{waitUntil:'networkidle'});
  await p.fill('input[autocomplete="username"]','admin');
  await p.fill('input[autocomplete="current-password"]','admin123');
  await p.click('button[type="submit"]');
  await p.waitForTimeout(500);

  const pages = [
    { path:'/', name:'Dashboard' },
    { path:'/cases', name:'CaseList' },
    { path:'/cases/new', name:'CaseCreate' },
    { path:'/cases/1/supplement', name:'Supplement' },
    { path:'/admin/rules', name:'Rules' },
    { path:'/admin/indications', name:'Indications' },
    { path:'/admin/projects', name:'Projects' },
    { path:'/admin/orgs', name:'Organizations' },
    { path:'/admin/queue', name:'Queue' },
    { path:'/admin/logs', name:'AuditLogs' },
    { path:'/admin/eval', name:'Evaluation' },
    { path:'/admin/config', name:'SystemConfig' },
    { path:'/admin/reports', name:'Reports' },
    { path:'/admin/drug-db', name:'DrugDB' },
    { path:'/admin/terms', name:'TermsDocs' },
  ];

  for (const page of pages) {
    await p.goto('http://localhost:5173'+page.path,{waitUntil:'networkidle'});
    await p.waitForTimeout(300);
    const text = (await p.textContent('body')).replace(/\s+/g,' ').trim();
    console.log(`\n=== ${page.name} (${page.path}) [${text.length} chars] ===`);
    console.log(text.slice(0, 400));
    await p.screenshot({ path: `test-screenshots/${page.name.toLowerCase()}.png` });
  }

  // C端
  const ctx2 = await b.newContext(); const p2 = await ctx2.newPage();
  await p2.goto('http://localhost:5173/c/',{waitUntil:'networkidle'});
  await p2.waitForTimeout(800);
  const cText = (await p2.textContent('body')).replace(/\s+/g,' ').trim();
  console.log(`\n=== C端 /c/ [${cText.length} chars] ===`);
  console.log(cText.slice(0, 400));
  await p2.screenshot({ path: 'test-screenshots/c-home.png' });
  await ctx2.close();

  await b.close();
  console.log('\n\nScreenshots saved to test-screenshots/');
})();
