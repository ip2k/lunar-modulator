// editor/editor.js -- the Advanced editor on the simulator's page (stage
// ED2, notes/2026-10-06-web-editor.md §4, §7, §8, §10, §11, §13, §14):
// loaded on first use, when the layout switch leaves Panel.
//
// - The shell: the app bar (the layout switch, the keys chip, follow,
//   undo and redo, RAM by part in percent of the FM-1's budget), the
//   outline with the FM-1's screen card, the detail bar.
// - Two views: the Flow (four strips into the Mix and the master slots;
//   selection only in this stage) and a sound's inspector (its engine by
//   the device's pages, both inserts, its MIDI effect).
// - Every control is built from the metadata (meta.json, §6); every value
//   reaches C as a packed record on the editor's own port of the worklet;
//   every text is C's (the shadow Worker's format and parse).
// - Follow both ways and the K1-K4 chips from the panel's view; one page
//   history with undo and redo for parameters; PLAY and EDIT keys.
// It names no engine, effect, kind or source. MIT licence, like the rest of
// this repository.

import {
  Meta, MIX_KEY, ROLE, T, SRC_EDITOR, SRC_PANEL, SOURCES, SOUNDS, INSERTS, MASTERS, LEVEL_MAX,
  packParam, packLevel, packOn, packView, decodeChanges, decodeView, applyToMirror, mirrorFromProject,
  blockKey, parseBlockKey, blockTag, viewFor, blockOfView, viewWords, controlKind, isBipolar, isLog, hasFlag,
  toPos, fromPos, zeroPos, stepValue, rawText, unitText, unitWords, flagWords, ramWords, ramPercent, toF32,
  ModMeta, T as REC_T, parseModKey,
} from './model.js';
import { History } from './history.js';
import { makeChains, cableIndex } from './chains.js';
import { makeProject } from './project.js';

const PREF = 'lunar.sim.editor.';
function pref(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(PREF + key);
    localStorage.setItem(PREF + key, String(value));
  } catch { /* storage blocked: the editor works in memory */ }
  return null;
}

const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');
const MOD = isMac ? '⌘' : 'Ctrl+';

function el(tag, cls, attrs = {}, kids = []) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : String(v));
  }
  for (const k of [].concat(kids)) if (k !== null && k !== undefined) e.append(k);
  return e;
}

let uidSeq = 0;
const nextId = (p) => `ed-${p}-${++uidSeq}`;

