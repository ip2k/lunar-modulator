// editor-ui.mjs -- the Advanced editor's shell, flow, sound, chains and
// modulation in headless Chromium (stages ED2 and ED3,
// notes/2026-10-06-web-editor.md §4, §7, §8, §10, §13, §14,
// §17). Runs in the Playwright container on aeon after editor.mjs
// (build-on-aeon.sh), never on the Mac:
//
//   node editor-ui.mjs WWW_DIR OUT_DIR
//
// Checks: the Panel layout loads none of the editor's files, and the first
// switch loads them; follow both ways (a turn of KNOB2 on the panel reaches
// the editor's row within a few frames and enters the history as the
// panel's; selecting M1 in the Flow opens it on the panel); the K1-K4 chips
// are the panel's knob map; an edit by the keyboard in EDIT then undo ends at
// the first state hash (the shadow Worker's), redo at the edited one; PLAY
// and EDIT (in EDIT no computer key reaches the FM-1, in PLAY no editor key
// edits; Ctrl+E and Esc switch); every module's inspector drawn from the
// metadata with no overflow at the Workbench's and the tablet's column
// widths; the Workbench and Editor layouts at 1,440 and 1,024 px with no
// sideways scroll, no label over its control, and screenshots to look at.
// ED3: a block moved by its keyboard twin and by a pointer drag, with C's
// verdict before the drop; a picker's RAM column; a refusal C makes, in the
// metadata's words, changing nothing; the matrix (a cable added, typed,
// its polarity set, one the planner leaves out); the rack (a module moved by
// keys, one chosen, one emptied); each undone to the state before it, the
// view aside; the rack's kinds among the inspectors; the Modulation view in
// the layouts.
// MIT licence, like the rest of this repository.

import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8768);
const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const report = { browser: `Chromium ${browser.version()} (Playwright, headless)`, checks: {}, logs: [], why: [] };
function check(name, ok, why) {
  report.checks[name] = !!ok;
  if (!ok) report.why.push(`${name}: ${typeof why === 'string' ? why : JSON.stringify(why)}`);
}

const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') report.logs.push(`error: ${m.text()}`); });
const requested = [];
page.on('request', (r) => requested.push(new URL(r.url()).pathname));
await page.goto(`${url}?load=examples/first-orbit.lunar`);
await page.waitForTimeout(500);
check('the Panel layout loads none of the editor', !requested.some((p) => p.includes('/editor/')), requested);

await page.click('[data-layout="workbench"]');
await page.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 10000 });
check('the first switch loads the editor', requested.some((p) => p.endsWith('/editor/editor.js')) &&
  requested.some((p) => p.endsWith('/editor/editor.css')), requested.filter((p) => p.includes('editor')));
await page.click('#power-on');
await page.waitForFunction(() => window.fm1.editor.state.mirror && window.fm1.editor.state.panelView &&
  window.fm1.editor.state.mirror.blocks.size > 6, null, { timeout: 20000 });
await page.waitForTimeout(400);

// The helpers the checks share: the project's hash through the shadow
// Worker, and a count of what the page sends the worklet.
await page.evaluate(() => {
  const sim = window.fm1;
  window.__sent = [];
  const post = sim.node.port.postMessage.bind(sim.node.port);
  sim.node.port.postMessage = (m, t) => { window.__sent.push(m.type); return post(m, t); };
  window.__hash = async () => {
    const id = 900000 + Math.floor(Math.random() * 1000);
    const bin = await new Promise((resolve) => {
      const on = (e) => { if (e.data && e.data.type === 'state-saved' && e.data.id === id) { sim.node.port.removeEventListener('message', on); resolve(e.data.bytes); } };
      sim.node.port.addEventListener('message', on);
      post({ type: 'state-save', kind: 1, arg: 0, plain: true, id });
    });
    const r = await sim.files.shadow('hash', { bin: bin.slice(0) });
    window.__bins = window.__bins || [];
    window.__bins.push(bin);
    const v = window.fm1.editor.state.panelView;
    return { hash: r.hash, bin: window.__bins.length - 1, view: `${v.mode}.${v.sound}.${v.slot}` };
  };
});

