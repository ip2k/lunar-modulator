// editor/project.js -- stage ED4 of the Advanced editor (notes/2026-10-06-web-editor.md
// §8-§10, §13): files and the project, beside editor.js and chains.js.
// - Drop targets: a .lunar sound, effects or mod rack dropped on the block
//   it fits, with C's verdict before the load (pass 1 in the shadow Worker,
//   as the kind the block takes; a wrong kind is refused in C's words).
//   An item dragged from the library gets its verdict while it hovers.
// - Export per block, and Save to my library, through W1's save path (C's
//   canonical writer in the shadow Worker, W1's file names).
// - The library: W1's IndexedDB store and Recent, browsable and loadable.
// - Links: view=edit and sel (files.js reads their shape; here the block and
//   the parameter are found in the mirror and the metadata, or refused).
// - Search (⌘K / Ctrl+K) over blocks, parameters and commands.
// - A/B: two snapshots of the project or of one sound; one key switches,
//   and C loads them.
// - The Memory page: RAM by part (fm1w_ram_part), in percent of the budget.
// - Undo's snapshot fallback: a structural entry keeps the project as it
//   was (when the editor's copy is current); after its undo the Worker
//   hashes the state (C's fm1_edit_state_hash, no view) and, on a mismatch,
//   the snapshot is loaded instead.
// None of it names an engine or decides a rule: C answers, the page shows
// C's words. MIT licence, like the rest of this repository.

import { ROLE, MIX_KEY, SOUNDS, blockKey, parseBlockKey, blockTag, ramPercent, ramWords } from './model.js';

const ITEM_TYPE = 'application/x-lunar-item';
const FILE_CAP = 262144;              // the module's text buffer (files.js TEXT_CAP)
const SNAP_CAP = 4 * 1024 * 1024;     // §8: 4 MB of snapshots at most
const AB_KEY = 'x';

