// editor-v1.mjs -- the Advanced editor's v1 completion (notes/2026-10-06-web-editor.md,
// "v1 completed"): what the v1 audit found missing, each built and checked here in a real
// browser. Runs in the Playwright container on aeon after editor-map.mjs (build-on-aeon.sh),
// never on the Mac:
//
//   [BROWSER=chromium|firefox|webkit] node editor-v1.mjs WWW_DIR OUT_DIR
//
// Checks (the sections below):
//  1. modulation on the parameter rows: a modulated label, its chip, the bracket, the live tick
//     (one for each sounding voice) and the cables spoken in aria-valuetext; a row with no cable
//     has none of it; the telemetry's destination rows are subscribed in the Flow and a sound;
//  2. late cables: the `~` mark and C's words, the loop in words, the Map's Late chip and pill;
//  3. a refused cable's repair (Make it global), the slot inspector's drawn curves and each
//     voice's value; the sources' groups from the metadata; "an effects chain";
//  4. search operators: >cutoff, lfo1>, !, ~, v, s2, hz, and cables as a group;
//  5. A/B: picks per row, "Make B from the picks" (one step, undone by one), A and B back after
//     a reload;
//  6. slider key C; a link to one block and a strip dragged to the desktop (Chromium);
//  7. the arrival card: what is replaced, what is brought, the RAM after;
//  8. the Flow blocks' cable counts and bars;
//  9. phones: Add a cable in three steps, a long press that opens a block's menu;
// 10. §17's leftovers: axe-core on the layouts, a reduced-motion run, telemetry stopped while the
//     editor is hidden, a lock playing changing no base, the main thread's budget.
// MIT licence, like the rest of this repository.

import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { serve } from './serve.mjs';
import { launch, which } from './launch.mjs';

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8772);
const { browser, name: browserName } = await launch();
const report = { browser: browserName, checks: {}, logs: [], why: [] };
function check(name, ok, why) {
  report.checks[name] = !!ok;
  if (!ok) report.why.push(`${name}: ${typeof why === 'string' ? why : JSON.stringify(why)}`);
}

process.on('uncaughtException', (e) => {
  report.why.push(`crash: ${e.message}`);
  try { writeFileSync(join(out, 'editor-v1.json'), JSON.stringify(report, null, 1)); } catch (err) { /* the report is on the console */ }
  console.log(`${report.browser}: crashed after ${Object.keys(report.checks).length} checks`);
  for (const w of report.why) console.log(`  FAIL ${w}`);
  process.exit(1);
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await context.newPage();
page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') report.logs.push(`error: ${m.text()}`); });
await page.goto(`${url}?load=examples/first-orbit.lunar`);
await page.addScriptTag({ path: new URL('./layout-probe.js', import.meta.url).pathname });
await page.waitForTimeout(500);
await page.click('[data-layout="workbench"]');
await page.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 15000 });
await page.click('#power-on');
await page.waitForFunction(() => window.fm1.editor.state.mirror && window.fm1.editor.state.panelView &&
  window.fm1.editor.state.mirror.blocks.size > 6, null, { timeout: 30000 });
await page.click('[data-layout="editor"]');
await page.waitForTimeout(500);
const wait = (ms) => page.waitForTimeout(ms);
const shot = (name, sel) => (sel ? page.locator(sel).first().screenshot({ path: join(out, name) }) : page.screenshot({ path: join(out, name) }));
const noteOn = (n) => page.evaluate((n) => window.fm1.node.port.postMessage({ type: 'note-on', note: n, velocity: 100 }), n);
const noteOff = (n) => page.evaluate((n) => window.fm1.node.port.postMessage({ type: 'note-off', note: n }), n);