// ---- follow, panel to editor, and K1-K4 ----------------------------------------
const follow = await page.evaluate(async () => {
  const sim = window.fm1;
  const ed = sim.editor;
  const v = ed.state.panelView;
  const knob2 = v.knobs[1];
  const key = `${knob2.role === 1 ? `s${knob2.sound + 1}` : '?'}:${knob2.uid}`;
  const row = ed.rows.get(key);
  const before = row ? row.el.querySelector('.ed-val, [aria-checked="true"], select').value || row.el.textContent : null;
  const chips = [...document.querySelectorAll('.ed-k:not([hidden])')].map((c) => c.textContent);
  const t0 = performance.now();
  sim.node.port.postMessage({ type: 'encoder', encoder: 4, delta: 3 });
  let frames = 0;
  while (frames < 60) {
    await new Promise((r) => requestAnimationFrame(r));
    ++frames;
    const now = row ? row.el.querySelector('.ed-val, [aria-checked="true"], select').value || row.el.textContent : null;
    if (now !== before) break;
  }
  const h = ed.history.entries[ed.history.entries.length - 1];
  return { key, frames, ms: performance.now() - t0, chips, knobs: v.knobs.filter((k) => k.kind).length,
    entry: h ? { origin: h.origin, how: h.how, label: h.label } : null,
    from: document.querySelector('.ed-from').textContent, flashed: row && row.el.classList.contains('is-flash') };
});
report.follow_panel = follow;
check('a panel knob reaches the editor\'s row within a few frames', follow.frames <= 12, follow);
check('it enters the history as the panel\'s', follow.entry && follow.entry.origin === 'panel' && /KNOB2/.test(follow.from), follow);
check('K1-K4 mark the rows the panel\'s knobs turn now', follow.chips.length === follow.knobs &&
  follow.chips.every((c, i) => c === `K${i + 1}`), follow);

// ---- follow, editor to panel -------------------------------------------------
const toPanel = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  document.querySelector('.ed-out-fx').click();
  await new Promise((r) => setTimeout(r, 100));
  document.querySelector('.ed-flow [data-block="m1"]').click();
  for (let i = 0; i < 40; ++i) {
    await new Promise((r) => setTimeout(r, 25));
    const v = ed.state.panelView;
    if (v.mode === 'fx' && v.slot === 3) return { ok: true, ms: (i + 1) * 25, view: v.mode, slot: v.slot };
  }
  return { ok: false, view: ed.state.panelView };
});
report.follow_editor = toPanel;
check('selecting M1 in the Flow opens it on the panel', toPanel.ok, toPanel);
const tele = await page.evaluate(async () => {
  await new Promise((r) => setTimeout(r, 300));
  return { on: window.fm1.editor.state.teleOn, meters: document.querySelectorAll('.ed-flow [data-meter]').length };
});
check('the Flow subscribes to its meters while it is seen', tele.on && tele.meters >= 2, tele);

// ---- undo by hash, PLAY and EDIT ------------------------------------------------------
const first = await page.evaluate(() => window.__hash());
const sound = await page.evaluate(async () => {
  document.querySelectorAll('.ed-out')[1].click();          // S2
  await new Promise((r) => setTimeout(r, 200));
  const s = document.querySelector('.ed-sound .ed-row-slider [role=slider]:not([aria-valuemax="100"])');
  s.focus();
  return { label: s.getAttribute('aria-labelledby') && document.getElementById(s.getAttribute('aria-labelledby')).textContent,
    keys: window.fm1.editor.state.keys, before: s.getAttribute('aria-valuenow') };
});
check('focus in the editor gives it the keys (EDIT)', sound.keys === 'edit', sound);
await page.evaluate(() => { window.__sent.length = 0; });
for (let i = 0; i < 4; ++i) await page.keyboard.press('ArrowRight');
await page.keyboard.press('KeyA');                           // a note in PLAY
await page.waitForTimeout(400);
const edited = await page.evaluate(() => ({
  now: document.activeElement.getAttribute('aria-valuenow'), sent: window.__sent.slice(),
  entries: window.fm1.editor.history.entries.slice(-1).map((e) => [e.origin, e.how, e.before, e.after]),
}));
report.edit = { ...sound, ...edited };
check('arrow keys move one detent each, as one history step', edited.now !== sound.before && edited.entries[0][0] === 'editor' &&
  edited.entries[0][1] === 'key', report.edit);
