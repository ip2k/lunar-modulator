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
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
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
// Compared less the view and the current sound: opening a sound's page on
// the panel (follow, the view verb) makes it the current one, which a file
// keeps as session.current; neither is an edit nor in the history (§7, §8).
const lessView = (a, b) => page.evaluate(async ({ a, b }) => {
  const d = await window.fm1.files.shadow('diff', { a: window.__bins[a], b: window.__bins[b] });
  return (d.changes || []).filter((c) => !c.path.startsWith('view.') && c.path !== 'session.current').map((c) => c.path);
}, { a, b });
await page.click('[data-layout="editor"]');
await page.evaluate(() => window.fm1.editor.select('m1', { view: 'flow' }));
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
// The pointer: M1 dragged onto S1 In2 (both in view first, or the mouse
// would land on the panel's knobs).
await page.evaluate(() => { document.querySelector('.ed-flow').scrollIntoView({ block: 'center', behavior: 'instant' }); });
await page.waitForTimeout(200);
const box = async (sel) => page.locator(sel).first().boundingBox();
const from = await box('.ed-block[data-block="m1"]');
const to = await box('.ed-block[data-block="s1.in2"]');
const hits = await page.evaluate(({ a, b }) => [a, b].map(([x, y]) => { const e = document.elementFromPoint(x, y); return e ? `${e.tagName}.${e.className}` : null; }),
  { a: [from.x + from.width / 2, from.y + from.height / 2], b: [to.x + to.width / 2, to.y + to.height / 2] });
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
report.ed3.drag = { pill: dragPill, ...drag, hits };
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
  const lastId = () => (ed.history.entries.length ? ed.history.entries[ed.history.entries.length - 1].id : 0);
  const n = lastId();
  ed.chains.choose('s1', '');
  await new Promise((r) => setTimeout(r, 900));
  return { emptyOffered, kept: lastId() === n, detail: document.querySelector('.ed-detail').textContent, words: ed.meta.refusalWords(8) };
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
  const n0 = used();
  const h0 = ed.history.entries.length ? ed.history.entries[ed.history.entries.length - 1].id : 0;
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
  // Any sound's parameter that rebuilds the voices (flag nolock).
  let nl = null, nk = null;
  for (const [k, b] of ed.state.mirror.blocks) {
    const e = /^s[1-4]$/.test(k) ? ed.meta.engine(b.engine) : null;
    const p = e && e.params.find((x) => (x.flags || []).includes('nolock'));
    if (p) { nl = p; nk = k; break; }
  }
  let late = null;
  if (nl) {
    const to = `${ed.mm.unitCode(nk)}:${nl.uid}:0`;
    const sel = document.querySelector(`.ed-mx-r[data-cable="${i}"] [data-fk="c${i + 1}:to"]`);
    if (![...sel.options].some((o) => o.value === to)) sel.append(new Option('test', to));
    sel.value = to;
    sel.dispatchEvent(new Event('change'));
    await w(1200);
    const row = document.querySelector(`.ed-mx-r[data-cable="${i}"]`);
    late = { refused: row.classList.contains('is-refused'), text: row.querySelector('.ed-mx-v').textContent, words: ed.meta.refusalWords(34) };
  }
  return { n0, n1: used(), steps: ed.history.entries.filter((e) => e.id > h0).length, amount: c.amount, pol: (c.flags & 6) >> 1, late, slot: i };
});
report.ed3.matrix = mx;
check('Add a cable puts one in the first empty slot', mx.n1 === mx.n0 + 1, mx);
check('its amount typed and its polarity chosen reach C', mx.amount === Math.round(-0.4 * 16384) && mx.pol === 2, mx);
check('a cable the planner leaves out shows its reason in the metadata\'s words', !!mx.late && mx.late.refused && mx.late.text.startsWith(mx.late.words), mx.late);
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
  const h0 = ed.history.entries.length ? ed.history.entries[ed.history.entries.length - 1].id : 0;
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
  const moved = ed.history.entries[ed.history.entries.length - 1];
  const kinds = [...ed.mm.kinds.keys()];
  ed.chains.choose('p8', kinds[kinds.length - 1]);
  await w(1000);
  ed.chains.choose(`p${empty + 1}`, '');
  await w(1000);
  return { r0, r1, r2: rack(), empty, steps: ed.history.entries.filter((e) => e.id > h0).length, movedAfter: moved && moved.after };
});
report.ed3.rack = rk;
check('a rack module moves by keys, its kind with it, as one step in words', rk.empty > 0 && rk.r1[rk.empty] === rk.r0[0] && rk.movedAfter === 'moved', rk);
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