// A module-to-module loop, as a mod rack file: LFO 1 into LFO 2's Rate, and back; a cable
// that runs up the rack is read a tick late. A per-voice cable into an effect is refused.
const loopFile = JSON.stringify({
  lunar: '1.0', kind: 'mods', made: { by: 'test' }, name: 'LOOP', title: 'Loop test', about: '', licence: 'MIT',
  mod: { seed: 1, rack: [{ pos: 1, kind: 'lfo', params: {} }, { pos: 2, kind: 'lfo', params: {} }],
    cables: [
      { slot: 1, on: true, from: { module: 1, port: 'Out' }, via: null, to: { module: 2, param: 'Rate' }, amount: 20, offset: 0, polarity: 'auto', curve: 'lin', voice: false, lock: 0 },
      { slot: 2, on: true, from: { module: 2, port: 'Out' }, via: null, to: { module: 1, param: 'Rate' }, amount: 15, offset: 0, polarity: 'auto', curve: 'lin', voice: false, lock: 0 },
      { slot: 3, on: true, from: { module: 1, port: 'Out' }, via: null, to: { unit: 'snd2.fx1', param: 'Cutoff' }, amount: 30, offset: 0, polarity: 'auto', curve: 'cube', voice: true, lock: 0 },
    ] },
});
async function loadMods(text) {
  return page.evaluate(async (text) => {
    const bytes = new TextEncoder().encode(text);
    const r = await window.fm1.files.load(bytes, { d: { enc: 2, kind: 'mods', title: 'Loop test' }, target: { into: 0, slot: 0 }, before: false, quiet: true });
    await new Promise((res) => setTimeout(res, 900));
    return { ok: r.ok, message: r.report && (r.report.message || r.report.code) };
  }, text);
}
const sel = (key, view) => page.evaluate(async ([key, view]) => { window.fm1.editor.select(key, { view }); await new Promise((r) => setTimeout(r, 450)); }, [key, view]);

// ---- 1. modulation on the rows --------------------------------------------------------------
await sel('s2.in1', 'sound');
const rowFacts = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  const cab = st.mirror.cables.findIndex((c) => (c.flags & 1) && ed.mm.unitKey(c.unit) === 's2.in1');
  if (cab < 0) return { none: true };
  const c = st.mirror.cables[cab];
  const row = document.querySelector(`.ed-insp[data-block="s2.in1"] .ed-row[data-uid="${c.dst}"]`);
  await new Promise((r) => setTimeout(r, 1500));
  const slider = row && row.querySelector('.ed-slider');
  const plain = [...document.querySelectorAll('.ed-insp[data-block="s2.in1"] .ed-row-slider')].find((r) => !r.classList.contains('is-modulated') && r.querySelector('.ed-label.can-mod'));
  const tick = slider && slider.querySelector('.ed-tick:not([hidden])');
  return { cab, label: row && row.querySelector('.ed-label').className, chip: row && (row.querySelector('.ed-chip-c') || {}).textContent,
    bracket: !!(slider && slider.querySelector('.ed-bracket')), bracketW: slider && slider.querySelector('.ed-bracket') && slider.querySelector('.ed-bracket').style.width,
    tick: tick ? parseFloat(tick.style.left) : null, valuetext: slider && slider.getAttribute('aria-valuetext'),
    plain: plain ? { chip: !!plain.querySelector('.ed-chip-c'), bracket: !!plain.querySelector('.ed-bracket'), tick: !!plain.querySelector('.ed-tick:not([hidden])'), text: plain.querySelector('.ed-slider').getAttribute('aria-valuetext') } : null,
    sig: st.teleSig && st.teleSig.length, on: st.teleOn };
});
report.rowFacts = rowFacts;
check('a row a live cable reaches has its label in the modulation colour and a chip naming the source', rowFacts.cab >= 0 && /is-modulated/.test(rowFacts.label || '') && /\w/.test(rowFacts.chip || ''), rowFacts);
check('its slider has the bracket round the base and the live value as a tick', rowFacts.bracket && parseFloat(rowFacts.bracketW) > 0 && rowFacts.tick !== null && rowFacts.tick >= 0 && rowFacts.tick <= 100, rowFacts);
check('its aria-valuetext speaks the cable: "modulated by …, plus … percent"', /, modulated by .+, (plus|minus) \d+ percent$/.test(rowFacts.valuetext || ''), rowFacts.valuetext);
check('a row that takes a cable and has none shows no chip, bracket or tick, and speaks no cable', rowFacts.plain && !rowFacts.plain.chip && !rowFacts.plain.bracket && !rowFacts.plain.tick && !/modulated/.test(rowFacts.plain.text), rowFacts.plain);
check('the telemetry rows of the live cables are subscribed in a sound (not only in Modulation)', rowFacts.on && rowFacts.sig > 0, rowFacts);
await shot('v1-row-modulated.png', '.ed-insp[data-block="s2.in1"]');