check('in EDIT no computer key reaches the FM-1', !edited.sent.includes('key') && !edited.sent.includes('button'), edited.sent);
const changed = await page.evaluate(() => window.__hash());
await page.keyboard.press('Control+z');
await page.waitForTimeout(400);
const undone = await page.evaluate(() => window.__hash());
await page.keyboard.press('Control+Shift+z');
await page.waitForTimeout(400);
const redone = await page.evaluate(() => window.__hash());
// The shadow Worker's hash covers the project's view too, which follow
// moves (the panel went from M1 to S2's page): the projects are compared
// member by member as well, the view left out.
const sameBut = await page.evaluate(async ({ a, b }) => {
  const d = await window.fm1.files.shadow('diff', { a: window.__bins[a], b: window.__bins[b] });
  return (d.changes || []).filter((c) => !c.path.startsWith('view.')).map((c) => c.path);
}, { a: first.bin, b: undone.bin });
const sameRedo = await page.evaluate(async ({ a, b }) => {
  const d = await window.fm1.files.shadow('diff', { a: window.__bins[a], b: window.__bins[b] });
  return (d.changes || []).filter((c) => !c.path.startsWith('view.')).map((c) => c.path);
}, { a: changed.bin, b: redone.bin });
report.undo = { first: first.hash, changed: changed.hash, undone: undone.hash, redone: redone.hash,
  undone_vs_first: sameBut, redone_vs_changed: sameRedo, view_first: first.view, view_undone: undone.view };
check('undo ends at the first state (by hash where the view is the same, else member by member less the view)',
  changed.hash !== first.hash && (undone.hash === first.hash || (first.view !== undone.view && sameBut.length === 0)), report.undo);
check('redo ends at the edited state', redone.hash === changed.hash || sameRedo.length === 0, report.undo);
await page.keyboard.press('Escape');
await page.waitForTimeout(100);
const play = await page.evaluate(async () => {
  const st = window.fm1.editor.state;
  const was = st.keys;
  const n = window.fm1.editor.history.entries.length;
  window.__sent.length = 0;
  return { was, n };
});
await page.keyboard.down('KeyA');
await page.keyboard.up('KeyA');
await page.keyboard.press('KeyD');
await page.waitForTimeout(200);
const played = await page.evaluate(() => ({ sent: window.__sent.slice(), n: window.fm1.editor.history.entries.length, keys: window.fm1.editor.state.keys }));
report.play = { ...play, ...played };
check('Esc gives the keys back (PLAY): they play, and no editor key edits', play.was === 'play' && played.sent.includes('key') &&
  played.n === play.n, report.play);
await page.keyboard.press('Control+e');
await page.waitForTimeout(100);
const ctrlE = await page.evaluate(() => window.fm1.editor.state.keys);
await page.keyboard.press('Escape');
check('Ctrl+E gives them to the editor', ctrlE === 'edit', ctrlE);

