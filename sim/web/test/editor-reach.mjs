// editor-reach.mjs -- the Advanced editor's reach: keyboard and screen-reader
// passes (§13), the phone layout (§14) and the telemetry ED1 left empty
// (§12), in headless Chromium (stage ED5a, notes/2026-10-06-web-editor.md).
// Runs in the Playwright container on aeon after editor-ui.mjs
// (build-on-aeon.sh), never on the Mac:
//
//   node editor-reach.mjs WWW_DIR OUT_DIR
//
// Checks:
//  - Playwright's accessibility snapshot of the editor in every view (the
//    Flow, a sound, the Modulation view, the library, Memory, A/B): no
//    control without a name, every slider with a value in words, one polite
//    live region and nothing else that announces;
//  - the keyboard: Tab lands in the editor and gives it the keys; every
//    visible control is reachable by Tab (or sits in a group the arrows
//    walk), nothing clickable is out of the tab order; each of the first 40
//    stops shows a 2 px focus ring; targets are 24 px or more;
//  - announcements: a refusal reaches the live region in C's words, and a
//    burst of thirty is at most two updates a second;
//  - phones (375 px): the layouts are two tabs, Panel and Edit; the outline
//    is a row of tabs that scrolls inside itself; the screen card is 96 px;
//    the matrix is a list of cables with each cell named; no Map; no
//    sideways scroll in any view;
//  - telemetry: a Limiter driven hard reads gain reduction on its card
//    ("GR n dB" and a bar), and a per-voice cable shows its voices' values.
// MIT licence, like the rest of this repository.

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';


const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8769);
const { browser, name: browserName } = await launch();
const report = { browser: browserName, checks: {}, logs: [], why: [] };
function check(name, ok, why) {
  report.checks[name] = !!ok;
  if (!ok) report.why.push(`${name}: ${typeof why === 'string' ? why : JSON.stringify(why)}`);
}

const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') report.logs.push(`error: ${m.text()}`); });
await page.goto(`${url}?load=examples/first-orbit.lunar`);
await page.addScriptTag({ path: new URL('./layout-probe.js', import.meta.url).pathname });
await page.waitForTimeout(500);
await page.click('[data-layout="workbench"]');
await page.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 10000 });
await page.click('#power-on');
await page.waitForFunction(() => window.fm1.editor.state.mirror && window.fm1.editor.state.panelView &&
  window.fm1.editor.state.mirror.blocks.size > 6, null, { timeout: 20000 });
await page.click('[data-layout="editor"]');
await page.waitForTimeout(500);

const VIEWS = ['sound', 'flow', 'mod', 'library', 'memory', 'compare'];
async function goView(view) {
  await page.evaluate(async (view) => {
    const ed = window.fm1.editor;
    if (ed.project.searchOpen) ed.project.closeSearch(false);
    const q = (s) => document.querySelector(s).click();
    if (view === 'flow') q('.ed-out-fx');
    else if (view === 'mod') q('.ed-out-mod');
    else if (view === 'library') q('.ed-out-lib');
    else if (view === 'memory') q('.ed-out-mem');
    else if (view === 'compare') q('.ed-out-ab');
    else document.querySelectorAll('.ed-out')[2].click();
    window.scrollTo(0, 0);
    await new Promise((r) => setTimeout(r, 450));
  }, view);
}

