// screenshot.mjs -- open the virtual FM-1 in headless Chromium, power it on,
// play it, and save screenshots plus a JSON report. Runs in the Playwright
// container on aeon (build-on-aeon.sh), never on the Mac:
//
//   node screenshot.mjs WWW_DIR OUT_DIR
//
// Checks along the way: the page starts with no console errors, the
// AudioContext runs (at 44,118 Hz if Chromium allows it), the firmware draws
// its screen, held keys reach the output (an AnalyserNode's RMS), and the
// panel and screen respond to the encoders and buttons. Then input edge
// cases, from the 2026-10-01 review: keys released under Cmd, Ctrl or Alt,
// everything let go on blur and on a hidden tab, Enter's release reaching
// the button it pressed, a select giving the keyboard back, one
// AudioContext for a double click on Power on, wheel detents, screens still
// flowing on two recycled buffers; and on a phone, targets of at least
// 24 px with no page-wide horizontal scroll. And the theme: the title, the
// Audiowide face loaded from the page's own fonts/, the palette's base as
// the page background. MIT licence.

import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8765);

const report = { checks: {}, logs: [] };
const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
report.browser = `Chromium ${browser.version()} (Playwright, headless)`;

async function tftPng(page, name) {
  const data = await page.evaluate(() => document.getElementById('tft').toDataURL('image/png'));
  writeFileSync(join(out, name), Buffer.from(data.split(',')[1], 'base64'));
}
const level = (page) => page.evaluate(() => {
  const a = window.fm1.analyser;
  const buf = new Float32Array(a.fftSize);
  a.getFloatTimeDomainData(buf);
  return Math.sqrt(buf.reduce((s, x) => s + x * x, 0) / buf.length);
});
const wait = (page, ms) => page.waitForTimeout(ms);
async function wheel(page, selector, ticks) {
  await page.locator(selector).scrollIntoViewIfNeeded();
  const box = await page.locator(selector).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < Math.abs(ticks); ++i) {
    await page.mouse.wheel(0, ticks > 0 ? -100 : 100);
    await wait(page, 30);
  }
}
// Messages the page sends to the worklet, recorded from now on, and what
// they leave held down in the firmware.
async function spy(page) {
  await page.evaluate(() => {
    window.__sent = [];
    const port = window.fm1.node.port;
    const post = port.postMessage.bind(port);
    port.postMessage = (m, t) => {
      if (m.type !== 'screen-buffer') window.__sent.push(JSON.parse(JSON.stringify(m)));
      return post(m, t);
    };
  });
}
const resetSent = (page) => page.evaluate(() => { window.__sent.length = 0; });
const sent = (page) => page.evaluate(() => window.__sent);
const heldDown = (page) => page.evaluate(() => {
  const keys = new Set(), buttons = new Set();
  for (const m of window.__sent) {
    if (m.type === 'key') { if (m.down) keys.add(m.key); else keys.delete(m.key); }
    if (m.type === 'button') { if (m.down) buttons.add(m.button); else buttons.delete(m.button); }
    if (m.type === 'panic') keys.clear();
  }
  return { keys: [...keys], buttons: [...buttons] };
});
const nothingHeld = async (page) => {
  const h = await heldDown(page);
  return h.keys.length === 0 && h.buttons.length === 0;
};
const encoderTurns = async (page, encoder) => (await sent(page))
  .filter((m) => m.type === 'encoder' && m.encoder === encoder).reduce((a, m) => a + m.delta, 0);
const blurWindow = (page) => page.evaluate(() => window.dispatchEvent(new Event('blur')));