// ---- stage ED3: move and swap, pickers, refusals, the matrix, structural undo -------------
const lessView = (a, b) => page.evaluate(async ({ a, b }) => {
  const d = await window.fm1.files.shadow('diff', { a: window.__bins[a], b: window.__bins[b] });
  return (d.changes || []).filter((c) => !c.path.startsWith('view.')).map((c) => c.path);
}, { a, b });
await page.evaluate(() => { window.fm1.editor.setLayout('editor'); window.fm1.editor.select('m1', { view: 'flow' }); });
await page.waitForTimeout(400);
const e0 = await page.evaluate(() => window.__hash());
// The keyboard twin: M1 picked up with Space, aimed with the arrows, dropped with Space.
const kb = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  const eng = (k) => (ed.state.mirror.blocks.get(k) || {}).engine || '';
  const places = ed.chains.effectKeys();
  document.querySelector('.ed-block[data-block="m1"]').focus();
  ed.setKeys('edit');
  const key = (k) => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
  key(' ');
  for (let i = places.indexOf('m1'); i > 0; --i) { key('ArrowUp'); await w(40); }
  await w(900);
  const pill = document.querySelector('.ed-verdict');
  const target = document.querySelector('.is-target');
  const before = [eng('m1'), eng(places[0])];
  key(' ');
  await w(1000);
  const last = ed.history.entries[ed.history.entries.length - 1];
  return { verdict: pill && pill.textContent, target: target && target.dataset.drop, first: places[0], before, after: [eng('m1'), eng(places[0])],
    label: last && last.label, focus: document.activeElement && document.activeElement.dataset.block };
});
report.ed3 = { keys: kb };
check('Space picks a block up and the arrows aim it, with C\'s verdict before the drop', /^Swap · RAM \d+ %$/.test(kb.verdict || '') && kb.target === kb.first, kb);
check('Space drops it: the two slots swap, as one history step', kb.after[0] === kb.before[1] && kb.after[1] === kb.before[0] && /^Swap M1 and /.test(kb.label || ''), kb);
check('the keys stay with the moved block', kb.focus === kb.first, kb);
await page.evaluate(() => window.fm1.editor.undo());
await page.waitForTimeout(700);
const e1 = await page.evaluate(() => window.__hash());
const kbBack = await lessView(e0.bin, e1.bin);
check('undo puts the swap back', kbBack.length === 0, kbBack);
// The pointer: M1 dragged onto S1 In2.
const box = async (sel) => page.locator(sel).first().boundingBox();
const from = await box('.ed-block[data-block="m1"]');
const to = await box('.ed-block[data-block="s1.in2"]');
await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
await page.mouse.down();
for (let i = 1; i <= 8; ++i) await page.mouse.move(from.x + from.width / 2 + ((to.x - from.x) * i) / 8, from.y + from.height / 2 + ((to.y - from.y) * i) / 8);
await page.waitForTimeout(900);
const dragPill = await page.evaluate(() => { const p = document.querySelector('.ed-verdict'); return p && p.textContent; });
await page.mouse.up();
await page.waitForTimeout(1000);
const drag = await page.evaluate(() => {
  const ed = window.fm1.editor;
  return { m1: (ed.state.mirror.blocks.get('m1') || {}).engine || '', in2: (ed.state.mirror.blocks.get('s1.in2') || {}).engine || '' };
});
report.ed3.drag = { pill: dragPill, ...drag };
check('a pointer drag shows the verdict over its target and swaps on release', /^Swap · RAM/.test(dragPill || '') && drag.in2 === kb.before[0], report.ed3.drag);
await page.evaluate(() => window.fm1.editor.undo());
await page.waitForTimeout(700);
// A picker: each choice's RAM after in percent (or C's refusal), the choice made, then undone.
await page.evaluate(() => window.fm1.editor.select('m1', { view: 'flow' }));
await page.waitForTimeout(300);
await page.click('.ed-flow-insp .ed-pick');
await page.waitForFunction(() => document.querySelectorAll('.ed-pick-ram').length > 3 &&
  [...document.querySelectorAll('.ed-pick-o:not([hidden]) .ed-pick-ram')].every((c) => c.textContent !== '…'), null, { timeout: 15000 });
const pick = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const cells = [...document.querySelectorAll('.ed-pick-o:not([hidden])')].map((o) => [o.dataset.id, o.querySelector('.ed-pick-ram').textContent, o.classList.contains('is-refused')]);
  const was = (ed.state.mirror.blocks.get('m1') || {}).engine || '';
  const o = [...document.querySelectorAll('.ed-pick-o:not([hidden]):not(.is-refused):not(.is-cur)')].find((x) => x.dataset.id);
  o.click();
  await new Promise((r) => setTimeout(r, 1000));
  return { cells, was, chose: o.dataset.id, now: (ed.state.mirror.blocks.get('m1') || {}).engine || '' };
});
report.ed3.picker = { rows: pick.cells.length, chose: pick.chose, sample: pick.cells.slice(0, 4) };
check('a picker shows every choice\'s RAM in percent, or C\'s refusal in words', pick.cells.length > 10 &&
  pick.cells.every(([, t, refused]) => (refused ? t.length > 3 && !/RAM \d/.test(t) : /^RAM \d+ %$|^\d+ % over$/.test(t))), pick.cells);
