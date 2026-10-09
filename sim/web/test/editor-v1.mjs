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


// ---- 4. search operators --------------------------------------------------------------------
await loadMods(loopFile);                                     // a loop, a refused per-voice cable and the rest
await sel('s2', 'flow');
async function search(q) {
  await page.keyboard.press('Control+k');
  await page.keyboard.type(q);
  await wait(150);
  const r = await page.evaluate(() => ({ groups: [...document.querySelectorAll('.ed-search-g')].map((g) => g.textContent),
    items: [...document.querySelectorAll('.ed-search-o')].map((o) => o.textContent), n: document.querySelector('.ed-search-n').textContent }));
  await page.keyboard.press('Escape');
  await wait(100);
  return r;
}
const q = {};
for (const w of ['>cutoff', 'lfo>', 'lfo1>', '>lfo2', '!', '~', 'v', 's2', 'hz', '>cutoff !', 'cable']) q[w] = await search(w);
report.search = q;
const only = (r, g) => r.groups.length === 1 && r.groups[0] === g;
check('>cutoff finds the cables into a Cutoff, and only cables', only(q['>cutoff'], 'Cables') && q['>cutoff'].items.length === 1 && /Cable 3 · 1 LFO Out → S2 In1 Cutoff/.test(q['>cutoff'].items[0]), q['>cutoff']);
check('lfo> finds the cables out of an LFO (all three of the loop file\'s)', only(q['lfo>'], 'Cables') && q['lfo>'].items.length === 3, q['lfo>']);
check('a module can be said as a person says it: lfo1> is the cables out of the LFO in rack 1, >lfo2 the cables into the one in rack 2', only(q['lfo1>'], 'Cables') && q['lfo1>'].items.length === 2 && q['lfo1>'].items.every((t) => /Cable [13] /.test(t)) && only(q['>lfo2'], 'Cables') && q['>lfo2'].items.length === 1 && /^Cable 1 /.test(q['>lfo2'].items[0]), { a: q['lfo1>'], b: q['>lfo2'] });
check('! finds the refused cables: C\'s verdict, not a guess', only(q['!'], 'Cables') && q['!'].items.length === 1 && /^Cable 3 /.test(q['!'].items[0]) && /!/.test(q['!'].items[0]), q['!']);
check('~ finds the cable read a tick late', only(q['~'], 'Cables') && q['~'].items.length === 1 && /^Cable 2 /.test(q['~'].items[0]) && /~/.test(q['~'].items[0]), q['~']);
check('v finds the per-voice cables', only(q.v, 'Cables') && q.v.items.length === 1 && /^Cable 3 /.test(q.v.items[0]), q.v);
check('s2 keeps what belongs to Sound 2: its blocks, parameters and the cable into it', q.s2.items.length > 10 && q.s2.items.every((t) => /S2|Cable 3/.test(t)) && q.s2.items.some((t) => /^Cable 3/.test(t)), { n: q.s2.n, head: q.s2.items.slice(0, 4) });
const hzWant = await page.evaluate(() => { const ed = window.fm1.editor; let n = 0; for (const [, b] of ed.state.mirror.blocks) for (const pg of ed.meta.pages(b.engine)) for (const p of pg.params) if (p.unit === 'hz') ++n; return n; });
check('hz keeps the parameters in hertz, and only parameters (as many as the blocks hold)', only(q.hz, 'Parameters') && q.hz.items.length === hzWant && hzWant >= 1, { n: q.hz.n, want: hzWant, head: q.hz.items.slice(0, 3) });
check('operators and words combine: >cutoff ! is the refused cable into a Cutoff', only(q['>cutoff !'], 'Cables') && q['>cutoff !'].items.length === 1, q['>cutoff !']);
check('cables are a group of their own, searched by name', q.cable.groups.includes('Cables') && q.cable.items.some((t) => /^Cable 1 /.test(t)), q.cable);
await page.keyboard.press('Control+k');
await page.keyboard.type('~');
await page.keyboard.press('Enter');
await wait(600);
const picked = await page.evaluate(() => ({ sel: window.fm1.editor.state.selCable, view: window.fm1.editor.state.view }));
check('Enter on a found cable opens its slot in Modulation', picked.sel === 'c2' && picked.view === 'mod', picked);

// ---- 8. the Flow blocks' cable counts and bars (the loop file is still in) ----------------------
await sel('s2', 'flow');
const counts = await page.evaluate(async () => {
  const blk = (k) => document.querySelector(`.ed-flow [data-block="${k}"]`);
  const c = (k) => { const b = blk(k), x = b && b.querySelector('.ed-blk-c'); return x ? { text: x.textContent, refused: x.classList.contains('is-refused'), label: b.getAttribute('aria-label') } : null; };
  return { in1: c('s2.in1'), s1: c('s1'), meters: [...document.querySelectorAll('.ed-flow .ed-block .ed-blk-m')].map((m) => m.dataset.meter), mix: !!blk('the-mix') && !!blk('the-mix').querySelector('.ed-blk-m') };
});
report.counts = counts;
check('a Flow block carries its cable count, and the refusals among them in love\'s colour and in words', counts.in1 && counts.in1.text === '1 cable, 1 refused' && counts.in1.refused && /1 cable, 1 refused/.test(counts.in1.label), counts);
check('a block no cable ends on has no count', counts.s1 === null, counts);
check('the Flow blocks carry a meter each (engine, inserts, master slots, the Mix)', counts.meters.length >= 8 && counts.mix, counts);
await shot('v1-flow-counts.png', '.ed-flow');
// The bars move with the sound: a note on the current sound lights the engine's or the inserts' bar.
await page.evaluate(async () => { window.fm1.editor.select('the-mix', { view: 'flow' }); await new Promise((r) => setTimeout(r, 300)); const cur = [...document.querySelectorAll('.ed-cur')]; if (cur[1]) cur[1].click(); await new Promise((r) => setTimeout(r, 500)); });
await noteOn(60);
await wait(900);
const lvl = await page.evaluate(() => [...document.querySelectorAll('.ed-flow .ed-block .ed-blk-m')].map((m) => parseFloat(m.style.getPropertyValue('--lvl') || '0')));
await noteOff(60);
check('a note lights the bars of the blocks it passes through', lvl.some((x) => x > 0.05), lvl);

// ---- the project back, for the rest ---------------------------------------------------------
async function loadExample() {
  await page.evaluate(async () => {
    await window.fm1.files.load(new Uint8Array(await (await fetch('examples/first-orbit.lunar')).arrayBuffer()), { d: { enc: 2, kind: 'project', title: 'first-orbit' }, before: false, quiet: true });
    await new Promise((r) => setTimeout(r, 1500));
  });
}
await loadExample();