// ---- stage ED4: files and the project (§8-§10, §13) -----------------------------------------
await page.evaluate(() => document.querySelector('[data-layout="editor"]').click());
await page.waitForTimeout(300);
report.ed4 = {};
// Per-block export: C's canonical file through the shadow Worker, named as W1 names files.
await page.evaluate(() => window.fm1.editor.select('m1', { view: 'flow' }));
await page.waitForTimeout(400);
const [dl] = await Promise.all([page.waitForEvent('download'), page.click('[data-export="m1"]')]);
const dlText = readFileSync(await dl.path(), 'utf8');
report.ed4.export = { name: dl.suggestedFilename(), kind: (() => { try { return JSON.parse(dlText).kind; } catch { return null; } })() };
check('a block exports its file, named as W1 names files', /-master\.fx\.lunar$/.test(report.ed4.export.name) &&
  report.ed4.export.kind === 'fx', report.ed4.export);

// The ARP pages: selecting a MIDI effect opens them on the panel (HOME's entry 2).
const arp = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const key = [...ed.state.mirror.blocks.keys()].find((k) => /^s[1-4]\.mfx1$/.test(k));
  if (!key) return { key: null };
  ed.select(key, { view: 'flow' });
  await new Promise((r) => setTimeout(r, 900));
  const v = ed.state.panelView;
  return { key, arp: v.arp, sound: v.sound };
});
check('selecting an arpeggiator opens its ARP pages on the panel', arp.key && arp.arp === true &&
  arp.sound === Number(arp.key[1]) - 1, arp);

// Drops from the desktop: the verdict before anything loads; hostile files refused in words.
const dropped = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  const files = window.fm1.files;
  const enc = new TextEncoder();
  const soundText = await files.saveText('sound', 0);
  const modsText = await files.saveText('mods', 0);
  ed.select('s1', { view: 'flow' });
  await w(400);
  const drop = async (sel, list) => {
    const old = document.querySelector('.ed-arrive');
    if (old) old.querySelector('.ed-arrive-b button:last-child').click();
    await w(100);
    const t = document.querySelector(sel);
    if (!t) return { missing: sel };
    const dt = new DataTransfer();
    for (const f of list) dt.items.add(f);
    for (const type of ['dragenter', 'dragover', 'drop']) t.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true, cancelable: true }));
    for (let i = 0; i < 60 && !document.querySelector('.ed-arrive'); ++i) await w(50);
    const c = document.querySelector('.ed-arrive');
    return c ? { ok: c.classList.contains('is-ok'), text: c.innerText.replace(/\s+/g, ' ').slice(0, 200),
      asked: !document.getElementById('target-card').hidden } : { none: true };
  };
  const h0 = await window.__hash();
  const out = {
    big: await drop('.ed-block[data-block="s1"]', [new File([new Uint8Array(300 * 1024)], 'big.lunar')]),
    two: await drop('.ed-block[data-block="s1"]', [new File(['{}'], 'a.lunar'), new File(['{}'], 'b.lunar')]),
    malformed: await drop('.ed-block[data-block="s1"]', [new File(['{"kind":"sound","sounds":[{'], 'bad.lunar')]),
    garbage: await drop('.ed-block[data-block="s1"]', [new File([crypto.getRandomValues(new Uint8Array(4096))], 'x.lunar')]),
    syx: await drop('.ed-block[data-block="s1"]', [new File([new Uint8Array([0xf0, 0x43, 0, 9, 0x20, 0, 0xf7])], 'p.syx')]),
    wrongKind: await drop('.ed-block[data-block="s1"]', [new File([enc.encode(modsText)], 'rack.mods.lunar')]),
  };
  const h1 = await window.__hash();
  out.unchanged = h0.hash === h1.hash;
  out.good = await drop('.ed-block[data-block="s1"]', [new File([enc.encode(soundText)], 'mine.sound.lunar')]);
  const go = document.querySelector('.ed-arrive .ed-btn-go');
  if (go) go.click();
  await w(1500);
  out.loaded = document.querySelector('.ed-arrive') === null;
  return out;
});
report.ed4.drops = dropped;
const refusedCard = (d) => d && d.ok === false && d.text && !d.asked;
check('a file too large for the module is refused at the block, in words', refusedCard(dropped.big) && /larger than/.test(dropped.big.text), dropped.big);
check('two files at once are refused at the block', refusedCard(dropped.two), dropped.two);
check('malformed, random and DX7 files are refused with C\'s words, nothing asked', refusedCard(dropped.malformed) &&
  refusedCard(dropped.garbage) && refusedCard(dropped.syx), [dropped.malformed, dropped.garbage, dropped.syx]);