check('choosing in it changes the block', pick.now === pick.chose && pick.chose !== pick.was, pick);
await page.evaluate(() => window.fm1.editor.undo());
await page.waitForTimeout(800);
const e2 = await page.evaluate(() => window.__hash());
const pickBack = await lessView(e0.bin, e2.bin);
check('undo puts the effect back', pickBack.length === 0, pickBack);
// A refusal from C: S1's engine cannot be emptied. The picker does not
// offer it; asked anyway, nothing changes and the words are the metadata's.
const refusal = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  ed.select('s1', { view: 'sound' });
  await new Promise((r) => setTimeout(r, 300));
  document.querySelector('.ed-insp[data-block="s1"] .ed-pick').click();
  await new Promise((r) => setTimeout(r, 2500));
  const emptyOffered = !!document.querySelector('.ed-pick-o[data-id=""]:not([hidden])');
  ed.chains.closePicker();
  const n = ed.history.entries.length;
  ed.chains.choose('s1', '');
  await new Promise((r) => setTimeout(r, 900));
  return { emptyOffered, kept: ed.history.entries.length === n, detail: document.querySelector('.ed-detail').textContent, words: ed.meta.refusalWords(8) };
});
const e3 = await page.evaluate(() => window.__hash());
const refBack = await lessView(e0.bin, e3.bin);
report.ed3.refusal = refusal;
check('a choice C refuses is not offered, and asked anyway changes nothing, in its words', !refusal.emptyOffered && refusal.kept &&
  refusal.detail.includes(refusal.words) && refBack.length === 0, { refusal, refBack });
// The matrix: a cable added, its amount typed, its polarity set, aimed where
// the planner leaves it out (its reason in words), each undone.
await page.evaluate(() => window.fm1.editor.select('p1', { view: 'mod' }));
await page.waitForTimeout(500);
const mx = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  const used = () => ed.state.mirror.cables.filter((c) => c.flags & 1).length;
  const n0 = used(), h0 = ed.history.entries.length;
  [...document.querySelectorAll('.ed-btn')].find((b) => b.textContent === 'Add a cable').click();
  await w(1000);
  const i = Number(ed.state.selCable.slice(1)) - 1;
  const amt = document.querySelector(`.ed-mx-r[data-cable="${i}"] .ed-amt`);
  amt.focus();
  amt.value = '-40';
  amt.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  amt.blur();
  await w(900);
  const bi = [...document.querySelectorAll('.ed-slot .ed-segbtn')].find((b) => b.textContent === ed.mm.polarities[2]);
  bi.click();
  await w(900);
  const c = ed.state.mirror.cables[i];
  const s1 = ed.meta.engine(ed.state.mirror.blocks.get('s1').engine);
  const nl = s1.params.find((p) => (p.flags || []).includes('nolock'));
  let late = null;
  if (nl) {
    const to = `${ed.mm.unitCode('s1')}:${nl.uid}:0`;
    const sel = document.querySelector(`.ed-mx-r[data-cable="${i}"] [data-fk="c${i + 1}:to"]`);
    if (![...sel.options].some((o) => o.value === to)) sel.append(new Option('test', to));
    sel.value = to;
    sel.dispatchEvent(new Event('change'));
    await w(1200);
    const row = document.querySelector(`.ed-mx-r[data-cable="${i}"]`);
    late = { refused: row.classList.contains('is-refused'), text: row.querySelector('.ed-mx-v').textContent, words: ed.meta.refusalWords(34) };
  }
  return { n0, n1: used(), steps: ed.history.entries.length - h0, amount: c.amount, pol: (c.flags & 6) >> 1, late, slot: i };
});
report.ed3.matrix = mx;
check('Add a cable puts one in the first empty slot', mx.n1 === mx.n0 + 1, mx);
check('its amount typed and its polarity chosen reach C', mx.amount === Math.round(-0.4 * 16384) && mx.pol === 2, mx);
check('a cable the planner leaves out shows its reason in the metadata\'s words', !mx.late || (mx.late.refused && mx.late.text.startsWith(mx.late.words)), mx.late);
await page.evaluate(async (n) => { for (let k = 0; k < n; ++k) { window.fm1.editor.undo(); await new Promise((r) => setTimeout(r, 300)); } }, mx.steps);
await page.waitForTimeout(800);
const e4 = await page.evaluate(() => window.__hash());
const mxBack = await lessView(e0.bin, e4.bin);
check('undoing the matrix edits ends where they began', mxBack.length === 0, mxBack);
// The rack: a module moved by keys to the first empty place, one chosen and one emptied, each undone.
const rk = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  const rack = () => ed.state.mirror.rack.slice();
  const r0 = rack();
  const empty = r0.indexOf('');
  const h0 = ed.history.entries.length;
  ed.select('p1', { view: 'mod' });
  await w(300);
  document.querySelector('.ed-card-m[data-block="p1"]').focus();
  ed.setKeys('edit');
  const key = (k) => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
  key(' ');
  for (let i = 0; i < empty; ++i) { key('ArrowRight'); await w(40); }
  await w(800);
  key(' ');
  await w(1000);
  const r1 = rack();
  const kinds = [...ed.mm.kinds.keys()];
  ed.chains.choose('p8', kinds[kinds.length - 1]);
  await w(1000);
  ed.chains.choose(`p${empty + 1}`, '');
  await w(1000);
  return { r0, r1, r2: rack(), empty, steps: ed.history.entries.length - h0 };
});
report.ed3.rack = rk;
check('a rack module moves by keys, its kind with it', rk.empty > 0 && rk.r1[rk.empty] === rk.r0[0], rk);
await page.evaluate(async (n) => { for (let k = 0; k < n; ++k) { window.fm1.editor.undo(); await new Promise((r) => setTimeout(r, 350)); } }, rk.steps);
await page.waitForTimeout(800);
const e5 = await page.evaluate(() => window.__hash());
const rkBack = await lessView(e0.bin, e5.bin);
check('undoing the rack edits ends at the state before them', rk.steps === 3 && rkBack.length === 0, { steps: rk.steps, rkBack });

