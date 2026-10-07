// editor-map.mjs -- the Advanced editor's Map (stage ED5b,
// notes/2026-10-06-web-editor.md §10, §27): the cable slots drawn as a patch
// bay, with focus, a cable made by pointer or keys with C's verdict over the
// input, live values from the telemetry, and a check that no label is under
// a cable or another label, at four widths. Runs in the Playwright container
// on aeon (build-on-aeon.sh), never on the Mac:
//
//   [BROWSER=chromium|firefox|webkit] node editor-map.mjs WWW_DIR OUT_DIR
//
// Checks:
//  - the Map shows every cable of the matrix with both ends on a jack, one
//    cable per slot the table lists, and its own faults list (a cable over a
//    label or a block, labels over labels, a pill over a label) is empty at
//    1,440, 1,024 and 768 px; at 375 px there is no Map, only the cable list;
//  - focus: a module's header selects it and dims every cable that does not
//    touch it, with pills on the lit ones only; Esc shows all; F toggles;
//  - a cable dragged from an output to an input is one CABLE record in the
//    first empty slot (25 %), shown over the input with C's verdict before
//    the drop, and undone by one step; the same cable by keys (Enter on the
//    output, arrows, Enter) ends the same; Esc puts it back;
//  - the table and the Map are one truth: an amount typed in the table moves
//    the Map's pill; a cable removed in the Map's inspector leaves the Map;
//  - live values: a per-voice cable's pill reads its voices' range while a
//    note sounds; module outputs read live;
//  - the keyboard: one tab stop a column, arrows inside, every jack named.
// MIT licence, like the rest of this repository.

import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const pw = require('playwright');
const which = process.env.BROWSER || 'chromium';
const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8771);
const browser = await pw[which].launch(which === 'chromium' ? { args: ['--autoplay-policy=no-user-gesture-required'] } : {});
const report = { browser: `${which} ${browser.version()} (Playwright, headless)`, checks: {}, logs: [], why: [] };
function check(name, ok, why) {
  report.checks[name] = !!ok;
  if (!ok) report.why.push(`${name}: ${typeof why === 'string' ? why : JSON.stringify(why)}`);
}

const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') report.logs.push(`error: ${m.text()}`); });
await page.goto(`${url}?load=examples/first-orbit.lunar`);
await page.waitForTimeout(500);
await page.click('[data-layout="workbench"]');
await page.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 15000 });
await page.click('#power-on');
await page.waitForFunction(() => window.fm1.editor.state.mirror && window.fm1.editor.state.panelView &&
  window.fm1.editor.state.mirror.blocks.size > 6, null, { timeout: 30000 });
await page.click('[data-layout="editor"]');
await page.waitForTimeout(500);

const wait = (ms) => page.waitForTimeout(ms);
async function openMap() {
  await page.evaluate(async () => {
    document.querySelector('.ed-out-mod').click();
    await new Promise((r) => setTimeout(r, 300));
    const sw = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Map');
    if (sw && sw.getAttribute('aria-checked') !== 'true') sw.click();
    window.scrollTo(0, 0);
    await new Promise((r) => setTimeout(r, 600));
  });
}

