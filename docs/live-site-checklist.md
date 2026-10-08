# Live-site integration

Service HTTPS origin: __________  Exact site origin(s): __________  Revision/date: __________

1. Remove the old chat component and its script/component injection first. Both widgets use
   `z-index: 3000`; running both can produce competing launchers and input handlers. Verify the
   old component does not reappear after navigation or reload. Never copy its exposed LLM token.
2. On the confirmed allowed site origin, add one script tag using the matching PUBLIC site key:

   ```html
   <script src="https://SERVICE_HOST/widget.js?v=REVISION"
           data-api="https://SERVICE_HOST" data-site-key="PUBLIC_WIDGET_KEY" defer></script>
   ```

3. Verify there is one launcher, no mixed-content/CORS errors, and a real approved-content answer
   produces working citations. Confirm the server is `ENV=production` and the demo returns 404.
4. Switch the site's EN/AR toggle. It must update `<html lang="en">`/`<html lang="ar">` or `dir`.
   Confirm widget labels, alignment and panel direction follow it; EN and AR keep separate
   transcripts and conversation IDs. If the site toggle updates neither attribute, wire it to
   `RabbitHoleChat.setLanguage('en'|'ar')`. Do not set `data-lang` to a fixed language when expecting
   automatic following. On mobile, close the full-screen chat before using the page toggle.
5. Switch language while a request is pending: automatic attribute changes apply after the
   request finishes. An explicit `setLanguage` call is ignored while pending; the site's adapter
   must retry after completion if it uses that API instead of changing HTML attributes.
6. Inspect the widget on the site's actual fonts/styles and brightest backgrounds. Page CSS
   must not alter its buttons, textarea, text colour/contrast, sizing or paragraph layout.
   Confirm Shadow DOM styling holds in both EN and AR, including after page navigation.
7. In both EN/LTR and AR/RTL, compare the launcher with cookie banners, WhatsApp/support buttons,
   accessibility controls, back-to-top buttons and mobile navigation. Scroll and rotate; open
   and close the widget. Its physical corner stays fixed when language changes. If needed, use
   `data-position="left"` and a deliberate `data-z-index`; verify overlay order on the actual site.
8. Complete `device-results.md`. Keep Arabic source/UI changes separate and send corrections
   through the Arabic review pack before making content changes.

| Check | EN result | AR result | Issue / screenshot / action |
|---|---|---|---|
| Old component removed, one launcher | | | |
| Real answer/citations/CORS | | | |
| Language toggle / separate transcript | | | |
| Pending-request language change | | | |
| CSS/font/contrast isolation | | | |
| Launcher/fixed-element collisions | | | |
| Navigation/reload behaviour | | | |