// ---- the accessibility snapshot, every view -------------------------------------------------
const INTERACTIVE = new Set(['button', 'checkbox', 'radio', 'slider', 'combobox', 'textbox', 'spinbutton', 'tab', 'link', 'menuitem', 'switch', 'searchbox', 'listbox', 'option']);
function parseSnapshot(text) {
  const nameless = [], sliders = [];
  let live = 0;
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*- (\w+)(?: "((?:[^"\\]|\\.)*)")?(.*)$/);
    if (!m) continue;
    const [, role, name, rest] = m;
    if (INTERACTIVE.has(role) && !(name && name.trim())) nameless.push(line.trim());
    if (role === 'slider') sliders.push({ name, value: rest.replace(/^:\s*/, '') });
    if (role === 'status') ++live;
  }
  return { nameless, sliders, live };
}
const snaps = {};
for (const view of VIEWS) {
  await goView(view);
  const text = await page.locator('.ed').ariaSnapshot();
  const p = parseSnapshot(text);
  snaps[view] = { lines: text.split('\n').length, nameless: p.nameless.slice(0, 6), sliders: p.sliders.length };
  check(`the ${view} view: every control has a name in the accessibility snapshot`, p.nameless.length === 0, p.nameless.slice(0, 6));
  check(`the ${view} view: every slider has a name`, p.sliders.every((s) => s.name), p.sliders.filter((s) => !s.name).slice(0, 4));
}
report.snapshots = snaps;
await goView('sound');
const slideDom = await page.evaluate(() => [...document.querySelectorAll('.ed [role="slider"]')].filter((s) => s.getClientRects().length).map((s) => ({
  text: s.getAttribute('aria-valuetext'), now: s.getAttribute('aria-valuenow'), label: s.getAttribute('aria-labelledby') && document.getElementById(s.getAttribute('aria-labelledby')) ? [...document.getElementById(s.getAttribute('aria-labelledby')).childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim() : '' })));
check('sliders carry aria-valuenow, a valuetext in words and a label', slideDom.length > 3 && slideDom.every((s) => s.text && s.now !== null && s.label.trim() && s.text.startsWith(`${s.label},`)), slideDom.filter((s) => !s.text || !s.label.trim() || !s.text.startsWith(`${s.label},`)).slice(0, 3));
// The status region, and the search box's result count (announced as you type).
const liveRegions = await page.evaluate(() => [...document.querySelectorAll('.ed [aria-live], .ed [role="status"], .ed [role="alert"]')]
  .filter((e) => !e.classList.contains('ed-search-n')).map((e) => `${e.className} ${e.getAttribute('aria-live')} ${e.getAttribute('role')}`));
check('one polite live region in the editor (and the search count), and nothing else announces', liveRegions.length === 1 && /polite/.test(liveRegions[0]), liveRegions);

// ---- the keyboard -------------------------------------------------------------------------
const FOCUSABLE = 'button, input:not([type="hidden"]), select, textarea, [role="slider"], [tabindex], summary, a[href]';
const reach = await page.evaluate((FOCUSABLE) => {
  const bad = [];
  const ed = document.querySelector('.ed');
  for (const el of ed.querySelectorAll(FOCUSABLE)) {
    if (!el.getClientRects().length || el.closest('[hidden], .ed-sr, [aria-hidden="true"]') || el.disabled) continue;
    const roving = el.closest('[role="radiogroup"], [role="tablist"], [role="listbox"], [role="toolbar"], [role="menu"]');
    if (el.tabIndex < 0 && !roving && el.getAttribute('tabindex') === '-1') bad.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} is out of the tab order`);
  }
  // Clickable and not focusable, nor inside anything focusable.
  for (const el of ed.querySelectorAll('*')) {
    if (!el.getClientRects().length || el.closest('[hidden], .ed-sr, [aria-hidden="true"]')) continue;
    if (getComputedStyle(el).cursor !== 'pointer') continue;
    if (el.matches(FOCUSABLE) || el.closest(FOCUSABLE) || el.querySelector(FOCUSABLE) || el.closest('label')) continue;
    bad.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} is clickable but cannot be reached`);
  }
  return bad.slice(0, 8);
}, FOCUSABLE);
check('every visible control is reachable by Tab (or sits in a group the arrows walk)', reach.length === 0, reach);

// Tab from the layout switch into the editor: it gets the keys, and every stop
// shows a ring.
await page.evaluate(() => { document.querySelector('.layout-switch [aria-checked="true"]').focus(); });
await page.evaluate(() => window.fm1.editor.setKeys('play'));
const stops = [];
let entered = null;
for (let i = 0; i < 40; ++i) {
  await page.keyboard.press('Tab');
  const s = await page.evaluate(() => {
    const a = document.activeElement;
    const cs = getComputedStyle(a);
    const r = a.getBoundingClientRect();
    const label = a.closest('label');
    const box = label ? label.getBoundingClientRect() : r;
    return { tag: a.tagName.toLowerCase(), cls: String(a.className).split(' ')[0], inEd: !!a.closest('.ed'), keys: document.querySelector('.ed').dataset.keys,
      outline: cs.outlineStyle, ow: parseFloat(cs.outlineWidth) || 0, shadow: cs.boxShadow !== 'none', w: Math.round(box.width), h: Math.round(box.height),
      type: a.getAttribute('type') };
  });
  stops.push(s);
  if (s.inEd && entered === null) entered = s;
}
const inEd = stops.filter((s) => s.inEd);
check('Tab lands in the editor and gives it the keys', entered && entered.keys === 'edit', entered);
check('the first 40 stops: each shows a ring of 2 px or more', inEd.length > 10 && inEd.every((s) => (s.outline !== 'none' && s.ow >= 2) || s.shadow), inEd.filter((s) => !((s.outline !== 'none' && s.ow >= 2) || s.shadow)).slice(0, 5));
check('the first 40 stops: each target is 24 px or more each way', inEd.every((s) => s.w >= 24 && s.h >= 24), inEd.filter((s) => s.w < 24 || s.h < 24).slice(0, 5));
report.keyboard = { stops: stops.length, inEditor: inEd.length };
await page.keyboard.press('Escape');

