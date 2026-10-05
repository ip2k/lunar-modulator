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
// the page background. And publishing: the page served over https under a
// path, as a static host would publish it, plays with every file found
// there; served over plain http from a name that is not localhost (not a
// secure context), Power on says what the page needs. And the lab switch
// (docs/15 S3): with ?lab, PLAY/STOP plays the demo pattern (sound within a
// second, its LED lit), Space stops and starts it, SEQ shows the Track view
// with the white keys following the playhead and the status line names the
// tempo; multi-sound: SHIFT + PRESETS makes Sound 2 current, the Sound
// dropdown follows and loads Shapes there, and a key plays it with Sound 1's
// level at 0; with #lab the switch is on too; without either, Space sends nothing
// and PLAY/STOP stays a stub. Modulation with the switch (docs/16 MG3): LFO
// opens RACK (its LED lit); LFO held with Enter while the wheel turns a knob
// on HOME makes a cable and opens nothing; EDIT shows MATRIX; without the
// switch LFO stays a stub. Step entry (docs/15 S4): in SEQ mode OP3 (A#3)
// pages to bar 2, the computer's step keys enter four steps there, which
// light those keys, and played, they sound and their lights move with the
// playhead. MIT licence.

import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8765);

const report = { checks: {}, logs: [] };
// lunar.test stands for another machine's address: a name that is not
// localhost, so plain http from it is not a secure context.
const browser = await chromium.launch({
  args: ['--autoplay-policy=no-user-gesture-required', '--host-resolver-rules=MAP lunar.test 127.0.0.1'],
});
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

// A self-signed certificate for 127.0.0.1, made for this run only.
function selfSigned() {
  const dir = mkdtempSync(join(tmpdir(), 'fm1-tls-'));
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
    '-keyout', join(dir, 'key.pem'), '-out', join(dir, 'cert.pem')], { stdio: 'ignore' });
  return { key: readFileSync(join(dir, 'key.pem')), cert: readFileSync(join(dir, 'cert.pem')) };
}

async function publishingChecks(browser) {
  const r = {};
  // https, under a path, the page's URL a directory: as a static host
  // publishes www/. Every request must succeed and stay under that path.
  const https = await serve(www, 8443, { prefix: '/some/where/lunar/', tls: selfSigned() });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const failed = [], outside = [];
  page.on('pageerror', (e) => report.logs.push(`https pageerror: ${e.message}`));
  page.on('response', (res) => { if (res.status() >= 400) failed.push(`${res.status()} ${res.url()}`); });
  page.on('requestfailed', (req) => failed.push(`failed ${req.url()}`));
  page.on('request', (req) => {
    const u = req.url();
    if (!u.startsWith(https.url) && !u.endsWith('/favicon.ico')) outside.push(u);
  });
  await page.goto(https.url);
  const font = await page.evaluate(async () => {
    await document.fonts.load('400 24px Audiowide');
    return document.fonts.check('400 24px Audiowide');
  });
  await page.click('#power-on');
  await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  await page.keyboard.down('KeyG');
  await wait(page, 400);
  const rms = await level(page);
  await page.keyboard.up('KeyG');
  r.https = {
    url: https.url,
    secure_context: await page.evaluate(() => window.isSecureContext),
    rate: await page.evaluate(() => window.fm1.ctx.sampleRate),
    display_font_loaded: font, key_rms: rms,
    failed: failed.filter((f) => !f.endsWith('/favicon.ico')), outside,
  };
  await ctx.close();
  https.server.close();

  // Plain http from a name that is not localhost: no AudioWorklet there, so
  // Power on explains instead of failing.
  const plain = await serve(www, 8767, { host: 'lunar.test' });
  const p2 = await browser.newPage();
  p2.on('pageerror', (e) => report.logs.push(`insecure pageerror: ${e.message}`));
  await p2.goto(plain.url);
  await p2.click('#power-on');
  await wait(p2, 300);
  r.insecure_http = {
    url: plain.url,
    secure_context: await p2.evaluate(() => window.isSecureContext),
    started: await p2.evaluate(() => window.fm1.ctx !== null),
    status: await p2.textContent('#status'),
  };
  await p2.close();
  plain.server.close();

  r.pass = r.https.secure_context === true && r.https.display_font_loaded === true && r.https.key_rms > 0.005 &&
    r.https.failed.length === 0 && r.https.outside.length === 0 &&
    r.insecure_http.secure_context === false && r.insecure_http.started === false &&
    /secure context/.test(r.insecure_http.status);
  return r;
}

async function pressKey(page, key) {
  await page.locator(`[data-key="${key}"]`).scrollIntoViewIfNeeded();
  const box = await page.locator(`[data-key="${key}"]`).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await wait(page, 60);
  await page.mouse.up();
}