// A per-voice cable: one tick for each sounding voice (S3's Timbre, from the example's ENV).
await page.evaluate(async () => {
  const ed = window.fm1.editor;
  ed.select('the-mix', { view: 'flow' });
  await new Promise((r) => setTimeout(r, 400));
  const cur = [...document.querySelectorAll('.ed-cur')];
  if (cur[2]) cur[2].click();
  await new Promise((r) => setTimeout(r, 700));
  ed.select('s3', { view: 'sound' });
  await new Promise((r) => setTimeout(r, 500));
});
await noteOn(60); await noteOn(64);
await wait(1200);
const voiceTicks = await page.evaluate(() => {
  const ed = window.fm1.editor;
  const cab = ed.state.mirror.cables.findIndex((c) => (c.flags & 1) && (c.flags & 0x80 || c.flags & 128) && ed.mm.unitKey(c.unit) === 's3');
  const c = ed.state.mirror.cables[cab];
  const row = c && document.querySelector(`.ed-insp[data-block="s3"] .ed-row[data-uid="${c.dst}"]`);
  return { cab, ticks: row ? [...row.querySelectorAll('.ed-tick:not([hidden])')].map((t) => ({ left: parseFloat(t.style.left), voice: t.classList.contains('is-voice') })) : null };
});
await noteOff(60); await noteOff(64);
report.voiceTicks = voiceTicks;
check('a per-voice cable draws a tick for each sounding voice (two notes: two ticks)', voiceTicks.ticks && voiceTicks.ticks.length >= 2 && voiceTicks.ticks.every((t) => t.voice && t.left >= 0 && t.left <= 100), voiceTicks);