// ---- 6a. slider key C -----------------------------------------------------------------------
await sel('s2.in1', 'sound');
const keyC = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  const blk = st.mirror.blocks.get('s2.in1');
  const e = ed.meta.engine(blk.engine);
  const target = e.params.find((p) => p.type === 'float' && (p.flags || []).includes('mod') && !st.mirror.cables.some((c) => (c.flags & 1) && ed.mm.unitKey(c.unit) === 's2.in1' && c.dst === p.uid));
  const plain = e.params.find((p) => p.type === 'float' && !(p.flags || []).includes('mod'));
  return { uid: target && target.uid, name: target && target.name, plain: plain ? { uid: plain.uid, name: plain.name } : null, before: st.mirror.cables.filter((c) => c.flags & 1).length };
});
check('the example has a modulatable parameter without a cable', keyC.uid !== undefined && keyC.uid !== null, keyC);
await page.focus(`[data-fk="s2.in1:${keyC.uid}"]`);
await page.keyboard.press('c');
await wait(900);
const madeC = await page.evaluate((uid) => {
  const ed = window.fm1.editor, st = ed.state;
  const i = st.mirror.cables.findIndex((c) => (c.flags & 1) && ed.mm.unitKey(c.unit) === 's2.in1' && c.dst === uid);
  return { i, sel: st.selCable, view: st.view, n: st.mirror.cables.filter((c) => c.flags & 1).length, src: i >= 0 ? ed.chains.srcName(st.mirror.cables[i].src) : null };
}, keyC.uid);
report.keyC = { keyC, madeC };
check('key C on a slider makes a cable into that parameter and opens it', madeC.i >= 0 && madeC.n === keyC.before + 1 && madeC.sel === `c${madeC.i + 1}` && madeC.view === 'mod' && !!madeC.src, madeC);
await sel('s2.in1', 'sound');
if (keyC.plain) {
  await page.focus(`[data-fk="s2.in1:${keyC.plain.uid}"]`);
  await page.keyboard.press('c');
  await wait(300);
  const refusedC = await page.evaluate(() => (window.fm1.editor.state.refusal || {}).text);
  check('key C on a parameter that takes no cable says so in C\'s words', /Takes no modulation/.test(refusedC || '') && new RegExp(`${keyC.plain.name} takes no cable`).test(refusedC || ''), refusedC);
}
const keyList = await page.evaluate(() => { document.querySelector(`.ed-row .ed-slider`).focus(); return document.querySelector('.ed-detail, .ed-d-keys') ? document.querySelector('.ed-d-keys').textContent : ''; });
await page.focus(`[data-fk="s2.in1:${keyC.uid}"]`);
const keysText = await page.evaluate(() => document.querySelector('.ed-d-keys').textContent);
check('the detail bar lists the C key for a parameter that takes a cable', /C cable/.test(keysText.replace(/\s+/g, ' ')), keysText);

// ---- 6b. a link to one block, a strip dragged to the desktop --------------------------------------
await page.evaluate(() => { window.__copied = null; navigator.clipboard.writeText = async (t) => { window.__copied = t; }; });
await sel('s3', 'sound');
await page.click('.ed-insp[data-block="s3"] [data-link="s3"]');
await wait(900);
const link = await page.evaluate(() => window.__copied);
check('Copy a link on a block gives a link to that block\'s file, with where it goes', /^https?:\/\/[^#]+#lunar=[A-Za-z0-9_-]{40,}&into=s3$/.test(link || ''), (link || '').slice(0, 80));
if (which === 'chromium') {
  const dragged = await page.evaluate(async () => {
    window.fm1.editor.select('s3', { view: 'flow' });
    await new Promise((r) => setTimeout(r, 500));
    const tag = document.querySelector('.ed-tag[data-drag-file="s3"]');
    if (!tag) return { tag: false };
    const t = document.querySelector('.ed-tag[data-drag-file="s3"]');
    t.dispatchEvent(new PointerEvent('pointerenter', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 700));
    const dt = new DataTransfer();
    t.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: dt }));
    return { tag: true, draggable: t.draggable, data: dt.getData('DownloadURL') };
  });
  report.dragged = dragged;
  check('a sound\'s tag dragged to the desktop gives its file (DownloadURL: type, name, blob)', dragged.tag && dragged.draggable && /^application\/json:[^:]+\.sound\.lunar:blob:/.test(dragged.data || ''), dragged);
} else {
  await sel('s3', 'flow');
  const plainTag = await page.evaluate(() => !document.querySelector('.ed-tag[data-drag-file]'));
  check('the drag to the desktop is offered in Chromium only; elsewhere the tag is plain', plainTag, which);
}

// ---- 7. the arrival card --------------------------------------------------------------------
await sel('s2', 'flow');
const arrived = await page.evaluate(async () => {
  const text = await (await fetch('examples/deep-bass.sound.lunar')).text();
  const blk = document.querySelector('.ed-flow .ed-block[data-block="s2"]');
  const dt = new DataTransfer();
  dt.items.add(new File([text], 'deep-bass.sound.lunar', { type: 'application/json' }));
  blk.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: dt }));
  blk.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }));
  blk.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
  await new Promise((r) => setTimeout(r, 1200));
  const card = document.querySelector('.ed-arrive');
  if (!card) return { card: false };
  return { card: true, head: card.querySelector('.ed-arrive-h').textContent, dl: [...card.querySelectorAll('dt, dd')].map((x) => x.textContent),
    ram: (card.querySelector('.ed-arrive-ram') || {}).textContent, buttons: [...card.querySelectorAll('button')].map((b) => b.textContent) };
});
report.arrived = arrived;
check('a sound file dropped on a sound says what it replaces and what it brings (here C refuses: it does not fit)', arrived.card && arrived.dl[0] === 'Replaces' && /^Sound 2: .*Macro/.test(arrived.dl[1]) && arrived.dl[2] === 'Brings' && /Deep space bass.*Shapes.*In1 Filter.*1 module and 1 cable/.test(arrived.dl[3]) && /cannot go into Sound 2/.test(arrived.head), arrived);
await shot('v1-arrival-refused.png', '.ed-arrive');
await page.evaluate(() => { const b = [...document.querySelectorAll('.ed-arrive button')].find((x) => /Dismiss|Cancel/.test(x.textContent)); if (b) b.click(); });
await wait(300);
// A rack that fits: what it replaces, what it brings, the RAM after, and Load.
await sel('p1', 'mod');
await page.evaluate(() => { window.fm1.editor.state.view = 'library'; window.fm1.editor.select('s2', { view: 'library' }); });
await wait(700);
const fits = await page.evaluate(async () => {
  const text = await (await fetch('examples/wobble.mods.lunar')).text();
  const blk = document.querySelector('.ed-drop[data-block="p1"]');
  const dt = new DataTransfer();
  dt.items.add(new File([text], 'wobble.mods.lunar', { type: 'application/json' }));
  blk.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: dt }));
  blk.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
  await new Promise((r) => setTimeout(r, 1200));
  const card = document.querySelector('.ed-arrive');
  if (!card) return { card: false };
  return { card: true, head: card.querySelector('.ed-arrive-h').textContent, dl: [...card.querySelectorAll('dt, dd')].map((x) => x.textContent),
    ram: (card.querySelector('.ed-arrive-ram') || {}).textContent, buttons: [...card.querySelectorAll('button')].map((b) => b.textContent) };
});
report.fits = fits;
check('a rack that fits says what it replaces and brings, the RAM after, and offers Load', fits.card && fits.dl[0] === 'Replaces' && /^\d+ modules? and \d+ cables?$/.test(fits.dl[1]) && fits.dl[2] === 'Brings' && /Wobble.*2 modules and 3 cables/.test(fits.dl[3]) && /^RAM \d+ % of the FM-1's memory after it$/.test(fits.ram || '') && fits.buttons[0] === 'Load into the mod rack', fits);
await shot('v1-arrival.png', '.ed-arrive');
await page.evaluate(() => { const b = [...document.querySelectorAll('.ed-arrive button')].find((x) => x.textContent === 'Cancel'); if (b) b.click(); });
await wait(300);
await sel('s2', 'flow');
// An effects file on a sound: what it replaces is the inserts; a wrong kind is refused in C's words with the article right.
const wrongKind = await page.evaluate(async () => {
  const text = await (await fetch('examples/space-verbs.fx.lunar')).text();
  const blk = document.querySelector('.ed-flow .ed-block[data-block="s2"]');
  const dt = new DataTransfer();
  dt.items.add(new File([text], 'space-verbs.fx.lunar', { type: 'application/json' }));
  blk.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer: dt }));
  blk.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
  await new Promise((r) => setTimeout(r, 1200));
  const card = document.querySelector('.ed-arrive');
  return card ? (card.querySelector('.ed-arrive-w') || {}).textContent : null;
});
check('C\'s kind refusal has its article right: "A sound, not an effects chain, was expected."', wrongKind === 'A sound, not an effects chain, was expected.', wrongKind);
await page.evaluate(() => { const b = [...document.querySelectorAll('.ed-arrive button')].find((x) => /Dismiss|Cancel/.test(x.textContent)); if (b) b.click(); });