async function press(page, button) {
  await page.locator(`[data-button="${button}"]`).scrollIntoViewIfNeeded();
  const box = await page.locator(`[data-button="${button}"]`).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await wait(page, 60);
  await page.mouse.up();
}

const lit = (page, sel) => page.evaluate((q) => document.querySelector(q).classList.contains('lit'), sel);
// The loudest of a few analyser reads over `ms`, stopping at `enough`.
async function loudest(page, ms, enough) {
  const t0 = Date.now();
  let rms = 0;
  while (Date.now() - t0 < ms) {
    await wait(page, 50);
    rms = Math.max(rms, await level(page));
    if (rms > enough) break;
  }
  return { rms, ms: Date.now() - t0 };
}

async function labChecks(browser) {
  const r = {};
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('console', (m) => report.logs.push(`lab ${m.type()}: ${m.text()}`));
  page.on('pageerror', (e) => report.logs.push(`lab pageerror: ${e.message}`));
  await page.goto(`${url}?lab`);
  r.help_shown = await page.evaluate(() => !document.querySelector('[data-lab]').hidden &&
    document.querySelector('[data-lab-off]').hidden);
  await page.click('#power-on');
  await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  await wait(page, 300);
  r.lab = await page.evaluate(() => window.fm1.lab);
  r.silent_rms = await level(page);
  await press(page, 12);                                        // PLAY/STOP: the demo pattern
  const demo = await loudest(page, 1000, 0.01);
  r.demo_rms = demo.rms;
  r.demo_ms = demo.ms;
  await wait(page, 100);
  r.play_led = await lit(page, '[data-button="12"]');
  r.seq_status = await page.evaluate(() => window.fm1.seq);
  r.status = await page.textContent('#status');
  await press(page, 11);                                        // SEQ: the Track view
  await wait(page, 400);
  r.mode = await page.evaluate(() => window.fm1.state.mode);
  r.seq_led = await lit(page, '[data-button="11"]');
  // The white keys follow the playhead: their lights change within a beat.
  const whites = () => page.evaluate(() => [...document.querySelectorAll('.key.white')]
    .map((k) => (k.classList.contains('lit') ? '1' : '0')).join(''));
  const k0 = await whites();
  await wait(page, 260);
  r.white_keys = [k0, await whites()];
  await tftPng(page, 'tft-07-seq-track.png');
  await page.screenshot({ path: join(out, '08-lab-seq.png') });
  // Space is PLAY/STOP when no button has focus (a focused one, Space
  // presses, as Enter does).
  const unfocus = (p) => p.evaluate(() => document.activeElement && document.activeElement.blur &&
    document.activeElement.blur());
  await unfocus(page);
  await page.keyboard.press('Space');                           // Space: stop
  await wait(page, 300);
  r.play_led_after_space = await lit(page, '[data-button="12"]');
  r.playing_after_space = await page.evaluate(() => window.fm1.seq && window.fm1.seq.playing);
  await unfocus(page);
  await page.keyboard.press('Space');                           // and play again
  await wait(page, 300);
  r.playing_after_second_space = await page.evaluate(() => window.fm1.seq && window.fm1.seq.playing);
  await press(page, 8);                                         // HOME leaves SEQ mode
  await wait(page, 200);
  r.mode_after_home = await page.evaluate(() => window.fm1.state.mode);
  // Modulation (docs/16 MG3): LFO opens RACK at LFO1 and lights.
  await press(page, 5);
  await wait(page, 300);
  r.mod_rack_mode = await page.evaluate(() => window.fm1.state.mode);
  r.mod_lfo_led = await lit(page, '[data-button="5"]');
  await tftPng(page, 'tft-12-mod-rack.png');
  // HOME, then the gesture as a mouse can make it: LFO focused and held with
  // Enter while the wheel turns KNOB3 (Timbre). A turn while held makes a
  // cable, so the release opens nothing: HOME stays.
  await press(page, 8);
  await wait(page, 200);
  await page.focus('[data-button="5"]');
  await page.keyboard.down('Enter');
  await wheel(page, '[data-encoder="5"]', 20);
  await wait(page, 100);
  await tftPng(page, 'tft-13-mod-gesture.png');
  await page.keyboard.up('Enter');
  await wait(page, 300);
  r.mod_mode_after_gesture = await page.evaluate(() => window.fm1.state.mode);
  await tftPng(page, 'tft-14-mod-routed.png');
  await press(page, 6);                                         // EDIT: MATRIX
  await wait(page, 300);
  r.mod_matrix_mode = await page.evaluate(() => window.fm1.state.mode);
  r.mod_edit_led = await lit(page, '[data-button="6"]');
  await tftPng(page, 'tft-15-mod-matrix.png');
  await page.screenshot({ path: join(out, '09-lab-mod-matrix.png') });
  await press(page, 8);                                         // HOME again
  await wait(page, 200);
  // Step entry: SEQ, stop, A#3 (OP3) to bar 2, steps 1, 5, 9 and 13 there
  // from the computer's step keys (1, 5, C, M); stopped, exactly those
  // four white keys light. Played, the pattern sounds and the lights move.
  await press(page, 11);
  await wait(page, 200);
  await unfocus(page);
  await page.keyboard.press('Space');
  await wait(page, 200);
  await pressKey(page, 5);
  await wait(page, 150);
  for (const code of ['Digit1', 'Digit5', 'KeyC', 'KeyM']) {
    await page.keyboard.press(code);
    await wait(page, 120);
  }
  await wait(page, 250);
  r.step_keys = await whites();
  await tftPng(page, 'tft-08-seq-steps.png');
  await unfocus(page);
  await page.keyboard.press('Space');
  r.steps_rms = (await loudest(page, 1000, 0.01)).rms;
  const seen = new Set([await whites()]);
  for (let i = 0; i < 40 && seen.size < 3; ++i) {
    await wait(page, 150);
    seen.add(await whites());
  }
  r.step_lights_seen = seen.size;
  // Record and Capture (S5), still playing: REC in SEQ mode overdubs at
  // once and REC again stops; two keys played in HOME are buffered for
  // Capture, so REC blinks slowly (1 s); SHIFT (Shift in SEQ mode) + REC
  // captures them, and REC goes dark.
  const recLit = () => lit(page, '[data-button="13"]');
  const recStates = async (ms) => {
    const states = new Set();
    for (let t = 0; t < ms; t += 100) { states.add(await recLit()); await wait(page, 100); }
    return [...states].sort();
  };
  await press(page, 13);
  await wait(page, 300);
  r.recording_after_rec = await page.evaluate(() => window.fm1.seq && window.fm1.seq.recording);
  r.rec_led_recording = await recLit();
  await press(page, 13);
  await wait(page, 300);
  r.recording_after_second_rec = await page.evaluate(() => window.fm1.seq && window.fm1.seq.recording);
  await press(page, 8);                                         // HOME: the keys play notes
  await wait(page, 150);
  await pressKey(page, 9);
  await wait(page, 150);
  await pressKey(page, 12);
  r.rec_led_buffered = await recStates(1300);
  await press(page, 11);                                        // SEQ, then Shift + REC
  await wait(page, 150);
  await unfocus(page);
  await page.keyboard.down('Shift');
  await press(page, 13);
  await page.keyboard.up('Shift');
  await wait(page, 200);
  r.rec_led_captured = await recStates(1300);
  await tftPng(page, 'tft-09-seq-captured.png');
  // Tracks (S6): SEQ held with white key 2 focuses track 2, and the core's
  // watched track follows (the toast names it).
  await page.evaluate((m) => { for (const x of m) window.fm1.node.port.postMessage(x); }, [
    { type: 'button', button: 11, down: true }, { type: 'key', key: 2, down: true, velocity: 100 },
    { type: 'key', key: 2, down: false }, { type: 'button', button: 11, down: false }]);
  await wait(page, 300);
  r.focus_watch = await page.evaluate(() => window.fm1.seq && window.fm1.seq.watch_track);
  await tftPng(page, 'tft-11-seq-track-2.png');
  await page.close();

  // Multi-sound (docs/15 §3.16): SEL held as SHIFT while PRESETS turns makes
  // Sound 2 current and the Sound dropdown follows it; choosing Shapes there
  // loads it into Sound 2; with Sound 1's level at 0 on the Mix page (FX,
  // SELECT back from M1, KNOB1 down), a held key still sounds: it plays
  // Sound 2.
  const multi = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  multi.on('pageerror', (e) => report.logs.push(`multi pageerror: ${e.message}`));
  await multi.goto(`${url}?lab`);
  await multi.click('#power-on');
  await multi.waitForFunction(() => window.fm1 && window.fm1.state && window.fm1.screens > 0, null,
    { timeout: 20000 });
  await wait(multi, 300);
  const panel = (msgs) => multi.evaluate((m) => { for (const x of m) window.fm1.node.port.postMessage(x); }, msgs);
  await panel([{ type: 'button', button: 3, down: true }, { type: 'encoder', encoder: 1, delta: 1 },
    { type: 'button', button: 3, down: false }]);
  await wait(multi, 300);
  r.multi_sound = await multi.evaluate(() => window.fm1.state.sound);
  r.multi_label = await multi.textContent('label[for="sel-sound"]');
  const shapes = await multi.evaluate(() => window.fm1.catalog.findIndex((e) => e.id === 'shapes'));
  await multi.selectOption('#sel-sound', String(shapes));
  await wait(multi, 300);
  r.multi_units = await multi.evaluate(() => window.fm1.state.units);
  r.multi_shapes = shapes;
  await panel([{ type: 'button', button: 2, down: true }, { type: 'button', button: 2, down: false },
    { type: 'encoder', encoder: 0, delta: -1 }, { type: 'encoder', encoder: 3, delta: -64 },
    { type: 'encoder', encoder: 3, delta: -64 }]);
  await wait(multi, 200);
  await tftPng(multi, 'tft-09-multi-mix.png');
  await panel([{ type: 'button', button: 8, down: true }, { type: 'button', button: 8, down: false }]);
  r.multi_quiet_rms = (await loudest(multi, 300, 1)).rms;
  await multi.locator('[data-key="12"]').scrollIntoViewIfNeeded();
  const kb = await multi.locator('[data-key="12"]').boundingBox();
  await multi.mouse.move(kb.x + kb.width / 2, kb.y + kb.height / 2);
  await multi.mouse.down();
  r.multi_rms = (await loudest(multi, 1000, 0.01)).rms;
  await tftPng(multi, 'tft-10-multi-sound-2.png');
  await multi.mouse.up();
  await multi.close();

  const hash = await browser.newPage();
  await hash.goto(`${url}#lab`);
  r.hash_lab = await hash.evaluate(() => window.fm1.lab);
  await hash.close();

  // Without the switch: Space sends nothing; PLAY/STOP, SEQ and REC stay stubs.
  const off = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  off.on('pageerror', (e) => report.logs.push(`lab-off pageerror: ${e.message}`));
  await off.goto(url);
  await off.click('#power-on');
  await off.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
  await spy(off);
  await unfocus(off);
  await off.keyboard.press('Space');
  await wait(off, 150);
  r.off_space_messages = (await sent(off)).filter((m) => m.type === 'button').length;
  await press(off, 12);
  await press(off, 11);
  await press(off, 13);
  await press(off, 5);                                          // LFO: a stub too
  const quiet = await loudest(off, 600, 1);
  r.off_rms = quiet.rms;
  r.off_mode = await off.evaluate(() => window.fm1.state.mode);
  r.off_play_led = await lit(off, '[data-button="12"]');
  r.off_rec_led = await lit(off, '[data-button="13"]');
  r.off_seq_status = await off.evaluate(() => window.fm1.seq);
  r.off_help_hidden = await off.evaluate(() => document.querySelector('[data-lab]').hidden);
  await off.close();

  r.pass = r.help_shown && r.lab === true && r.demo_rms > 0.01 && r.demo_ms <= 1100 && r.play_led &&
    r.seq_status && r.seq_status.playing && r.seq_status.bpm_x100 === 12000 && /120\.00 BPM, playing/.test(r.status) &&
    r.mode === 3 && r.seq_led && r.white_keys[0] !== r.white_keys[1] && r.white_keys.every((k) => k.includes('1')) &&
    r.play_led_after_space === false && r.playing_after_space === false && r.playing_after_second_space === true &&
    r.mode_after_home === 0 && r.hash_lab === true &&
    r.step_keys === '1000100010001000' && r.steps_rms > 0.01 && r.step_lights_seen >= 3 &&
    r.recording_after_rec === true && r.rec_led_recording === true && r.recording_after_second_rec === false &&
    r.rec_led_buffered.length === 2 && r.rec_led_captured.length === 1 && r.rec_led_captured[0] === false &&
    r.focus_watch === 1 &&
    r.mod_rack_mode === 4 && r.mod_lfo_led && r.mod_mode_after_gesture === 0 && r.mod_matrix_mode === 5 &&
    r.mod_edit_led &&
    r.off_space_messages === 0 && r.off_rms < 0.001 && r.off_mode === 0 && r.off_play_led === false && r.off_rec_led === false &&
    r.off_seq_status === null && r.off_help_hidden === true &&
    r.multi_sound === 1 && r.multi_label === 'Sound 2 (PRESETS)' && r.multi_units[0] === r.multi_shapes &&
    r.multi_quiet_rms < 0.001 && r.multi_rms > 0.01;
  return r;
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
  report.checks.lab = await labChecks(browser);

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

  report.checks.publishing = await publishingChecks(browser);
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
  c.lab && c.lab.pass &&
  c.publishing && c.publishing.pass &&
  !report.logs.some((l) => l.startsWith('error') || l.includes('pageerror'));
writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, browser: report.browser, ...c, error: report.error }, null, 0));
process.exit(report.pass ? 0 : 1);
