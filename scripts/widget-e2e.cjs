// Reuses an installed Playwright; no Node dependencies are added to the service.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.WIDGET_TEST_URL;
if (!origin) throw Error('WIDGET_TEST_URL is required');
let checks = 0;
function check(condition, message) { assert.ok(condition, message); checks++; }
async function wait(page, selector, count) {
  await page.waitForFunction(({ selector, count }) =>
    document.querySelector('#rabbit-hole-chat').shadowRoot.querySelectorAll(selector).length === count,
    { selector, count });
}
async function open(page, lang = 'en', live = true) {
  await page.goto(origin + '/demo.html' + (live ? '?mode=live' : ''));
  if (lang === 'ar') await page.getByRole('button', { name: 'AR', exact: true }).click();
  await page.getByRole('button', { name: lang === 'en' ? 'Open chat' : 'فتح المحادثة', exact: true }).click();
  check(await page.locator('.panel').getAttribute('dir') === (lang === 'ar' ? 'rtl' : 'ltr'), 'panel direction');
}
async function ask(page, text) {
  await page.waitForFunction(() => !document.querySelector('#rabbit-hole-chat').shadowRoot.querySelector('.typing'));
  await page.locator('textarea').fill(text);
  const response = page.waitForResponse(r => r.url().endsWith('/chat'), { timeout: 90000 });
  await page.locator('textarea').press('Enter');
  const r = await response;
  await page.waitForFunction(() => !document.querySelector('#rabbit-hole-chat').shadowRoot.querySelector('.typing'));
  return r;
}
async function switchSiteLanguage(page, lang) {
  // The mobile sheet covers the page's language toggle while open.
  await page.locator('.panel .icon').last().click();
  await page.getByRole('button', { name: lang === 'ar' ? 'AR' : 'EN', exact: true }).click();
  await page.getByRole('button', { name: lang === 'ar' ? 'فتح المحادثة' : 'Open chat', exact: true }).click();
}
async function rendered(page, body) {
  const normalize = text => text.replace(/\*\*/g, '').replace(/^\s*(?:[-*\u2022]|\d+[.)])\s+/gm, '').replace(/\s+/g, ' ').trim();
  check(normalize(await page.locator('.bot .bubble').last().innerText()) === normalize(body.answer), 'answer meaning preserved in widget formatting');
  const urls = await page.locator('.sources a').evaluateAll(links => links.map(a => a.href));
  assert.deepEqual(urls, body.sources.map(s => s.url)); checks++;
  assert.deepEqual(await page.locator('.sources a').allTextContents(), body.sources.map(s => s.title)); checks++;
}