// ---- announcements ------------------------------------------------------------------------
const say = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const live = document.querySelector('.ed [aria-live]');
  const n = { v: 0 };
  const mo = new MutationObserver(() => { ++n.v; });
  mo.observe(live, { childList: true, characterData: true, subtree: true });
  // Idle, with the telemetry running: nothing is announced.
  await new Promise((r) => setTimeout(r, 1500));
  const idle = n.v;
  // A refusal C makes reaches the region in its words.
  ed.select('s1', { view: 'sound' });
  await new Promise((r) => setTimeout(r, 300));
  ed.chains.choose('s1', '');
  await new Promise((r) => setTimeout(r, 1200));
  const refusal = live.textContent;
  // A burst of thirty.
  n.v = 0;
  for (let i = 0; i < 30; ++i) { ed.say(`announcement ${i}`); await new Promise((r) => setTimeout(r, 15)); }
  await new Promise((r) => setTimeout(r, 1300));
  mo.disconnect();
  return { idle, refusal, burst: n.v, last: live.textContent, words: ed.meta.refusalWords(8) };
});
report.say = say;
check('nothing is announced while the editor is idle', say.idle === 0, say);
check('a refusal from C reaches the live region in its words', say.refusal && say.refusal.includes(say.words), say);
check('a burst of thirty announcements is at most three updates, the last one kept', say.burst <= 3 && say.last === 'announcement 29', say);

// ---- phones ----------------------------------------------------------------------------------
await page.setViewportSize({ width: 375, height: 812 });
await page.waitForTimeout(300);
const phone = await page.evaluate(() => {
  const vis = (e) => !!e && e.getClientRects().length > 0;
  const radios = [...document.querySelectorAll('#layout-switch [role="radio"]')].filter(vis).map((b) => b.innerText.trim());
  const outline = document.querySelector('.ed-outline');
  const screen = document.querySelector('.ed-screen').getBoundingClientRect();
  const o = outline.getBoundingClientRect();
  return { radios, outlineScrolls: outline.scrollWidth > outline.clientWidth, outlineRow: getComputedStyle(outline).flexDirection,
    outlineTop: Math.round(o.top), screen: [Math.round(screen.width), Math.round(screen.height)], layout: document.body.dataset.layout,
    sw: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth, map: !!document.querySelector('.ed-map, [data-view="map"]') };
});
report.phone = phone;
check('a phone has two tabs, Panel and Edit', phone.radios.length === 2 && phone.radios[0] === 'Panel' && phone.radios[1] === 'Edit', phone);
check('the outline is a row of tabs that scrolls inside itself, not the page', phone.outlineRow === 'row' && phone.outlineScrolls && phone.sw <= phone.vw + 1, phone);
check('the screen card shows a 96 px screen', phone.screen[0] === 96 && phone.screen[1] === 96, phone);
check('no Map on a phone', !phone.map, phone);
// The Workbench, asked for on a phone, is Edit.
const wb = await page.evaluate(async () => { document.querySelector('[data-layout="workbench"]').click(); await new Promise((r) => setTimeout(r, 400)); return document.body.dataset.layout; });
check('the Workbench becomes Edit on a phone', wb === 'editor', wb);
await goView('mod');
const list = await page.evaluate(async () => {
  [...document.querySelectorAll('.ed-btn')].find((b) => b.textContent === 'Add a cable').click();
  await new Promise((r) => setTimeout(r, 700));
  const rows = [...document.querySelectorAll('.ed-mx-r:not(.ed-mx-h):not(.is-empty)')];
  const r0 = rows[0];
  const cs = (e) => getComputedStyle(e);
  return { rows: rows.length, header: cs(document.querySelector('.ed-mx-h')).display, named: r0 ? [...r0.children].map((c) => c.dataset.h || '') : [],
    labelShown: r0 ? getComputedStyle(r0.children[2], '::before').content : '', cols: r0 ? cs(r0).gridTemplateColumns.split(' ').length : 0 };
});
report.cableList = list;
check('the matrix is a list of cables on a phone: no header row, each cell named, two columns', list.rows > 2 && list.header === 'none' &&
  list.named.join() === '#,On,From,VIA,To,Amount,Live,Verdict' && /From/.test(list.labelShown) && list.cols === 2, list);