// ---- 5. A/B: picks, Make B from the picks, and A and B back after a reload ----------------------
await sel('s2.in1', 'sound');
const abSetup = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  const blk = st.mirror.blocks.get('s2.in1');
  const e = ed.meta.engine(blk.engine);
  const ps = e.params.filter((p) => p.type === 'float').slice(1, 3);
  return { ps: ps.map((p) => ({ uid: p.uid, name: p.name, def: blk.values.get(p.uid) })) };
});
await page.evaluate(() => window.fm1.editor.project.keepA());
await wait(700);
for (const p of abSetup.ps) { await page.focus(`[data-fk="s2.in1:${p.uid}"]`); for (let i = 0; i < 6; ++i) await page.keyboard.press('ArrowRight'); }
await wait(900);
const val = (uid) => page.evaluate((uid) => window.fm1.editor.state.mirror.blocks.get('s2.in1').values.get(uid), uid);
const bVals = [await val(abSetup.ps[0].uid), await val(abSetup.ps[1].uid)];
await page.evaluate(async () => { await window.fm1.editor.project.switchAB(); });
await wait(900);
const aVals = [await val(abSetup.ps[0].uid), await val(abSetup.ps[1].uid)];
await page.evaluate(async () => { await window.fm1.editor.project.switchAB(); });
await wait(900);
check('A and B differ in the two edited parameters (A as kept, B as edited)', aVals[0] !== bVals[0] && aVals[1] !== bVals[1], { aVals, bVals });
await page.evaluate(() => { window.fm1.editor.state.view = 'ab'; window.fm1.editor.select('s2.in1', { view: 'ab' }); });
await wait(600);
const abView = await page.evaluate(() => ({ rows: document.querySelectorAll('.ed-ab-diff li').length, picks: document.querySelectorAll('.ed-ab-diff li [data-pick]').length, count: (document.querySelector('.ed-ab-count') || {}).textContent,
  make: (document.querySelector('.ed-ab-makeb') || {}).disabled }));
report.abView = abView;
check('the difference list has a pick for every row (A or B), all B to begin with, and Make B is off until one is picked from A', abView.rows >= 2 && abView.picks === abView.rows * 2 && /^\d+ from B, 0 from A$/.test(abView.count || '') && abView.make === true, abView);
// Pick the first row from A.
await page.evaluate(() => { document.querySelector('.ed-ab-diff li [data-pick="A"]').click(); });
await wait(300);
const abPicked = await page.evaluate(() => ({ count: (document.querySelector('.ed-ab-count') || {}).textContent, make: document.querySelector('.ed-ab-makeb').disabled, first: document.querySelector('.ed-ab-diff li').textContent }));
const rowPath = abPicked.first;
check('picking a row from A updates the count and offers Make B from the picks', /^\d+ from B, 1 from A$/.test(abPicked.count) && abPicked.make === false, abPicked);
await shot('v1-ab-picks.png', '.ed-ab');
const histBefore = await page.evaluate(() => window.fm1.editor.history.entries.length);
await page.click('.ed-ab-makeb');
await wait(2500);
const made = await page.evaluate(() => ({ last: window.fm1.editor.history.entries.slice(-1)[0], n: window.fm1.editor.history.entries.length }));
const mixed = [await val(abSetup.ps[0].uid), await val(abSetup.ps[1].uid)];
report.made = { histBefore, n: made.n, last: made.last && made.last.label, mixed, aVals, bVals };
const diffs = await page.evaluate(() => (window.fm1.editor.state.ab.diff || []).map((c) => c.path));
check('Make B from the picks loads B with A\'s value in the picked row and B\'s in the rest, as one step in the history', (mixed[0] === aVals[0] || mixed[1] === aVals[1]) && (mixed[0] === bVals[0] || mixed[1] === bVals[1]) && made.n === histBefore + 1 && made.last.label === 'Make B from the picks', { mixed, aVals, bVals, made: report.made, diffs });
await page.evaluate(() => window.fm1.editor.undo());
await wait(2200);
const undone = [await val(abSetup.ps[0].uid), await val(abSetup.ps[1].uid)];
check('one undo puts the project back as B was', undone[0] === bVals[0] && undone[1] === bVals[1], { undone, bVals });
await page.evaluate(() => window.fm1.editor.redo());
await wait(2200);
const redone = [await val(abSetup.ps[0].uid), await val(abSetup.ps[1].uid)];
check('redo makes it again', redone[0] === mixed[0] && redone[1] === mixed[1], { redone, mixed });
// A and B come back after a reload (IndexedDB's `snapshots`).
const stored = await page.evaluate(async () => { await new Promise((r) => setTimeout(r, 500)); const all = await window.fm1.files.store.all('snapshots'); return all.map((x) => ({ id: x.id, A: !!x.A, B: !!x.B, playing: x.playing, title: x.title })); });
check('A and B are kept in this browser\'s `snapshots` store', stored.length === 1 && stored[0].id === 'ab:project' && stored[0].A && stored[0].B, stored);
await page.reload();
await page.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 15000 });
await page.click('[data-layout="workbench"]');
await page.click('#power-on');
await page.waitForFunction(() => window.fm1.editor.state.mirror && window.fm1.editor.state.panelView && window.fm1.editor.state.mirror.blocks.size > 6, null, { timeout: 30000 });
await page.addScriptTag({ path: new URL('./layout-probe.js', import.meta.url).pathname });
await page.click('[data-layout="editor"]');
await wait(4200);
const back = await page.evaluate(() => { const ab = window.fm1.editor.state.ab; return { A: !!ab.A, B: !!ab.B, playing: ab.playing }; });
check('after a reload A and B are back, and the compare view can switch', back.A && back.B && !!back.playing, back);
await page.evaluate(() => window.fm1.editor.select('s2', { view: 'ab' }));
await wait(500);
check('the Compare view says which is playing after the reload', await page.evaluate(() => /Hearing [AB]/.test(document.querySelector('.ed-ab-state').textContent)), await page.evaluate(() => document.querySelector('.ed-ab-state').textContent));


// ---- 9. phones: Add a cable in three steps, a long press that opens a block's menu -----------------
await loadExample();
await page.setViewportSize({ width: 375, height: 800 });
await wait(700);
await sel('p1', 'mod');
const phoneBefore = await page.evaluate(() => window.fm1.editor.state.mirror.cables.filter((c) => c.flags & 1 || c.src || c.dst).length);
await page.click('[data-fk="mx:add"]');
await wait(400);
const step = () => page.evaluate(() => ({ step: (document.querySelector('.ed-sheet-step') || {}).textContent, title: (document.querySelector('.ed-sheet-t') || {}).textContent,
  modal: (document.querySelector('.ed-sheet') || {}).getAttribute && document.querySelector('.ed-sheet').getAttribute('aria-modal'), focus: document.activeElement && document.activeElement.getAttribute('aria-label') }));
