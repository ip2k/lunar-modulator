// Exercise the real local toast library: timing, focus, actions, replacement,
// plain-text safety, and persistent refusals without starting audio.
import { launch } from './launch.mjs';
import { serve } from './serve.mjs';
import { mkdir, writeFile } from 'node:fs/promises';

const out = process.argv[3] || 'scratch/notifications-ui';
await mkdir(out, { recursive: true });
const { server, url } = await serve(process.argv[2] || 'sim/web/www', 0);
const base = url.replace(/:\d+\//, `:${server.address().port}/`);
const { browser, name } = await launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
const errors = [], requests = [], checks = [];
page.on('pageerror', e => errors.push(e.message));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('request', r => requests.push(r.url()));
const check = (ok, message) => { if (!ok) throw Error(message); checks.push(message); };
try {
  await page.route('**/notice-fixture.html', r => r.fulfill({
    contentType: 'text/html',
    headers: { 'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'" },
    body: '<!doctype html><link rel="stylesheet" href="/vendor/sweetalert2/sweetalert2.min.css"><link rel="stylesheet" href="/style.css"><main><label>Song name<input id="name" value="Satellite Hearts"></label><button id="outside">Continue editing</button><div id="file-notice" class="file-notice" role="status" hidden></div></main><script type="module" src="/notice-fixture.js"></script>',
  }));
  await page.route('**/notice-fixture.js', r => r.fulfill({ contentType: 'text/javascript', body: `
    import {fileNotifications} from '/notifications.js';
    const element=document.querySelector('#file-notice'), notices=fileNotifications(element);
    window.actions=0;
    window.showNotice=(text, transient=true)=>{
      notices.dismiss();element.replaceChildren();
      const p=document.createElement('p');p.textContent=text;element.append(p);
      const action=document.createElement('button');action.textContent='Undo load';action.onclick=()=>window.actions++;element.append(action);
      const dismiss=document.createElement('button');dismiss.textContent='Dismiss';dismiss.onclick=notices.dismiss;element.append(dismiss);
      notices.show(transient);
    };
  ` }));
  await page.clock.install();
  await page.goto(base.replace('index.html', 'notice-fixture.html'));
  await page.waitForFunction(() => typeof window.showNotice === 'function');
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000));
  await page.locator('#name').focus();
  await page.evaluate(() => window.showNotice('<img src=x onerror=alert(1)> loaded'));
  await page.clock.runFor(30);
  const toast = page.locator('.lunar-toast');
  check(await toast.isVisible(), 'Transient notice is visible');
  check(await page.locator('#name').evaluate(e => e === document.activeElement), 'Toast does not steal editor focus');
  check(await toast.getAttribute('role') === 'alert' && await toast.getAttribute('aria-live') === 'polite' && await toast.getAttribute('aria-modal') !== 'true', 'Toast is a polite nonmodal announcement');
  check(await page.locator('#file-notice img').count() === 0 && (await page.locator('#file-notice').textContent()).includes('<img src=x'), 'Imported project names remain plain text');
  await page.clock.runFor(9000);
  check(await toast.isVisible(), 'Notice remains visible before ten seconds');
  await page.clock.runFor(1100);
  check(await toast.count() === 0 && await page.locator('#file-notice').isHidden(), 'Notice dismisses after ten seconds');

  await page.evaluate(() => window.showNotice('Hover and keyboard actions'));
  await page.clock.runFor(30);
  await toast.hover();
  await page.clock.runFor(15000);
  check(await toast.isVisible(), 'Hover pauses dismissal');
  await page.getByRole('button', { name: 'Undo load', exact: true }).focus();
  await page.mouse.move(0, 0);
  await page.clock.runFor(15000);
  check(await toast.isVisible(), 'Keyboard focus pauses dismissal after pointer leaves');
  await page.keyboard.press('Enter');
  check(await page.evaluate(() => window.actions === 1), 'Original native action button still works');
  await page.locator('#outside').focus();
  await page.clock.runFor(11000);
  check(await toast.count() === 0, 'Dismissal resumes after keyboard focus leaves');

  await page.evaluate(() => window.showNotice('Old transient'));
  await page.clock.runFor(30);
  await page.clock.runFor(9000);
  await page.evaluate(() => window.showNotice('Refused: project exceeds memory', false));
  await page.clock.runFor(20000);
  check(await page.locator('#file-notice').isVisible() && await toast.count() === 0 && (await page.locator('#file-notice').textContent()).includes('Refused'), 'Old toast timer cannot hide a replacement refusal');
  check(await page.locator('#file-notice').getAttribute('role') === 'status', 'Inline refusal retains its live region');
  await page.getByRole('button', { name: 'Dismiss', exact: true }).click();
  check(await page.locator('#file-notice').isHidden(), 'Persistent refusal can be dismissed explicitly');

  for (const size of [{ width: 1280, height: 800 }, { width: 667, height: 375 }]) {
    await page.setViewportSize(size);
    await page.evaluate(() => window.showNotice('Project saved. Your controls are still available.'));
    await page.clock.runFor(30);
    check(await toast.evaluate(e => { const r=e.getBoundingClientRect();return r.top>=0 && r.left>=0 && r.bottom<=innerHeight && r.right<=innerWidth; }), `Toast fits ${size.width} viewport`);
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No page overflow at ${size.width}`);
    await page.screenshot({ path: `${out}/${size.width}.png` });
    await page.getByRole('button', { name: 'Dismiss', exact: true }).click();
    await page.clock.runFor(30);
    check(await page.locator('#file-notice').count() === 1 && await toast.count() === 0, 'Manual dismissal restores one original notice without orphan popup');
  }
  check(requests.every(r => r.startsWith(new URL(base).origin)), 'Assets work entirely on the local origin');
  check(errors.length === 0, 'No page or CSP errors');
  await writeFile(`${out}/results.json`, JSON.stringify({ passed: true, name, checks, errors }, null, 2));
  console.log(`PASS ${name}: local notifications, timing, focus, actions and refusals`);
} catch (e) {
  await page.screenshot({ path: `${out}/failure.png` });
  await writeFile(`${out}/results.json`, JSON.stringify({ passed: false, name, checks, errors, failure: e.stack }, null, 2));
  throw e;
} finally { await browser.close(); server.close(); }