async function inputChecks(browser) {
  const r = {};
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('pageerror', (e) => report.logs.push(`input pageerror: ${e.message}`));
  await page.addInitScript(() => {
    window.__ctx = [];
    const AC = window.AudioContext;
    window.AudioContext = class extends AC {
      constructor(o) { super(o); window.__ctx.push(this); }
    };
  });
  await page.goto(url);

  // Two clicks on Power on before the first start has finished.
  await page.evaluate(() => { const b = document.getElementById('power-on'); b.click(); b.click(); });
  await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  await wait(page, 200);
  r.open_contexts_after_double_power_on = await page.evaluate(() => window.__ctx.filter((c) => c.state !== 'closed').length);
  await spy(page);

  // A key released while a modifier is down is still released.
  r.released_under_modifier = {};
  for (const mod of ['Meta', 'Control', 'Alt']) {
    await resetSent(page);
    await page.keyboard.down('KeyA');
    await page.keyboard.down(mod);
    await page.keyboard.up('KeyA');
    await page.keyboard.up(mod);
    await wait(page, 150);
    r.released_under_modifier[mod] = await nothingHeld(page) &&
      await page.evaluate(() => document.querySelectorAll('.key.lit').length === 0);
  }
  // macOS: no keyup at all for a key released under Cmd; Cmd lets it go.
  await resetSent(page);
  await page.keyboard.down('KeyA');
  const pressed = (await sent(page)).some((m) => m.type === 'key' && m.key === 0 && m.down);
  await page.keyboard.down('Meta');
  await page.keyboard.up('Meta');
  r.cmd_releases_held_keys = pressed && await nothingHeld(page);
  await page.keyboard.up('KeyA');

  // Blur and a hidden tab let go of computer keys, Z/X and pointers.
  await resetSent(page);
  await page.keyboard.down('KeyZ');
  await page.keyboard.down('KeyS');
  const key5 = await page.locator('[data-key="5"]').boundingBox();
  await page.mouse.move(key5.x + key5.width / 2, key5.y + key5.height / 2);
  await page.mouse.down();
  await wait(page, 50);
  await blurWindow(page);
  r.blur_releases_everything = await nothingHeld(page);
  await page.mouse.up();
  await page.keyboard.up('KeyS');
  await page.keyboard.up('KeyZ');
  await resetSent(page);
  await page.keyboard.down('KeyX');
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    delete document.visibilityState;
  });
  r.hidden_tab_releases_everything = await nothingHeld(page);
  await page.keyboard.up('KeyX');

  // Enter on FX, Tab away, release: the up goes to FX, and the next press works.
  await resetSent(page);
  const modeBefore = await page.evaluate(() => window.fm1.state.mode);
  await page.focus('[data-button="2"]');
  await page.keyboard.down('Enter');
  await page.keyboard.press('Tab');
  await page.keyboard.up('Enter');
  await wait(page, 100);
  const enterMsgs = (await sent(page)).filter((m) => m.type === 'button');
  r.enter_release_reaches_its_button = enterMsgs.length === 2 && enterMsgs.every((m) => m.button === 2) &&
    await page.evaluate(() => !document.querySelector('[data-button="2"]').classList.contains('down'));
  await page.focus('[data-button="2"]');
  await page.keyboard.press('Enter');
  await wait(page, 100);
  r.fx_press_after_that_works = await page.evaluate((m) => window.fm1.state.mode === m, modeBefore);

  // A select gives the keyboard back once a choice is made.
  await page.focus('#sel-fx1');
  const ensemble = await page.evaluate(() => window.fm1.catalog.find((e) => e.id === 'ensemble').index);
  await page.selectOption('#sel-fx1', String(ensemble));
  await wait(page, 100);
  await resetSent(page);
  await page.keyboard.press('KeyD');
  await wait(page, 100);
  r.select_gives_keys_back = await page.evaluate((i) => window.fm1.state.units[1] === i, ensemble) &&
    (await sent(page)).some((m) => m.type === 'key' && m.key === 4 && m.down);

  // Wheel: horizontal turns nothing, a trackpad's small deltas add up, each
  // mouse notch is one detent.
  // Selecting above scrolled the page down to the dropdown; a player scrolls
  // back to the knob before turning it.
  await page.locator('[data-encoder="3"]').scrollIntoViewIfNeeded();
  const knob1 = await page.locator('[data-encoder="3"]').boundingBox();
  await page.mouse.move(knob1.x + knob1.width / 2, knob1.y + knob1.height / 2);
  await resetSent(page);
  await page.mouse.wheel(120, 0);
  await wait(page, 300);
  r.wheel_horizontal = await encoderTurns(page, 3);
  for (let i = 0; i < 20; ++i) { await page.mouse.wheel(0, -4); await wait(page, 16); }
  await wait(page, 300);
  r.wheel_trackpad_80px = await encoderTurns(page, 3);
  await resetSent(page);
  for (let i = 0; i < 5; ++i) { await page.mouse.wheel(0, 100); await wait(page, 250); }
  r.wheel_five_slow_notches = await encoderTurns(page, 3);
  await resetSent(page);
  for (let i = 0; i < 5; ++i) { await page.mouse.wheel(0, -100); await wait(page, 60); }
  r.wheel_five_fast_notches = await encoderTurns(page, 3);

  // Screens keep coming on the two recycled buffers while a note plays.
  await page.keyboard.down('KeyG');
  const s0 = await page.evaluate(() => window.fm1.screens);
  await wait(page, 1000);
  r.screens_per_second_playing = (await page.evaluate(() => window.fm1.screens)) - s0;
  await page.keyboard.up('KeyG');

  await page.click('#power-off');
  await wait(page, 200);
  r.open_contexts_after_power_off = await page.evaluate(() => window.__ctx.filter((c) => c.state !== 'closed').length);
  await page.close();

  r.pass = r.open_contexts_after_double_power_on === 1 && r.open_contexts_after_power_off === 0 &&
    Object.values(r.released_under_modifier).every(Boolean) && r.cmd_releases_held_keys &&
    r.blur_releases_everything && r.hidden_tab_releases_everything &&
    r.enter_release_reaches_its_button && r.fx_press_after_that_works && r.select_gives_keys_back &&
    r.wheel_horizontal === 0 && r.wheel_trackpad_80px >= 1 && r.wheel_trackpad_80px <= 3 &&
    r.wheel_five_slow_notches === -5 && r.wheel_five_fast_notches === 5 &&
    r.screens_per_second_playing >= 10;
  return r;
}