const st1 = await step();
check('on a phone, Add a cable opens a sheet at step 1 of 3: the source', st1.step === 'Step 1 of 3 · From' && st1.title === 'Add a cable' && st1.modal === 'true' && st1.focus === 'Cable from', st1);
await page.selectOption('.ed-sheet select', { label: '2 LFO Out' });
await page.click('.ed-sheet-go');
await wait(300);
const st2 = await step();
check('step 2 is the destination', st2.step === 'Step 2 of 3 · To' && st2.focus === 'Cable to', st2);
const destLabel = await page.evaluate(() => [...document.querySelector('.ed-sheet select').options].map((o) => o.textContent).find((t) => /S3 .*Timbre/.test(t)));
await page.selectOption('.ed-sheet select', { label: destLabel });
await page.click('.ed-sheet-go');
await wait(900);
const st3 = await page.evaluate(() => ({ step: document.querySelector('.ed-sheet-step').textContent, sum: document.querySelector('.ed-sheet-sum').textContent, verdict: document.querySelector('.ed-sheet-verdict').textContent, amt: document.querySelector('.ed-sheet-amt').textContent }));
check('step 3 is the amount, with the pair and C\'s verdict before the cable is made', st3.step === 'Step 3 of 3 · Amount' && /^2 LFO Out → S3 .*Timbre$/.test(st3.sum) && /^Runs\.$/.test(st3.verdict) && st3.amt === '+25 %', st3);
await page.evaluate(() => { const r = document.querySelector('.ed-sheet-range'); r.value = '40'; r.dispatchEvent(new Event('input', { bubbles: true })); });
await shot('v1-sheet-amount.png');
await page.click('.ed-sheet-go');
await wait(1200);
const phoneMade = await page.evaluate(() => { const st = window.fm1.editor.state; const i = st.mirror.cables.findIndex((c) => (c.flags & 1) && c.src === 64 + 8 * 1 + 0 && window.fm1.editor.mm.unitKey(c.unit) === 's3'); return { i, amount: i >= 0 ? st.mirror.cables[i].amount : null, sheet: !!document.querySelector('.ed-sheet'), n: st.mirror.cables.filter((c) => c.flags & 1).length }; });
check('Make the cable puts it in the first empty slot with the chosen amount (40 %), and closes the sheet', phoneMade.i >= 0 && Math.round(phoneMade.amount / 163.84) === 40 && !phoneMade.sheet, phoneMade);
// The sheet keeps the keys: Esc closes it and the focus goes back.
await page.click('[data-fk="mx:add"]');
await wait(300);
await page.keyboard.press('Escape');
await wait(200);
const esc = await page.evaluate(() => ({ open: !!document.querySelector('.ed-sheet'), focus: document.activeElement && document.activeElement.dataset.fk }));
check('Esc closes the sheet and gives the focus back to the button', !esc.open && esc.focus === 'mx:add', esc);
// A long press on a block: a touch held half a second without moving.
await sel('s2', 'flow');
const press = async (selector, hold) => page.evaluate(async ([selector, hold]) => {
  const n = document.querySelector(selector);
  const r = n.getBoundingClientRect();
  const o = { bubbles: true, cancelable: true, pointerType: 'touch', pointerId: 7, isPrimary: true, button: 0, clientX: r.left + 12, clientY: r.top + 12 };
  n.dispatchEvent(new PointerEvent('pointerdown', o));
  await new Promise((res) => setTimeout(res, hold));
  n.dispatchEvent(new PointerEvent('pointerup', o));
  n.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  await new Promise((res) => setTimeout(res, 150));
  return { open: !!document.querySelector('.ed-sheet'), title: (document.querySelector('.ed-sheet-t') || {}).textContent, items: [...document.querySelectorAll('.ed-sheet .ed-sheet-i')].map((x) => x.textContent), sel: window.fm1.editor.state.selected, move: !!document.querySelector('.ed-sheet select.ed-sheet-move') };
}, [selector, hold]);
const short_ = await press('.ed-flow .ed-block[data-block="s2.in1"]', 200);
check('a short touch only selects the block (no menu)', !short_.open && short_.sel === 's2.in1', short_);
await sel('s2', 'flow');
const long_ = await press('.ed-flow .ed-block[data-block="s2.in1"]', 650);
report.longPress = long_;
check('a touch held half a second opens that block\'s menu: its page, another effect, move, export, library, link', long_.open && long_.title === 'S2 In1 · Filter' && long_.items.includes('Open its page') && long_.items.includes('Choose another…') && long_.items.includes('Export S2\'s effects…') && long_.items.includes('Save to my library') && long_.items.includes('Copy a link') && long_.move, long_);
check('the touch that opened the menu did not also select the block', long_.sel !== 's2.in1' || long_.sel === 's2', long_);
await shot('v1-block-menu.png');
await page.keyboard.press('Escape');
await wait(200);
await page.evaluate(() => document.querySelector('.ed-flow .ed-block[data-block="s2.in1"]').dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true })));
await wait(200);
check('the menu key (contextmenu) opens it too, for the keyboard', await page.evaluate(() => !!document.querySelector('.ed-sheet') && /In1/.test(document.querySelector('.ed-sheet-t').textContent)), 'contextmenu');
await page.evaluate(() => [...document.querySelectorAll('.ed-sheet .ed-sheet-i')].find((x) => x.textContent === 'Open its page').click());
await wait(400);
check('"Open its page" selects the block and closes the menu', await page.evaluate(() => !document.querySelector('.ed-sheet') && window.fm1.editor.state.selected === 's2.in1'), 'open its page');
await page.setViewportSize({ width: 1440, height: 1000 });
await wait(700);

