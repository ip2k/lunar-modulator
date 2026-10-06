// readme-screenshots.mjs -- the pictures for the README and the manual: the
// page and its front panel, the firmware's screen for every sound engine, an
// effect page, a parameter page with turned knobs, the sequencer's Track view,
// the modulation matrix, the phone layout, and a figure of the parity result.
// Runs in the Playwright container on the build host after
// screenshot.mjs (build-on-aeon.sh --readme-screenshots), never on the Mac:
//
//   node readme-screenshots.mjs WWW_DIR OUT_DIR PARITY_DIR
//
// PARITY_DIR is build/parity from build.sh: the native renders and the
// browser module's own render (app.wav) of each scenario. Screens are the
// firmware's 240 x 240 frame buffer doubled pixel for pixel (480 x 480).
// Every picture is meant to be looked at before it is committed
// (assets/screenshots/README.md). MIT licence.

import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');

const [www, out, parityDir] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8766);
const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const report = { browser: `Chromium ${browser.version()} (Playwright, headless)`, shots: [], logs: [] };

const wait = (page, ms) => page.waitForTimeout(ms);
const save = (name, data) => {
  writeFileSync(join(out, name), Buffer.from(data.split(',')[1], 'base64'));
  report.shots.push(name);
};

// The firmware's screen, each pixel doubled (no smoothing).
async function screen2x(page, name) {
  save(name, await page.evaluate(() => {
    const src = document.getElementById('tft');
    const c = document.createElement('canvas');
    c.width = 480;
    c.height = 480;
    const g = c.getContext('2d');
    g.imageSmoothingEnabled = false;
    g.drawImage(src, 0, 0, 480, 480);
    return c.toDataURL('image/png');
  }));
}

async function powerOn(page) {
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  await page.click('#power-on');
  await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0 && window.fm1.catalog, null,
    { timeout: 20000 });
  await wait(page, 300);
}

const indexOf = (page, id) => page.evaluate((i) => window.fm1.catalog.find((e) => e.id === i).index, id);
async function choose(page, select, id) {
  await page.selectOption(select, id === null ? '-1' : String(await indexOf(page, id)));
  await wait(page, 100);
}
// A parameter of a unit (0 the sound, 1-2 the effect slots), as MIDI or a
// preset would set it: no popup.
const setParam = (page, unit, index, value) => page.evaluate(([u, i, v]) => {
  window.fm1.node.port.postMessage({ type: 'param', unit: u, index: i, value: v });
}, [unit, index, value]);
const midi = (page, notes, on) => page.evaluate(([ns, down]) => {
  for (const note of ns) {
    window.fm1.node.port.postMessage(down ? { type: 'note-on', note, velocity: 120 } : { type: 'note-off', note });
  }
}, [notes, on]);
async function hold(page, codes) { for (const k of codes) await page.keyboard.down(k); }
async function release(page, codes) { for (const k of codes) await page.keyboard.up(k); }
async function wheel(page, selector, ticks) {
  await page.locator(selector).scrollIntoViewIfNeeded();
  const box = await page.locator(selector).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < Math.abs(ticks); ++i) {
    await page.mouse.wheel(0, ticks > 0 ? -100 : 100);
    await wait(page, 30);
  }
}
async function press(page, button) {
  await page.locator(`[data-button="${button}"]`).scrollIntoViewIfNeeded();
  const box = await page.locator(`[data-button="${button}"]`).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await wait(page, 60);
  await page.mouse.up();
}

// C4, E4, G4 on the computer keyboard (F3 is A).
const CHORD = ['KeyG', 'KeyJ', 'KeyL'];
// C4, D#4, G4: C minor, the demo pattern's key.
const MINOR = ['KeyG', 'KeyU', 'KeyL'];