check('a mod rack dropped on a sound is refused in C\'s words', refusedCard(dropped.wrongKind) && /mod rack/i.test(dropped.wrongKind.text), dropped.wrongKind);
check('no refused drop changes the state', dropped.unchanged, dropped);
check('a sound dropped on a sound shows C\'s verdict and RAM after, then loads', dropped.good && dropped.good.ok &&
  /RAM \d+ %/.test(dropped.good.text) && dropped.loaded, dropped.good);

// The library: Save to my library, then drag it onto a block, the verdict while it hovers.
const lib = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  ed.select('s1', { view: 'flow' });
  await w(400);
  document.querySelector('.ed-insp[data-block="s1"] .ed-keep').click();
  await w(800);
  ed.select('m1', { view: 'flow' });
  await w(400);
  document.querySelector('.ed-insp[data-block="m1"] .ed-keep').click();
  await w(800);
  document.querySelector('.ed-out-lib').click();
  for (let i = 0; i < 40 && !document.querySelector('.ed-lib-item'); ++i) await w(50);
  const hover = async (kind, sel) => {
    const li = document.querySelector(`.ed-lib-item[data-kind="${kind}"]`);
    const t = document.querySelector(sel);
    if (!li || !t) return { missing: [!!li, !!t] };
    const dt = new DataTransfer();
    li.dispatchEvent(new DragEvent('dragstart', { dataTransfer: dt, bubbles: true }));
    t.dispatchEvent(new DragEvent('dragenter', { dataTransfer: dt, bubbles: true, cancelable: true }));
    for (let i = 0; i < 60 && !t.dataset.verdict; ++i) await w(50);
    return { t, dt, li, verdict: t.dataset.verdict || '', ok: t.classList.contains('is-drop-ok') };
  };
  const wrong = await hover('fx', '.ed-drop[data-block="s4"]');
  const wrongOut = { verdict: wrong.verdict, ok: wrong.ok };
  if (wrong.t) { wrong.t.dispatchEvent(new DragEvent('dragleave', { dataTransfer: wrong.dt, bubbles: true })); wrong.li.dispatchEvent(new DragEvent('dragend', { bubbles: true })); }
  const right = await hover('sound', '.ed-drop[data-block="s3"]');
  const rightOut = { verdict: right.verdict, ok: right.ok };
  if (right.t) right.t.dispatchEvent(new DragEvent('drop', { dataTransfer: right.dt, bubbles: true, cancelable: true }));
  for (let i = 0; i < 60 && !document.querySelector('.ed-arrive .ed-btn-go'); ++i) await w(50);
  const go = document.querySelector('.ed-arrive .ed-btn-go');
  if (go) go.click();
  await w(1500);
  const eng = (k) => (ed.state.mirror.blocks.get(k) || {}).engine || '';
  return { items: document.querySelectorAll('.ed-lib-item').length, wrong: wrongOut, right: rightOut, s1: eng('s1'), s3: eng('s3') };
});
report.ed4.library = lib;
check('the library lists what was saved to it', lib.items >= 2, lib);
check('a library item hovering a block it does not fit shows C\'s refusal before the drop', lib.wrong.ok === false && lib.wrong.verdict.length > 0 &&
  !/^Load/.test(lib.wrong.verdict), lib.wrong);
check('a library sound hovering a sound shows its verdict and loads on the drop', lib.right.ok && /^Load · RAM \d+ %$/.test(lib.right.verdict) &&
  lib.s3 === lib.s1, lib);

// Search: Ctrl+K, words, the arrows, Enter; Esc gives the focus back.
await page.evaluate(() => { window.fm1.editor.select('s1', { view: 'flow' }); document.querySelector('.ed-block[data-block="s1"]').focus(); });
await page.waitForTimeout(300);
await page.keyboard.press('Control+k');
await page.keyboard.type('memory');
const s1 = await page.evaluate(() => ({ open: window.fm1.editor.project.searchOpen, at: (document.querySelector('.ed-search-o.is-at') || {}).textContent,
  active: document.activeElement.className }));