// ---- the new UI states, looked at by the layout probe (no overlap, no clipping, no sideways scroll) ---
await loadMods(loopFile);
await sel('s2.in1', 'sound');
await page.evaluate(() => window.fm1.editor.project.keepA());
await wait(600);
await page.focus(`[data-fk="s2.in1:${abSetup.ps[0].uid}"]`);
for (let i = 0; i < 4; ++i) await page.keyboard.press('ArrowRight');
await wait(700);
await page.evaluate(async () => { await window.fm1.editor.project.switchAB(); });
await wait(900);
const probeViews = [['sound', () => sel('s2.in1', 'sound')], ['flow', () => sel('s2', 'flow')],
  ['mod-table', async () => { await sel('p1', 'mod'); await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Table'); if (t) t.click(); }); await wait(400); }],
  ['mod-map', async () => { await sel('p1', 'mod'); await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Map'); if (t) t.click(); }); await wait(600); }],
  ['slot', async () => { await sel('c2', 'mod'); await wait(300); }],
  ['compare', () => sel('s2', 'ab')]];
const faults = {};
for (const w of [1440, 1024, 768, 375]) {
  await page.setViewportSize({ width: w, height: 1000 });
  await wait(700);
  for (const [name, go] of probeViews) { await go(); await wait(300); faults[`${w}-${name}`] = await page.evaluate(() => window.lunarLayoutProbe()); if ((w === 375 && ['sound', 'mod-table', 'compare'].includes(name)) || (w === 1024 && name === 'sound')) await page.screenshot({ path: join(out, `v1-${w}-${name}.png`), fullPage: false }); }
  if (w === 375) {
    await page.evaluate(() => { document.querySelector('.ed-flow') || window.fm1.editor.select('s2', { view: 'flow' }); });
    await sel('s2', 'flow');
    await page.evaluate(() => document.querySelector('.ed-flow .ed-block[data-block="s2.in1"]').dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true })));
    await wait(300);
    faults['375-menu-open'] = await page.evaluate(() => window.lunarLayoutProbe());
    await page.keyboard.press('Escape');
  }
}
await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Table'); if (t) t.click(); });
await page.setViewportSize({ width: 1440, height: 1000 });
await wait(700);
report.faults = faults;
const dirty = Object.entries(faults).filter(([, v]) => v.length);
check('the new UI at 1,440, 1,024, 768 and 375 px (modulated rows, counts and bars, late marks, the slot, Compare with picks, a menu): no overlap, clipping or sideways scroll', dirty.length === 0, dirty.slice(0, 4).map(([k, v]) => `${k}: ${v.slice(0, 3).join(' | ')}`));

// ---- 10. §17's leftovers ---------------------------------------------------------------------
// axe-core on the layouts: the editor at 1,440 and 1,024 px in every view, and at 375 px.
const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
let axeOk = true;
try { await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') }); } catch (err) { axeOk = false; report.logs.push(`axe-core is not installed: ${err.message}`); }
check('axe-core is available to the page test', axeOk, 'npm install axe-core in the Playwright directory');
async function axe(label) {
  const r = await page.evaluate(async () => {
    const res = await window.axe.run(document.querySelector('.ed'), { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } });
    return res.violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, sample: v.nodes.slice(0, 2).map((x) => `${x.target.join(' ')} :: ${(x.failureSummary || '').split('\n').slice(1, 2).join('')}`) }));
  });
  return r;
}
const axeViews = [['flow', () => sel('s2', 'flow')], ['sound', () => sel('s2', 'sound')], ['mod-table', async () => { await sel('p1', 'mod'); await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Table'); if (t) t.click(); }); await wait(400); }],
  ['mod-map', async () => { await sel('p1', 'mod'); await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Map'); if (t) t.click(); }); await wait(500); }],
  ['library', () => sel('s2', 'library')], ['memory', () => sel('s2', 'memory')], ['compare', () => sel('s2', 'ab')]];
const axeAll = {};
if (axeOk) {
  for (const w of [1440, 1024]) {
    await page.setViewportSize({ width: w, height: 1000 });
    await wait(600);
    for (const [name, go] of axeViews) { await go(); await wait(300); axeAll[`${w}-${name}`] = await axe(name); }
  }
  await page.setViewportSize({ width: 375, height: 800 });
  await wait(600);
  for (const [name, go] of [axeViews[0], axeViews[1], axeViews[2]]) { await go(); await wait(300); axeAll[`375-${name}`] = await axe(name); }
  await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Table'); if (t) t.click(); });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await wait(600);
  report.axe = axeAll;
  const bad = Object.entries(axeAll).filter(([, v]) => v.length);
  check('axe-core finds no violation in any view at 1,440, 1,024 or 375 px (WCAG 2.x A and AA, and its best practices)', bad.length === 0, bad.slice(0, 4).map(([k, v]) => `${k}: ${JSON.stringify(v.slice(0, 3))}`));
}

// Reduced motion: no animation runs, and the telemetry is drawn at half the rate (15 a second).
await page.evaluate(() => window.scrollTo(0, 0));
await sel('s2', 'flow');
await wait(500);
await page.evaluate(() => {
  const ed = window.fm1.editor;
  window.__frames = 0;
  const was = ed.chains.onTelemetry;
  ed.chains.onTelemetry = (f) => { window.__frames += 1; return was(f); };
  window.__restore = () => { ed.chains.onTelemetry = was; };
});
await noteOn(60);
const count = async () => { await page.evaluate(() => { window.__frames = 0; }); await wait(2000); return page.evaluate(() => window.__frames); };
const normal = await count();
await page.emulateMedia({ reducedMotion: 'reduce' });
await wait(300);
const reduced = await count();
const anims = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').map((a) => a.animationName || a.constructor.name));
await page.emulateMedia({ reducedMotion: 'no-preference' });
report.reduced = { normal, reduced, anims };
check('under reduced motion the telemetry is drawn about half as often (15 a second)', normal >= 20 && reduced <= normal * 0.7 && reduced >= 4, report.reduced);
check('under reduced motion no animation is running', anims.length === 0, anims);

// Telemetry stops while the editor is hidden, and starts again when it is seen.
const hiddenRun = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  let raw = 0;
  const on = (e) => { if (e.data && e.data.type === 'telemetry') raw += 1; };
  st.port.addEventListener('message', on);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  await wait(400);
  const seen = { on: st.teleOn, sig: st.teleSig.length };
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
  document.dispatchEvent(new Event('visibilitychange'));
  await wait(500);
  raw = 0; window.__frames = 0;
  await wait(1200);
  const hidden = { on: st.teleOn, sig: st.teleSig.length, raw, frames: window.__frames };
  delete document.visibilityState;
  document.dispatchEvent(new Event('visibilitychange'));
  await wait(900);
  const back = { on: st.teleOn, frames: window.__frames };
  st.port.removeEventListener('message', on);
  window.__restore();
  return { seen, hidden, back };
});
await noteOff(60);
report.hiddenRun = hiddenRun;
check('the telemetry stops while the editor is hidden: nothing is subscribed, nothing arrives, nothing is drawn', hiddenRun.seen.on && !hiddenRun.hidden.on && hiddenRun.hidden.sig === 0 && hiddenRun.hidden.raw === 0 && hiddenRun.hidden.frames === 0, hiddenRun);
check('and starts again when it is seen', hiddenRun.back.on && hiddenRun.back.frames > 5, hiddenRun.back);

// A lock playing changes no base (the example plays a lock lane on its second track).
await loadExample();
const lockRun = await page.evaluate(async () => {
  const ed = window.fm1.editor, st = ed.state;
  const bases = () => JSON.stringify([...st.mirror.blocks].map(([k, b]) => [k, [...b.values]]));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const before = bases();
  const n0 = ed.history.entries.length;
  let moved = 0;
  const port = window.fm1.node.port;
  port.postMessage({ type: 'button', button: 12, down: true }); port.postMessage({ type: 'button', button: 12, down: false });
  for (let i = 0; i < 8; ++i) { await wait(500); if (bases() !== before) ++moved; }
  port.postMessage({ type: 'button', button: 12, down: true }); port.postMessage({ type: 'button', button: 12, down: false });
  await wait(600);
  return { same: bases() === before, moved, entries: ed.history.entries.length - n0 };
});
report.lockRun = lockRun;
check('a lock playing for four seconds changes no base value in the editor and adds nothing to its history', lockRun.same && lockRun.moved === 0 && lockRun.entries === 0, lockRun);

// The main thread's budget while a slider is dragged: no long task over 50 ms; each handler under 4 ms.
await sel('s2.in1', 'sound');
await page.evaluate(() => {
  window.__long = []; window.__moves = []; window.__tele = [];
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(e.duration); }).observe({ entryTypes: ['longtask'] }); } catch (err) { window.__noLong = true; }
  const ed = window.fm1.editor;
  const was = ed.chains.onTelemetry;
  ed.chains.onTelemetry = (f) => { const t = performance.now(); const r = was(f); window.__tele.push(performance.now() - t); return r; };
  let t0 = 0;
  window.addEventListener('pointermove', () => { t0 = performance.now(); }, true);
  window.addEventListener('pointermove', () => { if (t0) window.__moves.push(performance.now() - t0); }, false);
});
await noteOn(60);
const box = await page.locator(`[data-fk="s2.in1:${abSetup.ps[0].uid}"]`).boundingBox();
await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2);
await page.mouse.down();
for (let i = 0; i < 120; ++i) { await page.mouse.move(box.x + box.width * (0.2 + 0.6 * (i % 40) / 40), box.y + box.height / 2); await wait(16); }
await page.mouse.up();
await noteOff(60);
const budget = await page.evaluate(() => { const p95 = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length * 0.95)] : 0; };
  return { long: window.__long, noLong: !!window.__noLong, moves: window.__moves.length, movesP95: p95(window.__moves), tele: window.__tele.length, teleP95: p95(window.__tele), teleMax: Math.max(0, ...window.__tele) }; });
report.budget = budget;
check('while a slider is dragged no long task passes 50 ms (Chromium measures it; elsewhere the handlers\' own cost stands)', budget.moves >= 60 && (budget.noLong || budget.long.every((d) => d <= 50)), budget);
check('a pointer move costs the page under 4 ms of script (95th percentile), and a telemetry frame too', budget.movesP95 < 4 && budget.teleP95 < 4 && budget.tele > 20, budget);