// The firmware's own buttons and encoders (fm1_panel.h), as the panel sends
// them: a gesture that holds one button while an encoder turns.
const BTN = { FX: 2, LFO: 5, EDIT: 6, HOME: 8, SEQ: 11, PLAY: 12, REC: 13 };
const ENC_KNOB3 = 5;
const post = (page, msg) => page.evaluate((m) => window.fm1.node.port.postMessage(m), msg);
async function tap(page, button) {
  await post(page, { type: 'button', button, down: true });
  await wait(page, 60);
  await post(page, { type: 'button', button, down: false });
}
// Hold LFO and turn KNOB3 `clicks` detents: a cable from LFO1 to the page's
// third parameter at `clicks` %, as chapter 8's gesture makes it.
async function lfoCable(page, clicks) {
  await post(page, { type: 'button', button: BTN.LFO, down: true });
  await wait(page, 60);
  for (let i = 0; i < clicks; ++i) await post(page, { type: 'encoder', encoder: ENC_KNOB3, delta: 1 });
  await wait(page, 60);
  await post(page, { type: 'button', button: BTN.LFO, down: false });
}
// REC's light over `ms`: a picture must not catch it blinking for notes that
// Capture holds (chapter 7), which would read as a fault.
async function recLit(page, ms) {
  const seen = [];
  for (let t = 0; t <= ms; t += 150) {
    seen.push(await page.evaluate((b) => document.querySelector(`[data-button="${b}"]`).classList.contains('lit'),
      BTN.REC));
    await wait(page, 150);
  }
  return seen.some(Boolean);
}
// Starting or stopping the transport empties Capture, so held notes no longer
// wait to be kept.
async function emptyCapture(page, keepPlaying) {
  await tap(page, BTN.PLAY);
  await wait(page, 120);
  if (!keepPlaying) await tap(page, BTN.PLAY);
}

// ---- the parity figure ------------------------------------------------------
function readWav(path) {
  const b = readFileSync(path);
  return new Int16Array(b.buffer.slice(b.byteOffset + 44, b.byteOffset + b.length));
}
function differing(a, b) {
  if (a.length !== b.length) return Math.max(a.length, b.length);
  let n = 0;
  for (let i = 0; i < a.length; ++i) if (a[i] !== b[i]) ++n;
  return n;
}