await page.keyboard.press('Enter');
await page.waitForTimeout(300);
const s1v = await page.evaluate(() => window.fm1.editor.state.view);
const pname = await page.evaluate(() => {
  const ed = window.fm1.editor;
  const p = ed.meta.pages(ed.state.mirror.blocks.get('s1').engine)[0].params[1];
  return { name: p.name, uid: p.uid };
});
await page.keyboard.press('Control+k');
await page.keyboard.type(`s1 ${pname.name}`);
const before = await page.evaluate(() => document.querySelector('.ed-search-in').getAttribute('aria-activedescendant'));
await page.keyboard.press('ArrowDown');
await page.keyboard.press('ArrowUp');
const after = await page.evaluate(() => document.querySelector('.ed-search-in').getAttribute('aria-activedescendant'));
await page.keyboard.press('Tab');
const kept = await page.evaluate(() => document.activeElement.className);
await page.keyboard.press('Enter');
await page.waitForTimeout(500);
const s2 = await page.evaluate(() => ({ row: window.fm1.editor.state.selRow, open: window.fm1.editor.project.searchOpen }));
await page.keyboard.press('Control+k');
await page.keyboard.type('zzzz nothing');
const none = await page.evaluate(() => document.querySelector('.ed-search-n').textContent);
await page.keyboard.press('Escape');
const s3 = await page.evaluate(() => ({ open: window.fm1.editor.project.searchOpen, keys: window.fm1.editor.state.keys }));
report.ed4.search = { s1, s1v, pname, before, after, kept, s2, none, s3 };
check('Ctrl+K opens the search with the keys in it', s1.open && s1.active === 'ed-search-in', s1);
check('a command found by its words runs on Enter', s1v === 'memory', s1v);
check('a parameter found by sound and name: Enter selects its row', s2.row === `s1:${pname.uid}` && !s2.open && before === after && kept === 'ed-search-in', report.ed4.search);
check('nothing matching is said so; Esc closes', none === 'Nothing matches' && !s3.open, report.ed4.search);

// Memory: RAM by part in percent, and what is free; the two add to 100 at most.
const mem = await page.evaluate(() => {
  document.querySelector('.ed-out-mem').click();
  const pc = (sel) => { const t = document.querySelector(sel); return t ? t.textContent : ''; };
  return { rows: document.querySelectorAll('.ed-mem-row').length, used: pc('.ed-mem-total .ed-mem-pc'), free: pc('.ed-mem-free .ed-mem-pc'),
    bytes: /\b(KB|kB|bytes|B)\b/.test(document.querySelector('.ed-mem').innerText) };
});
report.ed4.memory = mem;
check('the Memory page shows each part and what is free in percent, never in bytes', mem.rows === 8 && /^\d+ %$/.test(mem.used) &&
  /^\d+ %$/.test(mem.free) && parseInt(mem.used, 10) + parseInt(mem.free, 10) <= 100 && !mem.bytes, mem);

// A/B on one sound: Keep as A, edit, X hears A, X hears B again; C loads each.
const abSetup = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  document.querySelector('.ed-out-ab').click();
  await w(200);
  document.querySelectorAll('.ed-ab-scope .ed-segbtn')[1].click();        // Sound 1
  await w(200);
  await ed.project.keepA();
  ed.select('s1', { view: 'sound' });
  await w(400);
  const s = document.querySelector('.ed-insp[data-block="s1"] .ed-row-slider [role=slider]:not([aria-valuemax="100"])');
  s.focus();
  return { A: !!ed.state.ab.A, scope: ed.state.ab.scope, now: s.getAttribute('aria-valuenow'), max: s.getAttribute('aria-valuemax'),
    row: s.closest('.ed-row') && s.closest('.ed-row').dataset.fk };
});
await page.keyboard.press(abSetup.now === abSetup.max ? 'Home' : 'End');
await page.waitForTimeout(600);
const abVal = () => page.evaluate(() => {
  const s = document.querySelector('.ed-insp[data-block="s1"] .ed-row-slider [role=slider]:not([aria-valuemax="100"])');
  return s ? s.getAttribute('aria-valuenow') : null;
});
const abB = await abVal();
await page.keyboard.press('KeyX');
await page.waitForTimeout(1800);
const abA = await abVal();
const abState = await page.evaluate(() => ({ playing: window.fm1.editor.state.ab.playing, diff: (window.fm1.editor.state.ab.diff || []).length }));
await page.keyboard.press('KeyX');
await page.waitForTimeout(1800);
const abB2 = await abVal();
const abState2 = await page.evaluate(() => window.fm1.editor.state.ab.playing);
report.ed4.ab = { abSetup, abB, abA, abState, abB2, abState2 };
check('A/B: X hears A, as kept, with the differences from C', abSetup.A && abSetup.scope === 0 && abB !== abSetup.now &&
  abA === abSetup.now && abState.playing === 'A' && abState.diff >= 1, report.ed4.ab);
