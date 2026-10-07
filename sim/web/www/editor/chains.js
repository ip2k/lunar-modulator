// editor/chains.js -- the Advanced editor's chains and modulation (stage ED3,
// notes/2026-10-06-web-editor.md §5, §8, §10, §11, §13): moving and swapping
// blocks by pointer or keys with C's verdict before the drop, the pickers
// for engines, effects, MIDI effects and rack modules, the meters of the
// inserts, the master slots and the Mix, a kit's pads, the rack's cards, the
// matrix table and the slot inspector, and the undo records of every
// structural edit.
//
// Every edit is one of the edit layer's records or verbs (fm1_edit.h), sent
// by the editor's port; every verdict, RAM figure and refusal is C's: the
// live module's for what is done, the shadow Worker's for what would be
// (its `preview`). It names no engine, effect, kind or source. MIT licence,
// like the rest of this repository.

import {
  ROLE, T, SOUNDS, INSERTS, MASTERS, NONE, GATE_DST, SLOT_ON, VOICE, SLOTS,
  packUnit, packModule, packCable, packVerb, packParam, packOn, packCurrent, concat,
  blockKey, parseBlockKey, blockTag, modKey, parseModKey, hasFlag, ramPercent,
  cableEmpty, cableEqual, emptyCable, pctOfQ14, Q14, withPol, withCurve, withBit,
} from './model.js';
import { makeMap } from './map.js';

export const cableIndex = (key) => { const m = /^c([0-9]+)$/.exec(key || ''); return m ? Number(m[1]) - 1 : -1; };
const toQ = (pct) => Math.max(-Q14, Math.min(Q14, Math.round((pct * Q14) / 100)));