// ---- 11. A/B does not stop the transport ------------------------------------------------------------
// The editor review: switching A and B loaded a whole project and C reset the sequencer, so the transport
// stopped at the first X. Every transport message the worklet posts is recorded; none may say "stopped".
await loadExample();
await page.setViewportSize({ width: 1440, height: 1000 });
await sel('s2', 'ab');
await page.evaluate(() => window.fm1.editor.project.keepA());
await wait(700);
await page.evaluate(() => {
  const sim = window.fm1;
  let cur = sim.seq;
  window.__seqLog = [];
  Object.defineProperty(sim, 'seq', { configurable: true, get: () => cur, set: (v) => { cur = v; window.__seqLog.push(v.playing); } });
  const port = sim.node.port;
  port.postMessage({ type: 'button', button: 12, down: true }); port.postMessage({ type: 'button', button: 12, down: false });
});
await wait(900);
const playingAt = () => page.evaluate(() => ({ playing: !!(window.fm1.seq && window.fm1.seq.playing), log: window.__seqLog.slice() }));
const t0 = await playingAt();
check('PLAY starts the transport (the test\'s own start)', t0.playing, t0);
for (const [label, scope] of [['project', 'project'], ['a sound', 0]]) {
  if (scope !== 'project') {
    await page.evaluate((k) => { const b = [...document.querySelectorAll('.ed-ab-scope button')].find((x) => x.textContent === `Sound ${k + 1}`); if (b) b.click(); }, scope);
    await wait(300);
    await page.evaluate(() => window.fm1.editor.project.keepA());
    await wait(700);
  }
  const mark = (await playingAt()).log.length;
  await page.evaluate(async () => { await window.fm1.editor.project.switchAB(); });
  await wait(900);
  const toA = await playingAt();
  await page.evaluate(async () => { await window.fm1.editor.project.switchAB(); });
  await wait(900);
  const toB = await playingAt();
  check(`switching A/B (${label}) twice keeps the transport playing: no "stopped" is posted, and it plays after each`,
    toA.playing && toB.playing && !toB.log.slice(mark).includes(false), { label, mark, toA: toA.playing, toB: toB.playing, log: toB.log.slice(mark) });
}
// Make B from the picks and an undo of it are project loads too.
await page.evaluate(() => { const b = [...document.querySelectorAll('.ed-ab-scope button')].find((x) => x.textContent === 'Project'); if (b) b.click(); });
await wait(300);
await page.evaluate(() => window.fm1.editor.project.keepA());
await wait(700);
const ident = await page.evaluate(async () => {
  const f = window.fm1.files, ed = window.fm1.editor;
  const pid0 = f.pid;
  await ed.project.switchAB();
  await new Promise((r) => setTimeout(r, 700));
  const pidAfterSwitch = f.pid;
  await ed.project.switchAB();
  await new Promise((r) => setTimeout(r, 700));
  return { pid0, pidAfterSwitch, pidBack: f.pid, playing: !!window.fm1.seq.playing };
});
check('the project\'s identity is kept through A/B\'s own loads', !!ident.pid0 && ident.pid0 === ident.pidAfterSwitch && ident.pid0 === ident.pidBack && ident.playing, ident);

// ---- 12. the filters (a long list, the picker, the matrix) ---------------------------------------------
// Safari's dropdown ignores `hidden` on an <option>, so a filter that only hides them does nothing there: the
// options themselves must be fewer.
await loadExample();
await page.setViewportSize({ width: 1440, height: 1000 });
// The smallest sound with a long list that the example's sound 4 can hold (the biggest would not fit: C refuses it).
const longList = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const cands = ed.meta.doc.engines.filter((e) => e.kind === 'sound' && e.params.some((x) => x.type === 'enum' && x.entries.length > 24)).sort((a, b) => a.ram - b.ram);
  for (const e of cands) {
    ed.chains.choose('s4', e.id);
    await new Promise((r) => setTimeout(r, 1500));
    const b = ed.state.mirror.blocks.get('s4');
    if (b && b.engine === e.id) {
      const p = e.params.find((x) => x.type === 'enum' && x.entries.length > 24);
      return { id: e.id, uid: p.uid, name: p.name, entries: p.entries };
    }
  }
  return null;
});
check('some sound with an enum of more than 24 entries (the search control) fits in sound 4', !!longList, longList && longList.id);
if (longList) {
  await sel('s4', 'sound');
  const q = (longList.entries[Math.floor(longList.entries.length / 2)].split(/\s+/).find((w) => w.length >= 3) || 'a').slice(0, 3).toLowerCase();
  const hits = longList.entries.filter((n) => n.toLowerCase().includes(q)).length;
  const base = `.ed-insp[data-block="s4"] .ed-row[data-uid="${longList.uid}"]`;
  const optionsNow = () => page.evaluate((b) => { const s = document.querySelector(`${b} select.ed-select`); return s ? { n: s.options.length, texts: [...s.options].map((o) => o.textContent), cur: s.selectedOptions[0] && s.selectedOptions[0].textContent } : null; }, base);
  const all = await optionsNow();
  await page.fill(`${base} .ed-find`, q);
  await wait(150);
  const some = await optionsNow();
  const curHit = longList.entries[Math.round(await page.evaluate(([k, uid]) => window.fm1.editor.state.mirror.blocks.get(k).values.get(uid), ['s4', longList.uid]))];
  const want = hits + (curHit && !curHit.toLowerCase().includes(q) ? 1 : 0);
  check('a long list\'s filter rebuilds the select\'s options: only the matches (and the chosen entry) remain', all && all.n === longList.entries.length && some && some.n === want && some.n < all.n && some.texts.every((t) => t.toLowerCase().includes(q) || t === curHit), { q, hits, want, all: all && all.n, some: some && some.n });
  await shot('v1-longlist-filter.png', base);
  // Choosing from the filtered list sets the parameter, and the list keeps the chosen entry.
  const pickText = some.texts.find((t) => t !== curHit) || curHit;
  await page.selectOption(`${base} select.ed-select`, { label: pickText });
  await wait(500);
  const chosen = await page.evaluate(([k, uid]) => window.fm1.editor.state.mirror.blocks.get(k).values.get(uid), ['s4', longList.uid]);
  check('choosing from the filtered list sets the parameter', longList.entries[Math.round(chosen)] === pickText, { pickText, chosen });
  await page.fill(`${base} .ed-find`, '');
  await wait(150);
  check('clearing the filter brings every entry back', (await optionsNow()).n === longList.entries.length, '');
  // The picker's filter: buttons, hidden by the attribute, on every browser.
  await page.click('.ed-insp[data-block="s4"] [data-fk="s4:pick"]');
  await page.waitForSelector('.ed-picker .ed-find');
  await wait(900);
  const pickNames = await page.evaluate(() => [...document.querySelectorAll('.ed-picker .ed-pick-o')].filter((o) => o.offsetParent !== null).map((o) => o.querySelector('.ed-pick-n').textContent.toLowerCase()));
  const pq = (pickNames[3] || pickNames[1] || 'a').slice(0, 2);
  const pwant = pickNames.filter((n) => n.includes(pq)).length;
  await page.fill('.ed-picker .ed-find', pq);
  await wait(150);
  await shot('v1-picker-filter.png', '.ed-picker');
  const pickSome = await page.evaluate(() => [...document.querySelectorAll('.ed-picker .ed-pick-o')].filter((o) => o.offsetParent !== null).map((o) => o.querySelector('.ed-pick-n').textContent.toLowerCase()));
  check('the picker\'s filter shows only the choices naming what was typed (a rule that set `display` once kept every one on show)', pickNames.length > 3 && pickSome.length === pwant && pwant > 0 && pwant < pickNames.length && pickSome.every((t) => t.includes(pq)), { pq, all: pickNames.length, want: pwant, some: pickSome.length });
  await page.fill('.ed-picker .ed-find', '');
  await wait(150);
  check('and clearing it brings them all back', (await page.evaluate(() => [...document.querySelectorAll('.ed-picker .ed-pick-o')].filter((o) => o.offsetParent !== null).length)) === pickNames.length, '');
  await page.keyboard.press('Escape');
  await wait(200);
}
// The matrix filter: rows by what they read.
await loadExample();
await sel('p1', 'mod');
await page.evaluate(() => { const t = [...document.querySelectorAll('.ed-mapsw [role=radio]')].find((b) => b.textContent === 'Table'); if (t) t.click(); });
await wait(500);
const rowsText = () => page.evaluate(() => [...document.querySelectorAll('.ed-mx-body .ed-mx-r')].map((r) => [...r.querySelectorAll('select')].map((s) => (s.selectedOptions[0] || {}).textContent || '').join(' ').toLowerCase()));
const mxAll = await rowsText();
const word = (mxAll.find((t) => /\w{3}/.test(t)) || '').split(/\s+/).find((w) => w.length >= 3 && mxAll.some((t) => !t.includes(w))) || '';
if (word) {
  await page.fill('[data-fk="mx:find"]', word);
  await wait(200);
  const mxSome = await rowsText();
  check('the matrix filter keeps the cables that read what was typed, and no others', mxSome.length > 0 && mxSome.length < mxAll.length && mxSome.every((t) => t.includes(word)), { word, all: mxAll.length, some: mxSome.length });
  await page.fill('[data-fk="mx:find"]', 'zzzzzz');
  await wait(200);
  check('a filter that matches nothing says so', await page.evaluate(() => /No cable matches/.test(document.querySelector('.ed-mx-body').textContent)), '');
  await page.fill('[data-fk="mx:find"]', '');
  await wait(200);
  check('and clearing it brings the cables back', (await rowsText()).length === mxAll.length, '');
} else {
  check('the example has cables to filter', false, mxAll);
}

