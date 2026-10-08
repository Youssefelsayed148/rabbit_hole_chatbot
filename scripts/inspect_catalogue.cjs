// Read only the owner-supplied public collection page; never download application bundles.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const requests = [];
    const pending = [];
    page.on('response', response => {
      const url = new URL(response.url());
      if (url.hostname === 'rabbitholeapi.theosirislabs.com' && /^\/v1\/(products|collections)(\/|$)/.test(url.pathname)) {
        pending.push((async () => {
          const headers = response.request().headers();
          const row = { url: response.url(), status: response.status(), headers: { origin: headers.origin, referer: headers.referer, accept: headers.accept, userAgent: headers['user-agent'] } };
          if (response.ok()) { try { row.data = await response.json(); } catch {} }
          requests.push(row);
        })());
      }
    });
    const response = await page.goto('https://darkturquoise-dunlin-447124.hostingersite.com/collection', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(7000);
    await Promise.allSettled(pending);
    const content = await page.locator('body').innerText();
    const links = await page.locator('a[href]').evaluateAll(nodes => nodes.map(a => ({ text: a.textContent.trim(), url: a.href })).filter(a => /\/(product|collection)/.test(a.url)));
    await page.getByText('AR', { exact: true }).first().click();
    await page.waitForTimeout(5000);
    await Promise.allSettled(pending);
    const report = { pageStatus: response.status(), title: await page.title(), content: content.slice(0, 24000), links, requests };
    const fs = require('node:fs');
    fs.writeFileSync('/results/catalogue-inspection.json', JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ ...report, requests: requests.map(r => ({ ...r, data: r.data ? { ...r.data, pieces: undefined, items: r.data.items, images: undefined, thumbnail_images: undefined, artwork: undefined } : undefined })) }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