check('A/B: X again hears B, the edit back', abB2 === abB && abState2 === 'B', report.ed4.ab);

// Undo's hash check and snapshot fallback (§8).
const fb = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const w = (t) => new Promise((r) => setTimeout(r, t));
  ed.select('s1', { view: 'flow' });
  await w(1200);                                     // the editor's copy goes current
  const h0 = await window.__hash();
  const cur = (ed.state.mirror.blocks.get('s1.in2') || {}).engine;
  const id = ed.meta.doc.engines.filter((e) => e.kind === 'audio_fx' && e.id !== cur).sort((a, b) => a.ram - b.ram).map((e) => e.id)[0];
  ed.chains.choose('s1.in2', id);
  await w(1500);
  const e = ed.history.entries[ed.history.at - 1];
  const had = !!(e && e.snap);
  ed.undo();
  await w(1800);
  const h1 = await window.__hash();
  const check1 = e.check;
  ed.redo();
  await w(1500);
  // Its inverse records taken away: only the snapshot can put it back.
  e.info.undo = [];
  e.info.cables = ed.state.mirror.cables.map((c) => ({ ...c }));
  ed.undo();
  await w(3000);
  const h2 = await window.__hash();
  return { id, had, check1, check2: e.check, h0: h0.hash, h1: h1.hash, h2: h2.hash };
});
report.ed4.fallback = fb;
check('a structural edit keeps a snapshot; its undo is checked by hash (no view, no current sound)', fb.had && fb.check1 === 'hash' &&
  fb.h1 === fb.h0, fb);
check('an undo whose inverse records fall short loads the snapshot, back to the same hash', fb.check2 === 'snapshot' && fb.h2 === fb.h0, fb);

// Links: view=edit and sel, and hostile ones, on a fresh page (no load, no storage).
const linkPage = await browser.newPage({ viewport: { width: 1024, height: 768 } });
const linkLog = [];
const linkReq = [];
linkPage.on('pageerror', (e) => linkLog.push(e.message));
linkPage.on('dialog', (d) => { linkLog.push(`dialog: ${d.message()}`); d.dismiss(); });
linkPage.on('request', (r) => linkReq.push(r.url()));
const tryLink = async (q, power) => {
  await linkPage.goto(`${url}?${q}`);
  await linkPage.waitForTimeout(800);
  if (power) {
    await linkPage.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 10000 });
    await linkPage.click('.ed-power');
    await linkPage.waitForFunction(() => window.fm1.editor.state.mirror, null, { timeout: 20000 });
    await linkPage.waitForTimeout(1200);
  }
  return linkPage.evaluate(() => {
    const n = document.getElementById('file-notice');
    const ed = window.fm1 && window.fm1.editor;
    return { layout: document.body.dataset.layout, notice: n.hidden ? '' : n.innerText.split('\n')[0], sel: ed ? ed.state.selected : null,
      row: ed ? ed.state.selRow || null : null, view: ed ? ed.state.view : null, imgs: document.querySelectorAll('img[src="x"]').length,
      address: location.search };
  });
};
const links = {
  param: await tryLink('view=edit&sel=s1:Harmonics', true),
  empty: await tryLink('view=edit&sel=p8', true),
  noBlock: await tryLink('view=edit&sel=s9'),
  html: await tryLink(`view=edit&sel=${encodeURIComponent('s1:<img src=x onerror=alert(1)>')}`),
  long: await tryLink(`view=edit&sel=p1:${'A'.repeat(200)}`),
  url: await tryLink(`view=edit&sel=${encodeURIComponent('https://evil.example/a.lunar')}`),
  load: await tryLink(`view=edit&load=${encodeURIComponent('https://evil.example/a.lunar')}`),
  bogus: await tryLink('view=edit&sel=s1:NoSuchParameter', true),
};
await linkPage.close();
links.offsite = linkReq.filter((u) => !u.startsWith('data:') && !u.startsWith('blob:') && new URL(u).origin !== new URL(url).origin);
links.log = linkLog;
report.ed4.links = links;
check('view=edit&sel=s1:Harmonics opens the editor at that parameter', links.param.layout === 'editor' && links.param.row === 's1:2' &&
  links.param.view === 'sound' && links.param.address === '', links.param);