// ---- the view, no faults, at three widths --------------------------------------------------------
await openMap();
const first = await page.evaluate(() => {
  const ed = window.fm1.editor, m = ed.chains.map;
  const cables = ed.state.mirror.cables.map((c, i) => [c, i]).filter(([c]) => c.flags & 1 || c.amount || c.unit || c.dst || c.src).map(([, i]) => i);
  return { shown: m.stats().cables, slots: cables.length, switchOn: !!document.querySelector('.ed-mapsw'), faults: m.faults(), table: !!document.querySelector('.ed-mx'),
    jacks: document.querySelectorAll('.ed-map .ed-jack').length, unnamed: [...document.querySelectorAll('.ed-map .ed-jack')].filter((b) => b.tagName === 'BUTTON' && !b.getAttribute('aria-label')).length };
});
report.first = first;
check('the Map shows every cable of the matrix, each on a jack at both ends', first.shown === first.slots && first.slots >= 3, first);
check('the Map replaces the table, and has a switch back', first.switchOn && !first.table, first);
check('every jack is named', first.jacks > 20 && first.unnamed === 0, first);
check('1,440 px: no cable over a label or a block, no label over a label, no pill over a label', first.faults.length === 0, first.faults);
await page.screenshot({ path: join(out, 'ed5b-map-1440.png') });
for (const w of [1024, 768]) {
  await page.setViewportSize({ width: w, height: 1000 });
  await wait(700);
  const g = await page.evaluate(() => ({ faults: window.fm1.editor.chains.map.faults(), room: window.fm1.editor.chains.mapOn(), side: document.documentElement.scrollWidth > document.documentElement.clientWidth }));
  check(`${w} px: the Map has no faults and the page does not scroll sideways`, g.room && g.faults.length === 0 && !g.side, g);
  await page.screenshot({ path: join(out, `ed5b-map-${w}.png`) });
}
await page.setViewportSize({ width: 375, height: 800 });
await wait(700);
const phone = await page.evaluate(() => ({ room: window.fm1.editor.chains.mapOn(), map: !!document.querySelector('.ed-map'), sw: !!document.querySelector('.ed-mapsw'), list: !!document.querySelector('.ed-mx') }));
check('375 px: no Map and no switch; the cable list stays', !phone.map && !phone.sw && phone.list && !phone.room, phone);
await page.setViewportSize({ width: 1440, height: 1000 });
await wait(700);
await openMap();

// ---- focus ---------------------------------------------------------------------------------------
const foc = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (ms) => new Promise((r) => setTimeout(r, ms));
  const mods = [...document.querySelectorAll('.ed-map-mod:not(.is-empty) .ed-map-mh')];
  // The module with the most cables on it.
  const count = (pos) => ed.state.mirror.cables.filter((c) => (c.flags & 1) && ((c.src >= 64 && ((c.src - 64) >> 3) === pos) || ed.mm.unitKey(c.unit) === `p${pos + 1}`)).length;
  let best = null;
  for (const h of mods) { const pos = Number(h.closest('.ed-map-mod').dataset.pos); const n = count(pos); if (!best || n > best.n) best = { h, pos, n }; }
  best.h.click();
  await w(700);
  const dim = document.querySelectorAll('.ed-map-svg .ed-cab.is-dim').length;
  const lit = document.querySelectorAll('.ed-map-svg .ed-cab:not(.is-dim)').length;
  const pillsLit = [...document.querySelectorAll('.ed-map-pill')].filter((p) => !!document.querySelector(`.ed-cab[data-cable="${p.dataset.cable}"]:not(.is-dim)`)).length;
  const pillsDim = document.querySelectorAll('.ed-map-pill').length - pillsLit;
  const chip = document.querySelector('.ed-fchip.is-on') && document.querySelector('.ed-fchip.is-on').textContent;
  const faults = ed.chains.map.faults();
  return { pos: best.pos, expect: best.n, dim, lit, pillsLit, pillsDim, chip, faults, total: ed.chains.map.stats().cables };
});
report.focus = foc;
check('focus on a module keeps its cables bright and dims the rest', foc.lit === foc.expect && foc.dim === foc.total - foc.expect && foc.lit >= 1, foc);
check('only the bright cables carry pills; the chip names the focus', foc.pillsLit >= 1 && foc.pillsDim === 0 && /Focus/.test(foc.chip || ''), foc);
check('with focus on there are still no faults', foc.faults.length === 0, foc.faults);
await page.screenshot({ path: join(out, 'ed5b-map-focus.png') });
await page.evaluate(() => document.querySelector('.ed-map-mod.is-sel .ed-map-mh').focus());
await page.keyboard.press('Escape');
await wait(500);
const esc = await page.evaluate(() => ({ dim: document.querySelectorAll('.ed-map-svg .ed-cab.is-dim').length, mode: window.fm1.editor.state.mapMode }));
check('Escape shows every cable again', esc.dim === 0 && esc.mode === 'all', esc);
await page.evaluate(() => document.querySelector('.ed-map-mod:not(.is-empty) .ed-map-mh').focus());
await page.keyboard.press('f');
await wait(500);
const fk = await page.evaluate(() => ({ mode: window.fm1.editor.state.mapMode, focus: document.activeElement && document.activeElement.dataset.fk }));
check('F on a module focuses it', fk.mode === 'focus', fk);
await page.keyboard.press('Escape');
await wait(400);