// ---- every module's inspector from the metadata, at two column widths ----------------
const inspectors = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const ids = ed.meta.doc.engines.map((e) => e.id).concat(ed.mm ? [...ed.mm.kinds.keys()] : []);
  const bad = [];
  let rows = 0;
  for (const width of [620, 360]) {
    const box = document.createElement('div');
    box.className = 'ed';
    box.style.cssText = `position:absolute;left:0;top:0;width:${width}px`;
    document.body.append(box);
    for (const id of ids) {
      box.innerHTML = '';
      const insp = ed.inspectorFor(id);
      box.append(insp);
      await new Promise((r) => requestAnimationFrame(r));
      const e = ed.meta.engine(id);
      const shown = ed.meta.pages(id).reduce((n, pg) => n + pg.params.length, 0);
      const got = insp.querySelectorAll('.ed-row:not([data-uid="level"]):not([data-uid="on"])').length;
      const folded = insp.querySelectorAll('details.ed-page-more').length;
      if (got !== shown && !folded) bad.push(`${id}@${width}: ${got} rows of ${shown}`);
      rows += got;
      if (insp.scrollWidth > insp.clientWidth + 1) bad.push(`${id}@${width}: inspector wider than its column`);
      for (const t of insp.querySelectorAll('.ed-label, .ed-segbtn, .ed-insp-name, .ed-page-n, .ed-page-k, .ed-place')) {
        if (t.scrollWidth > t.clientWidth + 1) bad.push(`${id}@${width}: "${t.textContent}" overflows`);
      }
      for (const r of insp.querySelectorAll('.ed-row')) {
        const kids = [...r.children].filter((c) => !c.hidden && c.getBoundingClientRect().width > 0).map((c) => c.getBoundingClientRect());
        for (let i = 0; i < kids.length; ++i) for (let j = i + 1; j < kids.length; ++j) {
          const a = kids[i], b = kids[j];
          if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) {
            bad.push(`${id}@${width}: row "${r.querySelector('.ed-label').textContent}" overlaps itself`);
            i = kids.length;
            break;
          }
        }
        const lab = r.querySelector('.ed-label');
        if (lab && lab.getBoundingClientRect().right > insp.getBoundingClientRect().right) bad.push(`${id}@${width}: label past the edge`);
      }
      for (const s of insp.querySelectorAll('[role=slider]')) {
        const val = s.nextElementSibling;
        if (!val || !val.classList.contains('ed-val')) bad.push(`${id}@${width}: a slider with no value field`);
      }
      if (e.gpl && !insp.querySelector('.ed-gpl')) bad.push(`${id}: no GPL chip`);
    }
    box.remove();
  }
  ed.select(ed.state.selected);      // the rows map back to the page's
  return { modules: ids.length, rows, bad };
});
report.inspectors = { modules: inspectors.modules, rows: inspectors.rows, faults: inspectors.bad.slice(0, 20) };
check('every module draws an inspector from the metadata with nothing overflowing', inspectors.bad.length === 0 &&
  inspectors.modules >= 30, inspectors.bad.slice(0, 10));

