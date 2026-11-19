// Regression test: every shop tab must list items (the Potions tab once rendered empty
// because mystery() assumed every tab was a cosmetic). Run: node tools/tests/shop-tabs.test.js
const { chromium } = require('playwright');
const path = require('path');
const FILE = 'file://' + path.resolve(__dirname, '../../index.html');
const SAVES = {
  fresh: null,
  old: { gems: 40, inv: { health: 2, shield: 1, glow: 0 }, skins: ['hero'], skin: 'hero' },
};
(async () => {
  const b = await chromium.launch(); let fail = 0;
  for (const [name, save] of Object.entries(SAVES)){
    const p = await b.newPage(); const errs = [];
    p.on('pageerror', e => { if (!/ServiceWorker|file:/.test(e.message)) errs.push(e.message); });
    p.on('console', m => { if (m.type() === 'error' && !/ServiceWorker|file:/.test(m.text())) errs.push(m.text()); });
    if (save) await p.addInitScript(s => localStorage.setItem('lavaleap.save.v1', s), JSON.stringify(save));
    await p.goto(FILE); await p.waitForTimeout(800);
    await p.evaluate(() => openShop('startCard'));
    const n = await p.evaluate(() => document.querySelectorAll('#shopTabs .tab').length);
    for (let i = 0; i < n; i++){
      const r = await p.evaluate(i => { document.querySelectorAll('#shopTabs .tab')[i].click();
        return { tab: shopTab, items: document.querySelectorAll('#shopGrid .it').length, btn: document.getElementById('pvBtn').textContent }; }, i);
      const ok = r.items > 0 && r.btn;
      if (!ok) fail++;
      console.log(`${ok ? 'ok  ' : 'FAIL'} [${name}] ${r.tab}: ${r.items} items, button "${r.btn}"`);
    }
    const pot = await p.evaluate(() => { document.querySelectorAll('#shopTabs .tab')[0].click();
      return [...document.querySelectorAll('#shopGrid .it')].map(e => e.getAttribute('aria-label')); });
    if (pot.length !== 3){ fail++; console.log('FAIL potions:', pot); }
    if (errs.length){ fail++; console.log(`FAIL [${name}] errors:`, errs); }
    await p.close();
  }
  await b.close();
  console.log(fail ? `${fail} failure(s)` : 'all shop tabs OK');
  process.exit(fail ? 1 : 0);
})();
