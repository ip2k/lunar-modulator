// screenshot.mjs -- open the virtual FM-1 in headless Chromium, power it on,
// play it, and save screenshots plus a JSON report. Runs in the Playwright
// container on aeon (build-on-aeon.sh), never on the Mac:
//
//   node screenshot.mjs WWW_DIR OUT_DIR
//
// Checks along the way: the page starts with no console errors, the
// AudioContext runs (at 44,118 Hz if Chromium allows it), the firmware draws
// its screen, held keys reach the output (an AnalyserNode's RMS), and the
// panel and screen respond to the encoders and buttons. MIT licence.

import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });

const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.wasm': 'application/wasm', '.json': 'application/json',
};
const server = createServer((req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^\/+/, '');
  const file = join(www, path || 'index.html');
  if (!file.startsWith(www) || !existsSync(file)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' });
  res.end(readFileSync(file));
});
await new Promise((r) => server.listen(8765, '127.0.0.1', r));
const url = 'http://127.0.0.1:8765/index.html';

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
  const box = await page.locator(selector).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < Math.abs(ticks); ++i) {
    await page.mouse.wheel(0, ticks > 0 ? -100 : 100);
    await wait(page, 30);
  }
}
async function press(page, button) {
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

  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  phone.on('pageerror', (e) => report.logs.push(`phone pageerror: ${e.message}`));
  await phone.goto(url);
  await phone.click('#power-on');
  await phone.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  await wait(phone, 300);
  report.checks.phone_scroll_width = await phone.evaluate(() => document.documentElement.scrollWidth);
  await phone.screenshot({ path: join(out, '05-phone.png'), fullPage: true });
  await phone.close();
} catch (err) {
  report.error = String(err && err.stack || err);
} finally {
  await browser.close();
  server.close();
}

const c = report.checks;
report.pass = !report.error && c.screens > 0 && c.chord_rms > 0.01 && c.lit_keys === 3 &&
  c.fx_led === true && c.phone_scroll_width <= 390 &&
  !report.logs.some((l) => l.startsWith('error') || l.includes('pageerror'));
writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, browser: report.browser, ...c, error: report.error }, null, 0));
process.exit(report.pass ? 0 : 1);