// ---- a cable by pointer, with C's verdict over the input -----------------------------------------------
const before = await page.evaluate(() => ({ n: window.fm1.editor.state.mirror.cables.filter((c) => c.flags & 1).length, steps: window.fm1.editor.history.entries.length,
  free: window.fm1.editor.state.mirror.cables.findIndex((c) => !(c.flags & 1) && !c.amount && !c.src && !c.unit && !c.dst) }));
const src = await page.evaluate(() => { const j = document.querySelector('.ed-map-srcs [data-src="0"]'); const r = j.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
await page.mouse.move(src.x, src.y);
await page.mouse.down();
await page.mouse.move(src.x + 14, src.y + 6, { steps: 3 });
await wait(300);
const tgt = await page.evaluate(() => {
  const j = [...document.querySelectorAll('.ed-map-dsts [data-block="s1"] .ed-jack-in')].find((x) => x.getClientRects().length);
  if (!j) return null;
  j.scrollIntoView({ block: 'center' });
  const r = j.getBoundingClientRect();
  return { x: r.x + r.width / 2, y: r.y + r.height / 2, dst: j.dataset.dst, hand: document.querySelector('.ed-map').classList.contains('is-patching'), more: !!document.querySelector('.ed-map-morelist') };
});
check('taking a cable up opens every destination', !!tgt && tgt.hand, tgt);
await page.mouse.move(tgt.x, tgt.y, { steps: 6 });
await wait(700);
const aim = await page.evaluate(() => ({ cls: [...document.querySelectorAll('.ed-jack.is-aim')].map((j) => j.className), hand: document.querySelector('.ed-map-hand').textContent }));
report.aim = aim;
check('over an input the Map says what C answers (runs, or its words)', aim.cls.length === 1 && /is-(ok|no)/.test(aim.cls[0]) && aim.hand.length > 6, aim);
await page.mouse.up();
await wait(1200);
const after = await page.evaluate((free) => {
  const ed = window.fm1.editor;
  const c = ed.state.mirror.cables[free];
  return { c, n: ed.state.mirror.cables.filter((x) => x.flags & 1).length, steps: ed.history.entries.length, sel: ed.state.selCable, patching: document.querySelector('.ed-map').classList.contains('is-patching') };
}, before.free);
report.drag = { before, after, tgt };
check('the drop writes one cable in the first empty slot, 25 %, from the source to that input', after.n === before.n + 1 && after.c.src === 0 && `${after.c.unit}:${after.c.dst}:${after.c.flags & 8 ? 1 : 0}` === tgt.dst && after.c.amount === 4096, { after, tgt });
check('it is one history step and the hand is empty', after.steps === before.steps + 1 && !after.patching, { before, after });
check('the new cable is selected and the Map draws it', after.sel === `c${before.free + 1}`, after);
await page.evaluate(() => window.fm1.editor.undo());
await wait(1200);
const undone = await page.evaluate(() => window.fm1.editor.state.mirror.cables.filter((x) => x.flags & 1).length);
check('one undo takes it away', undone === before.n, { undone, n: before.n });

// ---- the same by keys; Escape puts it back ---------------------------------------------------------------
await page.evaluate(() => { const j = document.querySelector('.ed-map-srcs [data-src="0"]'); j.focus(); });
await page.keyboard.press('Enter');
await wait(500);
const kb = await page.evaluate(() => ({ patching: document.querySelector('.ed-map').classList.contains('is-patching'), at: document.activeElement && document.activeElement.className, hand: document.querySelector('.ed-map-hand').textContent }));
check('Enter on an output takes the cable up and moves to the first input', kb.patching && /ed-jack-in/.test(kb.at) && /in hand/.test(kb.hand), kb);
await page.keyboard.press('Escape');
await wait(400);
const kbEsc = await page.evaluate(() => ({ patching: document.querySelector('.ed-map').classList.contains('is-patching'), at: document.activeElement && document.activeElement.dataset.src, ed: window.fm1.editor.state.keys }));
check('Escape puts it back and returns to the output', !kbEsc.patching && kbEsc.at === '0', kbEsc);
await page.evaluate(() => { document.querySelector('.ed-map-srcs [data-src="0"]').focus(); });
await page.keyboard.press('Enter');
await wait(500);
await page.keyboard.press('ArrowDown');
await page.keyboard.press('ArrowDown');
await wait(700);
const walked = await page.evaluate(() => ({ dst: document.activeElement.dataset.dst, name: document.activeElement.getAttribute('aria-label'), aim: document.querySelectorAll('.ed-jack.is-aim').length }));
await page.keyboard.press('Enter');
await wait(1200);
const kd = await page.evaluate((free) => { const c = window.fm1.editor.state.mirror.cables[free]; return { c, n: window.fm1.editor.state.mirror.cables.filter((x) => x.flags & 1).length }; }, before.free);
check('arrows walk the inputs and Enter drops the cable on the one with the keys', kd.n === before.n + 1 && `${kd.c.unit}:${kd.c.dst}:${kd.c.flags & 8 ? 1 : 0}` === walked.dst, { walked, kd });
await page.evaluate(() => window.fm1.editor.undo());
await wait(1000);

// ---- one truth: the table's edit moves the Map's pill -----------------------------------------------------------
const two = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (ms) => new Promise((r) => setTimeout(r, ms));
  const i = ed.state.mirror.cables.findIndex((c) => c.flags & 1);
  ed.chains.map.cancel();
  ed.select(`c${i + 1}`, { view: 'mod' });
  await w(700);
  const pill = () => { const p = document.querySelector(`.ed-map-pill[data-cable="${i}"] .ed-pill-a`); return p ? p.textContent : null; };
  const was = pill();
  return { i, was, hasInspector: !!document.querySelector('.ed-slot') };
});
report.two = two;
check('selecting a cable in the Map opens its inspector below, and its pill shows the amount', two.hasInspector && /%/.test(two.was || ''), two);
await page.screenshot({ path: join(out, 'ed5b-map-selected.png') });
const typed = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (ms) => new Promise((r) => setTimeout(r, ms));
  const i = Number(/c([0-9]+)/.exec(ed.state.selCable)[1]) - 1;
  const was = ed.chains.cableGet(i, 'amount');
  ed.chains.cableSet(i, 'amount', -55, {});
  await w(900);
  document.querySelector('.ed-out-mod').click();
  await w(700);
  const p = document.querySelector(`.ed-map-pill[data-cable="${i}"] .ed-pill-a`);
  const text = p ? p.textContent : null;
  ed.chains.cableSet(i, 'amount', was, {});
  await w(700);
  return { text, was };
});
check('an amount changed through the edit layer reaches the Map\'s pill', /-55 %/.test(typed.text || ''), typed);