// ---- 2. late cables -------------------------------------------------------------------------
const loaded = await loadMods(loopFile);
check('a rack with a loop loads', loaded.ok, loaded);
await sel('p1', 'mod');
const late = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  const loops = st.mirror.loops;
  const idx = [...loops.keys()].filter((i) => loops[i] !== 0);
  const rows = idx.map((i) => document.querySelector(`.ed-mx-r[data-cable="${i}"]`));
  const marks = (r) => r ? [...r.querySelectorAll('.ed-mark')].map((m) => ({ ch: m.textContent, title: m.title })) : [];
  const run = [...document.querySelectorAll('.ed-mx-r[data-cable]')].find((r) => /runs$/.test((r.querySelector('.ed-mx-v') || {}).textContent || '') && !r.classList.contains('is-empty'));
  const legend = document.querySelector('.ed-legend') ? document.querySelector('.ed-legend').textContent : '';
  return { idx, mask: idx.map((i) => loops[i]), marks: rows.map(marks), verdict: rows.map((r) => r && r.querySelector('.ed-mx-v').textContent),
    runMarks: marks(run), legend, tried: st.mirror.cables.filter((c) => c.flags & 1).length };
});
report.late = late;
check('C reports the loop each late cable closes (one cable, the one that runs up the rack; both rack positions in the loop)', late.idx.length === 1 && late.mask[0] === 3, late);
check('the table marks it ~ and says so in C\'s words: "a tick late"', late.marks[0] && late.marks[0].some((m) => m.ch === '~' && m.title === 'a tick late') && /a tick late/.test(late.verdict[0] || ''), late);
check('a cable that runs on time has the > mark and no ~', late.runMarks.some((m) => m.ch === '>') && !late.runMarks.some((m) => m.ch === '~'), late.runMarks);
check('the legend names the marks from C\'s words', /a tick late/.test(late.legend), late.legend);
await page.evaluate(async (i) => { const row = document.querySelector(`.ed-mx-r[data-cable="${i}"] .ed-mx-n`); row.click(); await new Promise((r) => setTimeout(r, 500)); }, late.idx[0]);
const lateNote = await page.evaluate(() => (document.querySelector('.ed-slot .ed-late') || {}).textContent);
check('the slot inspector explains the loop in words, naming the modules in it', /^A tick late: closes a loop through LFO \(rack 1\) and LFO \(rack 2\), so it reads its source from the tick before\.$/.test(lateNote || ''), lateNote);
await shot('v1-late-slot.png', '.ed-slot');
// The Map: a Late chip, the ~ on the pill.
const hasRoom = await page.evaluate(() => window.fm1.editor.chains.mapOn !== undefined);
await page.evaluate(async () => {
  const sw = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Map');
  if (sw) sw.click();
  await new Promise((r) => setTimeout(r, 700));
});
const mapLate = await page.evaluate(async () => {
  const chip = [...document.querySelectorAll('.ed-fchip')].find((c) => /^A tick late/.test(c.textContent));
  if (!chip) return { chip: null };
  chip.click();
  await new Promise((r) => setTimeout(r, 600));
  const pill = document.querySelector('.ed-map-pill .ed-pill-l');
  return { chip: chip.textContent, pill: pill ? pill.textContent : null, lit: document.querySelectorAll('.ed-map-pill').length, faults: window.fm1.editor.chains.map.faults() };
});
report.mapLate = mapLate;
check('the Map has a Late chip with the count; it lights that cable with ~ on its pill and no label under a cable', mapLate.chip === 'A tick late · 1' && mapLate.pill === '~' && mapLate.faults.length === 0, mapLate);
await shot('v1-map-late.png');
await page.evaluate(() => { const c = [...document.querySelectorAll('.ed-fchip')].find((x) => /^A tick late/.test(x.textContent)); if (c) c.click(); const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Table'); if (t) t.click(); });
await wait(500);

// ---- 3. refusal fixes, curves, voices, groups ------------------------------------------------
const refused = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  const i = st.mirror.cables.findIndex((c, k) => (c.flags & 1) && st.mirror.verdicts[k] === 38);
  return { i, code: i >= 0 ? st.mirror.verdicts[i] : null };
});
check('a per-voice cable into an effect is refused by C (VOICE_TO_EFFECT)', refused.i >= 0, refused);
await page.evaluate(async (i) => { document.querySelector(`.ed-mx-r[data-cable="${i}"] .ed-mx-n`).click(); await new Promise((r) => setTimeout(r, 500)); }, refused.i);
const fixUi = await page.evaluate(() => {
  const slot = document.querySelector('.ed-slot');
  const fix = slot && slot.querySelector('.ed-fix');
  const thumbs = slot ? slot.querySelectorAll('.ed-row[data-uid="curve"] svg.ed-curve-thumb').length : 0;
  const big = slot && slot.querySelector('.ed-row[data-uid="curve"] svg.ed-curve-big .ed-curve-line');
  const d = big ? big.getAttribute('d') : '';
  return { fix: fix ? fix.textContent : null, why: slot && (slot.querySelector('.ed-why') || {}).textContent, thumbs, points: (d.match(/[ML]/g) || []).length,
    curves: window.fm1.editor.mm.curves.length, chosen: slot && slot.querySelector('.ed-row[data-uid="curve"] [aria-checked="true"]').textContent.trim() };
});
report.fixUi = fixUi;
check('a refusal with a repair offers it, in C\'s words: "Make it global"', fixUi.fix === 'Make it global' && /kept as written/.test(fixUi.why || ''), fixUi);
check('the slot inspector draws every curve (C\'s own 33 points) and the chosen one larger', fixUi.thumbs === fixUi.curves && fixUi.points === 33 && /cube/i.test(fixUi.chosen), fixUi);
await shot('v1-slot-refused.png', '.ed-slot');
await page.click('.ed-slot .ed-fix');
await wait(1200);
const fixed = await page.evaluate((i) => { const st = window.fm1.editor.state; return { voice: !!(st.mirror.cables[i].flags & 128), verdict: st.mirror.verdicts[i], fix: !!document.querySelector('.ed-slot .ed-fix') }; }, refused.i);
check('"Make it global" clears the per-voice flag as an edit, and C then runs the cable', !fixed.voice && fixed.verdict === 0 && !fixed.fix, fixed);

