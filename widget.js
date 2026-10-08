/*!
 * Rabbit Hole chat widget: framework-free, Shadow DOM, talks to the standalone RAG service.
 *
 * <script src="https://YOUR-SERVICE/widget.js" data-api="https://YOUR-SERVICE"
 *         data-site-key="pk_..." defer></script>
 *
 * Attributes: data-api (default: this script's origin) · data-site-key · data-name (default "Mr Wizard")
 * data-lang (auto|en|ar, default auto: follows <html lang>) · data-contact (support email)
 * data-storage (session|local|none, default session) · data-history-days (30)
 * data-position (right|left) · data-z-index (3000) · data-max-length (1000)
 *
 * JS API: RabbitHoleChat.open() / close() / toggle() / setLanguage('en'|'ar') / reset() / destroy()
 */
(() => {
  'use strict';
  if (window.RabbitHoleChat) return;

  const script = document.currentScript || document.querySelector('script[src*="widget.js"]');
  const attr = (k, d) => (script && script.dataset[k]) || d;
  const origin = (() => { try { return new URL(script.src).origin; } catch { return ''; } })();
  const cfg = {
    api: attr('api', origin).replace(/\/+$/, ''),
    siteKey: attr('siteKey', ''),
    name: attr('name', 'Mr Wizard'),
    lang: attr('lang', 'auto'),
    contact: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(attr('contact', '')) ? attr('contact', '') : 'info@rabbithole.ae',
    position: attr('position', 'right') === 'left' ? 'left' : 'right',
    z: parseInt(attr('zIndex', '3000'), 10) || 3000,
    maxLen: parseInt(attr('maxLength', '1000'), 10) || 1000,
    timeoutMs: 45000,
    storage: ['local', 'none'].includes(attr('storage', 'session')) ? attr('storage', 'session') : 'session',
    historyDays: Math.max(1, Math.min(30, parseInt(attr('historyDays', '30'), 10) || 30)),
  };

  const T = {
    en: {
      sub: 'Ask about Rabbit Hole', welcome: 'Welcome to Rabbit Hole. I can help with the brand, the collection, exchanges and refunds, or how to reach us.',
      placeholder: 'Type your message...', send: 'Send', close: 'Close chat', open: 'Open chat', fresh: 'New chat', typing: 'is typing',
      sources: 'Sources', viewProduct: 'View collection', vat: 'Includes VAT', available: 'In stock', unavailable: 'Currently unavailable', email: 'Email support', retry: 'Retry', msgLabel: 'Your message',
      errNet: 'No connection to the assistant. Check your network, then retry.',
      errRate: 'Too many messages in a short time. Wait a moment, then retry.',
      errBad: 'That message could not be sent. Shorten it and try again.',
      errGen: 'The assistant is unavailable right now. Try again, or email us.',
      chips: [
        ['Browse products', 'Show me your products.'],
        ['Our collection', 'Tell me about your collection story.'],
        ['Exchange and refund policy', 'What is your exchange and refund policy?'],
        ['Report a defect', 'I received a manufacturing defect. What should I do?'],
        ['About the brand', 'Tell me about Rabbit Hole.'],
        ['Contact us', 'How can I contact you?'],
      ],
    },
    ar: {
      sub: 'اسأل عن رابت هول', welcome: 'أهلاً بك في رابت هول. يسعدني مساعدتك في التعريف بالعلامة والتشكيلة، وسياسة الاستبدال والاسترجاع، وطريقة التواصل معنا.',
      placeholder: 'اكتب رسالتك ...', send: 'إرسال', close: 'إغلاق المحادثة', open: 'فتح المحادثة', fresh: 'محادثة جديدة', typing: 'يكتب الآن',
      sources: 'المصادر', viewProduct: 'عرض التشكيلة', vat: 'شامل الضريبة', available: 'متوفر', unavailable: 'غير متوفر حاليًا', email: 'راسل الدعم', retry: 'إعادة المحاولة', msgLabel: 'رسالتك',
      errNet: 'تعذّر الاتصال بالمساعد. تحقق من الشبكة ثم أعد المحاولة.',
      errRate: 'عدد الرسائل كبير في وقت قصير. انتظر قليلاً ثم أعد المحاولة.',
      errBad: 'تعذّر إرسال هذه الرسالة. اختصرها وحاول مرة أخرى.',
      errGen: 'المساعد غير متاح الآن. حاول مرة أخرى أو راسلنا بالبريد.',
      chips: [
        ['تصفح المنتجات', 'اعرض لي المنتجات.'],
        ['التشكيلة', 'حدثني عن قصة التشكيلة.'],
        ['سياسة الاستبدال والاسترجاع', 'ما هي سياسة الاستبدال والاسترجاع؟'],
        ['الإبلاغ عن عيب', 'استلمت قطعة بها عيب مصنعي. ماذا أفعل؟'],
        ['عن العلامة', 'حدثني عن رابت هول.'],
        ['تواصل معنا', 'كيف يمكنني التواصل معكم؟'],
      ],
    },
  };

  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const mobileMQ = matchMedia('(max-width: 520px)');
  const storeKey = () => 'rh-chat-v2:' + cfg.api + ':' + cfg.siteKey + ':' + state.lang;
  const state = { lang: 'en', langLocked: cfg.lang === 'en' || cfg.lang === 'ar', open: false, pending: false, convId: '', msgs: [] };

  // Browser-local history; unavailable/blocked storage must never break chat.
  const storage = () => cfg.storage === 'none' ? null : cfg.storage === 'session' ? sessionStorage : localStorage;
  const clearSaved = () => { try { storage()?.removeItem(storeKey()); sessionStorage.removeItem(storeKey()); } catch {} };
  const load = () => {
    state.convId = ''; state.msgs = [];
    try {
      const target = storage();
      if (!target) return;
      let raw = target.getItem(storeKey());
      // Carry an existing tab conversation into persistent history once.
      if (!raw && cfg.storage === 'local') {
        raw = sessionStorage.getItem(storeKey());
        if (raw) { target.setItem(storeKey(), raw); sessionStorage.removeItem(storeKey()); }
      }
      const saved = JSON.parse(raw || 'null');
      if (!saved) return;
      if (saved.updatedAt && Date.now() - saved.updatedAt > cfg.historyDays * 86400000) { clearSaved(); return; }
      if (typeof saved.convId !== 'string' || !/^[A-Za-z0-9_-]{0,64}$/.test(saved.convId) || !Array.isArray(saved.msgs)) { clearSaved(); return; }
      state.convId = saved.convId;
      state.msgs = saved.msgs.slice(-40).filter(m => m && ['user', 'bot'].includes(m.role) && typeof m.text === 'string' && !m.error)
        .map(m => ({ role: m.role, text: m.text, needsHuman: m.needsHuman === true,
          products: Array.isArray(m.products) ? m.products.filter(p => p && typeof p === 'object') : [],
          sources: Array.isArray(m.sources) ? m.sources.filter(s => s && typeof s.title === 'string' && typeof s.url === 'string') : [] }));
    } catch { clearSaved(); }
  };
  const save = () => { try { storage()?.setItem(storeKey(), JSON.stringify({ convId: state.convId, msgs: state.msgs.slice(-40), updatedAt: Date.now() })); } catch {} };

  const resolveLang = () => {
    if (cfg.lang === 'en' || cfg.lang === 'ar') return cfg.lang;
    return /^ar/i.test(document.documentElement.lang || '') || document.documentElement.dir === 'rtl' ? 'ar' : 'en';
  };
  const t = () => T[state.lang];

  // ---- tiny DOM helper ----
  const h = (tag, props = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null) el.append(kid);
    return el;
  };
  const svg = (d, vb = '0 0 24 24') => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', vb); s.setAttribute('width', '18'); s.setAttribute('height', '18');
    s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '1.8');
    s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', d); s.append(p);
    return s;
  };

  // Safe linkify: builds nodes, never injects HTML.
  const URL_OR_MAIL = /(https?:\/\/[^\s<>"']+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)/g;
  const linkify = (text) => {
    const out = []; let last = 0;
    for (const m of text.matchAll(URL_OR_MAIL)) {
      let hit = m[0]; const trail = (hit.match(/[.,;:!?)،؛؟]+$/) || [''])[0];
      if (trail) hit = hit.slice(0, -trail.length);
      out.push(text.slice(last, m.index));
      const isMail = !/^https?:/i.test(hit);
      out.push(h('a', { href: isMail ? 'mailto:' + hit : hit, target: isMail ? null : '_blank', rel: 'noopener noreferrer' }, hit));
      last = m.index + hit.length;
    }
    out.push(text.slice(last));
    return out;
  };
  const safeUrl = (u) => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : null; } catch { return null; } };

  // ---- styles ----
  const CSS = `
  :host { all: initial; position: fixed; inset-block-end: 16px; ${cfg.position}: 16px; z-index: ${cfg.z};
    font-family: "Black Mango", Cairo, system-ui, -apple-system, "Segoe UI", Tahoma, sans-serif; color: #fff; }
  @media print { :host { display: none } }
  *, *::before, *::after { box-sizing: border-box; }
  /* Pin every inherited property here: the host sits in the page's cascade (and \`all: initial\` skips direction),
     so page CSS or <html dir="rtl"> must not leak in. Panel direction is set separately via its dir attribute. */
  .root { display: flex; flex-direction: column; align-items: ${cfg.position === 'left' ? 'flex-start' : 'flex-end'}; gap: 14px;
    direction: ltr; unicode-bidi: normal; font: 400 16px/normal "Black Mango", Cairo, system-ui, -apple-system, "Segoe UI", Tahoma, sans-serif;
    color: #fff; letter-spacing: normal; word-spacing: normal; text-transform: none; text-align: start; text-indent: 0; text-shadow: none; white-space: normal; font-style: normal; visibility: visible; }
  button { font: inherit; color: inherit; cursor: pointer; }
  :focus-visible { outline: 2px solid #fff; outline-offset: 2px; }

  .panel { width: 380px; height: min(580px, calc(100dvh - 112px)); display: flex; flex-direction: column; overflow: hidden;
    background: rgba(10,10,10,.84); -webkit-backdrop-filter: blur(20px) saturate(1.15); backdrop-filter: blur(20px) saturate(1.15);
    border: 1px solid rgba(255,255,255,.14); border-radius: 20px; box-shadow: 0 24px 64px rgba(0,0,0,.5);
    transform-origin: bottom ${cfg.position}; transition: opacity .28s ease, transform .28s cubic-bezier(.2,.8,.2,1), visibility 0s linear 0s; }
  @supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) { .panel { background: #0b0b0b; } }
  .root:not([data-open]) .panel { opacity: 0; visibility: hidden; transform: translateY(10px) scale(.97); transition: opacity .2s ease, transform .2s ease, visibility 0s linear .2s; pointer-events: none; }

  header { display: flex; align-items: center; gap: 12px; padding-block: 16px 14px; padding-inline: 20px 12px; background: rgba(0,0,0,.42); border-block-end: 1px solid rgba(255,255,255,.1); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,.8); flex: none; }
  .who { display: flex; flex-direction: column; min-width: 0; flex: 1; line-height: 1.25; }
  .who strong { font-weight: 500; font-size: 16px; }
  .who span { font-size: 12px; color: rgba(255,255,255,.62); }
  .icon { width: 36px; height: 36px; display: grid; place-items: center; border: 0; border-radius: 50%; background: transparent; color: rgba(255,255,255,.75); transition: background .15s, color .15s; }
  .icon:hover { background: rgba(255,255,255,.12); color: #fff; }

  .log { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 18px 18px 8px; display: flex; flex-direction: column; gap: 12px; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,.25) transparent; }
  .msg { display: flex; flex-direction: column; gap: 8px; max-width: 86%; }
  .msg.user { align-self: flex-end; }
  .msg.bot { align-self: flex-start; }
  .bubble { padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
  .user .bubble { background: #fff; color: #0a0a0a; border-end-end-radius: 6px; }
  .bot .bubble { white-space: normal; background: rgba(255,255,255,.1); color: #fff; border-end-start-radius: 6px; }
  .bubble p { margin: 0; white-space: pre-wrap; }
  .bubble p + p, .bubble ul + p, .bubble ol + p { margin-block-start: 12px; }
  .bubble ul, .bubble ol { margin: 10px 0; padding-inline-start: 20px; }
  .bubble li { margin-block: 7px; white-space: pre-wrap; }
  .bubble strong { font-weight: 650; }
  .bot.err .bubble { background: rgba(239,68,68,.16); border: 1px solid rgba(239,68,68,.45); }
  .bubble a { color: inherit; text-decoration: underline; text-underline-offset: 3px; }
  .enter { animation: rise .26s ease both; }
  @keyframes rise { from { opacity: 0; transform: translateY(6px) } to { opacity: 1; transform: none } }

  .sources { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px; color: rgba(255,255,255,.62); }
  .sources a, .cta, .chip, .retry { border: 1px solid rgba(255,255,255,.28); border-radius: 999px; padding: 6px 12px; font-size: 13px; line-height: 1.2; color: #fff; background: transparent; text-decoration: none; transition: background .15s, border-color .15s; }
  .sources a:hover, .cta:hover, .chip:hover, .retry:hover { background: rgba(255,255,255,.14); border-color: rgba(255,255,255,.5); }
  .cta { align-self: flex-start; background: #fff; color: #0a0a0a; border-color: #fff; font-weight: 500; }
  .cta:hover { background: rgba(255,255,255,.86); border-color: rgba(255,255,255,.86); }
  .retry { align-self: flex-start; }
  .chips { display: flex; flex: none; flex-wrap: nowrap; gap: 8px; overflow-x: auto; overflow-y: hidden; min-width: 0; padding: 10px 18px 8px; overscroll-behavior-x: contain; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,.4) transparent; }
  .chips::-webkit-scrollbar { height: 6px; }
  .chips::-webkit-scrollbar-thumb { background: rgba(255,255,255,.4); border-radius: 999px; }
  .chip { flex: 0 0 auto; padding: 9px 14px; white-space: nowrap; }

  .products { display: grid; gap: 10px; }
  .product { border: 1px solid rgba(255,255,255,.2); border-radius: 14px; overflow: hidden; background: rgba(255,255,255,.06); }
  .product img { display: block; width: 100%; height: 150px; object-fit: contain; background: rgba(255,255,255,.08); }
  .product-info { padding: 12px; display: grid; gap: 7px; font-size: 13px; }
  .product-info strong { font-size: 15px; }
  .product-info small { font-size: 11px; opacity: .7; }
  .product-info a { color: #fff; text-underline-offset: 3px; }
  .chip:disabled, .retry:disabled { opacity: .45; cursor: wait; }
  .typing { display: inline-flex; gap: 5px; align-items: center; padding: 15px 16px; }
  .typing i { width: 6px; height: 6px; border-radius: 50%; background: rgba(255,255,255,.7); animation: blink 1.1s infinite ease-in-out; }
  .typing i:nth-child(2) { animation-delay: .15s } .typing i:nth-child(3) { animation-delay: .3s }
  @keyframes blink { 0%, 80%, 100% { opacity: .25; transform: none } 40% { opacity: 1; transform: translateY(-3px) } }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }

  form { position: relative; padding: 10px 18px 18px; }
  textarea { display: block; width: 100%; resize: none; max-height: 112px; min-height: 46px; scrollbar-width: none; border-radius: 23px; border: 1px solid rgba(255,255,255,.18);
    background: rgba(255,255,255,.08); color: #fff; font: inherit; font-size: 15px; line-height: 1.4; padding: 12px 18px; padding-inline: 18px 92px; overflow-y: auto; transition: background .15s, border-color .15s; }
  textarea::-webkit-scrollbar { display: none; }
  textarea::placeholder { color: rgba(255,255,255,.5); }
  textarea:focus { outline: none; background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.55); }
  .send { position: absolute; inset-block-end: 24px; inset-inline-end: 26px; height: 34px; padding: 0 16px; border: 0; border-radius: 999px; background: #fff; color: #0a0a0a; font-size: 13px; font-weight: 500; transition: opacity .15s, transform .15s; }
  .send:hover:not(:disabled) { transform: scale(1.04) }
  .send:disabled { opacity: .35; cursor: not-allowed; }
  .count { position: absolute; inset-block-start: -2px; inset-inline-end: 24px; font-size: 11px; color: rgba(255,255,255,.55); }
  .count[hidden] { display: none }

  .launcher { position: relative; width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; gap: 2px; border-radius: 50%;
    background: rgba(0,0,0,.62); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,.24); color: #fff;
    font-size: 14px; font-weight: 500; transition: transform .2s ease, background .2s; }
  .launcher:hover { transform: scale(1.05); background: rgba(0,0,0,.78); }
  .launcher svg { width: 11px; height: 11px; transition: transform .25s ease; }
  .root[data-open] .launcher svg { transform: rotate(180deg); }
  .launcher .pip { position: absolute; inset-block-start: 5px; inset-inline-end: 5px; width: 9px; height: 9px; border-radius: 50%; background: #22c55e; border: 2px solid #0b0b0b; }
  @supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) { .launcher { background: #0b0b0b; } }

  @media (max-width: 520px) {
    .panel { position: fixed; inset: 0; width: auto; height: 100dvh; border-radius: 0; border: 0; box-shadow: none; transform-origin: bottom center; background: rgba(10,10,10,.96); }
    .root:not([data-open]) .panel { transform: translateY(24px); }
    .root[data-open] .launcher { display: none; }
    .launcher { width: 54px; height: 54px; }
    header { padding-block-start: max(16px, env(safe-area-inset-top)); }
    form { padding-block-end: max(18px, env(safe-area-inset-bottom)); }
    textarea { font-size: 16px; }
    .msg { max-width: 92%; }
  }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition-duration: .01ms !important; } }
  `;

  // ---- build ----
  const host = h('div', { id: 'rabbit-hole-chat' });
  const shadow = host.attachShadow({ mode: 'open' });
  const log = h('div', { class: 'log', role: 'log', 'aria-live': 'polite', 'aria-relevant': 'additions text', tabindex: '0' });
  const title = h('strong', {}, cfg.name);
  const subEl = h('span');
  const freshBtn = h('button', { class: 'icon', type: 'button', onclick: () => api.reset() }, svg('M3 12a9 9 0 1 0 3-6.7M3 4v5h5'));
  const closeBtn = h('button', { class: 'icon', type: 'button', onclick: () => api.close() }, svg('M6 6l12 12M18 6L6 18'));
  const input = h('textarea', { rows: '1', maxlength: String(cfg.maxLen), enterkeyhint: 'send', autocomplete: 'off', id: 'msg' });
  const label = h('label', { class: 'sr', for: 'msg' });
  const sendBtn = h('button', { class: 'send', type: 'submit', disabled: true });
  const count = h('div', { class: 'count', hidden: true, 'aria-hidden': 'true' });
  const shortcuts = h('div', { class: 'chips', role: 'group', 'aria-label': 'Suggested questions' });
  const form = h('form', { onsubmit: (e) => { e.preventDefault(); const v = input.value; if (v.trim() && !state.pending) { input.value = ''; autosize(); send(v); } } }, label, input, sendBtn, count);
  const panel = h('section', { class: 'panel', id: 'panel', role: 'dialog', 'aria-modal': 'false', inert: true },
    h('header', {}, h('span', { class: 'dot' }), h('div', { class: 'who' }, title, subEl), freshBtn, closeBtn), log, shortcuts, form);
  const launcher = h('button', { class: 'launcher', type: 'button', 'aria-controls': 'panel', 'aria-expanded': 'false', onclick: () => api.toggle() },
    h('span', {}, 'RH'), svg('M6 15l6-6 6 6'), h('span', { class: 'pip' }));
  const root = h('div', { class: 'root' }, panel, launcher);
  shadow.append(h('style', {}, CSS), root);

  // ---- rendering ----
  const scrollEnd = () => requestAnimationFrame(() => log.scrollTo({ top: log.scrollHeight, behavior: reduceMotion.matches ? 'auto' : 'smooth' }));
  // A small, text-only formatter: paragraphs, lists and bold; never interpret HTML.
  const inline = text => {
    const parts = text.split(/(\*\*[^*\n]+\*\*)/g);
    return parts.flatMap(part => part.startsWith('**') && part.endsWith('**')
      ? [h('strong', {}, linkify(part.slice(2, -2)))] : linkify(part));
  };
  const answerBody = text => {
    const nodes = []; let list = null;
    for (const line of text.split(/\r?\n/)) {
      const item = line.match(/^\s*(?:([-*•])|\d+[.)])\s+(.+)$/);
      if (item) {
        const tag = item[1] ? 'ul' : 'ol';
        if (!list || list.tagName.toLowerCase() !== tag) { list = h(tag); nodes.push(list); }
        list.append(h('li', {}, inline(item[2])));
      } else {
        list = null;
        if (!line.trim()) continue;
        // Older stored/plain responses also get short, readable paragraphs.
        const paragraphs = line.length > 360 ? line.split(/(?<=[.!?؟])\s+(?=[A-Z\u0600-\u06ff])/u) : [line];
        for (const paragraph of paragraphs) nodes.push(h('p', {}, inline(paragraph)));
      }
    }
    return nodes;
  };
  const bubble = (text, formatted = false) => h('div', { class: 'bubble', dir: 'auto' }, formatted ? answerBody(text) : linkify(text));
  const renderShortcuts = () => {
    shortcuts.setAttribute('aria-label', state.lang === 'ar' ? 'أسئلة مقترحة' : 'Suggested questions');
    shortcuts.replaceChildren(...t().chips.map(([label, question]) => h('button', { class: 'chip', type: 'button', disabled: state.pending, onclick: () => send(question) }, label)));
    shortcuts.scrollLeft = 0;
  };


  const productCards = products => h('div', { class: 'products' }, products.slice(0, 6).flatMap(product => {
    if (!product || typeof product.name !== 'string' || !safeUrl(product.url)) return [];
    const image = safeUrl(product.image);
    const details = h('div', { class: 'product-info' }, h('strong', {}, product.name));
    if (typeof product.price === 'number' && Number.isFinite(product.price) && /^[A-Z]{3}$/.test(product.currency || '')) {
      details.append(h('span', {}, new Intl.NumberFormat(state.lang === 'ar' ? 'ar-AE' : 'en-AE', { style: 'currency', currency: product.currency }).format(product.price)));
      if (product.price_includes_vat === true) details.append(h('small', {}, t().vat));
    }
    if (typeof product.in_stock === 'boolean') details.append(h('span', {}, product.in_stock ? t().available : t().unavailable));
    details.append(h('a', { href: safeUrl(product.url), target: '_blank', rel: 'noopener noreferrer' }, t().viewProduct));
    return [h('article', { class: 'product' }, image ? h('img', { src: image, alt: product.name, loading: 'lazy', referrerpolicy: 'no-referrer' }) : null, details)];
  }));

  function renderMsg(m, animate = true) {
    const cls = ['msg', m.role === 'user' ? 'user' : 'bot', m.error ? 'err' : '', animate ? 'enter' : ''].join(' ');
    const wrap = h('div', { class: cls.trim() });
    wrap.append(bubble(m.text || '', m.role === 'bot' && !m.error));
    if (m.role === 'bot' && !m.error) {
      if (Array.isArray(m.products) && m.products.length) wrap.append(productCards(m.products));
      const srcs = (m.sources || []).map((s) => ({ title: s.title, url: safeUrl(s.url) })).filter((s) => s.url);
      if (srcs.length) wrap.append(h('div', { class: 'sources' }, h('span', {}, t().sources), srcs.map((s) => h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.title || s.url))));
      if (m.needsHuman) wrap.append(h('a', { class: 'cta', href: 'mailto:' + cfg.contact }, t().email));
    }
    if (m.error) wrap.append(h('button', { class: 'retry', type: 'button', onclick: () => { wrap.remove(); send(m.retryText, true); } }, t().retry));
    return wrap;
  }

  function renderAll() {
    log.replaceChildren();
    if (!state.msgs.length) {
      log.append(h('div', { class: 'msg bot' }, bubble(t().welcome)));
    } else for (const m of state.msgs) log.append(renderMsg(m, false));
    scrollEnd();
  }

  function applyLang() {
    const L = t();
    panel.setAttribute('dir', state.lang === 'ar' ? 'rtl' : 'ltr');   // not on .root: the launcher keeps its physical corner
    panel.lang = state.lang;
    subEl.textContent = L.sub; input.placeholder = L.placeholder; sendBtn.textContent = L.send; label.textContent = L.msgLabel;
    closeBtn.setAttribute('aria-label', L.close); closeBtn.title = L.close;
    freshBtn.setAttribute('aria-label', L.fresh); freshBtn.title = L.fresh;
    launcher.setAttribute('aria-label', state.open ? L.close : L.open);
    panel.setAttribute('aria-label', cfg.name);
    renderShortcuts(); renderAll();
  }

  const autosize = () => {
    input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 112) + 'px';
    sendBtn.disabled = state.pending || !input.value.trim();
    panel.querySelectorAll('.chip, .retry').forEach(button => { button.disabled = state.pending; });
    const n = input.value.length; count.hidden = n < cfg.maxLen * 0.8; count.textContent = n + '/' + cfg.maxLen;
  };
  input.addEventListener('input', autosize);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (e.isComposing || e.keyCode === 229) return;   // IME confirm (incl. Safari ordering quirk)
      form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  });
  panel.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); api.close(); } });

  // ---- network ----
  const errKey = (e) => (e && e.status === 429 ? 'errRate' : e && [400, 413, 422].includes(e.status) ? 'errBad' : e && e.status ? 'errGen' : 'errNet');

  // Keep this executable contract checked against ChatResponse in the browser tests.
  const responseContract = {"answer":"string","sources":"array","products":"array","needs_human":"boolean","conversation_id":"string","language":"string"};
  const sourceContract = {"title":"string","url":"string","document_id":"string"};
  const matchesContract = (d, c) => d && Object.entries(c).every(([k, type]) =>
    type === 'array' ? Array.isArray(d[k]) : typeof d[k] === type);
  const validResponse = (d) => matchesContract(d, responseContract) &&
    typeof d.needs_human === 'boolean' && typeof d.conversation_id === 'string' &&
    /^[A-Za-z0-9_-]{1,64}$/.test(d.conversation_id) && ['en', 'ar'].includes(d.language) &&
    Array.isArray(d.products) && d.products.every((p) => p && typeof p === 'object' && !Array.isArray(p)) &&
    d.sources.every((s) => matchesContract(s, sourceContract));

  async function send(text, isRetry = false) {
    text = String(text || '').trim();
    if (!text || state.pending) return;
    if (!isRetry) { const m = { role: 'user', text }; state.msgs.push(m); if (state.msgs.length === 1) log.replaceChildren(); log.append(renderMsg(m)); save(); }
    state.pending = true; autosize();
    const requestLang = state.lang;
    const typing = h('div', { class: 'msg bot enter', role: 'status', 'aria-label': cfg.name + ' ' + t().typing }, h('div', { class: 'bubble typing' }, h('i'), h('i'), h('i')));
    log.append(typing); scrollEnd();
    const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), cfg.timeoutMs);
    try {
      const res = await fetch(cfg.api + '/chat', {
        method: 'POST', credentials: 'omit', signal: ctl.signal,
        headers: Object.assign({ 'Content-Type': 'application/json' }, cfg.siteKey ? { 'X-Site-Key': cfg.siteKey } : {}),
        body: JSON.stringify({ message: text, language: requestLang, conversation_id: state.convId || undefined }),
      });
      if (!res.ok) throw { status: res.status };
      const data = await res.json();
      if (!validResponse(data)) throw { status: 502 };
      if (state.convId && data.conversation_id !== state.convId) { state.msgs = state.msgs.filter(m => m.role === 'user').slice(-1); log.replaceChildren(...state.msgs.map(m => renderMsg(m, false))); }
      if (data.conversation_id) state.convId = data.conversation_id;
      const m = { role: 'bot', text: data.answer, sources: data.sources, products: data.products, needsHuman: data.needs_human };
      state.msgs.push(m); typing.remove(); log.append(renderMsg(m)); save();
    } catch (e) {
      typing.remove();
      log.append(renderMsg({ role: 'bot', error: true, text: t()[errKey(e)], retryText: text }));   // errors are shown, never stored
    } finally {
      clearTimeout(timer); state.pending = false; autosize(); scrollEnd();
      if (!state.langLocked && resolveLang() !== state.lang) changeLanguage(resolveLang());
      if (state.open && !mobileMQ.matches) input.focus({ preventScroll: true });
    }
  }

  // ---- mobile keyboard: keep the sheet inside the visual viewport ----
  const vv = window.visualViewport;
  const fitSheet = () => {
    if (!vv || !mobileMQ.matches || !state.open) { panel.style.height = ''; panel.style.transform = ''; return; }
    panel.style.height = vv.height + 'px'; panel.style.transform = 'translateY(' + vv.offsetTop + 'px)';
  };
  if (vv) { vv.addEventListener('resize', fitSheet); vv.addEventListener('scroll', fitSheet); }
  mobileMQ.addEventListener('change', fitSheet);

  // ---- public API ----
  const api = {
    version: '1.0.0',
    open() {
      if (state.open) return; state.open = true;
      root.setAttribute('data-open', ''); panel.inert = false; launcher.setAttribute('aria-expanded', 'true'); launcher.setAttribute('aria-label', t().close);
      fitSheet(); setTimeout(() => input.focus({ preventScroll: true }), reduceMotion.matches ? 0 : 120); scrollEnd();
    },
    close() {
      if (!state.open) return; state.open = false;
      root.removeAttribute('data-open'); panel.inert = true; launcher.setAttribute('aria-expanded', 'false'); launcher.setAttribute('aria-label', t().open);
      fitSheet(); launcher.focus({ preventScroll: true });
    },
    toggle() { state.open ? api.close() : api.open(); },
    setLanguage(l) { if (state.pending || (l !== 'en' && l !== 'ar')) return; state.langLocked = true; changeLanguage(l); },
    reset() { if (state.pending) return; state.msgs = []; state.convId = ''; clearSaved(); renderAll(); input.focus({ preventScroll: true }); },
    destroy() { mo.disconnect(); if (vv) { vv.removeEventListener('resize', fitSheet); vv.removeEventListener('scroll', fitSheet); } host.remove(); delete window.RabbitHoleChat; },
  };

  // Follow the site's EN/AR toggle (<html lang|dir>) unless the language was fixed explicitly.
  function changeLanguage(l) { if (l === state.lang) return; save(); state.lang = l; load(); applyLang(); }
  const mo = new MutationObserver(() => { if (state.langLocked || state.pending) return; changeLanguage(resolveLang()); });
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['lang', 'dir'] });

  state.lang = resolveLang(); load(); applyLang(); autosize();
  const mount = () => document.body.append(host);
  document.body ? mount() : document.addEventListener('DOMContentLoaded', mount, { once: true });
  window.RabbitHoleChat = api;
})();