export function makeChains(ctx) {
  const { st, meta, mm, el, history, files } = ctx;
  const budget = () => (st.ram && st.ram.budget) || meta.budget;

  // ---- words ------------------------------------------------------------------
  // A refusal's words and detail, from the metadata, with what C's code
  // leaves to fill in (the figures are percentages of the FM-1's budget).
  function verdictWords(code, fills = {}) {
    const r = meta.refusals.get(code);
    if (!r) return `refused (code ${code})`;
    let d = r.detail || '';
    for (const f of r.fills || []) d = d.replace(`{${f}}`, fills[f] !== undefined ? String(fills[f]) : '…');
    return d && !d.includes('…') ? `${r.words}: ${d}` : r.words;
  }
  function ramAfter(total) {
    const b = budget();
    return total > b ? `${ramPercent(total - b, b)} % over` : `RAM ${ramPercent(total, b)} %`;
  }

  // ---- previews: what an edit would do (the shadow Worker, §5) ----------------
  async function preview(list, each, mod) {
    if (!st.live || !files.shadow || !list.length) return null;
    const r = await files.shadow('preview', { live: st.live.slice(0), ops: concat(list), each: !!each, mod: !!mod });
    return r && r.ok !== false ? r : null;
  }

  // ---- the blocks that move -----------------------------------------------------
  // The effect slots a block can move to: the master's, and the inserts of
  // every sound that has an engine (a sound with none shows no slots, and C
  // refuses an effect there: no file could hold it).
  const effectKeys = () => {
    const out = [];
    for (let k = 0; k < SOUNDS; ++k) {
      if (st.mirror && !st.mirror.blocks.has(blockKey(ROLE.SOUND, k))) continue;
      for (let j = 0; j < INSERTS; ++j) out.push(blockKey(ROLE.INSERT, k, j));
    }
    for (let j = 0; j < MASTERS; ++j) out.push(blockKey(ROLE.MASTER, 0, j));
    return out;
  };
  const rackKeys = () => Array.from({ length: mm.positions }, (_, i) => modKey(i));
  const isEffect = (key) => { const b = parseBlockKey(key); return !!b && (b.role === ROLE.INSERT || b.role === ROLE.MASTER); };
  const isModule = (key) => parseModKey(key) >= 0;
  const placesFor = (key) => (isModule(key) ? rackKeys() : isEffect(key) ? effectKeys() : []);
  function moveOp(a, b) {
    const A = parseBlockKey(a), B = parseBlockKey(b);
    return isModule(a) ? packVerb(T.MOVE, A, B) : packVerb(T.SWAP, A, B);
  }
  const nameAt = (key) => { const b = ctx.blockOf(key); return b ? ctx.engineName(b.engine) : 'empty'; };

  // ---- the records that put a block back (undo, §8) -----------------------------
  function paramRec(key, p, v, focus) {
    const b = parseBlockKey(key);
    const at = { role: b.role, sound: b.sound, slot: b.slot, uid: p.uid };
    if (focus !== undefined) at.focus = focus;
    return p.type === 'enum' ? packParam({ ...at, index: Math.round(v) }) : packParam({ ...at, value: v });
  }
  // A block as it is now: its unit (or module) and every value, a kit's
  // pads one by one with its focus last, a MIDI effect's on.
  function blockRecs(key) {
    const b = parseBlockKey(key);
    const blk = ctx.blockOf(key);
    const out = [b.role === ROLE.MODULE ? packModule(b.slot, blk ? blk.engine : '') : packUnit(b.role, b.sound, b.slot, blk ? blk.engine : '')];
    if (!blk) return out;
    const e = meta.engine(blk.engine);
    if (!e) return out;
    const fp = e.params.find((p) => hasFlag(p, 'focus'));
    for (const p of e.params) {
      if (p === fp || !blk.values.has(p.uid)) continue;
      if (blk.pads && hasFlag(p, 'per_focus')) continue;
      out.push(paramRec(key, p, blk.values.get(p.uid)));
    }
    if (blk.pads) {
      blk.pads.forEach((vals, pad) => { for (const p of e.params) if (vals.has(p.uid)) out.push(paramRec(key, p, vals.get(p.uid), pad)); });
    }
    if (fp && blk.values.has(fp.uid)) out.push(paramRec(key, fp, blk.values.get(fp.uid)));
    if (b.role === ROLE.MFX) out.push(packOn(b.sound, b.slot, blk.on));
    return out;
  }
  // The matrix put back as it was: every slot that held a cable then or
  // holds one now (an engine or a module changed may have re-aimed them).
  function cableRecs(before) {
    const out = [];
    before.forEach((c, i) => {
      const now = st.mirror.cables[i];
      if (!cableEmpty(c) || (now && !cableEmpty(now))) out.push(packCable(i, c));
    });
    return out;
  }

  // One structural edit: into the history with what undoes it, then to C.
  function structural({ key, target, label, before, after, ops, undo, how = 'set', origin = 'editor' }) {
    const cables = st.mirror.cables.map((c) => ({ ...c }));
    const entry = history.record({ target, label, before, after, origin, how,
      info: { struct: true, key, undo, cables, redo: ops ? concat(ops) : null } });
    if (entry && origin === 'editor' && ctx.onStruct) ctx.onStruct(entry);   // undo's snapshot (ED4, §8)
    if (ops) ctx.sendOps(concat(ops), { entry: entry ? entry.id : 0, label, struct: true });
    ctx.renderHistory();
    return entry;
  }
  function undoStruct(e, redo) {
    const recs = redo ? [e.info.redo] : [concat(e.info.undo || []), concat(cableRecs(e.info.cables))];
    const all = recs.filter((b) => b && b.length);
    if (!all.length) return 0;
    const n = all.reduce((s, b) => s + b.length, 0);
    const out = new Uint8Array(n);
    let o = 0;
    for (const b of all) { out.set(b, o); o += b.length; }
    const tag = ctx.sendOps(out, { label: e.label, struct: true, entryRef: e, [redo ? 'redo' : 'undo']: true });
    ctx.say(`${redo ? 'Redone' : 'Undone'}: ${e.label}`);
    return tag;
  }

  // A change the panel made to the structure: into the history from the
  // mirror as it was (so undo puts it back), before the snapshot replaces it.
  function fromPanel(rec, origin) {
    if (!st.mirror) return;
    if (rec.type === T.UNIT || rec.type === T.MODULE) {
      const key = blockKey(rec.type === T.MODULE ? ROLE.MODULE : rec.role, rec.sound, rec.slot);
      const was = nameAt(key);
      const now = rec.id ? ctx.engineName(rec.id) : 'empty';
      if (was === now) return;
      structural({ key, target: `${key}:unit`, label: `${blockTag(key)} ${rec.type === T.MODULE ? 'module' : 'engine'}`, before: was, after: now,
        undo: blockRecs(key), ops: null, origin, how: 'knob' }).info.redo = concat([rec.type === T.MODULE ? packModule(rec.slot, rec.id) : packUnit(rec.role, rec.sound, rec.slot, rec.id)]);
    } else if (rec.type === T.SWAP || rec.type === T.MOVE) {
      const a = blockKey(rec.role, rec.sound, rec.slot), b = blockKey(rec.to.role, rec.to.sound, rec.to.slot);
      const op = packVerb(rec.type, { role: rec.role, sound: rec.sound, slot: rec.slot }, rec.to);
      const back = rec.type === T.MOVE ? packVerb(T.MOVE, rec.to, { role: rec.role, sound: rec.sound, slot: rec.slot }) : op;
      structural({ key: a, target: `${a}>${b}`, label: `${rec.type === T.MOVE ? 'Move' : 'Swap'} ${blockTag(a)} and ${blockTag(b)}`,
        before: `${blockTag(a)} ${nameAt(a)}, ${blockTag(b)} ${nameAt(b)}`, after: 'swapped', undo: [back], ops: null, origin, how: 'knob' }).info.redo = op;
    }
  }

  // ---- moving: pointer, keys and "Move to…" (§13: every drag has a twin) --------------
  let held = null;         // { key, target, verdict }
  async function verdictFor(key, target) {
    if (key === target) return { ok: true, text: 'here' };
    const r = await preview([moveOp(key, target)]);
    if (!r) return { ok: true, text: isModule(key) ? 'Move' : 'Swap' };
    const code = r.codes[0];
    if (code !== 0 && code < 32) return { ok: false, text: verdictWords(code) };
    return { ok: true, text: `${isModule(key) ? 'Move' : 'Swap'} · ${ramAfter(r.ram[0].total)}` };
  }
  function pill(target, v) {
    for (const x of ctx.root.querySelectorAll('.ed-verdict')) x.remove();
    for (const x of ctx.root.querySelectorAll('.is-target')) x.classList.remove('is-target', 'is-refused');
    if (!target) return;
    const t = ctx.root.querySelector(`[data-drop="${target}"]`);
    if (!t) return;
    t.classList.add('is-target');
    if (v) {
      t.classList.toggle('is-refused', !v.ok);
      t.append(el('span', `ed-verdict${v.ok ? '' : ' is-refused'}`, { text: v.ok ? v.text : `${v.text} ✕` }));
    }
  }
  async function aim(target) {
    if (!held) return;
    held.target = target;
    pill(target, null);
    const h = held;
    const v = target ? await verdictFor(h.key, target) : null;
    if (held !== h || h.target !== target) return;
    h.verdict = v;
    pill(target, v);
    if (v) ctx.say(`${blockTag(target)}: ${v.text}`);
  }
  function drop() {
    const h = held;
    held = null;
    st.dragKey = null;
    pill(null);
    for (const x of ctx.root.querySelectorAll('.is-held')) x.classList.remove('is-held');
    if (!h || !h.target || h.target === h.key) return;
    if (h.verdict && !h.verdict.ok) { ctx.showRefusal(`${blockTag(h.key)} to ${blockTag(h.target)}`, h.verdict.text); ctx.say(h.verdict.text); return; }
    moveTo(h.key, h.target);
  }
  function cancel() {
    held = null;
    st.dragKey = null;
    pill(null);
    for (const x of ctx.root.querySelectorAll('.is-held')) x.classList.remove('is-held');
  }
  function moveTo(a, b) {
    const op = moveOp(a, b);
    const mod = isModule(a);
    const back = mod ? packVerb(T.MOVE, parseBlockKey(b), parseBlockKey(a)) : op;
    const label = mod ? `Move ${blockTag(a)} to ${blockTag(b)}` : `Swap ${blockTag(a)} and ${blockTag(b)}`;
    structural({ key: a, target: `${a}>${b}`, label, before: `${blockTag(a)} ${nameAt(a)}, ${blockTag(b)} ${nameAt(b)}`,
      after: mod ? 'moved' : 'swapped', ops: [op], undo: [back] });
    st.selected = b;
    // The keys stay with the block: on its new place once the view redraws.
    const ae = typeof document !== 'undefined' ? document.activeElement : null;
    if (ae && ae.dataset && ae.dataset.fk === a) st.focusAfter = b;
    ctx.say(label);
  }

  // A pointer drag whose block was redrawn under it never sees its own
  // pointerup: the page's ends it, so nothing stays held.
  if (typeof window !== 'undefined') {
    window.addEventListener('pointerup', () => { if (held && held.pointer) cancel(); });
    window.addEventListener('pointercancel', () => { if (held && held.pointer) cancel(); });
  }

  // A block that can be picked up: by pointer (a drag past 6 px), by keys
  // (Space picks up, arrows aim, Space drops, Esc cancels; ⌥ and an arrow
  // swap with the neighbour).
  function movable(btn, key) {
    const places = placesFor(key);
    if (!places.length) return btn;
    btn.dataset.drop = key;
    btn.setAttribute('aria-roledescription', 'movable block');
    btn.setAttribute('aria-keyshortcuts', 'Space Alt+ArrowLeft Alt+ArrowRight');
    let start = null, dragged = false;
    btn.addEventListener('pointerdown', (e) => { if (e.button === 0) { start = { x: e.clientX, y: e.clientY, id: e.pointerId }; dragged = false; } });
    btn.addEventListener('pointermove', (e) => {
      if (!start || e.pointerId !== start.id) return;
      if (!held) {
        if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 6) return;
        try { btn.setPointerCapture(e.pointerId); } catch { /* a pointer the browser no longer tracks */ }
        held = { key, target: null, pointer: true };
        st.dragKey = `block:${key}`;
        dragged = true;
        btn.classList.add('is-held');
      }
      const under = document.elementFromPoint(e.clientX, e.clientY);
      const t = under && under.closest('[data-drop]');
      const target = t && places.includes(t.dataset.drop) ? t.dataset.drop : null;
      if (target !== held.target) aim(target);
    });
    const up = () => { start = null; if (held && held.key === key && dragged) drop(); };
    btn.addEventListener('pointerup', up);
    btn.addEventListener('pointercancel', () => { start = null; if (dragged) cancel(); });
    btn.addEventListener('click', (e) => { if (dragged) { e.stopImmediatePropagation(); e.preventDefault(); dragged = false; } }, true);
    btn.addEventListener('keydown', (e) => {
      if (st.keys !== 'edit') return;
      const i = places.indexOf(held && held.key === key ? held.target || key : key);
      if (e.altKey && /^Arrow/.test(e.key)) {
        e.preventDefault();
        const j = i + (e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 1);
        if (j >= 0 && j < places.length) verdictFor(key, places[j]).then((v) => {
          if (v.ok) moveTo(key, places[j]); else { ctx.showRefusal(blockTag(key), v.text); ctx.say(v.text); }
        });
        return;
      }
      if (e.key === ' ') {
        e.preventDefault();
        if (held && held.key === key) drop();
        else { held = { key, target: key }; st.dragKey = `block:${key}`; btn.classList.add('is-held'); ctx.say(`${blockTag(key)} picked up: arrows choose where, Space drops, Escape cancels.`); }
        return;
      }
      if (!held || held.key !== key) return;
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cancel(); ctx.say('Cancelled.'); return; }
      if (/^Arrow/.test(e.key)) {
        e.preventDefault();
        const j = Math.max(0, Math.min(places.length - 1, i + (e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 1)));
        aim(places[j]);
      }
    });
    // Space activates a button on its release: not while it picks up or drops.
    btn.addEventListener('keyup', (e) => { if (e.key === ' ' && st.keys === 'edit') e.preventDefault(); });
    btn.addEventListener('blur', () => { if (held && held.key === key && !dragged) cancel(); });
    return btn;
  }
  function moveSelect(key) {
    const places = placesFor(key).filter((k) => k !== key);
    if (!places.length) return null;
    const s = el('select', 'ed-select ed-move', { 'aria-label': `Move ${blockTag(key)} to…`, 'data-fk': `${key}:move` });
    s.append(el('option', null, { value: '', text: isModule(key) ? 'Move to…' : 'Swap with…' }));
    for (const k of places) s.append(el('option', null, { value: k, text: `${blockTag(k)} · ${nameAt(k)}` }));
    s.addEventListener('change', async () => {
      const t = s.value;
      s.value = '';
      if (!t) return;
      const v = await verdictFor(key, t);
      if (v.ok) moveTo(key, t); else { ctx.showRefusal(blockTag(key), v.text); ctx.say(v.text); }
    });
    return s;
  }

  // ---- pickers: engines, effects, MIDI effects, modules (§10) ----------------------------
  function candidates(key) {
    const b = parseBlockKey(key);
    const want = b.role === ROLE.SOUND ? 'sound' : b.role === ROLE.MFX ? 'midi_fx' : b.role === ROLE.MODULE ? 'mod' : 'audio_fx';
    const list = (want === 'mod' ? [...mm.kinds.values()] : meta.doc.engines.filter((e) => e.kind === want)).map((e) => ({ id: e.id, e }));
    // Effects by the metadata's groups, in its order (an editor hint, never a rule).
    const order = (meta.doc.effect_groups || []).map((g) => g.id);
    if (want === 'audio_fx') list.sort((a, b) => order.indexOf(a.e.group) - order.indexOf(b.e.group));
    return [{ id: '', e: null }, ...list];
  }
  function pickerOp(key, id) {
    const b = parseBlockKey(key);
    return b.role === ROLE.MODULE ? packModule(b.slot, id) : packUnit(b.role, b.sound, b.slot, id);
  }
  function choose(key, id) {
    const blk = ctx.blockOf(key);
    if ((blk ? blk.engine : '') === id) return;
    const was = nameAt(key), now = id ? ctx.engineName(id) : 'empty';
    structural({ key, target: `${key}:unit`, label: `${blockTag(key)} ${isModule(key) ? 'module' : parseBlockKey(key).role === ROLE.SOUND ? 'engine' : 'effect'}`,
      before: was, after: now, ops: [pickerOp(key, id)], undo: blockRecs(key) });
    ctx.say(`${blockTag(key)}: ${now}`);
  }
  function pickerButton(key) {
    const b = parseBlockKey(key);
    const text = b.role === ROLE.MODULE ? 'Choose module…' : b.role === ROLE.SOUND ? 'Choose engine…' : b.role === ROLE.MFX ? 'Choose MIDI effect…' : 'Choose effect…';
    const btn = el('button', 'ed-btn ed-pick', { type: 'button', text, 'aria-haspopup': 'listbox', 'data-fk': `${key}:pick` });
    btn.addEventListener('click', () => openPicker(key, btn));
    return btn;
  }
  async function openPicker(key, anchor) {
    closePicker();
    const list = candidates(key);
    const cur = ctx.blockOf(key) ? ctx.blockOf(key).engine : '';
    const box = el('div', 'ed-picker', { role: 'dialog', 'aria-label': `${blockTag(key)}: choose` });
    const find = el('input', 'ed-find', { type: 'search', placeholder: `Filter ${list.length - 1}`, 'aria-label': 'Filter' });
    const lb = el('div', 'ed-pick-list', { role: 'listbox', 'aria-label': blockTag(key) });
    box.append(el('div', 'ed-pick-head', {}, [el('b', null, { text: `${blockTag(key)} · now ${nameAt(key)}` }),
      el('button', 'ed-icon', { type: 'button', text: 'Close', onclick: () => closePicker(true) })]), find, lb);
    anchor.after(box);
    st.picker = { key, box, anchor };
    const rowsBy = new Map();
    let group = null;
    for (const c of list) {
      const g = !c.e ? '' : c.e.kind === 'audio_fx' ? meta.groupName(c.e.group) : '';
      if (g && g !== group) { lb.append(el('div', 'ed-pick-g', { text: g, role: 'presentation' })); group = g; }
      const name = c.e ? c.e.name : 'Empty';
      const opt = el('button', `ed-pick-o${c.id === cur ? ' is-cur' : ''}`, { type: 'button', role: 'option', 'aria-selected': String(c.id === cur), 'data-id': c.id },
        [el('span', 'ed-pick-n', { text: name }), c.e && c.e.gpl ? el('span', 'ed-gpl', { text: 'GPL', title: `Licence: ${c.e.licence}` }) : null,
          el('span', 'ed-pick-ram', { text: '…' })]);
      opt.addEventListener('click', () => { if (!opt.disabled) { closePicker(); choose(key, c.id); } });
      rowsBy.set(c.id, opt);
      lb.append(opt);
    }
    find.addEventListener('input', () => {
      const q = find.value.trim().toLowerCase();
      for (const o of lb.querySelectorAll('.ed-pick-o')) o.hidden = !!q && !o.textContent.toLowerCase().includes(q);
    });
    box.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closePicker(true); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const os = [...lb.querySelectorAll('.ed-pick-o:not([hidden]):not([disabled])')];
        const i = os.indexOf(document.activeElement);
        const j = Math.max(0, Math.min(os.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)));
        if (os[j]) { e.preventDefault(); os[j].focus(); }
      }
    });
    (rowsBy.get(cur) || find).focus();
    // The RAM column: each choice tried alone on the live state, C's verdict.
    const r = await preview(list.map((c) => pickerOp(key, c.id)), true);
    if (!st.picker || st.picker.box !== box || !r) return;
    list.forEach((c, i) => {
      const o = rowsBy.get(c.id);
      const cell = o.querySelector('.ed-pick-ram');
      const code = r.codes[i];
      if (code === 0) { cell.textContent = ramAfter(r.ram[i].total); return; }
      if (code === 8) { o.hidden = true; return; }      // BAD: not offered here (C's say)
      const ram = c.e ? c.e.ram : 0;
      cell.textContent = verdictWords(code, { pct: ram ? ramPercent(ram, budget()) : '…', rate: meta.doc.build.rate,
        what: 'rack', used: mm.positions, max: mm.positions });
      o.classList.add('is-refused');
      o.disabled = true;
      o.setAttribute('aria-disabled', 'true');
    });
  }
  function closePicker(refocus) {
    if (!st.picker) return;
    const { box, anchor } = st.picker;
    st.picker = null;
    box.remove();
    if (refocus && anchor && anchor.isConnected) anchor.focus();
  }

  // ---- meters (telemetry, §12): an insert's, a master slot's, the Mix's ----------------
  // The meter rows, by the telemetry layout's order (fm1_tele.h, named in
  // the metadata): each sound with its inserts, then the Mix, the master
  // slots and the output.
  const meterRows = () => { const m = secOf('meters'); return m ? m.rows : []; };
  const mixRow = () => meterRows()[SOUNDS * (1 + INSERTS)] || '';
  const outRow = () => meterRows()[meterRows().length - 1] || '';
  const limiterRow = () => { const r = secOf('reduction'); return r ? r.rows[r.rows.length - 1] : ''; };
  function meterPoint(key) {
    const b = parseBlockKey(key);
    if (!b) return null;
    const rows = meterRows();
    if (b.role === ROLE.INSERT) { const i = b.sound * (1 + INSERTS) + 1 + b.slot; return { out: rows[i], in: rows[i - 1] }; }
    if (b.role === ROLE.MASTER) { const i = SOUNDS * (1 + INSERTS) + 1 + b.slot; return { out: rows[i], in: rows[i - 1] }; }
    return null;
  }
  // A meter row: the level bar (with a thin gain-reduction bar under it where
  // the row has one), its peak in dB, and "GR n dB" while the effect cuts. `inRow`
  // is the meter point before the effect: with no signal in there is nothing
  // to reduce (Squash's gate, closed over silence, is a cut of its own).
  function meterRow(label, row, red, inRow) {
    return el('div', 'ed-mrow', {}, [el('span', 'ed-m-l', { text: label }),
      el('span', 'ed-m-bars', {}, [el('span', 'ed-meter ed-meter-wide', { 'data-meter': row, 'aria-hidden': 'true' }),
        red ? el('span', 'ed-gr', { 'data-gr': red, 'data-grin': inRow || '', 'aria-hidden': 'true' }) : null]),
      el('span', 'ed-m-db', { 'data-db': row, text: '–' }),
      red ? el('span', 'ed-m-red', { 'data-red': red, 'data-grin': inRow || '', text: '' }) : null]);
  }
  function meters(key) {
    const pt = meterPoint(key);
    if (!pt) return null;
    return el('div', 'ed-meters', { role: 'group', 'aria-label': `${blockTag(key)} levels` }, [meterRow('In', pt.in), meterRow('Out', pt.out, pt.out, pt.in)]);
  }

  // The Mix (§10, the Mix page's own records): each sound's level and
  // meter, which sound is current, the Mix and the output.
  function mixInspector() {
    const box = el('section', 'ed-insp', { 'data-block': 'the-mix', 'aria-label': 'Mix' });
    box.append(el('header', 'ed-insp-head', {}, [el('span', 'ed-tag ed-tag-mix', { text: 'MIX' }), el('h3', 'ed-insp-name', { text: 'Mix' })]));
    const page = el('div', 'ed-page', { 'data-page': '1' });
    for (let k = 0; k < SOUNDS; ++k) {
      if (!ctx.blockOf(blockKey(ROLE.SOUND, k))) continue;
      const cur = st.mirror.current === k;
      const row = ctx.levelRow(k);
      const now = el('button', `ed-btn ed-cur${cur ? ' is-on' : ''}`, { type: 'button', 'aria-pressed': String(cur), text: cur ? 'Current' : 'Make current',
        title: 'The sound the panel plays and edits (SHIFT + PRESETS)', 'data-fk': `mix:cur${k}` });
      now.addEventListener('click', () => { if (!cur) ctx.sendOps(packCurrent(k), { verb: true, label: `S${k + 1} current` }); });
      page.append(el('div', 'ed-mix-row', {}, [row, el('span', 'ed-meter', { 'data-meter': meterRows()[k * (1 + INSERTS) + INSERTS], 'aria-hidden': 'true' }), now]));
    }
    box.append(page, el('div', 'ed-meters', { role: 'group', 'aria-label': 'Mix and output levels' }, [meterRow('Mix', mixRow()), meterRow('Out', outRow(), limiterRow())]));
    return box;
  }

  // ---- a kit's pads (API v4: flags focus and per_focus) -----------------------------------
  // The focused pad as an offset from the focus parameter's first entry: what
  // a record's focus byte names.
  function padOf(key) {
    const blk = ctx.blockOf(key);
    const e = blk && meta.engine(blk.engine);
    const fp = e && e.params.find((p) => hasFlag(p, 'focus'));
    if (!fp) return undefined;
    const v = blk.values.get(fp.uid);
    return Math.max(0, Math.round(fp.type === 'enum' ? v : v - fp.min));
  }

  // ---- the matrix (§10 Modulation · Table, ED8) --------------------------------------------
  const cableOf = (i) => (st.mirror && st.mirror.cables[i]) || emptyCable();
  function destName(s) {
    if (cableEmpty(s)) return '–';
    const key = mm.unitKey(s.unit);
    if (!key) return `unit ${s.unit} #${s.dst}`;
    if (key === 'host') { const p = mm.host.find((x) => x.uid === s.dst); return `Host ${p ? p.name : `#${s.dst}`}`; }
    const blk = ctx.blockOf(key);
    if (isModule(key)) {
      const k = blk ? mm.kind(blk.engine) : null;
      if (s.flags & GATE_DST) { const g = k && k.gates ? k.gates[s.dst] : null; return `${blockTag(key)} ${k ? k.abbr : 'empty'} ${g ? g.name : `gate ${s.dst + 1}`}`; }
      const p = blk ? meta.param(blk.engine, s.dst) : null;
      return `${blockTag(key)} ${k ? k.abbr : 'empty'} ${p ? p.name : `#${s.dst}`}`;
    }
    const p = blk ? meta.param(blk.engine, s.dst) : null;
    return `${blockTag(key)} ${p ? p.name : blk ? `#${s.dst}` : 'empty'}`;
  }
  const srcName = (code) => mm.sourceName(code, st.mirror ? st.mirror.rack : []);
  const toValue = (s) => `${s.unit}:${s.dst}:${s.flags & GATE_DST ? 1 : 0}`;
  // Every destination a cable can aim at now: the parameters that take
  // modulation (flag mod), the modules' gates, the host's.
  function destList() {
    const out = [];
    // Each named in full (a closed list shows only the option), grouped by block.
    const add = (group, unit, list) => {
      for (const x of list) {
        out.push({ group, value: `${unit}:${x.dst}:${x.gate ? 1 : 0}`,
          name: destName({ src: 1, via: NONE, unit, dst: x.dst, flags: SLOT_ON | (x.gate ? GATE_DST : 0), amount: 1, offset: 0 }) });
      }
    };
    const keys = [];
    for (let k = 0; k < SOUNDS; ++k) { keys.push(blockKey(ROLE.SOUND, k)); for (let j = 0; j < INSERTS; ++j) keys.push(blockKey(ROLE.INSERT, k, j)); }
    for (let j = 0; j < MASTERS; ++j) keys.push(blockKey(ROLE.MASTER, 0, j));
    for (let i = 0; i < mm.positions; ++i) keys.push(modKey(i));
    for (const key of keys) {
      const blk = ctx.blockOf(key);
      const unit = mm.unitCode(key);
      if (!blk || unit < 0) continue;
      const e = meta.engine(blk.engine);
      if (!e) continue;
      const list = e.params.filter((p) => hasFlag(p, 'mod')).map((p) => ({ dst: p.uid, name: p.name }));
      if (isModule(key)) (mm.kind(blk.engine).gates || []).forEach((g, gi) => list.push({ dst: gi, name: g.name, gate: true }));
      add(`${blockTag(key)} · ${e.name}`, unit, list);
    }
    const hostCode = mm.unitCode('host');
    if (hostCode >= 0) add('Host', hostCode, mm.host.filter((p) => hasFlag(p, 'mod')).map((p) => ({ dst: p.uid, name: p.name })));
    return out;
  }
  function selectOf(options, value, label, fk, onchange) {
    const s = el('select', 'ed-select', { 'aria-label': label, 'data-fk': fk });
    let group = null, og = s;
    let found = false;
    for (const o of options) {
      if (o.group !== undefined && o.group !== group) { group = o.group; og = el('optgroup', null, { label: group }); s.append(og); }
      const opt = el('option', null, { value: String(o.value), text: o.name });
      if (String(o.value) === String(value)) found = true;
      og.append(opt);
    }
    if (!found) s.prepend(el('option', null, { value: String(value), text: options.missing || String(value) }));
    s.value = String(value);
    s.addEventListener('change', () => onchange(s.value));
    return s;
  }
  function sourceOptions(withNone) {
    const list = mm.sourceList(st.mirror.rack).map((x) => ({ group: x.group, value: x.code, name: x.name }));
    return withNone ? [{ value: NONE, name: '– none', group: '' }, ...list] : list;
  }

  // A cable's fields as the editor edits them: on, src, via, to, amount and
  // offset (percent of the destination's range, exact to C's Q1.14), pol,
  // curve, voice, or all of it ('all', the slot as JSON).
  function cableGet(i, f) {
    const s = cableOf(i);
    switch (f) {
      case 'on': return !!(s.flags & SLOT_ON);
      case 'src': return s.src;
      case 'via': return s.via;
      case 'to': return toValue(s);
      case 'amount': return (s.amount * 100) / Q14;
      case 'offset': return (s.offset * 100) / Q14;
      case 'pol': return (s.flags & 0x06) >> 1;
      case 'curve': return (s.flags & 0x70) >> 4;
      case 'voice': return !!(s.flags & VOICE);
      default: return JSON.stringify(s);
    }
  }
  function cableWith(i, f, v) {
    const s = { ...cableOf(i) };
    switch (f) {
      case 'on': s.flags = withBit(s.flags, SLOT_ON, !!v); break;
      case 'src': s.src = Number(v) & 0xff; break;
      case 'via': s.via = Number(v) & 0xff; break;
      case 'to': { const [u, d, g] = String(v).split(':').map(Number); s.unit = u; s.dst = d; s.flags = withBit(s.flags, GATE_DST, g === 1); break; }
      case 'amount': s.amount = toQ(v); break;
      case 'offset': s.offset = toQ(v); break;
      case 'pol': s.flags = withPol(s.flags, Number(v)); break;
      case 'curve': s.flags = withCurve(s.flags, Number(v)); break;
      case 'voice': s.flags = withBit(s.flags, VOICE, !!v); break;
      default: Object.assign(s, JSON.parse(v)); break;
    }
    return s;
  }
  function cableSet(i, f, v, info) {
    const s = cableWith(i, f, v);
    st.mirror.cables[i] = s;
    ctx.sendOps(packCable(i, s), info);
  }
  function cableText(i, f, v) {
    switch (f) {
      case 'on': return v ? 'on' : 'off';
      case 'voice': return v ? 'per voice' : 'one value';
      case 'src': case 'via': return srcName(Number(v));
      case 'to': { const [u, d, g] = String(v).split(':').map(Number); return destName({ ...cableOf(i), unit: u, dst: d, flags: (g ? GATE_DST : 0) | SLOT_ON }); }
      case 'amount': case 'offset': return `${pctOfQ14(toQ(v)) > 0 ? '+' : ''}${pctOfQ14(toQ(v))} %`;
      case 'pol': return mm.polarities[v] || String(v);
      case 'curve': return mm.curves[v] || String(v);
      default: { const s = JSON.parse(v); return cableEmpty(s) ? 'empty' : `${srcName(s.src)} → ${destName(s)} ${pctOfQ14(s.amount)} %`; }
    }
  }
  const FIELD_NAMES = { on: 'On', src: 'From', via: 'VIA', to: 'To', amount: 'Amount', offset: 'Offset', pol: 'Polarity', curve: 'Curve', voice: 'Per voice', all: '' };
  const cableLabel = (i, f) => `Cable ${i + 1}${FIELD_NAMES[f] ? ` ${FIELD_NAMES[f]}` : ''}`;
  // A cable change from the panel, field by field, for the history.
  function cableFields(was, now) {
    const fs = [];
    if ((was.flags & SLOT_ON) !== (now.flags & SLOT_ON)) fs.push('on');
    if (was.src !== now.src) fs.push('src');
    if (was.via !== now.via) fs.push('via');
    if (was.unit !== now.unit || was.dst !== now.dst || (was.flags & GATE_DST) !== (now.flags & GATE_DST)) fs.push('to');
    if (was.amount !== now.amount) fs.push('amount');
    if (was.offset !== now.offset) fs.push('offset');
    if ((was.flags & 0x06) !== (now.flags & 0x06)) fs.push('pol');
    if ((was.flags & 0x70) !== (now.flags & 0x70)) fs.push('curve');
    if ((was.flags & VOICE) !== (now.flags & VOICE)) fs.push('voice');
    return fs.length === 1 ? fs : ['all'];
  }
  function fieldOf(s, f) {
    const saved = st.mirror.cables[0];
    st.mirror.cables[0] = s;
    try { return cableGet(0, f); } finally { st.mirror.cables[0] = saved; }
  }

  function verdictOf(i) {
    const s = cableOf(i);
    const code = st.mirror.verdicts[i] || 0;
    if (cableEmpty(s)) return { code: 0, text: '' };
    if (!(s.flags & SLOT_ON)) return { code: 0, text: 'off' };
    if (!code) return { code: 0, text: 'runs' };
    const p = (() => { const k = mm.unitKey(s.unit); const b = k && ctx.blockOf(k); const q = b ? meta.param(b.engine, s.dst) : null; return q ? q.name : `#${s.dst}`; })();
    return { code, text: verdictWords(code, { from: srcName(s.src), to: destName(s), param: p }) };
  }
  function marks(i) {
    const s = cableOf(i), v = verdictOf(i);
    const m = [];
    if (s.flags & VOICE) m.push(['v', 'per voice']);
    if (v.code) m.push(['!', 'refused']);
    if (!cableEmpty(s) && !(s.flags & SLOT_ON)) m.push(['–', 'off']);
    return m;
  }

  // The Map (stage ED5b) needs room: from 620 px of the editor's width. A phone keeps the cable list.
  const mapRoom = () => { const m = ctx.root.querySelector('.ed-main'); return !!m && m.clientWidth >= 620; };
  const mapOn = () => !!st.modMap && mapRoom();
  function viewSwitch() {
    const seg = el('div', 'ed-seg ed-mapsw', { role: 'radiogroup', 'aria-label': 'Modulation view' });
    [[false, 'Table'], [true, 'Map']].forEach(([v, label]) => seg.append(el('button', 'ed-segbtn', { type: 'button', role: 'radio', text: label, 'data-fk': `mod:v${label}`,
      'aria-checked': String(!!st.modMap === v), tabindex: !!st.modMap === v ? '0' : '-1', onclick: () => { st.modMap = v; ctx.render(); } })));
    seg.addEventListener('keydown', (e) => {
      const btns = [...seg.querySelectorAll('[role=radio]')];
      const i = btns.indexOf(document.activeElement);
      const j = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? Math.min(1, i + 1) : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? Math.max(0, i - 1) : -1;
      if (i < 0 || j < 0) return;
      e.preventDefault();
      st.focusAfter = `mod:v${j ? 'Map' : 'Table'}`;
      st.modMap = !!j;
      ctx.render();
    });
    return seg;
  }
  function modView() {
    const wrap = el('div', 'ed-mod');
    const wide = mapRoom();
    wrap.append(el('div', 'ed-sec-head', {}, [el('h2', 'ed-sec ed-sec-big', { text: 'Modulation' }),
      wide ? viewSwitch() : null,
      mapOn() ? null : el('p', 'ed-legend', {}, [el('span', 'ed-l-mod', { text: 'live value' }), el('span', 'ed-l-refuse', { text: '! refused' }), el('span', null, { text: 'v per voice' })])]));
    const sel = st.selected;
    if (mapOn()) {
      wrap.append(map.view());
      const insp = el('div', 'ed-mod-insp');
      if (isModule(sel)) insp.append(moduleInspector(sel));
      wrap.append(insp);
      const ci = cableIndex(st.selCable);
      if (ci >= 0) wrap.append(slotInspector(ci));
      return wrap;
    }
    // The rack: eight positions as cards.
    const rack = el('div', 'ed-rack', { role: 'group', 'aria-label': 'Rack' });
    for (let pos = 0; pos < mm.positions; ++pos) rack.append(rackCard(pos));
    wrap.append(el('h3', 'ed-sec', { text: 'Rack' }), rack);
    const insp = el('div', 'ed-mod-insp');
    if (isModule(sel)) insp.append(moduleInspector(sel));
    wrap.append(insp);
    wrap.append(matrix());
    const ci = cableIndex(st.selCable);
    if (ci >= 0) wrap.append(slotInspector(ci));
    return wrap;
  }
  function rackCard(pos) {
    const key = modKey(pos);
    const blk = ctx.blockOf(key);
    const k = blk ? mm.kind(blk.engine) : null;
    const n = st.mirror.cables.filter((c) => !cableEmpty(c) && ((c.src >= 64 && ((c.src - 64) >> 3) === pos) || mm.unitKey(c.unit) === key)).length;
    const card = el('button', `ed-card-m${blk ? '' : ' is-empty'}${st.selected === key ? ' is-sel' : ''}`, { type: 'button', 'data-block': key, 'data-fk': key,
      'aria-pressed': String(st.selected === key), 'aria-label': `Rack ${pos + 1}: ${k ? k.name : 'empty'}${n ? `, ${n} cables` : ''}`,
      onclick: () => ctx.select(key, { view: 'mod' }) }, [
      el('span', 'ed-blk-k', { text: `RACK ${pos + 1}` }),
      el('span', 'ed-blk-n', { text: k ? k.name : 'empty' }),
      k ? el('canvas', 'ed-trace', { width: 120, height: 28, 'data-trace': String(pos), 'aria-hidden': 'true' }) : null,
      el('span', 'ed-blk-s', { text: n ? `${n} cable${n > 1 ? 's' : ''}` : k ? 'no cables' : '' })]);
    return movable(card, key);
  }
  function moduleInspector(key) {
    const blk = ctx.blockOf(key);
    if (!blk) {
      return el('section', 'ed-insp is-empty', { 'data-block': key, 'aria-label': `${blockTag(key)} empty` }, [
        el('header', 'ed-insp-head', {}, [el('span', 'ed-tag', { text: blockTag(key).toUpperCase() }), el('h3', 'ed-insp-name', { text: 'empty' }), pickerButton(key)])]);
    }
    const box = ctx.inspector(key);
    const k = mm.kind(blk.engine);
    const pos = parseModKey(key);
    if (k && (k.outs || []).length) {
      const outs = el('div', 'ed-page', { 'data-page': 'outs' }, [el('div', 'ed-page-head', {}, [el('span', 'ed-page-n', { text: 'Outputs' }), el('span', 'ed-page-k', { text: 'live' })])]);
      k.outs.forEach((o, port) => outs.append(el('div', 'ed-row ed-row-out', {}, [el('span', 'ed-label', { text: `${o.name} · ${o.kind.replace('cv_uni', 'unipolar').replace('cv_bi', 'bipolar')}` }),
        el('span', 'ed-live', { 'data-out': `${pos}:${port}`, text: '–' })])));
      box.append(outs);
    }
    if (k && (k.gates || []).length) {
      const g = el('div', 'ed-page', { 'data-page': 'gates' }, [el('div', 'ed-page-head', {}, [el('span', 'ed-page-n', { text: 'Gate inputs' })])]);
      k.gates.forEach((x, gi) => {
        const into = st.mirror.cables.map((c, i) => [c, i]).filter(([c]) => !cableEmpty(c) && (c.flags & GATE_DST) && mm.unitKey(c.unit) === key && c.dst === gi);
        g.append(el('div', 'ed-row ed-row-out', {}, [el('span', 'ed-label', { text: x.name }),
          el('span', 'ed-note', { text: into.length ? into.map(([c, i]) => `${srcName(c.src)} (cable ${i + 1})`).join(', ') : x.normal ? `normalled to ${x.normal}` : 'nothing' })]));
      });
      box.append(g);
    }
    return box;
  }
  function headTools(key) {
    const out = [];
    const b = parseBlockKey(key);
    if (!b) return out;
    out.push(pickerButton(key));
    const mv = moveSelect(key);
    if (mv) out.push(mv);
    return out;
  }
  // The cables into a block, in words (§10's Sound view).
  function cablesInto(key) {
    const list = [];
    st.mirror.cables.forEach((c, i) => { if (!cableEmpty(c) && mm.unitKey(c.unit) === key) list.push(i); });
    if (!list.length) return null;
    const box = el('div', 'ed-into', { role: 'group', 'aria-label': `Cables into ${blockTag(key)}` }, [el('span', 'ed-page-n', { text: 'Cables in' })]);
    for (const i of list) {
      const v = verdictOf(i);
      box.append(el('button', `ed-into-c${v.code ? ' is-refused' : ''}`, { type: 'button', 'data-fk': `into:${i}`,
        onclick: () => { st.selCable = `c${i + 1}`; ctx.select(`c${i + 1}`, { view: 'mod' }); } },
      [`${srcName(cableOf(i).src)} → ${destName(cableOf(i))} `, el('b', null, { text: cableText(i, 'amount', cableGet(i, 'amount')) }),
        v.code ? el('span', 'ed-refused', { text: ` ✕ ${v.text}` }) : null]));
    }
    return box;
  }

  const filt = { q: '', empty: false, sort: 'slot' };
  function matrix() {
    const sec = el('section', 'ed-matrix', { 'aria-label': 'Matrix' });
    const q = el('input', 'ed-find', { type: 'search', placeholder: 'Filter: source or destination', 'aria-label': 'Filter the matrix', value: filt.q, 'data-fk': 'mx:find' });
    q.addEventListener('focus', () => { st.typing = true; });
    q.addEventListener('blur', () => { st.typing = false; if (st.verdictDirty) { st.verdictDirty = false; ctx.snapshotSoon(); } });
    q.addEventListener('input', () => { filt.q = q.value; fillRows(); });
    const showEmpty = el('input', null, { type: 'checkbox', id: ctx.nextId('mx'), 'data-fk': 'mx:empty' });
    showEmpty.checked = filt.empty;
    showEmpty.addEventListener('change', () => { filt.empty = showEmpty.checked; fillRows(); });
    const sort = selectOf([{ value: 'slot', name: 'Sort: slot' }, { value: 'src', name: 'Sort: source' }, { value: 'to', name: 'Sort: destination' }, { value: 'refused', name: 'Sort: refused first' }],
      filt.sort, 'Sort the matrix', 'mx:sort', (v) => { filt.sort = v; fillRows(); });
    const used = st.mirror.cables.filter((c) => !cableEmpty(c)).length;
    const add = el('button', 'ed-btn', { type: 'button', text: 'Add a cable', 'data-fk': 'mx:add', onclick: () => addCable() });
    sec.append(el('div', 'ed-sec-head', {}, [el('h3', 'ed-sec', { text: 'Matrix' }), el('span', 'ed-note', { text: `${used} of ${SLOTS} slots` })]),
      el('div', 'ed-mx-tools', {}, [q, el('label', 'ed-toggle', { for: showEmpty.id }, [showEmpty, el('span', null, { text: 'Empty slots' })]), sort, add]));
    const table = el('div', 'ed-mx', { role: 'table', 'aria-label': 'Modulation matrix' });
    table.append(el('div', 'ed-mx-r ed-mx-h', { role: 'row' }, ['#', 'On', 'From', 'VIA', 'To', 'Amount', 'Live', 'Verdict'].map((t) => el('span', null, { role: 'columnheader', text: t }))));
    const body = el('div', 'ed-mx-body', { role: 'rowgroup' });
    table.append(body);
    sec.append(table);
    function fillRows() {
      body.innerHTML = '';
      let idx = [...Array(SLOTS).keys()].filter((i) => filt.empty || !cableEmpty(cableOf(i)));
      const qq = filt.q.trim().toLowerCase();
      if (qq) idx = idx.filter((i) => `${srcName(cableOf(i).src)} ${destName(cableOf(i))} ${cableOf(i).via !== NONE ? srcName(cableOf(i).via) : ''}`.toLowerCase().includes(qq));
      const by = { src: (i) => srcName(cableOf(i).src), to: (i) => destName(cableOf(i)), refused: (i) => (verdictOf(i).code ? '0' : '1') + String(i).padStart(2, '0') };
      if (by[filt.sort]) idx.sort((a, b) => by[filt.sort](a).localeCompare(by[filt.sort](b)) || a - b);
      if (!idx.length) body.append(el('p', 'ed-note', { text: used ? 'No cable matches.' : 'No cables yet: "Add a cable", or MATRIX on the panel.' }));
      for (const i of idx) body.append(matrixRow(i));
    }
    fillRows();
    return sec;
  }
  function matrixRow(i) {
    const s = cableOf(i);
    const key = `c${i + 1}`;
    const v = verdictOf(i);
    const sel = st.selCable === key;
    const row = el('div', `ed-mx-r${sel ? ' is-sel' : ''}${v.code ? ' is-refused' : ''}${cableEmpty(s) ? ' is-empty' : ''}`, { role: 'row', 'data-cable': String(i) });
    const pick = () => { if (st.selCable !== key) { st.selCable = key; ctx.select(key, { view: 'mod' }); } };
    const num = el('button', 'ed-mx-n', { type: 'button', 'data-fk': `${key}:n`, 'aria-label': `Cable ${i + 1}: open its inspector`, onclick: pick },
      [String(i + 1), ...marks(i).map(([m, w]) => el('abbr', 'ed-mark', { title: w, text: m }))]);
    const on = el('input', null, { type: 'checkbox', 'aria-label': `Cable ${i + 1} on`, 'data-fk': `${key}:on` });
    on.checked = !!(s.flags & SLOT_ON);
    on.addEventListener('change', () => ctx.setValue(key, 'on', on.checked, 'set'));
    const src = selectOf(sourceOptions(false), s.src, `Cable ${i + 1} from`, `${key}:src`, (x) => ctx.setValue(key, 'src', Number(x), 'set'));
    const via = selectOf(sourceOptions(true), s.via, `Cable ${i + 1} VIA`, `${key}:via`, (x) => ctx.setValue(key, 'via', Number(x), 'set'));
    const dl = destList();
    dl.missing = destName(s);
    const to = selectOf(dl, toValue(s), `Cable ${i + 1} to`, `${key}:to`, (x) => ctx.setValue(key, 'to', x, 'set'));
    const amt = el('input', 'ed-val ed-amt', { type: 'text', inputmode: 'numeric', 'aria-label': `Cable ${i + 1} amount, percent`, 'data-fk': `${key}:amt`,
      value: String(pctOfQ14(s.amount)) });
    amt.addEventListener('focus', () => { st.typing = true; amt.select(); });
    amt.addEventListener('blur', () => {
      st.typing = false;
      amt.value = String(pctOfQ14(cableOf(i).amount));
      if (st.verdictDirty) { st.verdictDirty = false; ctx.snapshotSoon(); }
    });
    amt.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        const nv = Math.max(-100, Math.min(100, pctOfQ14(cableOf(i).amount) + (e.key === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 10 : 1)));
        ctx.setValue(key, 'amount', nv, 'key');
        amt.value = String(nv);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const n = Number(amt.value.replace(/[%+\s]/g, ''));
        if (Number.isFinite(n)) ctx.setValue(key, 'amount', Math.max(-100, Math.min(100, n)), 'typed');
        else ctx.say(`${amt.value} is not an amount`);
      }
    });
    const live = el('span', 'ed-live', { role: 'cell', 'data-dest': String(i), text: '–' });
    const verdict = el('span', `ed-mx-v${v.code ? ' is-refused' : ''}`, { role: 'cell', text: v.text, title: v.text });
    // Each control inside its cell, so it keeps its own role (button, list).
    const cell = (x, cls = 'ed-mx-c') => el('span', cls, { role: 'cell' }, [x]);
    row.append(cell(num), el('span', 'ed-mx-on', { role: 'cell' }, [on]), cell(src), cell(via), cell(to),
      el('span', 'ed-mx-amt', { role: 'cell' }, [amt, el('span', 'ed-u', { text: '%' })]), live, verdict);
    // The cells' names, for the cable list a phone shows (the table's header row says them otherwise).
    ['#', 'On', 'From', 'VIA', 'To', 'Amount', 'Live', 'Verdict'].forEach((h, n) => { if (row.children[n]) row.children[n].dataset.h = h; });
    row.addEventListener('focusin', () => { if (st.selCable !== key) { st.selCable = key; for (const r of ctx.root.querySelectorAll('.ed-mx-r.is-sel')) r.classList.remove('is-sel'); row.classList.add('is-sel'); ctx.openOnPanel(key); } });
    return row;
  }
  // A new cable from a source code to a destination ("unit:dst:gate"), 25 % to start with.
  const newSlot = (src, dest) => {
    const [u, dst, g] = String(dest).split(':').map(Number);
    return { src, via: NONE, unit: u, dst, flags: SLOT_ON | (g ? GATE_DST : 0), amount: toQ(25), offset: 0, uid: 0 };
  };
  const cableRecord = (i, src, dest) => packCable(i, newSlot(src, dest));
  // Puts a cable in the first empty slot and selects it; -1 (and C's words) when the matrix is full.
  function makeCable(src, dest) {
    const i = st.mirror.cables.findIndex((c) => cableEmpty(c));
    if (i < 0) {
      const w = verdictWords(6, { what: 'matrix', used: SLOTS, max: SLOTS });
      ctx.showRefusal('Add a cable', w);
      ctx.say(w);
      return -1;
    }
    ctx.setValue(`c${i + 1}`, 'all', JSON.stringify(newSlot(src, dest)), 'set');
    st.selCable = `c${i + 1}`;
    ctx.select(`c${i + 1}`, { view: 'mod' });
    return i;
  }
  function addCable() {
    const srcs = sourceOptions(false);
    const mod = srcs.find((x) => x.value >= 64) || srcs[0];
    const dl = destList();
    const sel = ctx.blockOf(st.selected) ? mm.unitCode(st.selected) : -1;
    const d = dl.find((x) => Number(x.value.split(':')[0]) === sel) || dl[0];
    if (!d) return;
    makeCable(mod.value, d.value);
  }

  // The slot inspector: every field of one cable, its verdict and its fix.
  function slotInspector(i) {
    const key = `c${i + 1}`;
    const s = cableOf(i);
    const v = verdictOf(i);
    const box = el('section', `ed-insp ed-slot${v.code ? ' is-refused' : ''}`, { 'data-block': key, 'aria-label': `Cable ${i + 1}` });
    box.append(el('header', 'ed-insp-head', {}, [el('span', 'ed-tag ed-tag-mod', { text: `CABLE ${i + 1}` }),
      el('h3', 'ed-insp-name', { text: cableEmpty(s) ? 'empty' : `${srcName(s.src)} → ${destName(s)}` }),
      el('button', 'ed-btn', { type: 'button', text: 'Remove', 'data-fk': `${key}:rm`, disabled: cableEmpty(s),
        onclick: () => ctx.setValue(key, 'all', JSON.stringify(emptyCable()), 'set') })]));
    if (v.code) box.append(el('p', 'ed-refused ed-why', { text: `${v.text}. The cable is kept as written; it runs once this is put right.` }));
    const page = el('div', 'ed-page', { 'data-page': '1' });
    const seg = (f, label, names) => {
      const r = ctx.rowShell(key, f, label, 'ed-row-seg');
      const p = { uid: f, name: label, type: 'enum', entries: names, def: 0, flags: [] };
      r.p = p;
      ctx.segControl(r, p, names.length <= 4 ? 'segments' : 'grid');
      return r.el;
    };
    const sel = (f, label, opts) => {
      const r = ctx.rowShell(key, f, label, 'ed-row-list');
      r.el.append(selectOf(opts, cableGet(i, f), label, `${key}:${f}`, (x) => ctx.setValue(key, f, f === 'to' ? x : Number(x), 'set')));
      return r.el;
    };
    const slider = (f, label) => {
      const r = ctx.rowShell(key, f, label, 'ed-row-slider');
      const p = { uid: f, name: label, type: 'float', min: -100, max: 100, def: 0, step: 1, unit: 'pct', flags: [] };
      r.p = p;
      ctx.sliderControl(r, p, () => cableGet(i, f), (x) => cableText(i, f, x));
      return r.el;
    };
    const dl = destList();
    dl.missing = destName(s);
    page.append(seg('on', 'On', ['Off', 'On']), sel('src', 'From', sourceOptions(false)), sel('via', 'VIA', sourceOptions(true)), sel('to', 'To', dl),
      slider('amount', 'Amount'), slider('offset', 'Offset'), seg('pol', 'Polarity', mm.polarities), seg('curve', 'Curve', mm.curves),
      seg('voice', 'Per voice', ['Off', 'On']));
    page.append(el('div', 'ed-row ed-row-out', {}, [el('span', 'ed-label', { text: 'Live value' }), el('span', 'ed-live', { 'data-dest': String(i), text: '–' })]));
    box.append(page);
    return box;
  }

  // ---- telemetry: traces, outputs and destinations (§12) ------------------------------------
  const traces = new Map();
  function sections() { return meta.doc.telemetry ? meta.doc.telemetry.sections : []; }
  const secOf = (name) => sections().find((x) => x.name === name);
  function wantRows(view) {
    const want = [];
    const all = (name) => { const s = secOf(name); if (s) for (let r = 0; r < s.rows.length; ++r) want.push(s.mask + r); };
    if (view === 'flow' || view === 'sound') { all('meters'); all('reduction'); }
    if (view === 'mod') { all('outs'); all('dests'); all('voice_dests'); }
    return want;
  }
  // A live value short enough for its cell: 1.13k, 420, 12.5, 0.33.
  const short = (x) => {
    const a = Math.abs(x);
    return a >= 10000 ? `${(x / 1000).toFixed(1)}k` : a >= 1000 ? `${(x / 1000).toFixed(2)}k` : a >= 100 ? x.toFixed(0) : a >= 10 ? x.toFixed(1) : x.toFixed(2);
  };
  function onTelemetry(f) {
    const outs = secOf('outs'), dests = secOf('dests'), red = secOf('reduction'), met = secOf('meters');
    if (met) {
      for (const m of ctx.root.querySelectorAll('[data-db]')) {
        const r = met.rows.indexOf(m.dataset.db);
        if (r < 0) continue;
        const peak = f[met.offset + r * met.fields.length];
        m.textContent = peak > 0 ? `${(20 * Math.log10(peak)).toFixed(1)} dB` : '–';
      }
    }
    if (red) {
      // C's words: dB cut, 0 or more. Shown while there is signal in (the
      // effect's input meter) and the cut is more than a twentieth of a dB.
      const gr = (name, inName) => {
        const r = red.rows.indexOf(name);
        const i = inName && met ? met.rows.indexOf(inName) : -1;
        const db = r >= 0 ? f[red.offset + r] : NaN;
        const live = i < 0 || f[met.offset + i * met.fields.length] > 1e-6;
        return Number.isFinite(db) && db > 0.05 && live ? db : 0;
      };
      for (const m of ctx.root.querySelectorAll('[data-red]')) {
        const db = gr(m.dataset.red, m.dataset.grin);
        m.textContent = db ? `GR ${db.toFixed(1)} dB` : '';
      }
      for (const m of ctx.root.querySelectorAll('[data-gr]')) {
        m.style.setProperty('--gr', Math.min(1, gr(m.dataset.gr, m.dataset.grin) / 24).toFixed(3));
      }
    }
    if (outs) {
      const nf = outs.fields.length, ni = outs.items.length || 8;
      for (const m of ctx.root.querySelectorAll('[data-out]')) {
        const [pos, port] = m.dataset.out.split(':').map(Number);
        const x = f[outs.offset + (pos * ni + port) * nf];
        m.textContent = Number.isFinite(x) ? short(x) : '–';
      }
      for (const c of ctx.root.querySelectorAll('canvas[data-trace]')) {
        const pos = Number(c.dataset.trace);
        const o = outs.offset + pos * ni * nf;
        const t = traces.get(pos) || [];
        t.push([f[o], f[o + 1], f[o + 2]]);
        if (t.length > 60) t.shift();
        traces.set(pos, t);
        drawTrace(c, t);
      }
    }
    if (dests) {
      const vd = secOf('voice_dests');
      const nv = vd ? vd.fields.length : 0;
      for (const m of ctx.root.querySelectorAll('[data-dest]')) {
        const i = Number(m.dataset.dest);
        if (vd && (cableOf(i).flags & VOICE)) {
          // A per-voice cable: each sounding voice has its own value.
          const vals = [];
          for (let v = 0; v < nv; ++v) { const x = f[vd.offset + i * nv + v]; if (Number.isFinite(x)) vals.push(x); }
          const lo = Math.min(...vals), hi = Math.max(...vals);
          m.textContent = !vals.length ? '–' : short(lo) === short(hi) ? short(lo) : `${short(lo)}–${short(hi)}`;
          m.title = vals.length ? `${vals.length} voice${vals.length > 1 ? 's' : ''} sounding` : 'no voice sounding';
          continue;
        }
        const x = f[dests.offset + i];
        m.textContent = Number.isFinite(x) ? short(x) : '–';
        m.removeAttribute('title');
      }
    }
  }
  function drawTrace(c, t) {
    const g = c.getContext('2d');
    const w = c.width, h = c.height;
    g.clearRect(0, 0, w, h);
    let lo = Infinity, hi = -Infinity;
    for (const [v, a, b] of t) for (const x of [v, a, b]) if (Number.isFinite(x)) { lo = Math.min(lo, x); hi = Math.max(hi, x); }
    if (!Number.isFinite(lo)) return;
    if (hi - lo < 1e-6) { hi += 0.5; lo -= 0.5; }
    const y = (x) => h - 2 - ((x - lo) / (hi - lo)) * (h - 4);
    const css = getComputedStyle(c);
    g.fillStyle = css.getPropertyValue('--ed-trace-band').trim() || 'rgba(120,200,200,.25)';
    t.forEach(([, a, b], i) => { if (Number.isFinite(a) && Number.isFinite(b)) g.fillRect((i / 60) * w, y(b), w / 60 + 0.5, Math.max(1, y(a) - y(b))); });
    g.strokeStyle = css.getPropertyValue('--ed-trace').trim() || '#7cc';
    g.lineWidth = 1.5;
    g.beginPath();
    t.forEach(([v], i) => { const X = (i / 60) * w; if (i) g.lineTo(X, y(v)); else g.moveTo(X, y(v)); });
    g.stroke();
  }

  const map = makeMap(ctx, { cableOf, verdictOf, destName, srcName, verdictWords, makeCable, cableRecord, toValue, pickerButton, preview });
  // The Map comes and goes as the editor's width crosses its room (a tablet turned over).
  let hadRoom = null;
  const mainEl = ctx.root.querySelector('.ed-main');
  if (mainEl && typeof ResizeObserver === 'function') {
    new ResizeObserver(() => {
      const room = mapRoom();
      if (hadRoom !== null && room !== hadRoom && st.view === 'mod' && st.modMap && st.mirror) ctx.render();
      hadRoom = room;
    }).observe(mainEl);
  }

  return {
    map, mapOn, makeCable,
    effectKeys, isEffect, isModule, movable, moveSelect, moveTo, pickerButton, openPicker, closePicker, choose,
    meters, mixInspector, padOf, modView, headTools, cablesInto, verdictWords, ramAfter, preview,
    blockRecs, cableRecs, structural, undoStruct, fromPanel, cableGet, cableSet, cableText, cableLabel, cableFields, fieldOf,
    onTelemetry, wantRows, verdictOf, destName, srcName, cancel, get held() { return held; },
  };
}
export { cableEqual };