async function parityFigure(scenario, rate) {
  // The caption describes this scenario; refuse to draw it over another one.
  const scenarios = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'scenarios.json'), 'utf8'));
  const sc = scenarios.scenarios.find((x) => x.name === scenario);
  const described = sc && sc.engine === 'sixop' && sc.params.join() === 'Patch=32' &&
    sc.notes.map((n) => n.split(':')[1]).join() === '60,64,67' &&
    sc.fx.length === 1 && sc.fx[0][0] === 'ensemble' && (sc.rate ?? 44118) === rate;
  if (!described) throw new Error(`parity figure: ${scenario} is not the scenario its caption describes`);
  const dir = join(parityDir, scenario);
  const app = readWav(join(dir, 'app.wav'));
  const glibc = readWav(join(dir, 'glibc.wav'));
  const musl = readWav(join(dir, 'musl.wav'));
  const js = readWav(join(dir, 'js.wav'));
  const start = Math.round(0.2 * rate), frames = Math.round(0.025 * rate);
  const left = (w) => Array.from({ length: frames }, (_, i) => w[2 * (start + i)]);
  const data = {
    native: left(glibc), browser: left(app),
    total: app.length, frames, rate,
    vsGlibc: differing(app, glibc), vsMusl: differing(app, musl), vsJs: differing(app, js),
  };
  // Its own page at twice the pixels, with the page's fonts and palette.
  const page = await browser.newPage({ viewport: { width: 1000, height: 600 }, deviceScaleFactor: 2 });
  await page.goto(url);
  const fig = await page.evaluate(async (d) => {
    await document.fonts.load('400 26px Audiowide');
    document.body.innerHTML = '<canvas id="fig"></canvas>';
    const W = 1000, H = 556, PAD = 32;
    const css = getComputedStyle(document.documentElement);
    const v = (n) => css.getPropertyValue(n).trim();
    const c = document.getElementById('fig');
    const dpr = window.devicePixelRatio;
    c.width = W * dpr;
    c.height = H * dpr;
    c.style.width = `${W}px`;
    c.style.height = `${H}px`;
    c.style.display = 'block';
    const g = c.getContext('2d');
    g.scale(dpr, dpr);
    g.fillStyle = v('--rp-base');
    g.fillRect(0, 0, W, H);
    const small = '"Exo 2", system-ui, sans-serif';
    const n = (x) => x.toLocaleString('en');
    const boxes = [];
    const text = (s, x, y, font, color, align = 'left') => {
      g.font = font;
      g.fillStyle = color;
      g.textAlign = align;
      g.textBaseline = 'alphabetic';
      g.fillText(s, x, y);
      const m = g.measureText(s);
      const x0 = align === 'right' ? x - m.width : x;
      boxes.push({ s, x0, x1: x0 + m.width, y0: y - m.actualBoundingBoxAscent, y1: y + m.actualBoundingBoxDescent });
    };

    text('Same samples in the browser', PAD, PAD + 26, '400 26px Audiowide', v('--rp-text'));
    text(`Six-Op FM, E.PIANO 1, a C major chord through Ensemble at ${n(d.rate)} Hz. ` +
      `25 ms of the left channel, from 0.20 s.`, PAD, PAD + 58, `400 15px ${small}`, v('--rp-subtle'));

    const peak = Math.max(1, ...d.native.map(Math.abs), ...d.browser.map(Math.abs));
    const plotW = W - 2 * PAD;
    const lane = (y, h, samples, scale, color) => {
      g.fillStyle = v('--rp-surface');
      g.fillRect(PAD, y, plotW, h);
      g.strokeStyle = v('--rp-highlight-med');
      g.lineWidth = 1;
      g.beginPath();
      g.moveTo(PAD, y + h / 2 + 0.5);
      g.lineTo(PAD + plotW, y + h / 2 + 0.5);
      g.stroke();
      g.strokeStyle = color;
      g.lineWidth = 1.6;
      g.beginPath();
      samples.forEach((s, i) => {
        const px = PAD + (i / (samples.length - 1)) * plotW;
        const py = y + h / 2 - (s / scale) * (h / 2 - 6);
        if (i) g.lineTo(px, py); else g.moveTo(px, py);
      });
      g.stroke();
    };

    let y = PAD + 100;
    text('Native: fm1-render, GCC and glibc', PAD, y, `600 15px ${small}`, v('--rp-foam'));
    lane(y + 12, 96, d.native, peak, v('--rp-foam'));
    y += 144;
    text('Browser: fm1.wasm, the page\'s own module', PAD, y, `600 15px ${small}`, v('--rp-iris'));
    lane(y + 12, 96, d.browser, peak, v('--rp-iris'));
    y += 144;
    const diff = d.browser.map((s, i) => s - d.native[i]);
    text('Difference, at ±4 LSB full scale', PAD, y, `600 15px ${small}`, v('--rp-love'));
    text(`${n(d.vsGlibc)} of ${n(d.total)} samples differ, whole render, both channels`,
      W - PAD, y, `600 15px ${small}`, v('--rp-text'), 'right');
    lane(y + 12, 56, diff, 4, v('--rp-love'));
    y += 56 + 12 + 34;
    text(`Also ${n(d.vsMusl)} against GCC with musl and ${n(d.vsJs)} against fm1-render compiled to ` +
      'WebAssembly. Source: sim/web/test/parity.mjs.', PAD, y, `400 14px ${small}`, v('--rp-subtle'));

    // Any two text runs closer than 4 px, or one off the figure?
    const faults = [];
    boxes.forEach((a, i) => {
      if (a.x0 < 0 || a.x1 > W || a.y0 < 0 || a.y1 > H) faults.push(`off: ${a.s}`);
      boxes.slice(i + 1).forEach((b) => {
        if (a.x0 < b.x1 + 4 && b.x0 < a.x1 + 4 && a.y0 < b.y1 + 4 && b.y0 < a.y1 + 4) faults.push(`${a.s} / ${b.s}`);
      });
    });
    return { faults, bottom: y };
  }, data);
  await page.locator('#fig').screenshot({ path: join(out, 'parity.png') });
  report.shots.push('parity.png');
  await page.close();
  return { ...fig, vs_glibc: data.vsGlibc, vs_musl: data.vsMusl, vs_js: data.vsJs, samples: data.total };
}

