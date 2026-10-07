// editor-ui.mjs -- the Advanced editor's shell, flow and sound in headless
// Chromium (stage ED2, notes/2026-10-06-web-editor.md §4, §7, §8, §13, §14,
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

// ---- every module's inspector from the metadata, at two column widths ----------------
const inspectors = await page.evaluate(async () => {
  const ed = window.fm1.editor;
  const ids = ed.meta.doc.engines.map((e) => e.id);
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
    for (const t of ed.querySelectorAll('.ed-label, .ed-segbtn, .ed-blk-n, .ed-blk-k, .ed-out-name, .ed-step, .ed-chip, .ed-ram, .ed-toggle')) {
      if (t.getClientRects().length && t.scrollWidth > t.clientWidth + 1) bad.push(`"${t.textContent.slice(0, 30)}" overflows`);
    }
    for (const b of ed.querySelectorAll('.ed-block, .ed-insp')) {
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
    for (const view of ['sound', 'flow']) {
      await page.evaluate(async ({ layout, view }) => {
        document.querySelector(`[data-layout="${layout}"]`).click();
        await new Promise((r) => setTimeout(r, 150));
        if (view === 'flow') document.querySelector('.ed-out-fx').click();
        else document.querySelectorAll('.ed-out')[2].click();       // S3
        window.scrollTo(0, 0);
        await new Promise((r) => setTimeout(r, 250));
      }, { layout, view });
      const name = `ed2-${layout}-${view}-${w}`;
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