export function makeProject(ctx) {
  const { st, meta, el, files, root, view, nextId, say, select, render, blockOf, engineName, rows, selectRow,
    snapshotSoon, history, undo, redo, setKeys, post } = ctx;
  const encoder = new TextEncoder();
  st.ab = { scope: 'project', A: null, B: null, playing: null, diff: null, busy: false };
  st.liveGen = -1;
  st.inflight = 0;
  let dragging = null;                // a library item being dragged
  const verdicts = new Map();         // `${item}|${key}` -> verdict
  let arrival = null;                 // { bytes, name, target, v }

  // ---- what a block takes, and what it exports ------------------------------------------
  function targetOf(key) {
    const b = parseBlockKey(key);
    if (!b) return null;
    if (b.role === ROLE.SOUND || b.role === ROLE.MFX) return { kind: 'sound', into: b.sound, slot: 0, words: `Sound ${b.sound + 1}`, arg: b.sound };
    if (b.role === ROLE.INSERT) return { kind: 'fx', into: b.sound, slot: 0, words: `Sound ${b.sound + 1}'s effects`, arg: b.sound };
    if (b.role === ROLE.MASTER) return { kind: 'fx', into: -1, slot: 0, words: 'the master effects', arg: -1 };
    if (b.role === ROLE.MODULE) return { kind: 'mods', into: 0, slot: 0, words: 'the mod rack', arg: 0 };
    return null;
  }
  const exportWords = (t) => (t.kind === 'sound' ? `Export Sound ${t.arg + 1}…` : t.kind === 'fx'
    ? (t.arg < 0 ? 'Export the master effects…' : `Export S${t.arg + 1}'s effects…`) : 'Export the mod rack…');

  // The inspector's export and library buttons (§9's "Out, per block").
  function headTools(key) {
    const t = targetOf(key);
    if (!t || (t.kind === 'sound' && !blockOf(blockKey(ROLE.SOUND, t.arg)))) return [];
    return [
      el('button', 'ed-btn ed-export', { type: 'button', 'data-export': key, text: exportWords(t), onclick: () => exportBlock(key) }),
      el('button', 'ed-btn ed-keep', { type: 'button', text: 'Save to my library', onclick: () => keepBlock(key) }),
    ];
  }
  async function exportBlock(key) {
    const t = targetOf(key);
    if (t) await files.saveAs(t.kind === 'mods' ? 'mods' : `${t.kind}:${t.arg}`);
  }
  async function keepBlock(key) {
    const t = targetOf(key);
    if (!t) return;
    try {
      const r = await files.saveToLibrary(t.kind, t.arg);
      say(`Saved to your library: ${r.name}.`);
      if (st.view === 'library') render();
    } catch (err) {
      say(`Not saved: ${err.message}`);
      files.notice('refused', `Not saved: ${err.message}`);
    }
  }

  // ---- drop targets (§9) -------------------------------------------------------------------
  const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
  const hasItem = (e) => e.dataTransfer && [...e.dataTransfer.types].includes(ITEM_TYPE);
  function wireDrop(node, key) {
    const t = targetOf(key);
    if (!t) return node;
    node.dataset.fileDrop = t.kind;   // not data-drop: that is chains.js's move target
    const clear = () => { node.classList.remove('is-drop-ok', 'is-drop-no'); node.removeAttribute('data-verdict'); };
    node.addEventListener('dragenter', (e) => {
      if (!hasFiles(e) && !(hasItem(e) && dragging)) return;
      e.preventDefault();
      node.classList.add('is-drop');
      if (dragging) showVerdict(node, key, t);
    });
    node.addEventListener('dragover', (e) => {
      if (!hasFiles(e) && !(hasItem(e) && dragging)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    });
    node.addEventListener('dragleave', (e) => {
      if (node.contains(e.relatedTarget)) return;
      node.classList.remove('is-drop');
      clear();
    });
    node.addEventListener('drop', async (e) => {
      if (!hasFiles(e) && !(hasItem(e) && dragging)) return;
      e.preventDefault();
      e.lunarInto = true;               // app.js leaves it to this target
      node.classList.remove('is-drop');
      clear();
      if (dragging && hasItem(e)) {
        const it = dragging;
        dragging = null;
        await arrive(it.bin, it.file || it.name, t, it.name);
        return;
      }
      const list = [...e.dataTransfer.files];
      if (list.length !== 1) { refuseCard(t, list.length ? 'Drop one file at a time on a block.' : 'Nothing to load was dropped.'); return; }
      const file = list[0];
      if (file.size > FILE_CAP) {
        refuseCard(t, `“${file.name}” is larger than the simulator reads.`);   // the cap is files.js's to say
        return;
      }
      let bytes;
      try { bytes = new Uint8Array(await file.arrayBuffer()); } catch (err) { refuseCard(t, `“${file.name}” could not be read.`); return; }
      await arrive(bytes, file.name, t);
    });
    return node;
  }
  async function showVerdict(node, key, t) {
    const id = `${dragging.store}:${dragging.id}|${key}`;
    let v = verdicts.get(id);
    if (!v) {
      v = await files.verdict(dragging.bin, dragging.file || dragging.name, t.kind, t);
      verdicts.set(id, v);
    }
    if (!node.classList.contains('is-drop')) return;
    node.classList.toggle('is-drop-ok', v.ok);
    node.classList.toggle('is-drop-no', !v.ok);
    node.dataset.verdict = v.ok ? `Load · ${ramText(v.report)}` : v.report.message || v.report.code;
  }
  const ramText = (rep) => (Number.isFinite(rep.percent) ? `RAM ${rep.percent} %` : 'RAM –');

  // The verdict before the load: C's pass 1 as the kind the block takes.
  async function arrive(bytes, name, t, title) {
    const v = await files.verdict(bytes, name, t.kind, t);
    arrival = { bytes, name, target: t, v, title: title || v.d.title };
    render();
    const b = root.querySelector('.ed-arrive button');
    if (b) b.focus();
  }
  function refuseCard(t, text) {
    arrival = { target: t, v: { ok: false, report: { code: 'BAD', message: text } }, title: '' };
    render();
  }
  function arrivalCard() {
    if (!arrival) return null;
    const { v, target: t } = arrival;
    const close = () => { arrival = null; render(); };
    const btns = [];
    if (v.ok) {
      btns.push(el('button', 'ed-btn ed-btn-go', { type: 'button', text: `Load into ${t.words}`, onclick: () => go(0) }));
    } else if (arrival.bytes && (v.report.code === 'UNKNOWN' || v.report.code === 'NO_ROOM')) {
      btns.push(el('button', 'ed-btn', { type: 'button', text: 'Load without what does not fit', onclick: () => go(1) }));
    }
    btns.push(el('button', 'ed-btn', { type: 'button', text: v.ok ? 'Cancel' : 'Dismiss', onclick: close }));
    async function go(flags) {
      const a = arrival;
      arrival = null;
      const r = await files.load(a.bytes, { d: { ...a.v.d, title: a.title }, target: { into: t.into, slot: t.slot }, flags, ui: true });
      say(r.ok ? `Loaded “${a.title}” into ${t.words}.` : `“${a.title}” was not loaded: ${r.report.message || r.report.code}`);
      snapshotSoon();
      render();
    }
    const head = v.ok ? `Load “${arrival.title}” into ${t.words}?` : arrival.title ? `“${arrival.title}” cannot go into ${t.words}.` : `Nothing loads into ${t.words}.`;
    return el('section', `ed-arrive ${v.ok ? 'is-ok' : 'is-no'}`, { 'aria-label': 'Drop', role: 'region' }, [
      el('p', 'ed-arrive-h', { text: head }),
      el('p', 'ed-arrive-w', { text: v.report.message || v.report.code }),
      v.ok ? el('p', 'ed-arrive-ram', { text: `${ramText(v.report)} of the FM-1's memory after it` }) : null,
      el('div', 'ed-arrive-b', {}, btns)]);
  }

  // ---- the library (W1's store) ----------------------------------------------------------
  async function libraryView() {
    const wrap = el('div', 'ed-lib');
    wrap.append(el('div', 'ed-sec-head', {}, [el('h2', 'ed-sec ed-sec-big', { text: 'Library' }),
      el('span', 'ed-note', { text: 'in this browser' })]),
    el('p', 'ed-note', { text: 'Load a project here, or drag a sound, effects or mod rack onto the block it fits: its verdict shows before you let go.' }));
    const [saved, recent] = await Promise.all([files.store.all('files'), files.store.all('recent')]);
    const KW = { project: 'project', sound: 'sound', fx: 'effects', mods: 'mod rack' };
    const section = (title, list, storeName, empty) => {
      const ul = el('ul', 'ed-lib-list');
      for (const it of list.sort((a, b) => b.modified - a.modified)) {
        const item = { ...it, store: storeName };
        const kind = it.kind || 'project';
        const li = el('li', 'ed-lib-item', { draggable: kind !== 'project' ? 'true' : null, 'data-kind': kind }, [
          el('span', 'ed-lib-name', { text: it.name }),
          el('span', 'ed-lib-meta', { text: `${KW[kind] || kind} · ${new Date(it.modified).toLocaleDateString()}` }),
          el('span', 'ed-lib-b', {}, [el('button', 'ed-btn', { type: 'button', text: 'Load', onclick: () => files.loadItem(it).then(() => snapshotSoon()) })])]);
        if (kind !== 'project') {
          li.addEventListener('dragstart', (e) => {
            dragging = item;
            e.dataTransfer.setData(ITEM_TYPE, `${storeName}:${it.id}`);
            e.dataTransfer.effectAllowed = 'copy';
          });
          li.addEventListener('dragend', () => { dragging = null; });
        }
        ul.append(li);
      }
      return el('section', 'ed-lib-sec', { 'aria-label': title }, [el('h3', 'ed-sec', { text: title }),
        list.length ? ul : el('p', 'ed-note', { text: empty })]);
    };
    wrap.append(section('Saved', saved, 'files', 'Nothing yet: SAVE on the panel keeps the project here, and each block can be saved here.'),
      section('Recent', recent, 'recent', 'The state a load replaces is kept here, the last five.'));
    // The Flow's blocks as drop targets, beside the list.
    const targets = el('div', 'ed-lib-targets', { role: 'group', 'aria-label': 'Drop targets' });
    for (let k = 0; k < SOUNDS; ++k) {
      const key = blockKey(ROLE.SOUND, k);
      targets.append(wireDrop(el('div', `ed-drop ed-s${k + 1}`, { 'data-block': key }, [
        el('span', 'ed-tag', { text: `S${k + 1}` }), el('span', null, { text: blockOf(key) ? engineName(blockOf(key).engine) : 'Empty' })]), key));
      targets.append(wireDrop(el('div', `ed-drop ed-s${k + 1}`, { 'data-block': blockKey(ROLE.INSERT, k, 0) }, [
        el('span', 'ed-tag', { text: `S${k + 1} FX` }), el('span', null, { text: 'its effects' })]), blockKey(ROLE.INSERT, k, 0)));
    }
    targets.append(wireDrop(el('div', 'ed-drop', { 'data-block': 'm1' }, [el('span', 'ed-tag', { text: 'MASTER' }), el('span', null, { text: 'master effects' })]), 'm1'),
      wireDrop(el('div', 'ed-drop', { 'data-block': 'p1' }, [el('span', 'ed-tag', { text: 'RACK' }), el('span', null, { text: 'mod rack' })]), 'p1'));
    wrap.append(el('section', 'ed-lib-sec', { 'aria-label': 'Drop here' }, [el('h3', 'ed-sec', { text: 'Drop here' }), targets]));
    return wrap;
  }

  // ---- the Memory page (§10, mockup 06) ----------------------------------------------------
  function memoryView() {
    const r = st.ram;
    const wrap = el('div', 'ed-mem');
    wrap.append(el('div', 'ed-sec-head', {}, [el('h2', 'ed-sec ed-sec-big', { text: 'Memory' }),
      el('span', 'ed-note', { text: "in percent of the FM-1's budget, as C counts it at 44,118 Hz" })]));
    if (!r) { wrap.append(el('p', 'ed-note', { text: 'Waiting for the module’s figures.' })); return wrap; }
    const names = [];
    for (let k = 0; k < SOUNDS; ++k) {
      const b = blockOf(blockKey(ROLE.SOUND, k));
      names.push([`S${k + 1}`, b ? engineName(b.engine) : 'empty', `ed-s${k + 1}`]);
    }
    names.push(['Master', 'M1 and M2', 'ed-part-master'], ['Shared', 'Mix, sequencer, modulation', 'ed-part-rest']);
    const tbl = el('div', 'ed-mem-rows', { role: 'table', 'aria-label': 'RAM by part' });
    const row = (cls, tag, name, bytes, words) => el('div', `ed-mem-row ${cls}`, { role: 'row' }, [
      el('span', 'ed-mem-tag', { role: 'cell', text: tag }), el('span', 'ed-mem-name', { role: 'cell', text: name }),
      el('span', 'ed-mem-bar', { role: 'cell', 'aria-hidden': 'true' }, [el('span', 'ed-mem-fill', { style: `width:${Math.min(100, 100 * bytes / r.budget).toFixed(2)}%` })]),
      el('b', 'ed-mem-pc', { role: 'cell', text: words })]);
    r.parts.forEach((bytes, i) => { if (names[i]) tbl.append(row(names[i][2], names[i][0], names[i][1], bytes, ramWords(bytes, r.budget))); });
    const over = r.total > r.budget;
    tbl.append(row('ed-mem-total', 'All', 'In use', r.total, over ? `${ramPercent(r.total - r.budget, r.budget)} % over` : ramWords(r.total, r.budget)));
    // What is left, rounded down (what is used rounds up), so the two add to 100 at most.
    const freePc = over ? 0 : Math.floor((r.budget - r.total) * 100 / r.budget);
    tbl.append(row('ed-mem-free', 'Free', 'What is left', Math.max(0, r.budget - r.total), over ? 'none' : `${freePc} %`));
    wrap.append(tbl);
    // What would fit in what is left: the metadata's own RAM figures.
    const free = r.budget - r.total;
    const fits = (kind) => (meta.doc.engines || []).filter((e) => e.kind === kind && e.ram > 0 && e.ram <= free)
      .sort((a, b) => b.ram - a.ram);
    const line = (label, list) => el('p', 'ed-mem-fit', {}, [el('b', null, { text: `${label}: ` }),
      document.createTextNode(list.length ? `${list.length} would fit, the largest ${list.slice(0, 4).map((e) => `${e.name} (${ramWords(e.ram, r.budget)})`).join(', ')}` : 'none would fit')]);
    wrap.append(el('h3', 'ed-sec', { text: 'What would fit' }), line('Sounds', fits('sound')), line('Effects', fits('audio_fx')));
    return wrap;
  }

  // ---- A/B (§9: A is kept, B is now; C loads either) -------------------------------------
  async function takeLive() {
    if (!st.port) return null;
    const id = -(++st.snapAux || (st.snapAux = 1));
    const m = await new Promise((resolve) => { st.snapWait.set(id, resolve); post({ type: 'snapshot', id, kind: 1 }); });
    return m.ok ? m.bytes.slice(0) : null;
  }
  const abKind = () => (st.ab.scope === 'project' ? { kind: 1, arg: 0 } : { kind: 2, arg: st.ab.scope });
  async function keepA(quiet) {
    const live = await takeLive();
    if (!live) return;
    Object.assign(st.ab, { A: live, B: null, playing: 'B', diff: null });
    if (!quiet) say(`A kept: ${abWords()}. Edit on; X switches between A and B.`);
    if (!quiet || st.view === 'ab') render();
  }
  // A load (a file, a drop, the library) sets A to what it loaded; A/B's
  // own loads, and their echoes for a moment after, do not.
  let loadTimer = 0;
  function onLoaded() {
    if (st.ab.busy || performance.now() < (st.ab.quietUntil || 0)) return;
    clearTimeout(loadTimer);
    loadTimer = setTimeout(() => { if (!st.ab.busy && performance.now() >= (st.ab.quietUntil || 0)) keepA(true); }, 300);
  }
  window.addEventListener('fm1-power', (e) => {
    if (e.detail && e.detail.on) return;
    Object.assign(st.ab, { A: null, B: null, playing: null, diff: null, busy: false });
    arrival = null;
    dragging = null;
  });
  async function switchAB() {
    const ab = st.ab;
    if (!ab.A || ab.busy || !st.port) { if (!ab.A) say('Keep an A first: Compare, then Keep as A.'); return; }
    ab.busy = true;
    try {
      const live = await takeLive();
      if (!live) return;
      const to = ab.playing === 'A' ? 'B' : 'A';
      ab[ab.playing] = live;
      const bin = ab[to];
      if (!bin) { ab.playing = to; return; }
      let r;
      if (ab.scope === 'project') {
        r = await files.load(bin.slice(0), { d: { enc: 1, kind: 'project', title: files.title }, before: false, quiet: true });
      } else {
        const s = await files.shadow('save', { kind: 2, arg: ab.scope, live: bin.slice(0) });
        if (!s.ok || typeof s.text !== 'string') { say(`${to} could not be read back.`); return; }
        r = await files.load(encoder.encode(s.text), { d: { enc: 2, kind: 'sound', title: `Sound ${ab.scope + 1}` },
          target: { into: ab.scope, slot: 0 }, before: false, quiet: true });
      }
      if (!r.ok) { say(`${to} was not loaded: ${r.report.message || r.report.code}`); return; }
      ab.playing = to;
      say(`Now ${to}: ${abWords()}.`);
      snapshotSoon();
      await diffAB();
    } finally {
      ab.busy = false;
      ab.quietUntil = performance.now() + 1500;
      if (st.view === 'ab') render();
    }
  }
  async function diffAB() {
    const ab = st.ab;
    const live = await takeLive();
    const other = ab.playing === 'A' ? ab.B : ab.A;
    if (!live || !other) { ab.diff = null; return; }
    const k = abKind();
    const [a, b] = ab.playing === 'A' ? [live, other] : [other, live];
    const r = await files.shadow('diff', { a, b, kind: k.kind, arg: k.arg });
    ab.diff = r && r.changes ? r.changes.filter((c) => !/^(view|session\.current)/.test(c.path)) : null;
  }
  const abWords = () => (st.ab.scope === 'project' ? 'the project' : `Sound ${st.ab.scope + 1}`);
  function compareView() {
    const ab = st.ab;
    const wrap = el('div', 'ed-ab');
    wrap.append(el('div', 'ed-sec-head', {}, [el('h2', 'ed-sec ed-sec-big', { text: 'Compare' }),
      el('span', 'ed-note', { text: 'A is kept, B is now; C loads either' })]));
    const scopes = el('div', 'ed-seg ed-ab-scope', { role: 'radiogroup', 'aria-label': 'What to compare' });
    const opts = [['project', 'Project'], ...[0, 1, 2, 3].map((k) => [k, `Sound ${k + 1}`])];
    for (const [v, label] of opts) {
      const on = ab.scope === v;
      scopes.append(el('button', 'ed-segbtn', { type: 'button', role: 'radio', 'aria-checked': on ? 'true' : 'false', tabindex: on ? '0' : '-1',
        disabled: v !== 'project' && !blockOf(blockKey(ROLE.SOUND, v)), text: label,
        onclick: () => { if (ab.scope !== v) { Object.assign(ab, { scope: v, A: null, B: null, playing: null, diff: null }); render(); } } }));
    }
    const state = ab.A ? `Hearing ${ab.playing}` : 'No A yet';
    wrap.append(scopes,
      el('div', 'ed-ab-row', {}, [
        el('button', 'ed-btn', { type: 'button', text: ab.A ? 'Keep now as A' : 'Keep as A', onclick: () => keepA() }),
        el('button', 'ed-btn ed-ab-switch', { type: 'button', disabled: !ab.A, 'aria-keyshortcuts': 'X',
          text: ab.A ? `Switch to ${ab.playing === 'A' ? 'B' : 'A'}` : 'Switch A/B', onclick: () => switchAB() }, [el('kbd', null, { text: 'X' })]),
        el('span', `ed-ab-state${ab.A ? ` is-${ab.playing}` : ''}`, { role: 'status', text: state })]));
    if (ab.diff) {
      const list = el('ul', 'ed-ab-diff');
      for (const c of ab.diff.slice(0, 24)) {
        list.append(el('li', null, {}, [el('code', null, { text: c.path }),
          el('span', 'ed-ab-v', { text: `A ${short(c.a)}` }), el('span', 'ed-ab-v', { text: `B ${short(c.b)}` })]));
      }
      wrap.append(el('h3', 'ed-sec', { text: ab.diff.length ? `${ab.diff.length} difference${ab.diff.length === 1 ? '' : 's'}` : 'A and B are the same' }), list);
    } else if (ab.A) {
      wrap.append(el('p', 'ed-note', { text: 'Edit, then switch: the differences show here, from C’s own files.' }));
    }
    return wrap;
  }
  const short = (v) => (v === undefined ? '–' : String(typeof v === 'object' ? JSON.stringify(v) : v).slice(0, 40));

  // ---- links: view=edit and sel ------------------------------------------------------------
  function applyLink(link) {
    st.pendingSel = link && link.sel ? link.sel : null;
    if (st.mirror) applyPendingSel();
  }
  function applyPendingSel() {
    const s = st.pendingSel;
    if (!s || !st.mirror || files.pending && files.pending.length) return;
    st.pendingSel = null;
    const key = /^mix$/.test(s.key) ? MIX_KEY : s.key;   // the link's word for the Mix block
    if (/^c[0-9]+$/.test(key)) { select(key, { view: 'mod' }); return; }
    const b = parseBlockKey(key);
    if (key !== MIX_KEY && (!b || !blockOf(key))) {
      files.notice('refused', `The link's selection “${s.key}” was not applied: that block is empty.`);
      return;
    }
    if (!s.param) { select(key, { view: b && b.role === ROLE.MODULE ? 'mod' : 'flow' }); return; }
    const p = blockOf(key) ? meta.engine(blockOf(key).engine).params.find((x) => x.name.toLowerCase() === s.param.toLowerCase()) : null;
    if (!p) {
      select(key, { view: 'flow' });
      files.notice('refused', `The link's parameter “${s.param}” is not one of ${blockTag(key)}'s.`);
      return;
    }
    goParam(key, p);
  }
  function goParam(key, p) {
    const b = parseBlockKey(key);
    select(key, { view: b && b.role === ROLE.MODULE ? 'mod' : (b && (b.role === ROLE.SOUND || b.role === ROLE.MFX) ? 'sound' : 'flow') });
    const r = rows.get(`${key}:${p.uid}`);
    if (!r) return;
    selectRow(r);
    r.el.scrollIntoView({ block: 'nearest' });
    const c = r.el.querySelector('[role=slider], button, select, input');
    if (c) c.focus({ preventScroll: true });
  }

  // ---- search: ⌘K / Ctrl+K (§10) -----------------------------------------------------------
  const sInput = el('input', 'ed-search-in', { type: 'search', role: 'combobox', 'aria-autocomplete': 'list', 'aria-expanded': 'true',
    placeholder: 'Blocks, parameters, commands', 'aria-label': 'Search the editor', spellcheck: 'false', autocomplete: 'off' });
  const sList = el('ul', 'ed-search-list', { role: 'listbox', id: nextId('sl'), 'aria-label': 'Results' });
  sInput.setAttribute('aria-controls', sList.id);
  const sCount = el('p', 'ed-search-n', { 'aria-live': 'polite' });
  const sBox = el('div', 'ed-search', { role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Search', hidden: true }, [
    el('div', 'ed-search-card', {}, [sInput, sCount, sList])]);
  root.append(sBox);
  let sItems = [], sShown = [], sAt = 0, sFrom = null;
  function items() {
    const out = [], params = [], cmds = [];
    const cmd = (label, run) => cmds.push({ group: 'Commands', label, run });
    if (st.mirror) {
      for (const [key, b] of st.mirror.blocks) {
        const e = meta.engine(b.engine);
        const name = e ? e.name : b.engine;
        out.push({ group: 'Blocks', label: `${blockTag(key)} ${name}`, run: () => select(key, { view: parseBlockKey(key).role === ROLE.MODULE ? 'mod' : 'flow' }) });
        for (const pg of meta.pages(b.engine)) {
          for (const p of pg.params) params.push({ group: 'Parameters', label: `${blockTag(key)} ${name} · ${p.name}`, run: () => goParam(key, p) });
        }
      }
    }
    cmd('Flow and effects', () => { st.view = 'flow'; render(); });
    cmd('Modulation', () => { st.view = 'mod'; render(); });
    for (let k = 0; k < SOUNDS; ++k) if (blockOf(blockKey(ROLE.SOUND, k))) cmd(`Sound ${k + 1}`, () => select(blockKey(ROLE.SOUND, k), { view: 'sound' }));
    cmd('Library', () => { st.view = 'library'; render(); });
    cmd('Memory', () => { st.view = 'memory'; render(); });
    cmd('Compare A/B', () => { st.view = 'ab'; render(); });
    cmd('Keep as A', () => keepA());
    if (st.ab.A) cmd('Switch A/B', () => switchAB());
    cmd('Undo', () => undo());
    cmd('Redo', () => redo());
    cmd('Export the project…', () => files.saveAs('project'));
    cmd('Copy a link to the project', () => files.copyLink());
    const t = targetOf(st.selected);
    if (t && blockOf(st.selected)) {
      cmd(`${exportWords(t)} (selected)`, () => exportBlock(st.selected));
      cmd(`Save ${blockTag(st.selected)} to my library`, () => keepBlock(st.selected));
    }
    cmd('Give the keys back to the panel (PLAY)', () => setKeys('play'));
    return [...out, ...params, ...cmds];
  }
  function openSearch() {
    if (!sBox.hidden) return;
    sFrom = document.activeElement;
    setKeys('edit');
    sItems = items();
    sInput.value = '';
    sBox.hidden = false;
    filter();
    sInput.focus();
  }
  function closeSearch(back = true) {
    sBox.hidden = true;
    if (back && sFrom && sFrom.isConnected) sFrom.focus();
  }
  function filter() {
    const words = sInput.value.toLowerCase().split(/\s+/).filter(Boolean).slice(0, 8);
    sShown = sItems.filter((it) => { const t = `${it.label} ${it.group}`.toLowerCase(); return words.every((w) => t.includes(w)); });
    sAt = 0;
    drawList();
  }
  function drawList() {
    sList.textContent = '';
    let group = null;
    const max = Math.min(sShown.length, 60);
    for (let i = 0; i < max; ++i) {
      const it = sShown[i];
      if (it.group !== group) { group = it.group; sList.append(el('li', 'ed-search-g', { role: 'presentation', text: group })); }
      const li = el('li', `ed-search-o${i === sAt ? ' is-at' : ''}`, { role: 'option', id: `${sList.id}-${i}`, 'aria-selected': i === sAt ? 'true' : 'false', text: it.label });
      li.addEventListener('mousedown', (e) => e.preventDefault());
      li.addEventListener('click', () => run(i));
      sList.append(li);
    }
    sInput.setAttribute('aria-activedescendant', sShown.length ? `${sList.id}-${sAt}` : '');
    sCount.textContent = sShown.length ? `${sShown.length} result${sShown.length === 1 ? '' : 's'}${sShown.length > max ? `, the first ${max} shown` : ''}` : 'Nothing matches';
    const at = sList.querySelector('.is-at');
    if (at) at.scrollIntoView({ block: 'nearest' });
  }
  function run(i) {
    const it = sShown[i];
    if (!it) return;
    closeSearch(false);
    it.run();
  }
  sInput.addEventListener('input', filter);
  sInput.addEventListener('keydown', (e) => {
    const n = Math.min(sShown.length, 60);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (n) { sAt = (sAt + (e.key === 'ArrowDown' ? 1 : n - 1)) % n; drawList(); }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      run(sAt);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeSearch();
    } else if (e.key === 'Tab') {
      e.preventDefault();               // the dialog keeps the keys until Esc or Enter
    }
  });
  sBox.addEventListener('mousedown', (e) => { if (e.target === sBox) closeSearch(); });

  // ---- undo's snapshot fallback (§8) ---------------------------------------------------------
  // The editor's copy of the live project is current when no change has come
  // since it was taken and no edit is on its way.
  const fresh = () => st.live && st.liveGen === st.gen && !st.inflight;
  let snapBytes = 0;
  function onStruct(entry) {
    if (!fresh()) return;
    const bin = st.live.slice(0);
    entry.snap = { bin, hash: files.shadow('hash', { bin: bin.slice(0) }).then((r) => (r && r.ok !== false ? r.hash : null)) };
    snapBytes += bin.length;
    // §8: 4 MB of snapshots at most; the oldest go first.
    for (const e of history.entries) {
      if (snapBytes <= SNAP_CAP) break;
      if (e.snap && e !== entry) { snapBytes -= e.snap.bin.length; e.snap = null; }
    }
  }
  async function checkUndo(e) {
    if (!e || !e.snap) { if (e) e.check = 'none'; return; }
    const now = await takeLive();
    if (!now) return;
    const [h, before] = await Promise.all([files.shadow('hash', { bin: now }).then((r) => r.hash), e.snap.hash]);
    if (before === null || before === undefined) { e.check = 'none'; return; }
    if (h === before) { e.check = 'hash'; return; }
    st.ab.quietUntil = performance.now() + 1500;        // not a load that sets A
    const r = await files.load(e.snap.bin.slice(0), { d: { enc: 1, kind: 'project', title: files.title }, before: false, quiet: true });
    e.check = r.ok ? 'snapshot' : 'failed';
    say(r.ok ? `${e.label}: undone from its snapshot, as the inverse edits left it otherwise.` : `${e.label} could not be undone exactly: ${r.report.message || r.report.code}`);
    snapshotSoon();
  }
  // Keeps the copy current: taken again a little after changes stop.
  let freshTimer = 0;
  function staleSoon() {
    clearTimeout(freshTimer);
    freshTimer = setTimeout(async () => {
      if (fresh() || !st.port || st.loading) return;
      const gen = st.gen;
      const id = -(++st.snapAux || (st.snapAux = 1));
      const m = await new Promise((resolve) => { st.snapWait.set(id, resolve); post({ type: 'snapshot', id, kind: 1 }); });
      if (m.ok && (m.gen >>> 0) >= gen) { st.live = m.bytes.slice(0); st.liveGen = m.gen >>> 0; }
    }, 400);
  }

  // ---- keys: ⌘K and X ------------------------------------------------------------------------
  function onKey(e, mod, inText) {
    if (mod && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') { e.preventDefault(); openSearch(); return true; }
    if (!mod && !e.altKey && !inText && st.keys === 'edit' && e.key.toLowerCase() === AB_KEY && st.ab.A && sBox.hidden) {
      e.preventDefault();
      switchAB();
      return true;
    }
    return false;
  }

  return {
    headTools, wireDrop, arrivalCard, libraryView, memoryView, compareView, applyLink, applyPendingSel,
    openSearch, closeSearch, onStruct, checkUndo, staleSoon, onKey, keepA, switchAB, targetOf, onLoaded,
    get searchOpen() { return !sBox.hidden; },
  };
}