// ---- 13. storage: an upgrade an older tab blocks, and a newer tab upgrading --------------------------------
// Version 2 of the database came with the editor's `snapshots`. A tab opened after a deploy, while a tab of the
// old page holds version 1, used to take the blocked request for "no storage" for good; and the connection set
// no versionchange handler, so it would block the next upgrade in turn.
{
  const ctx = await browser.newContext();
  const holder = await ctx.newPage();
  await holder.goto(new URL('source.json', url).href);      // the page's origin, nothing else loaded
  await holder.evaluate(() => new Promise((resolve, reject) => {
    const req = indexedDB.open('lunar-modulator', 1);        // held open like the old page: no versionchange handler
    req.onupgradeneeded = () => {
      const d = req.result;
      d.createObjectStore('files', { keyPath: 'id', autoIncrement: true });
      d.createObjectStore('autosave');
      d.createObjectStore('recent', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = () => { window.__old = req.result; resolve(true); };
    req.onerror = () => reject(req.error);
  }));
  const tab = await ctx.newPage();
  tab.on('pageerror', (e) => report.logs.push(`pageerror (storage tab): ${e.message}`));
  await tab.goto(url);
  const blocked = await tab.evaluate(async () => {
    const s = window.fm1.files.store;
    const ok = await s.available();
    await new Promise((r) => setTimeout(r, 300));
    await s.put('snapshots', { id: 'kept', n: 1 }, 'kept');
    return { ok, status: s.status(), memory: (await s.get('snapshots', 'kept')) !== null, note: (document.getElementById('file-notice') || {}).textContent || '' };
  });
  await tab.locator('#file-notice').screenshot({ path: join(out, 'v1-storage-blocked.png') }).catch(() => {});
  check('with an older tab holding the database, the open is blocked, not failed: memory for now, and the page says why',
    !blocked.ok && blocked.status.blocked && !blocked.status.failed && blocked.memory && /older version/.test(blocked.note), blocked);
  await holder.evaluate(() => window.__old.close());
  let freed = true;
  try { await tab.waitForFunction(() => window.fm1.files.store.status().open, null, { timeout: 8000 }); } catch (err) { freed = false; }
  const after = freed ? await tab.evaluate(async () => {
    const s = window.fm1.files.store;
    await new Promise((r) => setTimeout(r, 500));
    return { ok: await s.available(), status: s.status(), note: (document.getElementById('file-notice') || {}).textContent || '' };
  }) : null;
  check('when the older tab lets go, the pending request goes through and storage is used from then on, with a notice', freed && after.ok && !after.status.blocked && /free again/.test(after.note), after);
  const flushed = await holder.evaluate(() => new Promise((resolve) => {
    const r = indexedDB.open('lunar-modulator');
    r.onsuccess = () => {
      const g = r.result.transaction('snapshots', 'readonly').objectStore('snapshots').get('kept');
      g.onsuccess = () => { r.result.close(); resolve(g.result || null); };
    };
    r.onerror = () => resolve(null);
  }));
  check('what the tab kept in memory while it waited is written to the database', !!flushed && flushed.n === 1, flushed);
  // A newer tab upgrades: this tab's connection closes on versionchange, so the upgrade is not blocked.
  const up = await holder.evaluate(() => new Promise((resolve) => {
    const r = indexedDB.open('lunar-modulator', 3);
    let blockedUp = false;
    r.onblocked = () => { blockedUp = true; };
    r.onupgradeneeded = () => {};
    r.onsuccess = () => { r.result.close(); resolve({ blocked: blockedUp }); };
    r.onerror = () => resolve({ error: String(r.error), blocked: blockedUp });
    setTimeout(() => resolve({ timeout: true, blocked: blockedUp }), 6000);
  }));
  const down = await tab.evaluate(async () => {
    const s = window.fm1.files.store;
    const k = await s.put('autosave', { name: 'x', bin: new Uint8Array(4), modified: 0 }, 'project');
    return { open: s.status().open, put: k };
  });
  check('a newer tab\'s upgrade is not blocked by this one (its connection closes on versionchange), and this tab keeps working', !up.blocked && !up.timeout && !up.error && down.open === false && down.put === 'project', { up, down });
  await holder.evaluate(() => new Promise((resolve) => { const r = indexedDB.deleteDatabase('lunar-modulator'); r.onsuccess = r.onerror = r.onblocked = () => resolve(true); setTimeout(() => resolve(true), 2000); }));
  await ctx.close();
}

// ---- 14. stored A and B belong to a project, not to a title -------------------------------------------------
await loadExample();
await sel('s2', 'ab');
const own = await page.evaluate(async () => {
  const ed = window.fm1.editor, ab = ed.state.ab, f = window.fm1.files;
  await ed.project.keepA();
  await new Promise((r) => setTimeout(r, 600));
  const pid = f.pid, title = f.title, A = ab.A;
  const put = (p) => f.store.put('snapshots', { id: 'ab:project', scope: 'project', A, B: A, playing: 'B', title, pid: p, modified: Date.now() }, 'ab:project');
  const clear = () => Object.assign(ab, { A: null, B: null, playing: null });
  await put('another-project'); clear();
  const other = await ed.project.restoreAB();            // the same title, another project
  await put(undefined); clear();
  const none = await ed.project.restoreAB();             // a record with no identity (before this check existed)
  await put(pid); clear();
  const same = await ed.project.restoreAB();             // this project
  return { other, none, same, hasA: !!ab.A, pid: !!pid };
});
check('stored A and B come back for the same project and not for another of the same title, nor for a record without identity', own.pid && own.same === true && own.hasA && own.other === false && own.none === false, own);
const fresh = await page.evaluate(async () => {
  const f = window.fm1.files, before = f.pid;
  const bytes = new Uint8Array(await (await fetch('examples/first-orbit.lunar')).arrayBuffer());
  await f.load(bytes, { d: { enc: 2, kind: 'project', title: f.title }, before: false, quiet: true });
  await new Promise((r) => setTimeout(r, 300));
  await f.autosave();                                    // the same bytes as the last autosave, another project
  const saved = await f.store.get('autosave', 'project');
  return { before, after: f.pid, saved: saved && saved.pid };
});
check('opening a project again (even a file of the same name) is another project, and the autosave carries the new identity though its bytes are the same', !!fresh.before && !!fresh.after && fresh.before !== fresh.after && fresh.saved === fresh.after, fresh);

// ---- next stage: search selection and one-step batches -------------------------------
await page.evaluate(() => window.fm1.editor.project.openSearch());
await page.fill('.ed-search-in', '');
await page.keyboard.press('Shift+Enter');
const picks = await page.evaluate(() => ({ n: window.fm1.editor.state.searchPicks.length, text: document.querySelector('.ed-search-batch').textContent,
  shown: document.querySelectorAll('.ed-search-list [role=option]').length }));
check('Shift+Enter selects every match, including matches beyond the first 60 shown', picks.n > 60 && picks.shown === 60 && picks.text.includes(`${picks.n} matches selected`), picks);
await shot('editor-search-selection.png', '.ed-search-card');
await page.evaluate(() => window.fm1.editor.project.closeSearch(false));
await page.evaluate(() => window.fm1.editor.project.openSearch());
await page.fill('.ed-search-in', '>');
await page.keyboard.press('Shift+Enter');
const staleCableSetup = await page.evaluate(() => {
  const ed = window.fm1.editor, st = ed.state, picks = st.searchPicks;
  if (picks.length < 2) return { ready: false, picks: picks.length };
  const target = picks[0].index, source = picks[picks.length - 1].index;
  const before = st.mirror.cables.map((c) => ({ ...c }));
  if (JSON.stringify(before[target]) === JSON.stringify(before[source])) return { ready: false, picks: picks.length };
  window.__staleCableOriginal = before[target];
  st.mirror.cables[target] = { ...before[source] }; // simulate a slot replacement after Search captured its result
  return { ready: true, target, source, steps: ed.history.entries.length };
});
if (staleCableSetup.ready) {
  await page.getByRole('button', { name: 'Disable selected cables', exact: true }).click();
  const staleCableResult = await page.evaluate((setup) => {
    const ed = window.fm1.editor, st = ed.state;
    const result = { message: document.querySelector('.ed-search-batch [role=status]').textContent,
      steps: ed.history.entries.length, target: st.mirror.cables[setup.target] };
    // Restore the editor's pre-test state before continuing the ordinary batch scenario.
    st.mirror.cables[setup.target] = window.__staleCableOriginal;
    delete window.__staleCableOriginal;
    return result;
  }, staleCableSetup);
  check('a cable batch refuses a slot whose cable changed after Search captured it', /A selected cable changed/.test(staleCableResult.message) && staleCableResult.steps === staleCableSetup.steps, staleCableResult);
  await page.evaluate(() => window.fm1.editor.project.closeSearch(false));
} else {
  check('a cable batch has distinct cables available for stale-target regression', false, staleCableSetup);
  await page.evaluate(() => window.fm1.editor.project.closeSearch(false));
}
await page.evaluate(() => window.fm1.editor.project.openSearch());
await page.fill('.ed-search-in', '>');
const beforeBatch = await page.evaluate(() => ({ cables: JSON.stringify(window.fm1.editor.state.mirror.cables), steps: window.fm1.editor.history.entries.length }));
await page.keyboard.press('Shift+Enter');
await page.getByRole('button', { name: 'Disable selected cables', exact: true }).click();
await wait(1300);
const offBatch = await page.evaluate(() => ({ cables: window.fm1.editor.state.mirror.cables, steps: window.fm1.editor.history.entries.length }));
check('a batch disables the matching cables in one history step', offBatch.cables.every((c) => !(c.flags & 1)) && offBatch.steps === beforeBatch.steps + 1, offBatch);
await page.evaluate(() => window.fm1.editor.undo());
await wait(1200);
const batchUndo = await page.evaluate(() => JSON.stringify(window.fm1.editor.state.mirror.cables));
check('one undo restores every cable in the batch', batchUndo === beforeBatch.cables, batchUndo);
await page.evaluate(() => window.fm1.editor.redo());
await wait(1200);
const batchRedo = await page.evaluate(() => window.fm1.editor.state.mirror.cables.every((c) => !(c.flags & 1)));
check('one redo disables the entire batch again', batchRedo, batchRedo);
await page.evaluate(() => window.fm1.editor.undo());
await wait(1200);
await page.evaluate(() => window.fm1.editor.project.openSearch());
await page.fill('.ed-search-in', 'lfo rate');
await page.keyboard.press('Shift+Enter');
const paramBatch = await page.evaluate(() => window.fm1.editor.state.searchPicks.map((x) => ({ key: x.key, uid: x.p?.uid, value: x.p && window.fm1.editor.state.mirror.blocks.get(x.key).values.get(x.p.uid) })));
const beforeInvalid = await page.evaluate(() => window.fm1.editor.history.entries.length);
await page.fill('.ed-batch-value', 'not a number');
await page.getByRole('button', { name: 'Set selected parameters', exact: true }).click();
await wait(400);
const invalidBatch = await page.evaluate(() => ({ steps: window.fm1.editor.history.entries.length, message: document.querySelector('.ed-search-batch [role=status]').textContent }));
check('an invalid common value changes nothing and leaves the batch available to correct', invalidBatch.steps === beforeInvalid && /not a value/.test(invalidBatch.message), invalidBatch);
await page.fill('.ed-batch-value', '0.75');
await page.getByRole('button', { name: 'Set selected parameters', exact: true }).click();
await wait(1200);
const changedParams = await page.evaluate((xs) => xs.map((x) => window.fm1.editor.state.mirror.blocks.get(x.key).values.get(x.uid)), paramBatch);
check('compatible parameters accept one common value parsed by C', changedParams.length > 1 && changedParams.every((x) => x === 0.75), changedParams);
await page.evaluate(() => window.fm1.editor.undo());
await wait(1200);
const restoredParams = await page.evaluate((xs) => xs.map((x) => window.fm1.editor.state.mirror.blocks.get(x.key).values.get(x.uid)), paramBatch);
check('one undo restores each parameter to its own previous value', restoredParams.every((v, i) => v === paramBatch[i].value), { restoredParams, paramBatch });
// Gate telemetry is separate from GR, including silence and non-gated Types.
const gateResult = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  ed.chains.choose('m1', 'squash');
  await new Promise((r) => setTimeout(r, 800));
  ed.select('m1', { view: 'flow' });
  const uid = ed.meta.engine('squash').params.find((p) => p.name === 'Gate Rel').uid;
  const row = ed.rows.get(`m1:${uid}`);
  row.el.querySelector('[role=slider]').dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
  row.el.querySelector('[role=slider]').dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
  await new Promise((r) => setTimeout(r, 1800));
  return { text: document.querySelector('[data-block="m1"] [data-gate]')?.textContent,
    gr: document.querySelector('[data-block="m1"] [data-red]')?.textContent };
});
check('Squash shows its closed gate over silence separately from gain reduction', gateResult.text === 'Gate closed' && !gateResult.gr, gateResult);
await shot('editor-squash-gate.png');

writeFileSync(join(out, 'editor-v1.json'), JSON.stringify(report, null, 1));
await browser.close();
server.close();
const bad = Object.entries(report.checks).filter(([, ok]) => !ok);
console.log(`${report.browser}: ${Object.keys(report.checks).length - bad.length} of ${Object.keys(report.checks).length} checks pass`);
for (const w of report.why) console.log(`  FAIL ${w}`);
for (const l of report.logs.slice(0, 8)) console.log(`  log ${l}`);
process.exit(bad.length || report.logs.some((l) => l.startsWith('pageerror')) ? 1 : 0);