export async function startEditor(env) {
  const { sim, files, host, layoutSwitch, header, powerOn } = env;
  const css = el('link', null, { rel: 'stylesheet', href: new URL('editor.css', import.meta.url).href });
  document.head.append(css);
  const metaRes = await fetch(new URL('../meta.json', import.meta.url));
  const meta = new Meta(await metaRes.json());
  const mm = new ModMeta(meta);

  const st = {
    layout: 'panel', view: 'flow', sound: 0, selected: 's1', keys: 'play',
    followPanel: pref('follow-panel') !== '0', followEditor: pref('follow-editor') !== '0',
    port: null, node: null, mirror: null, gen: 0, loading: false, pendingChanges: [], panelView: null,
    ram: null, typing: false, dragKey: null, tag: 0, tags: new Map(), snapId: 0, snapWait: new Map(),
    lastViewSent: '', announceAt: 0, flash: null, teleOn: false, tele: null, lastPanelLine: '',
    live: null, picker: null, selCable: null, verdictDirty: false, teleSig: '',
  };
  const history = new History();
  const rows = new Map();         // `${key}:${uid}` -> row
  const fmtCache = new Map();

  // ---- the shell ----------------------------------------------------------
  const keysChip = el('button', 'ed-chip ed-keys', { type: 'button', onclick: () => setKeys(st.keys === 'play' ? 'edit' : 'play') });
  const followPanelBox = el('input', null, { type: 'checkbox', id: nextId('fp') });
  const followEditorBox = el('input', null, { type: 'checkbox', id: nextId('fe') });
  followPanelBox.checked = st.followPanel;
  followEditorBox.checked = st.followEditor;
  followPanelBox.addEventListener('change', () => { st.followPanel = followPanelBox.checked; pref('follow-panel', st.followPanel ? 1 : 0); });
  followEditorBox.addEventListener('change', () => { st.followEditor = followEditorBox.checked; pref('follow-editor', st.followEditor ? 1 : 0); });
  const undoBtn = el('button', 'ed-icon', { type: 'button', title: `Undo (${MOD}Z)`, text: 'Undo', onclick: () => undo() });
  const redoBtn = el('button', 'ed-icon', { type: 'button', title: `Redo (${isMac ? '⇧⌘Z' : 'Ctrl+Y'})`, text: 'Redo', onclick: () => redo() });
  const ramBar = el('span', 'ed-ram-bar', { 'aria-hidden': 'true' });
  const ramText = el('span', 'ed-ram-text', { text: 'RAM –' });
  const ramList = el('ul', 'ed-ram-list', { id: nextId('ram') });
  const ramBtn = el('button', 'ed-ram', { type: 'button', 'aria-expanded': 'false', 'aria-controls': ramList.id,
    onclick: () => { const open = ramList.hidden; ramList.hidden = !open; ramBtn.setAttribute('aria-expanded', String(open)); } },
  [el('span', 'ed-ram-label', { text: 'RAM' }), ramBar, ramText]);
  ramList.hidden = true;
  const title = el('span', 'ed-title', {}, [el('span', 'ed-brand', { text: 'Advanced editor' }), el('span', 'ed-project')]);
  const appbar = el('div', 'ed-appbar', { role: 'toolbar', 'aria-label': 'Editor' }, [
    el('div', 'ed-appbar-start', {}, [title]),
    el('div', 'ed-appbar-mid', {}, [keysChip,
      el('label', 'ed-toggle', { for: followPanelBox.id }, [followPanelBox, el('span', null, { text: 'Follow the panel' })]),
      el('label', 'ed-toggle', { for: followEditorBox.id }, [followEditorBox, el('span', null, { text: 'Open on the panel' })])]),
    el('div', 'ed-appbar-end', {}, [undoBtn, redoBtn, el('div', 'ed-ram-wrap', {}, [ramBtn, ramList])]),
  ]);

  const outline = el('nav', 'ed-outline', { 'aria-label': 'Outline' });
  const screen = el('canvas', 'ed-screen', { width: 240, height: 240, 'aria-label': 'The FM-1 screen, as on the panel' });
  const screenCap = el('p', 'ed-screen-cap');
  const card = el('section', 'ed-card', { 'aria-label': 'On the FM-1' }, [el('h3', 'ed-card-title', { text: 'On the FM-1' }), screen, screenCap]);
  const context = el('p', 'ed-context');
  const fromPanel = el('p', 'ed-from', { hidden: true });
  const view = el('div', 'ed-view');
  const histList = el('ol', 'ed-hist-list');
  const hist = el('section', 'ed-hist', { 'aria-label': 'Changes, both ways' }, [
    el('div', 'ed-sec-head', {}, [el('h3', 'ed-sec', { text: 'Changes, both ways' }), el('span', 'ed-note', { text: 'newest first' })]),
    histList]);
  const main = el('div', 'ed-main', {}, [el('div', 'ed-heads', {}, [context, fromPanel]), view, hist]);
  const detail = el('div', 'ed-detail', { 'aria-label': 'The selected parameter' });
  const live = el('div', 'ed-sr', { 'aria-live': 'polite', role: 'status' });
  const off = el('div', 'ed-off', {}, [
    el('p', null, { text: 'The editor edits the running FM-1. Power it on to start.' }),
    el('button', 'ed-power', { type: 'button', text: 'Power on', onclick: () => powerOn() })]);
  const body = el('div', 'ed-body', {}, [outline, card, main]);
  const root = el('section', 'ed', { 'aria-label': 'Advanced editor', 'data-keys': 'play' }, [appbar, off, body, detail, live]);
  host.append(root);
  const chains = makeChains({
    st, meta, mm, el, history, files, root, nextId, sendOps, say, showRefusal, select, render, blockOf, engineName,
    inspector, sliderControl, rowShell, segControl, levelRow, renderHistory, snapshotSoon, setValue, openOnPanel,
    onStruct: (e) => project.onStruct(e),
  });
  // Stage ED4: drop targets, export, the library, links, search, A/B, Memory
  // and undo's snapshot fallback.
  const project = makeProject({
    st, meta, el, files, root, view, nextId, say, select, render, blockOf, engineName, rows, selectRow: (r) => selectRow(r),
    snapshotSoon, history, undo: () => undo(), redo: () => redo(), setKeys: (m) => setKeys(m), post,
  });

  // ---- PLAY and EDIT (§13) ---------------------------------------------------
  function setKeys(mode) {
    if (mode === st.keys) return;
    st.keys = mode;
    sim.keysToEditor = mode === 'edit';
    if (mode === 'edit' && sim.releaseKeys) sim.releaseKeys();
    root.dataset.keys = mode;
    keysChip.innerHTML = '';
    keysChip.append('Keys ', el('b', null, { text: mode === 'play' ? 'PLAY' : 'EDIT' }),
      el('span', 'ed-hint', { text: mode === 'play' ? ` · ${MOD}E edits` : ' · Esc plays' }));
    keysChip.setAttribute('aria-label', mode === 'play'
      ? `Keys play the FM-1. ${MOD}E gives them to the editor.` : 'Keys edit. Escape gives them back to the FM-1.');
  }
  st.keys = '';
  setKeys('play');
  root.addEventListener('focusin', (e) => { if (!layoutSwitch.contains(e.target)) setKeys('edit'); });
  root.addEventListener('pointerdown', (e) => { if (!layoutSwitch.contains(e.target)) setKeys('edit'); });
  const device = document.querySelector('.device-wrap');
  if (device) {
    device.addEventListener('pointerdown', () => setKeys('play'));
    device.addEventListener('focusin', () => setKeys('play'));
  }
  window.addEventListener('keydown', (e) => {
    if (st.layout === 'panel') return;
    const mod = isMac ? e.metaKey : e.ctrlKey;
    if (mod && !e.altKey && e.key.toLowerCase() === 'e') {
      e.preventDefault();
      if (st.keys === 'play') { setKeys('edit'); focusSelection(); } else toPlay();
      return;
    }
    const inText = e.target.closest && e.target.closest('input[type=text], input[type=search], select');
    if (project.onKey(e, mod, inText)) return;
    if (st.keys !== 'edit') return;
    if (e.key === 'Escape' && !st.typing) { e.preventDefault(); toPlay(); return; }
    if (mod && !inText && (e.key.toLowerCase() === 'z' || e.key.toLowerCase() === 'y')) {
      e.preventDefault();
      if (e.key.toLowerCase() === 'y' || e.shiftKey) redo(); else undo();
    }
  });
  function toPlay() {
    if (document.activeElement && root.contains(document.activeElement)) document.activeElement.blur();
    setKeys('play');
  }
  function focusSelection() {
    const r = root.querySelector('.ed-row.is-sel [role=slider], .ed-row.is-sel button, .ed-block.is-sel') ||
      root.querySelector('.ed-view [tabindex="0"], .ed-view button');
    if (r) r.focus();
  }

  // ---- layouts (§4, §14) -------------------------------------------------------
  function setLayout(name) {
    st.layout = name;
    root.dataset.layout = name;
    if (name === 'panel') {
      header.append(layoutSwitch);
      setKeys('play');
      subscribe();
      return;
    }
    appbar.querySelector('.ed-appbar-start').prepend(layoutSwitch);
    render();
    subscribe();
  }

  // ---- the port, the snapshot and the change feed (§5, §7) ----------------------
  function attach() {
    if (!sim.node || st.node === sim.node) return;
    st.node = sim.node;
    st.teleSig = '';
    const ch = new MessageChannel();
    st.port = ch.port1;
    st.port.onmessage = (e) => onPort(e.data);
    sim.node.port.postMessage({ type: 'editor-port', port: ch.port2 }, [ch.port2]);
    const floats = meta.doc.telemetry ? meta.doc.telemetry.floats : 0;
    for (let i = 0; i < 2 && floats; ++i) {
      const b = new ArrayBuffer(floats * 4);
      st.port.postMessage({ type: 'telemetry-buffer', buffer: b }, [b]);
    }
    st.mirror = null;
    st.panelView = null;
    history.clear();
    snapshot();
    subscribe();
  }
  function detach() {
    if (st.port) st.port.close();
    Object.assign(st, { port: null, node: null, mirror: null, ram: null, panelView: null });
    render();
  }

  function post(m, transfer) { if (st.port) st.port.postMessage(m, transfer || []); }

  function newTag(info) {
    st.tag = st.tag >= 0xffff ? 1 : st.tag + 1;
    st.tags.set(st.tag, info);
    if (st.tags.size > 512) st.tags.delete(st.tags.keys().next().value);
    return st.tag;
  }
  function sendOps(bytes, info) {
    if (!st.port) return 0;
    const tag = newTag(info);
    st.inflight += 1;
    post({ type: 'edit', tag, bytes }, [bytes.buffer]);
    return tag;
  }

  async function snapshot() {
    if (!st.port) return;
    st.loading = true;
    const id = ++st.snapId;
    const reply = await new Promise((resolve) => {
      st.snapWait.set(id, resolve);
      post({ type: 'snapshot', id, kind: 1 });
    });
    if (id !== st.snapId) return;        // a newer one is on its way
    // Refused while the module is still starting: asked again shortly.
    if (!reply.ok) { if (st.port) setTimeout(() => { if (id === st.snapId) snapshot(); }, 250); return; }
    st.live = reply.bytes.slice(0);
    st.liveGen = reply.gen >>> 0;
    const r = await files.shadow('save', { kind: 1, live: reply.bytes, mod: true });
    if (id !== st.snapId) return;
    if (!r || !r.text) { if (st.port) setTimeout(() => { if (id === st.snapId) snapshot(); }, 250); return; }
    st.mirror = mirrorFromProject(meta, JSON.parse(r.text), r.mod);
    st.gen = reply.gen >>> 0;
    st.loading = false;
    const waiting = st.pendingChanges;
    st.pendingChanges = [];
    render();
    for (const c of waiting) onChanges(c);
    project.applyPendingSel();
  }
  let snapTimer = 0;
  function snapshotSoon() {
    clearTimeout(snapTimer);
    snapTimer = setTimeout(() => snapshot(), 60);
  }

  function onPort(m) {
    switch (m.type) {
      case 'snapshot': {
        const w = st.snapWait.get(m.id);
        if (w) { st.snapWait.delete(m.id); w(m); }
        break;
      }
      case 'changes': onChanges(decodeChanges(m.bytes)); break;
      case 'resync': snapshotSoon(); break;
      case 'edited': onEdited(m.tag, m.codes); break;
      case 'view': onView(decodeView(m.bytes)); break;
      case 'ram': onRam(m); break;
      case 'telemetry':
        onTelemetry(new Float32Array(m.buffer));
        post({ type: 'telemetry-buffer', buffer: m.buffer }, [m.buffer]);
        break;
      default: break;
    }
  }

  function onChanges(list) {
    if (st.loading || !st.mirror) { st.pendingChanges.push(list); return; }
    project.staleSoon();
    let structure = false, cables = false;
    const structFrom = new Set();       // sources whose structural change this batch already holds
    for (const c of list) {
      if (c.gen <= st.gen) continue;
      st.gen = c.gen;
      const info = c.src === SRC_EDITOR ? st.tags.get(c.tag) : null;
      const origin = c.src === SRC_PANEL ? 'panel' : SOURCES[c.src] || 'host';
      const t = c.rec.type;
      if (t === REC_T.LOADED) project.onLoaded();      // A/B: a load sets A (§9)
      // The panel's (or a script's) structural change, into the history
      // from the mirror as it was; the cables it re-aimed come with it.
      if (c.src !== SRC_EDITOR && origin !== 'load' && (t === REC_T.UNIT || t === REC_T.MODULE || t === REC_T.SWAP || t === REC_T.MOVE)) {
        chains.fromPanel(c.rec, origin);
        structFrom.add(c.src);
      }
      const r = applyToMirror(meta, st.mirror, c.rec);
      if (r === 'structure') { structure = true; continue; }
      if (!r) continue;
      if (r.cable !== undefined) {
        cables = true;
        if (c.src !== SRC_EDITOR && !structFrom.has(c.src) && origin !== 'load') {
          for (const f of chains.cableFields(r.was, r.now)) {
            history.record({ target: `${r.key}:${f}`, label: chains.cableLabel(r.cable, f), before: chains.fieldOf(r.was, f),
              after: chains.fieldOf(r.now, f), origin, how: 'knob', info: { key: r.key, uid: f } });
          }
        }
        continue;
      }
      // A kit's pad chosen: its per-pad values are the new pad's, which the
      // feed does not carry, so the mirror is taken again.
      const fp = typeof r.uid === 'number' ? paramOf(r.key, r.uid) : null;
      if (fp && hasFlag(fp, 'focus') && r.before !== r.after) structure = true;
      const target = `${r.key}:${r.uid}`;
      if (info) {
        if (info.entry && !info.struct) history.confirm(info.entry, r.after);
      } else if (c.src !== SRC_EDITOR) {
        const origin = c.src === SRC_PANEL ? 'panel' : SOURCES[c.src] || 'host';
        history.record({ target, label: labelOf(r.key, r.uid), before: r.before, after: r.after, origin, how: 'knob',
          info: { key: r.key, uid: r.uid, engine: engineOf(r.key) } });
        panelChanged(r);
      }
      if (st.dragKey !== target) refreshValue(r.key, r.uid);
    }
    if (structure) snapshotSoon();
    else if (cables) {
      // A cable's verdict is the planner's: the mirror is taken again, once
      // no drag or typed value is in hand.
      if (st.dragKey || st.typing) st.verdictDirty = true;
      else snapshotSoon();
    }
    renderHistory();
  }

  function onEdited(tag, codes) {
    st.inflight = Math.max(0, st.inflight - 1);
    project.staleSoon();
    const info = st.tags.get(tag);
    if (!info) return;
    const list = codes && codes.length ? Array.from(codes) : [];
    const code = list.find((c) => c !== 0 && c < 32) || 0;
    const late = list.find((c) => c >= 32) || 0;
    if (code && !info.verb) {
      if (info.entry) history.drop(info.entry);
      const words = chains.verdictWords(code);
      say(`${info.label || 'The edit'}: ${words}.`, true);
      showRefusal(info.label, words);
      snapshotSoon();
      renderHistory();
    } else if (late) {
      // A cable written but left out by the planner: kept, and said why.
      const words = chains.verdictWords(late);
      say(`${info.label || 'The cable'} is written but does not run: ${words}.`);
      showRefusal(`${info.label || 'The cable'} does not run`, words);
    }
    if (!code && info.undo && info.entryRef) project.checkUndo(info.entryRef);   // §8's hash check
    // The tag stays known until its change has come back.
    setTimeout(() => st.tags.delete(tag), 2000);
  }

  // ---- the panel's view: follow, K1-K4 (§7) ---------------------------------------
  function onView(v) {
    const was = st.panelView;
    st.panelView = v;
    const words = viewWords(v);
    screenCap.textContent = `${words}: the page the panel shows now`;
    context.innerHTML = '';
    context.append(el('span', 'ed-ctx-k', { text: 'On the panel now: ' }), words);
    markKnobs();
    markPanelBlock();
    const moved = !was || was.mode !== v.mode || was.sound !== v.sound || was.page !== v.page || was.slot !== v.slot || was.arp !== v.arp;
    if (!moved || st.layout !== 'workbench' || !st.followPanel || st.typing || st.dragKey || st.picker) return;
    if (st.keys === 'edit' && view.contains(document.activeElement)) return;     // a hand is in the editor
    const at = blockOfView(v);
    if (!at) return;
    if (cableIndex(at.key) >= 0 || parseModKey(at.key) >= 0) {
      if (cableIndex(at.key) >= 0) st.selCable = at.key;
      select(at.key, { view: 'mod', quiet: true });
    } else if (at.key === MIX_KEY || parseBlockKey(at.key).role === ROLE.MASTER) {
      select(at.key, { view: 'flow', quiet: true, page: at.page });
    } else {
      select(at.key, { view: 'sound', quiet: true, page: at.page });
    }
  }

  function markKnobs() {
    for (const c of root.querySelectorAll('.ed-k')) { c.hidden = true; c.textContent = ''; }
    const v = st.panelView;
    if (!v) return;
    v.knobs.forEach((k, i) => {
      let row = null;
      if (k.kind === 1) row = rows.get(`${blockKey(k.role, k.sound, k.slot)}:${k.uid}`);
      else if (k.kind === 2) row = rows.get(`${blockKey(ROLE.SOUND, k.sound)}:level`);
      if (row && row.k) { row.k.hidden = false; row.k.textContent = `K${i + 1}`; row.k.title = `KNOB${i + 1} turns this now`; }
    });
  }
  function markPanelBlock() {
    const at = st.panelView ? blockOfView(st.panelView) : null;
    for (const b of root.querySelectorAll('[data-block]')) b.classList.toggle('is-panel', !!at && b.dataset.block === at.key);
  }

  // A change made on the panel: the row lights, the line says it, once a
  // second at most it is spoken.
  function panelChanged(r) {
    const row = rows.get(`${r.key}:${r.uid}`);
    const v = st.panelView;
    let knob = 'the panel';
    if (v) {
      const i = v.knobs.findIndex((k) => (k.kind === 1 && `${blockKey(k.role, k.sound, k.slot)}:${k.uid}` === `${r.key}:${r.uid}`) ||
        (k.kind === 2 && r.uid === 'level' && blockKey(ROLE.SOUND, k.sound) === r.key));
      if (i >= 0) knob = `KNOB${i + 1}`;
    }
    const label = labelOf(r.key, r.uid);
    fromPanel.hidden = false;
    fromPanel.innerHTML = '';
    fromPanel.append(el('b', null, { text: `From the panel: ${knob}` }), ` ${label} `,
      el('span', 'ed-was', { text: textOf(r.key, r.uid, r.before) }), ' → ', el('b', null, { text: textOf(r.key, r.uid, r.after) }));
    if (row && !reduced()) {
      row.el.classList.remove('is-flash');
      void row.el.offsetWidth;
      row.el.classList.add('is-flash');
    }
    const now = performance.now();
    if (now - st.announceAt > 1000) {
      st.announceAt = now;
      say(`From the panel: ${label}, ${textOf(r.key, r.uid, r.after)}`);
    }
  }

  // At most one announcement a second (§13): the first at once, then the
  // latest of any that follow, when the second is up.
  let sayAt = -1e9, sayTimer = 0, sayLast = '';
  function say(text) {
    const wait = 1000 - (performance.now() - sayAt);
    sayLast = text;
    if (wait <= 0 && !sayTimer) { sayAt = performance.now(); live.textContent = text; return; }
    if (!sayTimer) {
      sayTimer = setTimeout(() => { sayTimer = 0; sayAt = performance.now(); live.textContent = sayLast; }, Math.max(0, wait));
    }
  }

  // ---- RAM by part (§11: a percentage of the FM-1's budget only) -----------------------
  function onRam(m) {
    st.ram = { total: m.total, budget: m.budget, parts: Array.from(m.parts) };
    renderRam();
  }
  function renderRam() {
    const r = st.ram;
    ramBar.innerHTML = '';
    ramList.innerHTML = '';
    if (!r) { ramText.textContent = '–'; return; }
    const over = r.total > r.budget;
    ramText.textContent = over ? `${ramPercent(r.total - r.budget, r.budget)} % over` : `${ramPercent(r.total, r.budget)} %`;
    ramBtn.classList.toggle('is-over', over);
    const names = [];
    for (let k = 0; k < SOUNDS; ++k) {
      const b = st.mirror && st.mirror.blocks.get(blockKey(ROLE.SOUND, k));
      names.push([`S${k + 1}`, b ? engineName(b.engine) : 'empty', `ed-s${k + 1}`]);
    }
    names.push(['Master', 'M1 and M2', 'ed-part-master'], ['Shared', 'Mix, sequencer, modulation', 'ed-part-rest']);
    const scale = Math.max(r.budget, r.total);
    r.parts.forEach((bytes, i) => {
      if (bytes > 0) ramBar.append(el('span', `ed-ram-seg ${names[i][2]}`, { style: `width:${(100 * bytes / scale).toFixed(2)}%` }));
      ramList.append(el('li', null, {}, [el('span', `ed-sw ${names[i][2]}`, { 'aria-hidden': 'true' }),
        el('span', 'ed-ram-name', { text: `${names[i][0]} ${names[i][1]}` }), el('b', null, { text: ramWords(bytes, r.budget) })]));
    });
    ramList.append(el('li', 'ed-ram-free', {}, [el('span', 'ed-sw', { 'aria-hidden': 'true' }), el('span', 'ed-ram-name', { text: 'Free' }),
      el('b', null, { text: over ? 'none' : ramWords(r.budget - r.total, r.budget) })]));
    ramBtn.setAttribute('aria-label', `RAM ${ramText.textContent} of the FM-1's memory. Show it by part.`);
  }

  // ---- telemetry: the Flow's meters, only while they are seen (§12) ----------------------
  // Only what the view shows, only while it is seen (§12): the meters and
  // gain reduction for the Flow and a sound, module outputs and each
  // cable's destination for Modulation.
  let flowSeen = false;
  const seen = new IntersectionObserver((list) => {
    flowSeen = list.some((x) => x.isIntersecting);
    subscribe();
  });
  seen.observe(view);
  function subscribe() {
    const want = !!st.port && st.layout !== 'panel' && flowSeen && document.visibilityState === 'visible' && !!st.mirror;
    const rowsOn = want ? chains.wantRows(st.view) : [];
    const sig = rowsOn.join(',');
    st.teleOn = want && rowsOn.length > 0;
    if (!st.port || sig === st.teleSig) return;
    st.teleSig = sig;
    const mask = new Uint32Array(meta.doc.telemetry ? meta.doc.telemetry.mask_words : 4);
    for (const b of rowsOn) mask[b >> 5] |= 1 << (b & 31);
    post({ type: 'subscribe', mask });
  }
  document.addEventListener('visibilitychange', subscribe);
  function meterSection() {
    return meta.doc.telemetry ? meta.doc.telemetry.sections.find((s) => s.name === 'meters') : null;
  }
  let teleSkip = 0;
  function onTelemetry(f) {
    if (!st.teleOn) return;
    if (reduced() && (teleSkip++ & 1)) return;          // 15 a second under reduced motion
    const sec = meterSection();
    if (!sec) return;
    for (const m of root.querySelectorAll('[data-meter]')) {
      const r = sec.rows.indexOf(m.dataset.meter);
      if (r < 0) continue;
      const peak = f[sec.offset + r * sec.fields.length];
      const db = peak > 0 ? 20 * Math.log10(peak) : -90;
      m.style.setProperty('--lvl', `${Math.max(0, Math.min(1, (db + 60) / 60)).toFixed(3)}`);
    }
    chains.onTelemetry(f);
  }

  // ---- names and text ----------------------------------------------------------------
  function engineName(id) { const e = meta.engine(id); return e ? e.name : id; }
  function blockOf(key) { return st.mirror ? st.mirror.blocks.get(key) || null : null; }
  function paramOf(key, uid) {
    const b = blockOf(key);
    return b ? meta.param(b.engine, uid) : null;
  }
  function labelOf(key, uid) {
    if (cableIndex(key) >= 0) return chains.cableLabel(cableIndex(key), uid);
    if (uid === 'level') return `${blockTag(key)} Level`;
    if (uid === 'on') return `${blockTag(key)} On`;
    const p = paramOf(key, uid);
    return `${blockTag(key)} ${p ? p.name : `#${uid}`}`;
  }
  function valueOf(key, uid) {
    if (!st.mirror) return 0;
    if (cableIndex(key) >= 0) return chains.cableGet(cableIndex(key), uid);
    if (uid === 'level') return st.mirror.levels[parseBlockKey(key).sound];
    const b = blockOf(key);
    if (!b) return 0;
    if (uid === 'on') return b.on;
    return b.values.get(uid);
  }
  function textOf(key, uid, v) {
    if (cableIndex(key) >= 0) return chains.cableText(cableIndex(key), uid, v);
    if (uid === 'level') return `${Math.round(v)} %`;
    if (uid === 'on') return v ? 'on' : 'off';
    const b = blockOf(key);
    const p = b ? meta.param(b.engine, uid) : null;
    if (!p) return String(v);
    return withUnit(p, fmt(b.engine, p, v));
  }
  function withUnit(p, text) {
    const u = unitText(p);
    return p.type === 'enum' || !u ? text : `${text} ${u}`;
  }
  // C's text for a value (the shadow Worker's fm1_look_value), the raw
  // number until it comes; the caller is redrawn when it does.
  function fmt(id, p, v, after) {
    if (p.type === 'enum') return rawText(p, v);
    const k = `${id}:${p.uid}:${toF32(v)}`;
    if (fmtCache.has(k)) return fmtCache.get(k);
    if (files.shadow && sim.wasm) {
      fmtCache.set(k, rawText(p, v));
      files.shadow('format', { id, uid: p.uid, values: [v] }).then((r) => {
        if (r && r.texts && r.texts[0]) {
          fmtCache.set(k, r.texts[0].trim());
          if (fmtCache.size > 4000) fmtCache.delete(fmtCache.keys().next().value);
          if (after) after(); else refreshText(id, p.uid);
        }
      });
    }
    return rawText(p, v);
  }

  // ---- edits ------------------------------------------------------------------------
  // A value from the editor: into the mirror and the history, then to C.
  function setValue(key, uid, v, how) {
    if (!st.mirror) return;
    const before = valueOf(key, uid);
    if (cableIndex(key) >= 0 && (uid === 'on' || uid === 'voice')) v = !!v;
    if (uid !== 'on' && uid !== 'level' && paramOf(key, uid) && paramOf(key, uid).type === 'float') v = toF32(v);
    if (v === before) return;
    const target = `${key}:${uid}`;
    // A kit's per-pad value goes to the pad shown now, named in the record,
    // so undo reaches the same pad wherever the panel's focus is then.
    const p = paramOf(key, uid);
    const focus = p && hasFlag(p, 'per_focus') ? chains.padOf(key) : undefined;
    const entry = history.record({ target: focus !== undefined ? `${target}:${focus}` : target, label: labelOf(key, uid), before, after: v, origin: 'editor', how,
      info: { key, uid, engine: engineOf(key), focus } });
    write(key, uid, v, { entry: entry ? entry.id : 0, label: labelOf(key, uid), focus });
    renderHistory();
  }
  function write(key, uid, v, info) {
    if (cableIndex(key) >= 0) {
      chains.cableSet(cableIndex(key), uid, v, info);
      refreshValue(key, uid);
      return;
    }
    const b = parseBlockKey(key);
    let bytes;
    if (uid === 'level') {
      st.mirror.levels[b.sound] = v;
      bytes = packLevel(b.sound, v);
    } else if (uid === 'on') {
      blockOf(key).on = v;
      bytes = packOn(b.sound, b.slot, v);
    } else {
      const p = paramOf(key, uid);
      const blk = blockOf(key);
      const focus = info && info.focus !== undefined ? info.focus : undefined;
      if (focus === undefined || focus === chains.padOf(key)) blk.values.set(uid, v);
      if (focus !== undefined && blk.pads && blk.pads[focus]) blk.pads[focus].set(uid, v);
      const at = focus !== undefined ? { ...b, uid, focus } : { ...b, uid };
      bytes = p.type === 'enum' ? packParam({ ...at, index: Math.round(v) }) : packParam({ ...at, value: v });
    }
    sendOps(bytes, info);
    refreshValue(key, uid);
  }
  // A block's engine now: a step recorded for another engine (the panel
  // changed it since) cannot be undone by value, and is said so (the
  // structural undo is ED3's).
  function engineOf(key) { const b = blockOf(key); return b ? b.engine : null; }
  function stale(e, verb) {
    if (engineOf(e.info.key) === e.info.engine) return false;
    say(`${e.label} cannot be ${verb}: ${blockTag(e.info.key)} has another engine now.`);
    showRefusal(e.label, `${blockTag(e.info.key)} has another engine now`);
    renderHistory();
    return true;
  }
  function undo() {
    const e = history.undo();
    if (e && e.info && e.info.struct) {
      // §8: checked by hash once C has applied it (onEdited); with nothing to send, now.
      if (!chains.undoStruct(e, false)) project.checkUndo(e);
      renderHistory();
      return;
    }
    if (!e || stale(e, 'undone')) return;
    write(e.info.key, e.info.uid, e.before, { undo: true, label: e.label, focus: e.info.focus });
    say(`Undone: ${e.label}, ${textOf(e.info.key, e.info.uid, e.before)}`);
    renderHistory();
  }
  function redo() {
    const e = history.redo();
    if (e && e.info && e.info.struct) { chains.undoStruct(e, true); renderHistory(); return; }
    if (!e || stale(e, 'redone')) return;
    write(e.info.key, e.info.uid, e.after, { redo: true, label: e.label, focus: e.info.focus });
    say(`Redone: ${e.label}, ${textOf(e.info.key, e.info.uid, e.after)}`);
    renderHistory();
  }

  // Follow, editor to panel: the page of what is selected opens there.
  let viewTimer = 0;
  function openOnPanel(key, page) {
    if (!st.followEditor || !st.port) return;
    const v = viewFor(key, page || 1);
    if (!v) return;
    const sig = JSON.stringify(v);
    const at = st.panelView ? blockOfView(st.panelView) : null;
    if (at && at.key === key && (!page || at.page === page)) { st.lastViewSent = sig; return; }
    if (sig === st.lastViewSent) return;
    clearTimeout(viewTimer);
    viewTimer = setTimeout(() => {
      st.lastViewSent = sig;
      sendOps(packView(v.mode, v.keys), { verb: true });
    }, 120);
  }

  // ---- selection and the views (§10) -------------------------------------------------
  function select(key, opt = {}) {
    if (key !== MIX_KEY && !parseBlockKey(key) && cableIndex(key) < 0) return;
    if (cableIndex(key) >= 0) st.selCable = key;
    const same = key === st.selected && (!opt.view || opt.view === st.view) && view.firstChild;
    if (same && opt.quiet) {             // following the panel to where it already is
      markPanelBlock();
      return;
    }
    st.selected = key;
    const b = parseBlockKey(key);
    if (opt.view) st.view = opt.view;
    if (b && b.role !== ROLE.MASTER && b.role !== ROLE.MODULE) st.sound = b.sound;
    render();
    if (!opt.quiet) openOnPanel(key, opt.page || 1);
    if (opt.page) {
      const pg = root.querySelector(`[data-block="${key}"] [data-page="${opt.page}"]`);
      if (pg && pg.scrollIntoView && !opt.noScroll) pg.scrollIntoView({ block: 'nearest', behavior: reduced() ? 'auto' : 'smooth' });
    }
  }

  function render() {
    // The control that had the keys keeps them across a redraw (data-fk).
    const ae = document.activeElement;
    const fkEl = ae && root.contains(ae) && ae.closest ? ae.closest('[data-fk]') : null;
    const fk = st.focusAfter || (fkEl ? fkEl.dataset.fk : null);
    if (st.mirror) st.focusAfter = null;
    chains.closePicker();
    root.classList.toggle('is-off', !st.port || !st.mirror);
    off.hidden = !!st.port;
    title.querySelector('.ed-project').textContent = files.title ? `· ${files.title}` : '';
    renderOutline();
    rows.clear();
    view.innerHTML = '';
    if (st.port && st.mirror) {
      const card = project.arrivalCard();
      if (card) view.append(card);
      if (st.view === 'flow') view.append(flowView());
      else if (st.view === 'mod') view.append(chains.modView());
      else if (st.view === 'memory') view.append(project.memoryView());
      else if (st.view === 'ab') view.append(project.compareView());
      else if (st.view === 'library') {
        const slot = el('div', 'ed-lib-slot');
        view.append(slot);
        project.libraryView().then((v) => { if (slot.isConnected) slot.replaceWith(v); });
      } else view.append(soundView(st.sound));
    }
    if (fk) {
      const t = root.querySelector(`[data-fk="${CSS.escape(fk)}"]`);
      if (t) t.focus({ preventScroll: true });
    }
    markKnobs();
    markPanelBlock();
    renderHistory();
    renderRam();
    renderDetail();
    subscribe();
  }

  function renderOutline() {
    outline.innerHTML = '';
    const mk = (label, short, cls, on, current, extra) => el('button', `ed-out ${cls || ''}${current ? ' is-sel' : ''}`,
      { type: 'button', onclick: on, 'aria-current': current ? 'true' : null, title: label }, [
        el('span', 'ed-out-tag', { text: short }), el('span', 'ed-out-name', { text: label }),
        extra ? el('span', 'ed-out-x', { text: extra }) : null]);
    outline.append(el('h3', 'ed-out-h', { text: 'Sounds' }));
    for (let k = 0; k < SOUNDS; ++k) {
      const b = blockOf(blockKey(ROLE.SOUND, k));
      outline.append(mk(b ? engineName(b.engine) : 'Empty', `S${k + 1}`, `ed-s${k + 1}`,
        () => select(blockKey(ROLE.SOUND, k), { view: 'sound' }), st.view === 'sound' && st.sound === k));
    }
    outline.append(el('h3', 'ed-out-h', { text: 'Signal' }));
    outline.append(mk('Flow and effects', 'FX', 'ed-out-fx', () => { st.view = 'flow'; render(); }, st.view === 'flow'));
    const nMods = st.mirror ? st.mirror.rack.filter(Boolean).length : 0;
    const nCables = st.mirror ? st.mirror.cables.filter((c) => c.flags & 1).length : 0;
    outline.append(mk('Modulation', 'MOD', 'ed-out-mod', () => { st.view = 'mod'; render(); }, st.view === 'mod',
      st.mirror ? `${nMods}·${nCables}` : null));
    outline.append(el('h3', 'ed-out-h', { text: 'Project' }));
    outline.append(mk('Library', 'LIB', 'ed-out-lib', () => { st.view = 'library'; render(); }, st.view === 'library'));
    outline.append(mk('Compare A/B', 'A/B', 'ed-out-ab', () => { st.view = 'ab'; render(); }, st.view === 'ab',
      st.ab && st.ab.A ? st.ab.playing : null));
    outline.append(mk('Memory', 'RAM', 'ed-out-mem', () => { st.view = 'memory'; render(); }, st.view === 'memory'));
    outline.append(el('button', 'ed-out ed-out-search', { type: 'button', onclick: () => project.openSearch(), title: `Search (${MOD}K)` }, [
      el('span', 'ed-out-tag', { text: MOD === '⌘' ? '⌘K' : '^K' }), el('span', 'ed-out-name', { text: 'Search' })]));
  }

  // The Flow (§10, mockup 01): four strips into the Mix and the master slots.
  function flowView() {
    const wrap = el('div', 'ed-flow-wrap');
    const legend = el('p', 'ed-legend', {}, [el('span', 'ed-l-audio', { text: 'audio' }), el('span', 'ed-l-empty', { text: 'empty slot' }),
      el('span', 'ed-l-sel', { text: 'selected' })]);
    const strips = el('div', 'ed-strips');
    for (let k = 0; k < SOUNDS; ++k) strips.append(strip(k));
    const masters = el('div', 'ed-masters', { role: 'group', 'aria-label': 'Master' });
    masters.append(flowBlock(MIX_KEY, 'Mix', 'MIX', `${st.mirror.blocks.size ? soundsOn() : 0} sounds`, 'ed-mix'));
    for (let j = 0; j < MASTERS; ++j) {
      const key = blockKey(ROLE.MASTER, 0, j);
      const b = blockOf(key);
      masters.append(chains.movable(flowBlock(key, b ? engineName(b.engine) : 'empty', `M${j + 1}`, b ? summary(key) : '', b ? '' : 'is-empty'), key));
    }
    masters.append(el('div', 'ed-out-meter', {}, [el('span', 'ed-blk-k', { text: 'OUT' }), el('span', 'ed-meter', { 'data-meter': 'out', 'aria-hidden': 'true' })]));
    const flow = el('div', 'ed-flow', { 'aria-label': 'Flow' }, [strips, masters]);
    wrap.append(el('div', 'ed-sec-head', {}, [el('h2', 'ed-sec ed-sec-big', { text: 'Flow' }), legend]),
      el('p', 'ed-note ed-hint-move', { text: 'Drag an effect onto another slot to swap them, or pick one up with Space, aim with the arrows and drop with Space.' }), flow);
    const insp = el('div', 'ed-flow-insp');
    if (st.selected === MIX_KEY) insp.append(chains.mixInspector());
    else if (blockOf(st.selected)) insp.append(inspector(st.selected));
    else if (parseBlockKey(st.selected) && parseBlockKey(st.selected).role !== ROLE.MODULE) insp.append(emptyInspector(st.selected));
    wrap.append(insp);
    return wrap;
  }
  function soundsOn() { let n = 0; for (let k = 0; k < SOUNDS; ++k) if (blockOf(blockKey(ROLE.SOUND, k))) ++n; return n; }

  function strip(k) {
    const sk = blockKey(ROLE.SOUND, k);
    const s = blockOf(sk);
    const row = el('div', `ed-strip ed-s${k + 1}${s ? '' : ' is-empty'}`, { role: 'group', 'aria-label': `Sound ${k + 1}` });
    row.append(el('span', 'ed-tag', { text: `S${k + 1}` }));
    if (!s) {
      row.append(el('span', 'ed-strip-empty', { text: 'Empty' }), chains.pickerButton(sk));
      return project.wireDrop(row, sk);    // a sound file loads into an empty sound too
    }
    const mk = blockKey(ROLE.MFX, k, 0);
    const m = blockOf(mk);
    row.append(m ? flowBlock(mk, engineName(m.engine), 'MIDI', m.on ? 'on' : 'off', m.on ? '' : 'is-bypassed')
      : flowBlock(mk, 'none', 'MIDI', '', 'is-empty'));
    row.append(flowBlock(sk, engineName(s.engine), 'ENGINE', summary(sk)));
    for (let j = 0; j < INSERTS; ++j) {
      const ik = blockKey(ROLE.INSERT, k, j);
      const ib = blockOf(ik);
      row.append(chains.movable(flowBlock(ik, ib ? engineName(ib.engine) : 'empty', `IN${j + 1}`, ib ? summary(ik) : '', ib ? '' : 'is-empty'), ik));
    }
    const lvl = st.mirror.levels[k];
    row.append(el('div', 'ed-level', { title: `Level ${Math.round(lvl)} %` }, [
      el('span', 'ed-meter', { 'data-meter': meterRow(k), 'aria-hidden': 'true' }),
      el('span', 'ed-level-n', { 'data-level': String(k), text: `${Math.round(lvl)} %` })]));
    return row;
  }
  // The telemetry row of a sound's output: the metadata's name for it.
  function meterRow(k) {
    const sec = meterSection();
    if (!sec) return '';
    const rowsOf = sec.rows.filter((r) => !r.includes('.'));
    return rowsOf[k] || '';
  }
  // A block's short summary: its first page's first list entry, if it has one.
  function summary(key) {
    const b = blockOf(key);
    if (!b) return '';
    const pg = meta.pages(b.engine)[0];
    const p = pg && pg.params.find((x) => x.type === 'enum');
    return p ? rawText(p, b.values.get(p.uid)) : '';
  }
  function flowBlock(key, name, kind, sub, cls = '') {
    const btn = el('button', `ed-block ${cls}${st.selected === key ? ' is-sel' : ''}`,
      { type: 'button', 'data-block': key, 'data-fk': key, 'aria-pressed': st.selected === key ? 'true' : 'false',
        'aria-label': `${kind} ${name}${sub ? `, ${sub}` : ''}`, onclick: () => select(key, { view: 'flow' }) },
      [el('span', 'ed-blk-k', { text: kind }), el('span', 'ed-blk-n', { text: name }), sub ? el('span', 'ed-blk-s', { text: sub }) : null]);
    return key === MIX_KEY ? btn : project.wireDrop(btn, key);
  }

  // An empty slot: what it is, and its picker.
  function emptyInspector(key) {
    const b = parseBlockKey(key);
    const tag = b.role === ROLE.INSERT ? `IN${b.slot + 1}` : b.role === ROLE.MFX ? 'MIDI' : b.role === ROLE.MASTER ? `M${b.slot + 1}` : 'ENGINE';
    return el('section', 'ed-insp is-empty', { 'data-block': key, 'aria-label': `${blockTag(key)} empty` }, [
      el('header', 'ed-insp-head', {}, [el('span', 'ed-tag', { text: tag }), el('h3', 'ed-insp-name', { text: `${blockTag(key)} · empty` }), ...chains.headTools(key)])]);
  }

  // A sound (§10, mockup 02): the path, then its engine, inserts and MIDI effect.
  function soundView(k) {
    const sk = blockKey(ROLE.SOUND, k);
    const s = blockOf(sk);
    const wrap = el('div', 'ed-sound');
    const head = el('div', 'ed-sound-head', {}, [el('span', `ed-tag ed-s${k + 1}`, { text: `S${k + 1}` }),
      el('h2', 'ed-sound-name', { text: s ? `Sound ${k + 1}` : `Sound ${k + 1} is empty` }),
      s ? el('span', 'ed-note', { text: `${engineName(s.engine)} · level ${Math.round(st.mirror.levels[k])} %` }) : null]);
    wrap.append(head);
    if (!s) {
      wrap.append(emptyInspector(sk));
      return wrap;
    }
    const path = el('nav', 'ed-path', { 'aria-label': `Sound ${k + 1}'s chain` });
    const step = (key, text) => el('button', `ed-step${st.selected === key ? ' is-sel' : ''}`, { type: 'button', 'data-block': key,
      onclick: () => { select(key, { view: 'sound' }); const t = root.querySelector(`.ed-sound [data-block="${key}"].ed-insp`); if (t) t.scrollIntoView({ block: 'nearest' }); } }, [text]);
    const mk = blockKey(ROLE.MFX, k, 0);
    const m = blockOf(mk);
    if (m) path.append(step(mk, `${engineName(m.engine)} ${m.on ? 'on' : 'off'}`), el('span', 'ed-arrow', { 'aria-hidden': 'true', text: '→' }));
    path.append(step(sk, engineName(s.engine)));
    for (let j = 0; j < INSERTS; ++j) {
      const ik = blockKey(ROLE.INSERT, k, j);
      const ib = blockOf(ik);
      path.append(el('span', 'ed-arrow', { 'aria-hidden': 'true', text: '→' }), step(ik, `In${j + 1} ${ib ? engineName(ib.engine) : 'empty'}`));
    }
    path.append(el('span', 'ed-arrow', { 'aria-hidden': 'true', text: '→' }), el('span', 'ed-step is-static', { text: 'Mix' }));
    wrap.append(path);
    const cols = el('div', 'ed-cols');
    const engineCol = el('div', 'ed-col');
    engineCol.append(inspector(sk, { level: k }));
    const insCol = el('div', 'ed-col');
    for (let j = 0; j < INSERTS; ++j) {
      const ik = blockKey(ROLE.INSERT, k, j);
      if (blockOf(ik)) insCol.append(inspector(ik));
      else insCol.append(emptyInspector(ik));
    }
    cols.append(engineCol, insCol);
    const mfxCol = el('div', 'ed-col');
    mfxCol.append(m ? inspector(mk, { open: 3 }) : emptyInspector(mk));
    cols.append(mfxCol);
    wrap.append(cols);
    return wrap;
  }

  // ---- the inspector: controls from metadata (§6, §11, §13) ----------------------------------
  function inspector(key, opt = {}) {
    const b = blockOf(key);
    const e = meta.engine(b.engine);
    const bk = parseBlockKey(key);
    const tagText = bk.role === ROLE.SOUND ? 'ENGINE' : bk.role === ROLE.INSERT ? `IN${bk.slot + 1}` :
      bk.role === ROLE.MFX ? 'MIDI' : bk.role === ROLE.MODULE ? `RACK ${bk.slot + 1}` : `M${bk.slot + 1}`;
    const box = el('section', `ed-insp${st.selected === key ? ' is-sel' : ''}`, { 'data-block': key, 'aria-label': `${blockTag(key)} ${e ? e.name : b.engine}` });
    const head = el('header', 'ed-insp-head', {}, [
      el('span', `ed-tag${bk.role === ROLE.SOUND ? ` ed-s${bk.sound + 1}` : ''}`, { text: tagText }),
      el('h3', 'ed-insp-name', { text: e ? e.name : b.engine }),
      e && e.gpl ? el('span', 'ed-gpl', { text: 'GPL', title: `Licence: ${e.licence}` }) : null,
      el('span', 'ed-insp-ram', { text: e && st.ram ? `RAM ${ramWords(e.ram, st.ram.budget)}` : '' })]);
    box.append(head);
    if (st.mirror && st.mirror.cables && !opt.bare) head.append(el('span', 'ed-tools', {}, [...chains.headTools(key), ...project.headTools(key)]));
    if (e && e.credits) box.append(el('p', 'ed-credits', { text: `${e.credits}${e.group ? ` · ${meta.groupName(e.group)}` : ''}` }));
    if (!e) { box.append(el('p', 'ed-note', { text: `${b.engine} is not in this build's metadata.` })); return box; }
    const mt = opt.bare ? null : chains.meters(key);
    if (mt) box.append(mt);
    if (bk.role === ROLE.MFX) box.append(onRow(key));
    if (opt.level !== undefined) box.append(el('div', 'ed-page', { 'data-page': '0' }, [levelRow(opt.level)]));
    // A kit (API v4): the pad strip above its per-pad rows; the pad follows
    // the panel's focus, and choosing one here moves the panel's too.
    const fp = e.params.find((p) => hasFlag(p, 'focus') && !p.hidden && p.page >= 1);
    if (fp) {
      const strip = el('div', 'ed-page ed-padstrip', { 'data-page': String(fp.page) });
      strip.append(paramRow(key, fp, { page: fp.page }));
      strip.append(el('p', 'ed-note', { text: `Rows marked "pad" are the pad chosen here, ${rawText(fp, b.values.get(fp.uid))}.` }));
      box.append(strip);
    }
    meta.pages(b.engine).forEach((pg, i) => {
      const label = pg.name ? pg.name : `Page ${pg.page}`;
      if (opt.open && i >= opt.open) {
        const d = el('details', 'ed-page ed-page-more', { 'data-page': String(pg.page) });
        const sum = el('summary', 'ed-page-sum', {}, [el('span', 'ed-page-n', { text: label }),
          el('span', 'ed-page-vals', { text: pg.params.map((p) => `${p.name} ${textOf(key, p.uid, b.values.get(p.uid))}`).join(' · ') })]);
        d.append(sum);
        d.addEventListener('toggle', () => { if (d.open && !d.dataset.built) { d.dataset.built = '1'; for (const p of pg.params) d.append(paramRow(key, p, pg)); markKnobs(); } });
        box.append(d);
        return;
      }
      const page = el('div', 'ed-page', { 'data-page': String(pg.page) }, [el('div', 'ed-page-head', {}, [
        el('span', 'ed-page-n', { text: label }), el('span', 'ed-page-k', { text: pg.knobs })])]);
      for (const p of pg.params) if (p !== fp) page.append(paramRow(key, p, pg));
      box.append(page);
    });
    const into = opt.bare || !st.mirror.cables ? null : chains.cablesInto(key);
    if (into) box.append(into);
    return box;
  }

  function rowShell(key, uid, labelText, cls) {
    const id = nextId('l');
    const r = { key, uid, el: el('div', `ed-row ${cls || ''}`, { 'data-uid': String(uid) }), id };
    r.k = el('span', 'ed-k', { hidden: true });
    r.label = el('span', 'ed-label', { id, text: labelText });
    r.el.append(r.k, r.label);
    r.el.addEventListener('focusin', () => selectRow(r));
    r.el.addEventListener('pointerdown', () => selectRow(r));
    rows.set(`${key}:${uid}`, r);
    if (`${key}:${uid}` === st.selRow) r.el.classList.add('is-sel');
    return r;
  }
  function selectRow(r) {
    if (st.selRow === `${r.key}:${r.uid}`) return;
    for (const x of root.querySelectorAll('.ed-row.is-sel')) x.classList.remove('is-sel');
    r.el.classList.add('is-sel');
    st.selRow = `${r.key}:${r.uid}`;
    if (st.selected !== r.key) {
      st.selected = r.key;
      for (const x of root.querySelectorAll('[data-block]')) x.classList.toggle('is-sel', x.dataset.block === r.key);
    }
    renderDetail();
    openOnPanel(r.key, r.page || 1);
  }

  function levelRow(k) {
    const key = blockKey(ROLE.SOUND, k);
    const p = { uid: 'level', name: 'Level', type: 'float', min: 0, max: LEVEL_MAX, def: LEVEL_MAX, step: 1, unit: 'pct', flags: [] };
    const r = rowShell(key, 'level', `S${k + 1} Level`, 'ed-row-slider');
    r.p = p;
    r.page = null;
    sliderControl(r, p, () => st.mirror.levels[k], (v) => `${Math.round(v)} %`);
    return r.el;
  }

  function onRow(key) {
    const r = rowShell(key, 'on', 'On', 'ed-row-seg');
    const seg = el('div', 'ed-seg', { role: 'radiogroup', 'aria-labelledby': r.id });
    const b = blockOf(key);
    for (const [label, val] of [['Off', false], ['On', true]]) {
      const s = el('button', 'ed-segbtn', { type: 'button', role: 'radio', 'aria-checked': String(b.on === val), tabindex: b.on === val ? '0' : '-1', text: label,
        onclick: () => setValue(key, 'on', val, 'set') });
      seg.append(s);
    }
    r.update = () => {
      const on = blockOf(key) && blockOf(key).on;
      [...seg.children].forEach((s, i) => { const c = (i === 1) === !!on; s.setAttribute('aria-checked', String(c)); s.tabIndex = c ? 0 : -1; });
    };
    segKeys(seg, (i) => setValue(key, 'on', i === 1, 'key'));
    r.el.append(seg);
    return r.el;
  }

  function paramRow(key, p, pg) {
    const kind = controlKind(p);
    const r = rowShell(key, p.uid, p.name, `ed-row-${kind === 'slider' ? 'slider' : kind}`);
    r.p = p;
    r.page = pg.page;
    if (hasFlag(p, 'mod')) r.label.classList.add('can-mod');
    if (hasFlag(p, 'poly')) r.label.append(el('span', 'ed-poly', { role: 'img', 'aria-label': 'per voice', text: 'v', title: 'per voice: a per-voice cable may land here' }));
    if (hasFlag(p, 'per_focus')) r.label.append(el('span', 'ed-pad-b', { text: 'pad', title: 'per pad: the pad chosen above' }));
    if (kind === 'slider') sliderControl(r, p, () => valueOf(key, p.uid), (v) => withUnit(p, fmt(blockOf(key).engine, p, v)));
    else if (kind === 'segments' || kind === 'grid') segControl(r, p, kind);
    else listControl(r, p, kind);
    return r.el;
  }

  function segKeys(seg, pick) {
    seg.addEventListener('keydown', (e) => {
      if (st.keys !== 'edit') return;
      const btns = [...seg.querySelectorAll('[role=radio]')];
      const i = btns.indexOf(document.activeElement);
      if (i < 0) return;
      let j = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = Math.min(btns.length - 1, i + 1);
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = Math.max(0, i - 1);
      else if (e.key === 'Home') j = 0;
      else if (e.key === 'End') j = btns.length - 1;
      if (j < 0) return;
      e.preventDefault();
      btns[j].focus();
      pick(j);
    });
  }

  function segControl(r, p, kind) {
    const seg = el('div', `ed-seg${kind === 'grid' ? ' ed-seg-grid' : ''}`, { role: 'radiogroup', 'aria-labelledby': r.id });
    // Each segment at least as wide as the longest entry, so a name wraps
    // to a new row of segments, never inside a word.
    const longest = Math.max(...p.entries.map((x) => String(x).length));
    seg.style.setProperty('--minw', `calc(${(longest * 0.62).toFixed(2)}em + 22px)`);
    p.entries.forEach((name, i) => {
      seg.append(el('button', 'ed-segbtn', { type: 'button', role: 'radio', text: name, onclick: () => setValue(r.key, p.uid, i, 'set') }));
    });
    segKeys(seg, (i) => setValue(r.key, p.uid, i, 'key'));
    r.update = () => {
      const v = Math.round(valueOf(r.key, p.uid));
      [...seg.children].forEach((s, i) => { s.setAttribute('aria-checked', String(i === v)); s.tabIndex = i === v ? 0 : -1; });
    };
    r.update();
    r.el.append(seg);
  }

  function listControl(r, p, kind) {
    const wrap = el('div', 'ed-list');
    const select = el('select', 'ed-select', { 'aria-labelledby': r.id });
    p.entries.forEach((name, i) => select.append(el('option', null, { value: String(i), text: name })));
    const place = el('span', 'ed-place', { 'aria-hidden': 'true' });
    select.addEventListener('change', () => setValue(r.key, p.uid, Number(select.value), 'set'));
    if (kind === 'search') {
      const find = el('input', 'ed-find', { type: 'search', placeholder: `Filter ${p.entries.length}`, 'aria-label': `Filter ${p.name}` });
      find.addEventListener('input', () => {
        const q = find.value.trim().toLowerCase();
        for (const o of select.options) o.hidden = !!q && !o.textContent.toLowerCase().includes(q);
      });
      find.addEventListener('focus', () => { st.typing = true; });
      find.addEventListener('blur', () => { st.typing = false; });
      wrap.append(find);
    }
    wrap.append(select, place);
    r.update = () => {
      const v = Math.round(valueOf(r.key, p.uid));
      select.value = String(v);
      place.textContent = `${v + 1}/${p.entries.length}`;
    };
    r.update();
    r.el.append(wrap);
  }

  // A slider with a typed value field (ED5): LOG on its law, bipolar from
  // zero, one detent per arrow key (⇧ ten, ⌥ a tenth), Home and End, D the
  // default, Enter to type. A drag is one history step and sends at most one
  // op a frame; a `nolock` parameter is sent once, on release.
  // A row's name without its badges (the per-voice mark): the label's own text.
  const labelName = (r) => [...r.label.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim() || r.label.textContent;
  function sliderControl(r, p, get, text) {
    const s = el('div', 'ed-slider', { role: 'slider', tabindex: '0', 'aria-labelledby': r.id, 'data-fk': `${r.key}:${r.uid}`,
      'aria-valuemin': String(p.min), 'aria-valuemax': String(p.max) });
    const zero = isBipolar(p) ? el('span', 'ed-zero', { 'aria-hidden': 'true' }) : null;
    const fill = el('span', 'ed-fill', { 'aria-hidden': 'true' });
    const thumb = el('span', 'ed-thumb', { 'aria-hidden': 'true' });
    if (zero) zero.style.left = `${(zeroPos(p) * 100).toFixed(2)}%`;
    s.append(...[el('span', 'ed-track', { 'aria-hidden': 'true' }), fill, zero, thumb].filter(Boolean));
    if (isLog(p)) s.classList.add('is-log');
    const field = el('input', 'ed-val', { type: 'text', inputmode: 'decimal', spellcheck: 'false', 'aria-label': `${labelName(r)}: type a value` });
    const target = `${r.key}:${r.uid}`;
    const nolock = hasFlag(p, 'nolock');
    let dragV = null;
    let raf = 0;
    const draw = (v) => {
      const u = toPos(p, v);
      const z = zeroPos(p);
      fill.style.left = `${(Math.min(u, z) * 100).toFixed(2)}%`;
      fill.style.width = `${(Math.abs(u - z) * 100).toFixed(2)}%`;
      thumb.style.left = `${(u * 100).toFixed(2)}%`;
      const t = text(v);
      if (!st.typing || document.activeElement !== field) field.value = t;
      s.setAttribute('aria-valuenow', String(Math.round(v * 1000) / 1000));
      s.setAttribute('aria-valuetext', `${labelName(r)}, ${t.replace(/ dB$/, ' decibels').replace(/ Hz$/, ' hertz').replace(/ ms$/, ' milliseconds').replace(/ %$/, ' percent')}`);
    };
    r.update = () => draw(dragV !== null ? dragV : get());
    const commit = (v, how) => setValue(r.key, r.uid, v, how);
    const atX = (x) => {
      const rect = s.getBoundingClientRect();
      let v = fromPos(p, (x - rect.left) / Math.max(1, rect.width));
      if (!isLog(p) && p.step > 0) v = p.min + Math.round((v - p.min) / p.step) * p.step;
      return Math.min(p.max, Math.max(p.min, v));
    };
    s.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      s.focus();
      s.setPointerCapture(e.pointerId);
      st.dragKey = target;
      history.beginDrag(target);
      dragV = atX(e.clientX);
      draw(dragV);
      if (!nolock) commit(dragV, 'drag');
    });
    s.addEventListener('pointermove', (e) => {
      if (st.dragKey !== target || !s.hasPointerCapture(e.pointerId)) return;
      dragV = atX(e.clientX);
      draw(dragV);
      if (!nolock && !raf) raf = requestAnimationFrame(() => { raf = 0; if (dragV !== null) commit(dragV, 'drag'); });
    });
    const release = () => {
      if (st.dragKey !== target) return;
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      if (dragV !== null) commit(dragV, 'drag');
      history.endDrag();
      st.dragKey = null;
      dragV = null;
      r.update();
      if (st.verdictDirty) { st.verdictDirty = false; snapshotSoon(); }
    };
    s.addEventListener('pointerup', release);
    s.addEventListener('pointercancel', release);
    s.addEventListener('keydown', (e) => {
      if (st.keys !== 'edit') return;
      const v = get();
      const mult = e.shiftKey ? 10 : e.altKey ? 0.1 : 1;
      let nv = null;
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') nv = stepValue(p, v, 1, mult);
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') nv = stepValue(p, v, -1, mult);
      else if (e.key === 'PageUp') nv = stepValue(p, v, 1, 10);
      else if (e.key === 'PageDown') nv = stepValue(p, v, -1, 10);
      else if (e.key === 'Home') nv = p.min;
      else if (e.key === 'End') nv = p.max;
      else if (e.key === 'd' || e.key === 'D') { if (!e.metaKey && !e.ctrlKey) nv = p.def; }
      else if (e.key === 'Enter') { e.preventDefault(); field.focus(); field.select(); return; }
      if (nv === null) return;
      e.preventDefault();
      commit(nv, e.key === 'd' || e.key === 'D' ? 'default' : 'key');
    });
    field.addEventListener('focus', () => { st.typing = true; field.select(); });
    field.addEventListener('blur', () => { st.typing = false; r.update(); if (st.verdictDirty) { st.verdictDirty = false; snapshotSoon(); } });
    field.addEventListener('keydown', async (e) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); field.blur(); s.focus(); return; }
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const typed = field.value.trim();
      const v = await parseTyped(r, p, typed);
      if (v === null) {
        field.classList.add('is-bad');
        field.setAttribute('aria-invalid', 'true');
        say(`${typed} is not a value for ${r.label.textContent}`);
        setTimeout(() => { field.classList.remove('is-bad'); field.removeAttribute('aria-invalid'); }, 1200);
        return;
      }
      commit(Math.min(p.max, Math.max(p.min, v)), 'typed');
      field.blur();
      s.focus();
    });
    r.update();
    r.el.append(s, field);
  }

  // Typed text back to a value: C's parser (the shadow Worker), which reads
  // "1.2k", "-6 dB" and "1/8D"; the level is a plain number.
  async function parseTyped(r, p, text) {
    if (!text) return null;
    if (r.uid === 'level' || cableIndex(r.key) >= 0) {
      const n = Number(text.replace(/[%+]/g, '').trim());
      return Number.isFinite(n) ? n : null;
    }
    const b = blockOf(r.key);
    if (!b || !files.shadow) return null;
    const reply = await files.shadow('parse', { id: b.engine, uid: p.uid, text: text.replace(/\s+/g, ' ') });
    return reply && reply.ok !== false && Number.isFinite(reply.value) ? reply.value : null;
  }

  function refreshValue(key, uid) {
    const r = rows.get(`${key}:${uid}`);
    if (r && r.update) r.update();
    if (st.view === 'flow' && (uid === 'on' || uid === 'level' || (blockOf(key) && isSummary(key, uid)))) {
      const blk = root.querySelector(`.ed-flow [data-block="${key}"] .ed-blk-s`);
      if (blk) blk.textContent = uid === 'on' ? (valueOf(key, 'on') ? 'on' : 'off') : summary(key);
      if (uid === 'level') {
        const n = root.querySelector(`.ed-level-n[data-level="${parseBlockKey(key).sound}"]`);
        if (n) n.textContent = `${Math.round(valueOf(key, 'level'))} %`;
      }
    }
    if (st.selRow === `${key}:${uid}`) renderDetail();
  }
  function isSummary(key, uid) {
    const pg = meta.pages(blockOf(key).engine)[0];
    const p = pg && pg.params.find((x) => x.type === 'enum');
    return p && p.uid === uid;
  }
  function refreshText(id, uid) {
    for (const r of rows.values()) {
      const b = blockOf(r.key);
      if (r.uid === uid && b && b.engine === id && r.update) r.update();
    }
    if (st.selRow) renderDetail();
  }

  // ---- the detail bar (mockup 02) --------------------------------------------------
  // A refusal stays in the detail bar for a while, through the redraw the
  // snapshot after it brings, until another parameter is selected.
  function showRefusal(label, words) {
    st.refusal = { text: `${label || 'The edit'}: ${words}`, until: performance.now() + 8000, row: st.selRow };
    renderDetail();
  }
  function renderDetail() {
    detail.innerHTML = '';
    const rf = st.refusal;
    if (rf && performance.now() < rf.until && rf.row === st.selRow) {
      detail.append(el('span', 'ed-refused', { text: rf.text }));
      return;
    }
    st.refusal = null;
    const sel = st.selRow ? rows.get(st.selRow) : null;
    if (!sel || !st.mirror) {
      detail.append(el('span', 'ed-note', { text: 'Select a parameter: its range, default, flags and keys show here.' }));
      return;
    }
    const p = sel.p;
    const path = el('span', 'ed-path-t', { text: `${blockTag(sel.key)} › ${p ? p.name : sel.uid}` });
    const v = valueOf(sel.key, sel.uid);
    detail.append(path, el('b', 'ed-d-val', { text: textOf(sel.key, sel.uid, v) }));
    if (p && p.type === 'float') {
      const b = blockOf(sel.key);
      const plain = sel.uid === 'level' || !b;
      const lo = plain ? `${p.min} %` : withUnit(p, fmt(b.engine, p, p.min, renderDetail));
      const hi = plain ? `${p.max} %` : withUnit(p, fmt(b.engine, p, p.max, renderDetail));
      const df = plain ? `${p.def} %` : withUnit(p, fmt(b.engine, p, p.def, renderDetail));
      detail.append(el('span', 'ed-d', { text: `${lo} to ${hi}` }), el('span', 'ed-d', { text: `default ${df}` }));
    } else if (p && p.type === 'enum') {
      detail.append(el('span', 'ed-d', { text: `${p.entries.length} choices · default ${p.entries[p.def] ?? p.def}` }));
    }
    if (p && p.flags) {
      const words = flagWords(p);
      if (isLog(p)) words.push('moves on the LOG law');
      if (typeof p.uid === 'number') words.push(`uid ${p.uid}`);
      if (words.length) detail.append(el('span', 'ed-d ed-flags', { text: words.join(' · ') }));
    }
    const keys = el('span', 'ed-d-keys', {}, p && p.type === 'float' ? [
      el('kbd', null, { text: '←→' }), ' one detent', el('kbd', null, { text: '⇧' }), ' ten', el('kbd', null, { text: 'Enter' }), ' type',
      el('kbd', null, { text: 'D' }), ' default'] : [el('kbd', null, { text: '←→' }), ' choose']);
    detail.append(keys);
  }

  // ---- the history list (§8) -------------------------------------------------------------
  function renderHistory() {
    undoBtn.disabled = !history.canUndo;
    redoBtn.disabled = !history.canRedo;
    const u = history.canUndo ? history.entries[history.at - 1] : null;
    undoBtn.title = u ? `Undo ${u.label} (${MOD}Z)` : 'Nothing to undo';
    histList.innerHTML = '';
    const list = history.entries.slice(-12).reverse();
    if (!list.length) {
      histList.append(el('li', 'ed-note', { text: 'Nothing yet: edits from the editor and the panel land here, and undo covers both.' }));
      return;
    }
    const doneIds = new Set(history.done.map((e) => e.id));
    for (const e of list) {
      histList.append(el('li', doneIds.has(e.id) ? '' : 'is-undone', {}, [
        el('span', `ed-origin is-${e.origin}`, { text: e.origin }),
        el('span', 'ed-h-how', { text: e.how }),
        el('span', 'ed-h-what', {}, [`${e.label} `, el('span', 'ed-was', { text: e.info.struct ? e.before : textOf(e.info.key, e.info.uid, e.before) }), ' → ',
          el('b', null, { text: e.info.struct ? e.after : textOf(e.info.key, e.info.uid, e.after) })])]));
    }
  }

  // ---- the screen card (§4: the same frame, drawn twice) --------------------------------
  const sctx = screen.getContext('2d');
  sim.screenListeners = sim.screenListeners || new Set();
  sim.screenListeners.add((image) => { if (st.layout === 'editor') sctx.putImageData(image, 0, 0); });

  // ---- power ---------------------------------------------------------------------------
  window.addEventListener('fm1-power', (e) => { if (e.detail && e.detail.on) attach(); else detach(); });
  if (sim.node) attach();

  render();
  const api = {
    setLayout, state: st, history, meta, mm, chains, rows, select, undo, redo, setKeys, project, say,
    applyLink: (l) => project.applyLink(l),
    // The page test's hooks: an inspector for any module, drawn from the
    // metadata with its defaults, and the mirror as it stands.
    inspectorFor(id) {
      const e = meta.engine(id);
      if (!e) return null;
      const values = new Map(e.params.map((p) => [p.uid, p.def]));
      const key = e.kind === 'sound' ? 's4' : e.kind === 'midi_fx' ? 's4.mfx1' : e.kind === 'mod' ? 'p8' : 's4.in2';
      const saved = st.mirror;
      st.mirror = { blocks: new Map([[key, { engine: id, values, on: true }]]), levels: [0, 0, 0, 0], current: 3 };
      try { return inspector(key, { level: e.kind === 'sound' ? 3 : undefined, bare: true }); } finally { st.mirror = saved; }
    },
  };
  sim.editor = api;
  return api;
}