check('a link to an empty block opens the editor and says so', links.empty.layout === 'editor' && /empty/.test(links.empty.notice), links.empty);
check('hostile sel links are refused in words, nothing injected', [links.noBlock, links.html, links.long, links.url].every((l) =>
  l.layout === 'editor' && /names no block/.test(l.notice) && l.imgs === 0), links);
check('an off-site load in a link is refused, and nothing off-site is asked for', /not|refus/i.test(links.load.notice) && links.offsite.length === 0 &&
  links.log.length === 0, links);
check('an unknown parameter in sel is said so', /not one of/.test(links.bogus.notice) && links.bogus.sel === 's1', links.bogus);

// ---- the layouts at desktop and tablet widths ---------------------------------------
async function layoutCheck(name) {
  return page.evaluate(() => {
    const bad = [];
    const vw = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > vw + 1) bad.push(`page scrolls sideways (${document.documentElement.scrollWidth} > ${vw})`);
    const ed = document.querySelector('.ed');
    if (ed.getBoundingClientRect().right > vw + 1) bad.push('the editor runs past the page');
    for (const t of ed.querySelectorAll('.ed-label, .ed-segbtn, .ed-blk-n, .ed-blk-k, .ed-out-name, .ed-step, .ed-chip, .ed-ram, .ed-toggle, .ed-mx-v, .ed-mx-n, .ed-btn, .ed-live, .ed-lib-name, .ed-lib-meta, .ed-mem-name, .ed-mem-pc, .ed-drop, .ed-ab-v, .ed-search-o')) {
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
    for (const view of ['sound', 'flow', 'mod', 'library', 'memory', 'compare', 'search']) {
      if (layout === 'workbench' && ['library', 'memory', 'compare', 'search'].includes(view)) continue;
      await page.evaluate(async ({ layout, view }) => {
        document.querySelector(`[data-layout="${layout}"]`).click();
        await new Promise((r) => setTimeout(r, 150));
        const ed = window.fm1.editor;
        if (ed.project.searchOpen) ed.project.closeSearch(false);
        if (view === 'flow') document.querySelector('.ed-out-fx').click();
        else if (view === 'mod') document.querySelector('.ed-out-mod').click();
        else if (view === 'library') document.querySelector('.ed-out-lib').click();
        else if (view === 'memory') document.querySelector('.ed-out-mem').click();
        else if (view === 'compare') document.querySelector('.ed-out-ab').click();
        else if (view === 'search') {
          document.querySelector('.ed-out-fx').click();
          ed.project.openSearch();
          const i = document.querySelector('.ed-search-in');
          i.value = 's1';
          i.dispatchEvent(new Event('input'));
        } else document.querySelectorAll('.ed-out')[2].click();       // S3
        window.scrollTo(0, 0);
        await new Promise((r) => setTimeout(r, 400));
      }, { layout, view });
      const name = `${view === 'mod' ? 'ed3' : ['sound', 'flow'].includes(view) ? 'ed2' : 'ed4'}-${layout}-${view}-${w}`;
      const bad = await layoutCheck(name);
      check(`${layout}, ${view} at ${w} px: no sideways scroll, nothing overflowing`, bad.length === 0, bad);
      const file = join(out, `${name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      shots.push(file);
    }
  }
}
report.screenshots = shots;
await page.evaluate(() => { const ed = window.fm1.editor; if (ed.project.searchOpen) ed.project.closeSearch(false); document.querySelector('[data-layout="panel"]').click(); });
report.logs = report.logs.filter((l) => !/AudioContext was not allowed/.test(l));
check('no page errors', report.logs.length === 0, report.logs);

report.pass = Object.values(report.checks).every(Boolean);
writeFileSync(join(out, 'editor-ui.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, why: report.why }));
await browser.close();
server.close();
process.exit(report.pass ? 0 : 1);