try {
  // ---- desktop: the engines, an effect page, a parameter page --------------
  const page = await browser.newPage({ viewport: { width: 1440, height: 1300 } });
  page.on('console', (m) => report.logs.push(`${m.type()}: ${m.text()}`));
  page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
  await powerOn(page);
  report.rec_lit = {};

  // Every sound engine's home page while it sounds.
  const engines = [
    { id: 'macro', file: 'screen-macro.png', param: [0, 4] },
    { id: 'shapes', file: 'screen-shapes.png', param: [0, 28], after: 120 },
    { id: 'macro-heavy', file: 'screen-macro-heavy.png', param: [0, 0] },
    { id: 'sixop', file: 'screen-sixop.png', param: [0, 32] },
    { id: 'dx7', file: 'screen-fm6.png', param: [0, 0] },   // FM6 on TINE EP (2026-10-06)
    // A kick wants a low note, as the sophie-kit scenario plays it (MIDI 36).
    { id: 'sw-sophie', file: 'screen-sophie.png', param: [0, 0], midi: [36], after: 50 },
    { id: 'drums', file: 'screen-drums.png', param: [0, 0], midi: [36], after: 50 },
  ];
  for (const e of engines) {
    await choose(page, '#sel-sound', e.id);
    await setParam(page, 0, ...e.param);
    await wait(page, 1200);
    if (e.midi) await midi(page, e.midi, true); else await hold(page, CHORD);
    await wait(page, e.after || 350);
    await screen2x(page, e.file);
    if (e.midi) await midi(page, e.midi, false); else await release(page, CHORD);
    await wait(page, 200);
  }

  // FX mode: Plate in M1, PSX Verb in M2, M2's first page. FX mode opens
  // on M1; SELECT walks Plate's two pages (its knobs, then Freeze) first.
  await choose(page, '#sel-sound', 'macro');
  await setParam(page, 0, 0, 4);
  await choose(page, '#sel-fx2', 'sw-psxverb');
  await press(page, 2);                                   // FX
  await wait(page, 150);
  await wheel(page, '[data-encoder="0"]', 2);             // SELECT: past Freeze to M2
  await wait(page, 1200);
  await hold(page, CHORD);
  await wait(page, 350);
  await screen2x(page, 'screen-fx.png');
  await release(page, CHORD);
  await press(page, 8);                                   // HOME
  await wait(page, 200);

  // A parameter page with the knobs turned: Macro's first page.
  await wheel(page, '[data-encoder="3"]', 2);             // KNOB1: Model, VA Pair -> 2-op FM
  await wheel(page, '[data-encoder="4"]', 18);            // KNOB2: Harmonics 0.50 -> 0.68
  await wheel(page, '[data-encoder="5"]', -22);           // KNOB3: Timbre 0.50 -> 0.28
  await wheel(page, '[data-encoder="6"]', 31);            // KNOB4: Morph 0.50 -> 0.81
  await page.mouse.move(5, 5);
  await wait(page, 1200);
  await hold(page, CHORD);
  await wait(page, 350);
  await emptyCapture(page, false);                        // REC stays dark
  await wait(page, 900);
  report.rec_lit.panel_params = await recLit(page, 600);
  await screen2x(page, 'screen-params.png');
  // The screen with KNOB1-4 and the buttons beside it, as on the panel.
  const clip = await page.evaluate(() => {
    const r = document.getElementById('panel').getBoundingClientRect();
    const mm = r.width / 167.5;
    const x = (v) => r.left + (v + 3) * mm, y = (v) => r.top + (v + 8) * mm;
    return { x: x(41), y: y(3), width: (159.5 - 41) * mm, height: (48.5 - 3) * mm };
  });
  await page.screenshot({ path: join(out, 'panel-params.png'), clip });
  report.shots.push('panel-params.png');
  await release(page, CHORD);
  report.values = await page.evaluate(() => window.fm1.state);
  await page.close();

  // ---- desktop: the page, the sequencer, modulation ---------------------------
  // The README's picture: Macro on VA Pair through Plate, LFO1 cabled to
  // Timbre (the page marks it), a C minor chord held while the demo pattern
  // plays. The chord goes down first and PLAY/STOP after it, so Capture holds
  // nothing and REC stays dark.
  const hero = await browser.newPage({ viewport: { width: 1440, height: 1300 } });
  hero.on('console', (m) => report.logs.push(`${m.type()}: ${m.text()}`));
  hero.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
  await powerOn(hero);
  await setParam(hero, 0, 0, 4);
  await choose(hero, '#sel-fx1', 'plate');
  await lfoCable(hero, 40);
  await wait(hero, 1300);                                 // the cable's popup goes
  await hold(hero, MINOR);
  await wait(hero, 150);
  await emptyCapture(hero, true);
  await wait(hero, 600);
  report.rec_lit.hero = await recLit(hero, 900);
  const bottom = await hero.evaluate(() => document.querySelector('.device-wrap').getBoundingClientRect().bottom);
  await hero.screenshot({ path: join(out, 'virtual-fm1.png'), clip: { x: 0, y: 0, width: 1440, height: Math.ceil(bottom) + 16 } });
  report.shots.push('virtual-fm1.png');
  await release(hero, MINOR);
  await wait(hero, 200);

  // SEQ mode's Track view while the demo pattern plays.
  await tap(hero, BTN.SEQ);
  await wait(hero, 1700);
  await screen2x(hero, 'screen-seq.png');
  await tap(hero, BTN.HOME);
  await tap(hero, BTN.PLAY);
  await wait(hero, 300);

  // The matrix: the default rack's two cables and LFO1's.
  await tap(hero, BTN.EDIT);
  await wait(hero, 2400);                                 // past the hint line's two seconds
  await screen2x(hero, 'screen-matrix.png');
  await tap(hero, BTN.EDIT);
  await hero.close();

  report.parity = await parityFigure('sixop-epiano', 44118);

  // ---- a phone ----------------------------------------------------------------
  // The README's picture's state, at a phone's width.
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  phone.on('pageerror', (e) => report.logs.push(`phone pageerror: ${e.message}`));
  await powerOn(phone);
  await setParam(phone, 0, 0, 4);
  await lfoCable(phone, 40);
  await wait(phone, 1300);
  await hold(phone, MINOR);
  await wait(phone, 150);
  await emptyCapture(phone, true);
  await wait(phone, 600);
  report.rec_lit.phone = await recLit(phone, 900);
  // The first screenful, down to the hint under the panel.
  const hint = await phone.evaluate(() => document.querySelector('.narrow-hint').getBoundingClientRect().bottom);
  await phone.screenshot({ path: join(out, 'phone.png'), clip: { x: 0, y: 0, width: 390, height: Math.min(844, Math.ceil(hint) + 16) } });
  report.shots.push('phone.png');
  await release(phone, MINOR);
  report.phone_scroll_width = await phone.evaluate(() => document.documentElement.scrollWidth);
  await phone.close();
} catch (err) {
  report.error = String(err && err.stack || err);
} finally {
  await browser.close();
  server.close();
}

report.pass = !report.error && report.shots.length === 15 && report.parity && report.parity.faults.length === 0 &&
  report.phone_scroll_width <= 390 && !Object.values(report.rec_lit || {}).some(Boolean) &&
  !report.logs.some((l) => l.startsWith('error') || l.includes('pageerror'));
writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, shots: report.shots, rec_lit: report.rec_lit, parity: report.parity,
  error: report.error }));
process.exit(report.pass ? 0 : 1);