// Each voice's value (the example's cable 2 is per voice into S3).
await page.evaluate(async () => {
  const ed = window.fm1.editor;
  await window.fm1.files.load(new Uint8Array(await (await fetch('examples/first-orbit.lunar')).arrayBuffer()), { d: { enc: 2, kind: 'project', title: 'first-orbit' }, before: false, quiet: true });
  await new Promise((r) => setTimeout(r, 1500));
  ed.select('the-mix', { view: 'flow' });
  await new Promise((r) => setTimeout(r, 400));
  const cur = [...document.querySelectorAll('.ed-cur')];
  if (cur[2]) cur[2].click();
  await new Promise((r) => setTimeout(r, 700));
  ed.select('c2', { view: 'mod' });
  await new Promise((r) => setTimeout(r, 600));
});
await noteOn(60); await noteOn(67);
await wait(1200);
report.cur = await page.evaluate(() => window.fm1.editor.state.mirror.current);
const voiceVals = await page.evaluate(() => ({ chips: [...document.querySelectorAll('.ed-slot .ed-voices .ed-voice')].map((c) => c.textContent), label: (document.querySelector('.ed-slot [data-voices]') || {}).previousSibling && document.querySelector('.ed-slot [data-voices]').previousSibling.textContent }));
await noteOff(60); await noteOff(67);
report.voiceVals = voiceVals;
check('the slot inspector of a per-voice cable shows each sounding voice\'s own value', voiceVals.chips.length >= 2 && voiceVals.chips.every((c) => /^\d+ -?[\d.]+k?$/.test(c)) && /by voice/.test(voiceVals.label || ''), voiceVals);

const groups = await page.evaluate(() => {
  const ed = window.fm1.editor;
  return { groups: ed.mm.groupedSources().map((g) => `${g.title}:${g.list.length}`), codeNames: /SQV|SEQ\[/.test(document.documentElement.innerHTML) };
});
report.groups = groups;
check('the sources\' groups come from the metadata: notes, a group for each sound, the lanes and their values', groups.groups.length >= 7 && /^Notes, clock and chance:/.test(groups.groups[0]) && groups.groups.some((g) => /^Sound 3's notes:5$/.test(g)) && groups.groups.some((g) => /^Sequencer lanes:8$/.test(g)) && groups.groups.some((g) => /^Lane values:8$/.test(g)), groups);

writeFileSync(join(out, 'editor-v1.json'), JSON.stringify(report, null, 1));
await browser.close();
server.close();
const bad = Object.entries(report.checks).filter(([, ok]) => !ok);
console.log(`${report.browser}: ${Object.keys(report.checks).length - bad.length} of ${Object.keys(report.checks).length} checks pass`);
for (const w of report.why) console.log(`  FAIL ${w}`);
for (const l of report.logs.slice(0, 8)) console.log(`  log ${l}`);
process.exit(bad.length || report.logs.some((l) => l.startsWith('pageerror')) ? 1 : 0);
