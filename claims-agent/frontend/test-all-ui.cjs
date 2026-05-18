const { chromium } = require('playwright');
const pages = [
  { path:'/login', name:'login', guest:true },
  { path:'/', name:'dashboard' },
  { path:'/cases', name:'cases' },
  { path:'/cases/new', name:'create' },
  { path:'/cases/1/supplement', name:'supplement' },
  { path:'/admin/rules', name:'rules' },
  { path:'/admin/indications', name:'indications' },
  { path:'/admin/projects', name:'projects' },
  { path:'/admin/orgs', name:'orgs' },
  { path:'/admin/queue', name:'queue' },
  { path:'/admin/logs', name:'logs' },
  { path:'/admin/eval', name:'eval' },
  { path:'/admin/config', name:'config' },
  { path:'/admin/reports', name:'reports' },
  { path:'/admin/drug-db', name:'drug-db' },
  { path:'/admin/terms', name:'terms' },
  { path:'/c/', name:'c-home', guest:true },
];
(async () => {
  const b = await chromium.launch({ executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true });
  let ok = 0;
  for (const page of pages) {
    const ctx = await b.newContext(); const p = await ctx.newPage();
    try {
      if (!page.guest) { await p.goto('http://localhost:5173/login',{waitUntil:'networkidle'}); await p.fill('input[autocomplete="username"]','admin'); await p.fill('input[autocomplete="current-password"]','admin123'); await p.click('button[type="submit"]'); await p.waitForTimeout(300); }
      const r = await p.goto('http://localhost:5173'+page.path, {waitUntil:'networkidle',timeout:8000});
      const text = (await p.textContent('body')).length;
      const status = text > 40 ? '✅' : '⚠️';
      if (text > 40) ok++;
      console.log(status+' '+page.name.padEnd(14)+' '+page.path.padEnd(22)+text+' chars');
    } catch(e) {
      console.log('❌ '+page.name+': '+e.message.slice(0,60));
    }
    await ctx.close();
  }
  console.log('\n'+ok+'/'+pages.length+' pages OK');
  await b.close();
})();