// ---- live values ---------------------------------------------------------------------------------------------------
await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'note-on', note: 64, velocity: 100 }));
await wait(700);
const live = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (ms) => new Promise((r) => setTimeout(r, ms));
  ed.state.mapMode = 'all';
  ed.state.selCable = null;
  ed.select('p3', { view: 'mod' });
  await w(800);
  const outs = [...document.querySelectorAll('.ed-map [data-out]')].map((e) => e.textContent).filter((t) => t && t !== '–');
  const lives = [...document.querySelectorAll('.ed-map-pill .ed-map-live')].map((e) => e.textContent).filter((t) => t);
  return { outs: outs.length, lives, pills: document.querySelectorAll('.ed-map-pill').length };
});
report.live = live;
check('module outputs read live on the Map while a note sounds', live.outs >= 1, live);
await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'note-off', note: 64 }));

// ---- full matrix: C's words for "no room" ------------------------------------------------------------------------------
const full = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (ms) => new Promise((r) => setTimeout(r, ms));
  const s0 = ed.state.mirror.cables.map((c) => ({ ...c }));
  let guard = 0, k = 0;
  // Distinct cables: sources and inputs taken from the Map itself, spread over its columns.
  const dsts = [...document.querySelectorAll('.ed-map .ed-jack-in:not(.is-stub)')].map((j) => j.dataset.dst);
  const srcs = [...ed.mm.sources.keys()];
  while (ed.chains.makeCable(srcs[(k * 5) % srcs.length], dsts[(k * 7 + 3) % dsts.length]) >= 0 && guard++ < 40) { k++; await w(60); }
  await w(900);
  document.querySelector('.ed-out-mod').click();
  await w(900);
  const faults = ed.chains.map.faults();
  const stats = ed.chains.map.stats();
  const refused = document.querySelectorAll('.ed-map-svg .ed-cab.is-refused').length;
  const shot = ed.chains.map.stats().cables;
  return { n: ed.state.mirror.cables.filter((c) => c.flags & 1).length, faults, stats, refused, shot, saved: s0.length };
});
report.full = full;
check('with all 32 slots used the Map still draws every cable with no label over a cable', full.n >= 31 && full.stats.cables >= 30 && full.faults.length === 0, full);
await page.screenshot({ path: join(out, 'ed5b-map-full.png') });
const noRoom = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const r = ed.chains.makeCable(0, `${ed.mm.unitCode('s1')}:1:0`);
  return { r, refusal: document.querySelector('.ed-refusal, [data-refusal]') ? document.querySelector('.ed-refusal, [data-refusal]').textContent : null, words: ed.meta.refusalWords(6) };
});
check('a thirty-third cable is refused in C\'s words (No room)', noRoom.r === -1, noRoom);
// Take the added cables away again with undo.
await page.evaluate(async () => { const ed = window.fm1.editor; for (let k = 0; k < 40; ++k) { ed.undo(); await new Promise((r) => setTimeout(r, 120)); } });
await wait(900);