// ---- the layouts at desktop and tablet widths ---------------------------------------
async function layoutCheck(name) {
  return page.evaluate(() => {
    const bad = [];
    const vw = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > vw + 1) bad.push(`page scrolls sideways (${document.documentElement.scrollWidth} > ${vw})`);
    const ed = document.querySelector('.ed');
    if (ed.getBoundingClientRect().right > vw + 1) bad.push('the editor runs past the page');
    for (const t of ed.querySelectorAll('.ed-label, .ed-segbtn, .ed-blk-n, .ed-blk-k, .ed-out-name, .ed-step, .ed-chip, .ed-ram, .ed-toggle, .ed-mx-v, .ed-mx-n, .ed-btn')) {
      if (t.getClientRects().length && t.scrollWidth > t.clientWidth + 1) bad.push(`"${t.textContent.slice(0, 30)}" overflows`);
    }
    for (const b of ed.querySelectorAll('.ed-block, .ed-insp, .ed-card-m, .ed-mx-r')) {
      const r = b.getBoundingClientRect();
      const p = b.parentElement.getBoundingClientRect();
      if (r.width && (r.right > p.right + 1 || r.left < p.left - 1)) bad.push(`${b.dataset.block} outside its row`);
    }
    return bad;
  }).then((bad) => { report.layouts = report.layouts || {}; report.layouts[name] = bad.slice(0, 10); return bad; });
}
const shots = [];
for (const [w, h] of [[1440, 1000], [1024, 768]]) {
  await page.setViewportSize({ width: w, height: h });
  for (const layout of ['workbench', 'editor']) {
    for (const view of ['sound', 'flow', 'mod']) {
      await page.evaluate(async ({ layout, view }) => {
        document.querySelector(`[data-layout="${layout}"]`).click();
        await new Promise((r) => setTimeout(r, 150));
        if (view === 'flow') document.querySelector('.ed-out-fx').click();
        else if (view === 'mod') document.querySelector('.ed-out-mod').click();
        else document.querySelectorAll('.ed-out')[2].click();       // S3
        window.scrollTo(0, 0);
        await new Promise((r) => setTimeout(r, 250));
      }, { layout, view });
      const name = `${view === 'mod' ? 'ed3' : 'ed2'}-${layout}-${view}-${w}`;
      const bad = await layoutCheck(name);
      check(`${layout}, ${view} at ${w} px: no sideways scroll, nothing overflowing`, bad.length === 0, bad);
      const file = join(out, `${name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      shots.push(file);
    }
  }
}
report.screenshots = shots;
await page.evaluate(() => document.querySelector('[data-layout="panel"]').click());
report.logs = report.logs.filter((l) => !/AudioContext was not allowed/.test(l));
check('no page errors', report.logs.length === 0, report.logs);

report.pass = Object.values(report.checks).every(Boolean);
writeFileSync(join(out, 'editor-ui.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, why: report.why }));
await browser.close();
server.close();
process.exit(report.pass ? 0 : 1);