(async () => {
  const browser = await chromium.launch();
  try {
    if (process.env.WIDGET_SMOKE_CASES) {
      const page = await browser.newPage();
      await open(page);
      const answers = [];
      for (const c of JSON.parse(process.env.WIDGET_SMOKE_CASES)) {
        await page.evaluate(l => { RabbitHoleChat.setLanguage(l); RabbitHoleChat.reset(); }, c.id === 'widget-ar' ? 'ar' : 'en');
        const response = await ask(page, c.question);
        check(response.status() === 200, c.id + ' HTTP success');
        const body = await response.json();
        await rendered(page, body);
        answers.push(body);
      }
      fs.writeFileSync(process.env.WIDGET_TEST_OUT, JSON.stringify({ checks, answers }, null, 2));
      return;
    }

    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      for (const lang of ['en', 'ar']) {
        const page = await browser.newPage({ viewport });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await open(page, lang);
        const ingest = await page.request.post(origin + '/admin/ingest', { headers: { Authorization: 'Bearer ' + (process.env.WIDGET_ADMIN_TOKEN || 'dev-test') } });
        check(ingest.status() === 200, 'explicit ingestion');
        const response = await ask(page, lang === 'en' ? 'When should I report a manufacturing defect?' : 'ما هي مهلة الإبلاغ عن عيب تصنيع؟');
        check(response.status() === 200, 'real chat');
        const body = await response.json();
        check(response.request().headers()['x-site-key'] === 'pk_demo', 'dev key');
        assert.deepEqual(Object.keys(response.request().postDataJSON()).sort(), ['language', 'message']); checks++;
        check(body.language === lang && body.sources[0].document_id === 'refund-' + lang, 'language-filtered citation');
        await rendered(page, body);
        // Wait for the opening transition before measuring the mobile sheet.
        await page.waitForFunction(() => {
          const box = document.querySelector('#rabbit-hole-chat').shadowRoot.querySelector('.panel').getBoundingClientRect();
          return box.x >= 0 && box.right <= innerWidth + 1 && box.y >= 0 && box.bottom <= innerHeight + 1;
        });
        const box = await page.locator('.panel').boundingBox();
        check(box.x >= 0 && box.x + box.width <= viewport.width + 1 && box.y >= 0 && box.y + box.height <= viewport.height + 1,
          'panel fits viewport: ' + JSON.stringify({ lang, viewport, box }));
        const follow = await ask(page, lang === 'en' ? 'What about defects?' : 'وماذا عن العيوب؟');
        check(follow.request().postDataJSON().conversation_id === body.conversation_id, 'conversation round trip');
        const other = lang === 'en' ? 'ar' : 'en';
        await switchSiteLanguage(page, other);
        await wait(page, '.user', 0);
        const handoff = await ask(page, other === 'en' ? 'Where is my order?' : 'أين طلبي؟');
        check(!handoff.request().postDataJSON().conversation_id, 'separate language conversation');
        check((await handoff.json()).needs_human, 'needs_human');
        check(await page.locator('.cta').getAttribute('href') === 'mailto:info@rabbithole.ae', 'support email button');
        await switchSiteLanguage(page, lang);
        await wait(page, '.user', 2);
        check(errors.length === 0, 'no page errors');
        await page.close();
      }
    }

    // Short paragraphs/lists/bold are safe DOM nodes, with one persistent shortcut strip above the composer.
    const layoutPage = await browser.newPage();
    await open(layoutPage);
    const formatted = { answer: 'According to the policy:\n\n- **Deadline:** Report within 7 days.\n- **Condition:** Keep tags and packaging.\n\nContact info@rabbithole.ae.',
      sources: [], products: [], needs_human: false, conversation_id: 'format-session', language: 'en' };
    await layoutPage.route('**/chat', route => route.fulfill({ json: formatted }), { times: 1 });
    await ask(layoutPage, 'Explain policy');
    check(await layoutPage.locator('.bot .bubble li').count() === 2, 'policy renders as list items');
    check(await layoutPage.locator('.bot .bubble strong').count() === 2, 'labels render in bold');
    check(await layoutPage.locator('.panel > .chips .chip').count() === 6, 'question buttons after response');
    check(await layoutPage.locator('.bot .bubble a').getAttribute('href') === 'mailto:info@rabbithole.ae', 'formatted contact link');
    await layoutPage.route('**/chat', route => route.fulfill({ json: { ...formatted, answer: 'Collection story.' } }), { times: 1 });
    const next = layoutPage.waitForResponse('**/chat');
    await layoutPage.locator('.panel > .chips .chip').filter({ hasText: 'Our collection' }).click();
    const nextResponse = await next;
    check(nextResponse.request().postDataJSON().message === 'Tell me about your collection story.', 'shortcut sends collection question');
    await layoutPage.waitForFunction(() => !document.querySelector('#rabbit-hole-chat').shadowRoot.querySelector('.typing'));
    check(await layoutPage.locator('.panel > .chips').count() === 1, 'one shortcut strip remains after every reply');
    check(await layoutPage.locator('.log .chips').count() === 0, 'shortcuts do not repeat in messages');
    const strip = layoutPage.locator('.panel > .chips');
    check(await strip.evaluate(el => el.nextElementSibling.tagName === 'FORM'), 'shortcuts directly above composer');
    check(await strip.evaluate(el => getComputedStyle(el).flexWrap === 'nowrap' && el.scrollWidth > el.clientWidth), 'single horizontal row overflows');
    await strip.evaluate(el => { el.scrollLeft = 200; });
    check(await strip.evaluate(el => el.scrollLeft > 0), 'horizontal shortcut scrolling works');
    for (const language of ['en', 'ar']) {
      await layoutPage.setViewportSize({ width: 390, height: 844 });
      await switchSiteLanguage(layoutPage, language);
      check(await strip.evaluate(el => el.scrollWidth > el.clientWidth), 'mobile shortcut row scrolls in ' + language);
      const bounds = await strip.boundingBox();
      const inputBounds = await layoutPage.locator('textarea').boundingBox();
      check(bounds.y + bounds.height <= inputBounds.y, 'mobile shortcuts above input in ' + language);
      check(await layoutPage.locator('.panel').evaluate(el => el.scrollWidth <= el.clientWidth), 'no horizontal panel overflow in ' + language);
    }
    await switchSiteLanguage(layoutPage, 'en');
    await layoutPage.setViewportSize({ width: 1280, height: 900 });
    const product = { name: '<script>unsafe</script>', image: 'javascript:alert(1)', url: 'https://example.com/collection',
      price: 1365, currency: 'AED', price_includes_vat: true, in_stock: true };
    await layoutPage.route('**/chat', route => route.fulfill({ json: { ...formatted, answer: 'Current catalogue.', products: [product] } }), { times: 1 });
    await ask(layoutPage, 'Show products');
    check(await layoutPage.locator('.product').count() === 1, 'live product card renders');
    check((await layoutPage.locator('.product').textContent()).includes('1,365'), 'product card uses VAT-inclusive live price');
    check((await layoutPage.locator('.product').textContent()).includes('VAT'), 'VAT inclusion visible');
    check(await layoutPage.locator('.product img, .product script').count() === 0, 'product name and image cannot inject HTML');
    check(await layoutPage.locator('.product a').getAttribute('href') === product.url, 'product card links to verified collection');
    await layoutPage.reload();
    await layoutPage.getByRole('button', { name: 'Open chat', exact: true }).click();
    check(await layoutPage.locator('.product').count() === 1, 'product cards survive reload');
    await layoutPage.close();

    // Reload keeps the tab conversation; a new tab/browser session starts fresh.
    const sessionContext = await browser.newContext();
    const sessionPage = await sessionContext.newPage();
    await open(sessionPage);
    const sessionBody = await (await ask(sessionPage, 'hello')).json();
    await sessionPage.reload();
    await sessionPage.getByRole('button', { name: 'Open chat', exact: true }).click();
    check(await sessionPage.locator('.user').count() === 1, 'reload retains current session');
    const followResponse = await ask(sessionPage, 'What about defects?');
    check(followResponse.request().postDataJSON().conversation_id === sessionBody.conversation_id, 'reload retains server conversation');
    check(await sessionPage.evaluate(() => !Object.keys(localStorage).some(k => k.startsWith('rh-chat-v2:'))), 'default history never enters persistent storage');
    const freshPage = await sessionContext.newPage();
    await open(freshPage);
    check(await freshPage.locator('.user').count() === 0, 'new tab starts fresh');
    const freshResponse = await ask(freshPage, 'hello');
    check(!freshResponse.request().postDataJSON().conversation_id, 'new tab sends no old conversation ID');
    await sessionPage.evaluate(() => RabbitHoleChat.reset());
    await sessionPage.reload();
    await sessionPage.getByRole('button', { name: 'Open chat', exact: true }).click();
    check(await sessionPage.locator('.user').count() === 0, 'New chat clears saved history');
    await sessionContext.close();

    const profile = fs.mkdtempSync(require('node:path').join(require('node:os').tmpdir(), 'rh-session-'));
    let persistent = await chromium.launchPersistentContext(profile);
    const beforeRestart = await persistent.newPage();
    await open(beforeRestart);
    await ask(beforeRestart, 'hello');
    await persistent.close();
    persistent = await chromium.launchPersistentContext(profile);
    const afterRestart = await persistent.newPage();
    await open(afterRestart);
    check(await afterRestart.locator('.user').count() === 0, 'browser restart starts fresh');
    const restartedResponse = await ask(afterRestart, 'hello');
    check(!restartedResponse.request().postDataJSON().conversation_id, 'restarted browser sends no old conversation ID');
    await persistent.close();

    const page = await browser.newPage();
    await open(page);
    for (const status of [400, 401, 403, 413, 422, 500, 503]) {
      await page.route('**/chat', route => route.fulfill({ status, json: { detail: 'test fault' } }), { times: 1 });
      const response = await ask(page, 'hello');
      check(response.status() === status, 'injected error ' + status);
      check((await page.locator('.err .bubble').textContent()).includes([400, 413, 422].includes(status) ? 'Shorten' : 'unavailable'), 'error display ' + status);
      const retry = page.waitForResponse('**/chat');
      await page.getByRole('button', { name: 'Retry', exact: true }).click();
      check((await retry).status() === 200, 'retry goes to real service');
      await wait(page, '.err', 0);
    }
    // Response content is untrusted data: titles are text, URL schemes are filtered.
    await page.evaluate(() => RabbitHoleChat.reset());
    const title = '<img src=x onerror="alert(1)">';
    const urls = ['https://example.com/a', 'http://example.com/b', 'javascript:alert(1)', 'data:text/html,test', 'mailto:x@example.com', '//example.com',
      ...Array.from({ length: 6 }, (_, i) => 'https://example.com/source-' + i)];
    const body = { answer: '<script>alert(1)</script>', sources: urls.map((url, i) => ({ title, url, document_id: String(i) })),
      products: [], needs_human: true, conversation_id: 'test-conversation', language: 'en' };
    await page.route('**/chat', route => route.fulfill({ json: body }), { times: 1 });
    await ask(page, 'hostile sources');
    check(await page.locator('.sources a').count() === 8, 'all HTTP citations, including more than five');
    check((await page.locator('.sources a').allTextContents()).every(text => text === title), 'titles are plain text');
    check(await page.locator('.log img, .log script').count() === 0, 'no HTML injection');
    check(await page.locator('.cta').getAttribute('href') === 'mailto:info@rabbithole.ae', 'handoff with hostile sources');
    let errorCount = 0;
    for (const field of Object.keys(body)) {
      const bad = { ...body }; delete bad[field];
      await page.route('**/chat', route => route.fulfill({ json: bad }), { times: 1 });
      await ask(page, 'missing ' + field);
      await wait(page, '.err', ++errorCount); checks++;
    }
    for (const changes of [{ needs_human: 'false' }, { sources: [null] }, { sources: [{ title: title, url: 'https://example.com' }] },
      { conversation_id: 'bad id!' }, { products: [null] }]) {
      await page.route('**/chat', route => route.fulfill({ json: { ...body, ...changes } }), { times: 1 });
      await ask(page, 'bad response');
      await wait(page, '.err', ++errorCount); checks++;
    }
    await page.close();

    const mock = await browser.newPage();
    await open(mock, 'en', false);
    let chatCalls = 0;
    mock.on('request', r => { if (r.url().endsWith('/chat')) chatCalls++; });
    await mock.locator('textarea').fill('defect');
    await mock.locator('textarea').press('Enter');
    await wait(mock, '.sources a', 1);
    check(chatCalls === 0, 'mock default uses no chat network');
    await mock.close();

    // Exhaust the actual limiter only after the successful-path checks.
    const limited = await browser.newPage();
    await open(limited);
    let status = 200;
    for (let i = 0; i < Number(process.env.WIDGET_RATE_LIMIT || 100) + 10 && status !== 429; i++) {
      status = await limited.evaluate(async () => (await fetch('/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Site-Key': 'pk_demo' },
        body: JSON.stringify({ message: 'hello', language: 'en' }) })).status);
    }
    check(status === 429, 'real limiter exhausted');
    check((await ask(limited, 'hello')).status() === 429, 'widget receives real 429');
    check((await limited.locator('.err .bubble').textContent()).includes('Too many messages'), '429 display');
    await switchSiteLanguage(limited, 'ar');
    check((await ask(limited, 'مرحبا')).status() === 429, 'Arabic real 429');
    check((await limited.locator('.err .bubble').textContent()).includes('عدد الرسائل'), 'Arabic 429 display');
    fs.writeFileSync(process.env.WIDGET_TEST_OUT, JSON.stringify({ checks }));
    console.log(checks + ' Playwright checks passed');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