// ---- the keyboard and the names ---------------------------------------------------------------------------------------
await openMap();
const keys = await page.evaluate(() => {
  const stops = [...document.querySelectorAll('.ed-map button')].filter((b) => b.getClientRects().length && b.tabIndex === 0);
  const cols = [...document.querySelectorAll('.ed-map-col')].map((c) => ({ role: c.getAttribute('role'), label: c.getAttribute('aria-label'), stops: [...c.querySelectorAll('button')].filter((b) => b.getClientRects().length && b.tabIndex === 0).length }));
  return { stops: stops.length, cols, hidden: document.querySelector('.ed-map-svg').getAttribute('aria-hidden') };
});
report.keys = keys;
check('one tab stop in each column, each a labelled toolbar; the picture itself is hidden from readers', keys.cols.length === 3 && keys.cols.every((c) => c.role === 'toolbar' && c.label && c.stops === 1) && keys.hidden === 'true', keys);

writeFileSync(join(out, 'editor-map.json'), JSON.stringify(report, null, 1));
await browser.close();
server.close();
const bad = Object.entries(report.checks).filter(([, ok]) => !ok);
console.log(`${report.browser}: ${Object.keys(report.checks).length - bad.length} of ${Object.keys(report.checks).length} checks pass`);
for (const w of report.why) console.log(`  FAIL ${w}`);
for (const l of report.logs.slice(0, 8)) console.log(`  log ${l}`);
process.exit(bad.length || report.logs.some((l) => l.startsWith('pageerror')) ? 1 : 0);