// The smallest side of each kind of control, and the page's scroll width,
// at the current viewport, in CSS px.
async function targets(page) {
  return page.evaluate(() => {
    const min = (sel) => Math.min(...[...document.querySelectorAll(sel)].map((e) => {
      const r = e.getBoundingClientRect();
      return Math.round(10 * Math.min(r.width, r.height)) / 10;
    }));
    return {
      page_scroll_width: document.documentElement.scrollWidth,
      white_key: min('.key.white .cap'), black_key: min('.key.black .cap'),
      button: min('.btn .cap'), knob: min('.knob .body'),
    };
  });
}
const bigEnough = (t, px) => Math.min(t.white_key, t.black_key, t.button, t.knob) >= px;

async function press(page, button) {
  await page.locator(`[data-button="${button}"]`).scrollIntoViewIfNeeded();
  const box = await page.locator(`[data-button="${button}"]`).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await wait(page, 60);
  await page.mouse.up();
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('console', (m) => report.logs.push(`${m.type()}: ${m.text()}`));
  page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
  await page.goto(url);
  // The theme: the title, the display face actually loaded from fonts/, the
  // palette's base behind everything.
  report.checks.theme = await page.evaluate(async () => {
    await document.fonts.ready;
    const loaded = await document.fonts.load('400 24px Audiowide');
    return {
      title: document.title,
      display_font_loaded: loaded.length > 0 && document.fonts.check('400 24px Audiowide'),
      body_background: getComputedStyle(document.body).backgroundColor,
      brand: getComputedStyle(document.querySelector('.brand')).textTransform === 'uppercase' &&
        document.querySelector('.brand').textContent.trim(),
    };
  });
  await page.screenshot({ path: join(out, '01-powered-off.png'), fullPage: true });

  await page.click('#power-on');
  await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  report.checks.rate = await page.evaluate(() => window.fm1.ctx.sampleRate);
  report.checks.requested_rate = await page.evaluate(() => window.fm1.requestedRate);
  report.checks.silent_rms = await level(page);

  for (const k of ['KeyA', 'KeyD', 'KeyG']) await page.keyboard.down(k);   // F3, A3, C4
  await wait(page, 400);
  report.checks.chord_rms = await level(page);
  report.checks.lit_keys = await page.evaluate(() => document.querySelectorAll('.key.lit').length);
  await page.screenshot({ path: join(out, '02-playing.png') });
  await tftPng(page, 'tft-02-home.png');
  for (const k of ['KeyA', 'KeyD', 'KeyG']) await page.keyboard.up(k);

  await wheel(page, '[data-encoder="3"]', 12);                  // KNOB1: the first parameter on the page
  await wait(page, 150);
  await tftPng(page, 'tft-03-knob1.png');
  await wheel(page, '[data-encoder="1"]', 1);                   // PRESETS: next sound
  await wait(page, 150);
  await tftPng(page, 'tft-04-presets-popup.png');
  report.checks.sound_after_presets = await page.evaluate(() => window.fm1.state.units[0]);
  await wait(page, 1200);
  await press(page, 2);                                         // FX
  await wait(page, 150);
  await wheel(page, '[data-encoder="0"]', 1);                   // SELECT: slot 2
  await wheel(page, '[data-encoder="2"]', 2);                   // ALGORITHM: an effect there
  await wait(page, 1300);
  await page.screenshot({ path: join(out, '03-fx-mode.png') });
  await tftPng(page, 'tft-05-fx.png');
  report.checks.units_after_fx = await page.evaluate(() => window.fm1.state.units);
  report.checks.fx_led = await page.evaluate(() => document.querySelector('[data-button="2"]').classList.contains('lit'));
  await press(page, 7);                                         // GLO
  await wait(page, 200);
  await tftPng(page, 'tft-06-global.png');
  await page.click('#zoom');
  await wait(page, 100);
  await page.screenshot({ path: join(out, '04-global-zoom.png'), fullPage: true });
  report.checks.status = await page.textContent('#status');
  report.checks.screens = await page.evaluate(() => window.fm1.screens);
  await page.close();

  report.checks.input = await inputChecks(browser);

  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  phone.on('pageerror', (e) => report.logs.push(`phone pageerror: ${e.message}`));
  await phone.goto(url);
  await phone.click('#power-on');
  await phone.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  await wait(phone, 300);
  report.checks.phone = await targets(phone);
  report.checks.phone_scroll_width = report.checks.phone.page_scroll_width;
  await phone.screenshot({ path: join(out, '05-phone.png'), fullPage: true });
  // Dragging the case below the keys pans the panel to its right half.
  const at = await phone.evaluate(() => {
    const r = document.getElementById('panel').getBoundingClientRect();
    return { x: r.left + (60 + 3) / 167.5 * r.width, y: r.top + (92 + 8) / 107 * r.height };
  });
  await phone.mouse.move(at.x, at.y);
  await phone.mouse.down();
  await phone.mouse.move(at.x - 200, at.y, { steps: 8 });
  await phone.mouse.up();
  report.checks.phone_pan_px = await phone.evaluate(() => document.getElementById('device-scroll').scrollLeft);
  await phone.screenshot({ path: join(out, '06-phone-panned.png') });
  await phone.close();

  const landscape = await browser.newPage({ viewport: { width: 844, height: 390 }, deviceScaleFactor: 2 });
  await landscape.goto(url);
  report.checks.landscape = await targets(landscape);
  await landscape.screenshot({ path: join(out, '07-landscape.png') });
  await landscape.close();
} catch (err) {
  report.error = String(err && err.stack || err);
} finally {
  await browser.close();
  server.close();
}

const c = report.checks;
const theme = c.theme || {};
report.pass = !report.error && theme.title === 'Lunar Modulator' && theme.display_font_loaded === true &&
  theme.body_background === 'rgb(35, 33, 54)' && c.screens > 0 && c.chord_rms > 0.01 && c.lit_keys === 3 &&
  c.fx_led === true && c.phone_scroll_width <= 390 && bigEnough(c.phone, 24) && c.phone_pan_px > 100 &&
  c.landscape.page_scroll_width <= 844 && bigEnough(c.landscape, 24) && c.input && c.input.pass &&
  !report.logs.some((l) => l.startsWith('error') || l.includes('pageerror'));
writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, browser: report.browser, ...c, error: report.error }, null, 0));
process.exit(report.pass ? 0 : 1);