const sweep = [];
for (const view of VIEWS) {
  await goView(view);
  await page.evaluate(() => { window.scrollTo(0, 0); });
  const bad = await page.evaluate(() => window.lunarLayoutProbe ? window.lunarLayoutProbe() : ['no probe']);
  sweep.push([view, bad.length]);
  if (bad.length) report.why.push(`phone ${view}: ${JSON.stringify(bad.slice(0, 4))}`);
}
check('every view at 375 px is clean: no sideways scroll, nothing clipped or overlapping', sweep.every(([, n]) => n === 0), sweep);
await goView('mod');
await page.locator('.ed-matrix').scrollIntoViewIfNeeded();
await page.screenshot({ path: join(out, 'ed5a-phone-matrix-375.png') });
await goView('flow');
await page.screenshot({ path: join(out, 'ed5a-phone-flow-375.png') });
await page.setViewportSize({ width: 1440, height: 1000 });
await page.waitForTimeout(300);

// ---- telemetry: gain reduction and per-voice values ------------------------------------------
await page.evaluate(() => window.fm1.editor.setKeys('play'));
await goView('flow');
const gr = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  const k = ed.state.mirror.current;
  const key = `s${k + 1}.in1`;
  ed.chains.choose(key, 'limit');
  await w(800);
  ed.select(key, { view: 'flow' });
  await w(500);
  const drive = [...document.querySelectorAll('.ed-flow-insp .ed-row')].find((r) => /Drive/.test(r.textContent));
  const field = drive && drive.querySelector('.ed-val');
  if (!field) return { error: 'no Drive row', rows: [...document.querySelectorAll('.ed-flow-insp .ed-label')].map((l) => l.textContent) };
  return { key, k, rowReady: true };
});
report.gr = gr;
if (gr.rowReady) {
  // By the keyboard: focus the Drive slider and press End.
  const slider = page.locator('.ed-flow-insp .ed-row', { hasText: 'Drive' }).locator('[role="slider"]').first();
  await slider.focus();
  await slider.press('End');
  await page.waitForTimeout(300);
  await page.evaluate(() => window.fm1.editor.setKeys('play'));
  await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'note-on', note: 60, velocity: 127 }));
  const seen = await page.evaluate(async () => {
    let text = '', bar = 0;
    for (let i = 0; i < 60 && !text; ++i) {
      await new Promise((r) => setTimeout(r, 100));
      const m = document.querySelector('.ed-flow-insp [data-red]');
      const g = document.querySelector('.ed-flow-insp [data-gr]');
      text = m ? m.textContent : '';
      bar = g ? Number(g.style.getPropertyValue('--gr')) : 0;
    }
    return { text, bar };
  });
  await page.locator('.ed-flow-insp').screenshot({ path: join(out, 'ed5a-limiter-gr.png') });
  await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'note-off', note: 60 }));
  report.gr.seen = seen;
  check('a Limiter driven hard shows its gain reduction ("GR n dB" and a bar) on its card', /^GR \d/.test(seen.text) && seen.bar > 0, seen);
}
// A per-voice cable: the example's cable 2 (ENV into S3 Timbre, per voice).
await page.evaluate(async () => {
  const ed = window.fm1.editor;
  document.querySelector('.ed-out-mix, .ed-out-fx').click();
  await new Promise((r) => setTimeout(r, 400));
  const cur = [...document.querySelectorAll('.ed-cur')];
  if (cur[2]) cur[2].click();                                // Make S3 current
  await new Promise((r) => setTimeout(r, 600));
  document.querySelector('.ed-out-mod').click();
  await new Promise((r) => setTimeout(r, 500));
});
await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'note-on', note: 64, velocity: 100 }));
const vd = await page.evaluate(async () => {
  const rows = [...document.querySelectorAll('.ed-mx-r:not(.ed-mx-h)')];
  const voiceRows = rows.filter((r) => r.querySelector('.ed-mx-n') && /v/.test(r.querySelector('.ed-mx-n').textContent) && r.querySelector('[data-dest]'));
  let seen = null;
  for (let i = 0; i < 40 && !seen; ++i) {
    await new Promise((r) => setTimeout(r, 100));
    for (const r of voiceRows) { const t = r.querySelector('[data-dest]').textContent; if (t && t !== '–') { seen = { text: t, title: r.querySelector('[data-dest]').title }; break; } }
  }
  return { voiceRows: voiceRows.length, seen };
});
await page.locator('.ed-matrix').screenshot({ path: join(out, 'ed5a-voice-dests.png') });
await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'note-off', note: 64 }));
report.voiceDests = vd;
check('a per-voice cable shows its voices\' value in the live column while a note sounds', vd.voiceRows >= 1 && vd.seen && /\d/.test(vd.seen.text) && /voice/.test(vd.seen.title), vd);

report.logs = report.logs.filter((l) => !/AudioContext was not allowed/.test(l));
check('no page errors', report.logs.length === 0, report.logs);
report.pass = Object.values(report.checks).every(Boolean);
writeFileSync(join(out, 'editor-reach.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, why: report.why }));
await browser.close();
server.close();
process.exit(report.pass ? 0 : 1);
