// editor-unit.mjs -- the web editor's data and history (stages ED2 and ED3,
// notes/2026-10-06-web-editor.md §6, §8), against the module itself:
//
//   node editor-unit.mjs WWW_DIR
//
// Checks: every parameter of every module in meta.json gets a control by
// §6's table, and its LOG law, detents and defaults stay in range; records
// packed by editor/model.js are what C applies (the change feed carries
// them back, decoded the same); the panel's view decodes, and a view verb
// opens the page model.js names; the mirror built from C's canonical JSON
// matches the module's own values; the history merges a drag, key repeats
// and knob turns as §8 says, and undoing every step of a random edit
// sequence ends at the first state hash, redoing at the last; RAM by part
// adds up to the whole (when the module has fm1w_ram_part). ED3: modules,
// cables, swaps and moves as packed records, the feed and fm1w_mod_records
// decoded the same; refused records change nothing; random structural edits
// made through chains.js undone to the first state hash and redone to the
// last. Prints a JSON
// report; exits 1 on any failure. MIT licence, like the rest of this
// repository.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { playbackDelta } from './playback-stats.mjs';

const www = process.argv[2];
const imp = (p) => import(pathToFileURL(join(www, p)).href);
const M = await imp('editor/model.js');
const { History } = await imp('editor/history.js');
const { instantiateFm1 } = await imp('fm1-wasm.mjs');

const report = { checks: {}, failed: 0, why: [] };
function check(name, ok, why) {
  report.checks[name] = !!ok;
  if (!ok) { report.failed += 1; report.why.push(`${name}: ${why || ''}`); }
}

// Browser counters are cumulative; Chromium's duration is seconds. These
// reproduce the one/two-event CI reports, including a nonzero baseline.
{
  const zero = playbackDelta({ events: 3, seconds: 0.13 }, { events: 3, seconds: 0.13 });
  const one = playbackDelta({ events: 0, seconds: 0 }, { events: 1, seconds: 0.01 });
  const two = playbackDelta({ events: 3, seconds: 0.13 }, { events: 5, seconds: 0.15 });
  check('playback duration is milliseconds and events stay exact',
    zero.underrun_events === 0 && zero.underrun_ms === 0 &&
    one.underrun_events === 1 && one.underrun_ms === 10 &&
    two.underrun_events === 2 && Math.abs(two.underrun_ms - 20) < 1e-9 &&
    playbackDelta(null, null) === null,
    JSON.stringify({ zero, one, two }));
}

const metaDoc = JSON.parse(readFileSync(join(www, 'meta.json'), 'utf8'));
const meta = new M.Meta(metaDoc);

// ---- controls from metadata -------------------------------------------------
{
  let params = 0, bad = [];
  const kinds = {};
  for (const e of metaDoc.engines) {
    for (const pg of meta.pages(e.id)) {
      for (const p of pg.params) {
        ++params;
        const k = M.controlKind(p);
        kinds[k] = (kinds[k] || 0) + 1;
        const n = (p.entries || []).length;
        if (p.type === 'enum' && !((n <= 4 && k === 'segments') || (n > 4 && n <= 8 && k === 'grid') ||
            (n > 8 && n <= 24 && k === 'list') || (n > 24 && k === 'search'))) bad.push(`${e.id}.${p.uid} ${k}`);
        if (p.type === 'float') {
          if (k !== 'slider') bad.push(`${e.id}.${p.uid} float as ${k}`);
          for (const u of [0, 0.25, 0.5, 1]) {
            const v = M.fromPos(p, u);
            if (!(v >= p.min - 1e-6 && v <= p.max + 1e-6)) bad.push(`${e.id}.${p.uid} fromPos(${u})=${v}`);
            if (Math.abs(M.toPos(p, v) - u) > 1e-6) bad.push(`${e.id}.${p.uid} pos round trip at ${u}`);
          }
          let v = p.def;
          for (let i = 0; i < 400; ++i) v = M.stepValue(p, v, 1);
          if (Math.abs(v - p.max) > 1e-6 * Math.max(1, Math.abs(p.max))) bad.push(`${e.id}.${p.uid} detents end at ${v}, not ${p.max}`);
          const up = M.stepValue(p, p.def, 1);
          if (p.def < p.max && !(up > p.def)) bad.push(`${e.id}.${p.uid} one detent up does not move`);
          if (M.isBipolar(p) && !(M.zeroPos(p) > 0 && M.zeroPos(p) < 1)) bad.push(`${e.id}.${p.uid} zero mark`);
        }
        if (!(p.def >= p.min && p.def <= p.max)) bad.push(`${e.id}.${p.uid} default out of range`);
      }
    }
  }
  report.params = params;
  report.kinds = kinds;
  check('every parameter gets the control §6 names', bad.length === 0 && params > 300, bad.slice(0, 5).join('; '));
  // LOG: halfway along a 20 Hz-20 kHz slider is the geometric middle.
  const logp = { type: 'float', min: 20, max: 20000, step: 0.01, flags: ['log'] };
  check('the LOG law', Math.abs(M.fromPos(logp, 0.5) - Math.sqrt(20 * 20000)) < 1e-6 && M.isLog(logp));
  check('memory reads as the screen rounds it', M.ramPercent(300672, 387924) === 78 && M.ramWords(1000, 387924) === 'under 1 %' &&
    M.ramWords(0, 387924) === '0 %' && M.ramWords(387924, 387924) === '100 %');
}

// ---- the module: records, the feed, the view, the mirror, undo --------------------
const fm1 = await instantiateFm1(readFileSync(join(www, 'fm1.wasm')));
const ex = fm1.exports;
ex.fm1w_init(44100);
ex.fm1w_default_chain();
const dec = new TextDecoder();
const text = () => new Uint8Array(fm1.memory.buffer, ex.fm1w_text_buf(), ex.fm1w_text_cap());
let gen = 0;
function apply(recs, tag) {
  new Uint8Array(fm1.memory.buffer, ex.fm1w_edit_buf(), 64 * M.REC).set(M.concat(recs));
  const n = ex.fm1w_edit(recs.length, tag);
  const codes = Array.from(new Int8Array(fm1.memory.buffer, ex.fm1w_edit_codes(), recs.length));
  ex.fm1w_render(64);
  return { n, codes };
}
function changes() {
  const c = ex.fm1w_changes(gen, 256) >>> 0;
  if (c === 0xffffffff || c === 0) return [];
  const list = M.decodeChanges(new Uint8Array(fm1.memory.buffer, ex.fm1w_changes_buf(), c * M.CHANGE).slice());
  gen = list[list.length - 1].gen;
  return list;
}
function project() {
  const n = ex.fm1w_state_save(1, 0, 0);
  return JSON.parse(dec.decode(text().slice(0, n)));
}
const crcTable = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; ++k) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
function hash() {
  const n = ex.fm1w_state_save(1, 0, 2);
  const b = text().subarray(0, n);
  let c = 0xffffffff;
  for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

changes();
let mirror = M.mirrorFromProject(meta, project());
const s1 = mirror.blocks.get('s1');
check('the mirror holds the start chain', !!s1 && meta.engine(s1.engine) && mirror.blocks.has('m1'));
{
  // Every value of the mirror is the module's own (fm1w_get_param, unit 0).
  const e = meta.engine(s1.engine);
  let bad = [];
  e.params.forEach((p, i) => {
    if (p.hidden) return;
    const v = ex.fm1w_get_param(0, i);
    const m = s1.values.get(p.uid);
    if (Math.abs(v - m) > 1e-6 * Math.max(1, Math.abs(v))) bad.push(`${p.name} ${m} != ${v}`);
  });
  check('the mirror\'s values are C\'s', bad.length === 0, bad.slice(0, 4).join('; '));
}

// A float, an enum and a level, packed here, applied there, fed back.
const e1 = meta.engine(s1.engine);
const fl = e1.params.find((p) => p.type === 'float' && !p.hidden && !M.hasFlag(p, 'nolock'));
const en = e1.params.find((p) => p.type === 'enum' && !p.hidden && p.entries.length > 2);
const fv = M.toF32(fl.min + (fl.max - fl.min) * 0.3);
const r1 = apply([M.packParam({ role: M.ROLE.SOUND, sound: 0, uid: fl.uid, value: fv }),
  M.packParam({ role: M.ROLE.SOUND, sound: 0, uid: en.uid, index: 2 }), M.packLevel(0, 55)], 7);
const fed = changes();
check('records packed here are applied by C', r1.n === 3 && r1.codes.every((c) => c === 0), JSON.stringify(r1));
const byUid = new Map(fed.filter((c) => c.rec.type === M.T.PARAM).map((c) => [c.rec.uid, c]));
check('the feed carries them back with the editor\'s source and tag',
  byUid.get(fl.uid) && byUid.get(fl.uid).rec.value === fv && byUid.get(fl.uid).src === M.SRC_EDITOR && byUid.get(fl.uid).tag === 7 &&
  byUid.get(en.uid) && Math.round(byUid.get(en.uid).rec.value) === 2 &&
  fed.some((c) => c.rec.type === M.T.LEVEL && Math.abs(c.rec.value - 55) < 1e-6), JSON.stringify(fed.map((c) => c.rec)));
for (const c of fed) M.applyToMirror(meta, mirror, c.rec);
check('the feed keeps the mirror', mirror.blocks.get('s1').values.get(fl.uid) === fv && mirror.blocks.get('s1').values.get(en.uid) === 2 &&
  Math.abs(mirror.levels[0] - 55) < 1e-6);
check('a refusal names its words', apply([M.packParam({ role: M.ROLE.SOUND, sound: 0, uid: 0xfff0, value: 1 })], 8).codes[0] !== 0 &&
  meta.refusalWords(apply([M.packParam({ role: M.ROLE.SOUND, sound: 0, uid: 0xfff0, value: 1 })], 8).codes[0]).length > 2);
changes();

// The view: a verb opens a page; the view record names it back.
{
  const pages = meta.pages(s1.engine);
  const last = pages[pages.length - 1].page;
  const v = M.viewFor('s1', last);
  apply([M.packView(v.mode, v.keys)], 9);
  const view = M.decodeView(new Uint8Array(fm1.memory.buffer, ex.fm1w_view_get(), M.VIEW_BYTES).slice());
  const at = M.blockOfView(view);
  check('a view verb opens the page, and the view names it', at && at.key === 's1' && at.page === last, JSON.stringify(view));
  const k = view.knobs.filter((x) => x.kind === 1);
  check('the knob map names that page\'s parameters (K1-K4)',
    k.length > 0 && k.every((x) => pages[pages.length - 1].params.some((p) => p.uid === x.uid)), JSON.stringify(view.knobs));
  const vm = M.viewFor('m1', 1);
  apply([M.packView(vm.mode, vm.keys)], 10);
  const at2 = M.blockOfView(M.decodeView(new Uint8Array(fm1.memory.buffer, ex.fm1w_view_get(), M.VIEW_BYTES).slice()));
  check('a master slot opens on FX', at2 && at2.key === 'm1', JSON.stringify(at2));
}

// ---- the history: merging (§8) ----------------------------------------------------
{
  let t = 0;
  const h = new History({ now: () => t });
  h.beginDrag('a');
  for (let i = 1; i <= 20; ++i) { t += 16; h.record({ target: 'a', before: i - 1, after: i, origin: 'editor', how: 'drag' }); }
  h.endDrag();
  t += 100;
  h.record({ target: 'a', before: 20, after: 21, origin: 'editor', how: 'key' });
  t += 300;
  h.record({ target: 'a', before: 21, after: 22, origin: 'editor', how: 'key' });
  t += 900;
  h.record({ target: 'a', before: 22, after: 23, origin: 'editor', how: 'key' });
  t += 10;
  h.record({ target: 'a', before: 23, after: 24, origin: 'panel', how: 'knob' });
  t += 10;
  h.record({ target: 'b', before: 0, after: 1, origin: 'panel', how: 'knob' });
  check('a drag is one step; repeats within 600 ms merge; origins and targets never',
    h.entries.length === 5 && h.entries[0].before === 0 && h.entries[0].after === 20 && h.entries[1].after === 22,
    JSON.stringify(h.entries.map((e) => [e.target, e.before, e.after])));
  h.undo(); h.undo();
  h.record({ target: 'c', before: 0, after: 1, origin: 'editor', how: 'set' });
  check('a new edit clears redo', !h.canRedo && h.entries.length === 4);
  const big = new History({ limit: 200 });
  for (let i = 0; i < 260; ++i) big.record({ target: `t${i}`, before: 0, after: 1, origin: 'editor', how: 'set' });
  check('200 entries at most', big.entries.length === 200);
}

// ---- undo to the first hash, redo to the last (§17's undo test) -----------------------
{
  let seed = 12345;
  const rnd = () => { seed = (seed * 1103515245 + 12345) >>> 0; return seed / 4294967296; };
  changes();
  mirror = M.mirrorFromProject(meta, project());
  const first = hash();
  const h = new History({ now: () => 0 });
  const targets = [];
  for (const [key, b] of mirror.blocks) {
    if (M.parseBlockKey(key).role === M.ROLE.MFX) continue;
    for (const pg of meta.pages(b.engine)) for (const p of pg.params) if (!M.hasFlag(p, 'focus')) targets.push({ key, p });
  }
  const write = (key, p, v) => {
    const b = M.parseBlockKey(key);
    const rec = p.type === 'enum' ? M.packParam({ ...b, uid: p.uid, index: v }) : M.packParam({ ...b, uid: p.uid, value: v });
    return apply([rec], 20).codes[0];
  };
  let refused = 0;
  for (let i = 0; i < 120; ++i) {
    const { key, p } = targets[Math.floor(rnd() * targets.length)];
    const blk = mirror.blocks.get(key);
    const before = blk.values.get(p.uid);
    const after = p.type === 'enum' ? Math.floor(rnd() * p.entries.length) : M.toF32(M.fromPos(p, rnd()));
    if (write(key, p, after) !== 0) { ++refused; continue; }
    for (const c of changes()) M.applyToMirror(meta, mirror, c.rec);
    const now = blk.values.get(p.uid);
    h.record({ target: `${key}:${p.uid}`, before, after: now, origin: 'editor', how: 'typed', info: { key, p } });
  }
  const last = hash();
  let e;
  while ((e = h.undo())) { write(e.info.key, e.info.p, e.before); for (const c of changes()) M.applyToMirror(meta, mirror, c.rec); }
  const back = hash();
  while ((e = h.redo())) { write(e.info.key, e.info.p, e.after); for (const c of changes()) M.applyToMirror(meta, mirror, c.rec); }
  const again = hash();
  report.undo = { steps: h.entries.length, refused, first, last, back, again };
  check('undoing every step ends at the first hash', back === first && last !== first, JSON.stringify(report.undo));
  check('redoing every step ends at the last hash', again === last, JSON.stringify(report.undo));
}

// ---- stage ED3: structure, the rack, the matrix, structural undo ------------------------
{
  const C = await imp('editor/chains.js');
  const mm = new M.ModMeta(meta);
  const REC = M.REC;
  const stateHash = () => { const n = ex.fm1w_edit_dump(); return /hash ([0-9a-f]+)/.exec(dec.decode(text().slice(0, n)))[1]; };
  function applyAll(bytes) {
    const codes = [];
    for (let o = 0; o < bytes.length; o += 64 * REC) {
      const chunk = bytes.subarray(o, Math.min(bytes.length, o + 64 * REC));
      new Uint8Array(fm1.memory.buffer, ex.fm1w_edit_buf(), 64 * REC).set(chunk);
      ex.fm1w_edit(chunk.length / REC, 0);
      codes.push(...new Int8Array(fm1.memory.buffer, ex.fm1w_edit_codes(), chunk.length / REC));
    }
    ex.fm1w_render(64);
    return codes;
  }
  const hasRecords = typeof ex.fm1w_mod_records === 'function';
  const modBytes = () => { if (!hasRecords) return null; const n = ex.fm1w_mod_records(); return text().slice(0, n * REC + 2 * M.SLOTS); };
  const snap = () => M.mirrorFromProject(meta, project(), modBytes());
  changes();

  // Records and verbs in, the change feed and fm1w_mod_records out, decoded the same.
  const kinds = [...mm.kinds.keys()];
  const s1e = meta.engine(snap().blocks.get('s1').engine);
  const modP = s1e.params.find((p) => M.hasFlag(p, 'mod') && !M.hasFlag(p, 'nolock') && p.type === 'float');
  const nolockP = s1e.params.find((p) => M.hasFlag(p, 'nolock'));
  const cab = { src: M.moduleSource(7, 0), via: M.NONE, unit: mm.unitCode('s1'), flags: M.SLOT_ON | M.withPol(0, 2), dst: modP.uid,
    amount: M.q14OfPct(-37), offset: M.q14OfPct(12), uid: 0 };
  const r = applyAll(M.concat([M.packModule(7, kinds[1]), M.packCable(31, cab)]));
  const fed = changes();
  const fc = fed.find((c) => c.rec.type === M.T.CABLE && c.rec.slot === 31);
  const fm = fed.find((c) => c.rec.type === M.T.MODULE && c.rec.slot === 7);
  check('a module and a cable from the editor apply', r[0] === 0 && r[1] === 0, JSON.stringify(r));
  check('the feed carries them back, decoded as packed', !!fc && M.cableEqual(fc.rec.cable, cab) && !!fm && fm.rec.id === kinds[1],
    JSON.stringify({ fc: fc && fc.rec.cable, cab }));
  if (hasRecords) {
    const d = M.decodeMod(modBytes());
    check('fm1w_mod_records gives the rack and the matrix as C keeps them', d.rack[7] === kinds[1] && M.cableEqual(d.cables[31], cab) && d.verdicts[31] === 0,
      JSON.stringify({ rack: d.rack, c: d.cables[31], v: d.verdicts[31] }));
    if (nolockP) {
      const rr = applyAll(M.packCable(30, { ...cab, dst: nolockP.uid }));
      const d2 = M.decodeMod(modBytes());
      check('a cable the planner leaves out is written, with its reason as verdict', rr[0] >= 32 && d2.verdicts[30] === rr[0] && !M.cableEmpty(d2.cables[30]),
        JSON.stringify({ rr, v: d2.verdicts[30] }));
      applyAll(M.packCable(30, M.emptyCable()));
    }
    // A loop (the editor's v1 completion): LFO in rack 6 into LFO 7's Rate and back. The cable that runs up the rack
    // is read a tick late, and C names the loop it closes: both rack positions.
    const lfoRate = mm.kind('lfo').params.find((p) => p.name === 'Rate');
    const loopCab = (from, to) => ({ src: M.moduleSource(from, 0), via: M.NONE, unit: mm.unitCode(`p${to + 1}`), flags: M.SLOT_ON, dst: lfoRate.uid, amount: M.q14OfPct(20), offset: 0, uid: 0 });
    const rl = applyAll(M.concat([M.packModule(5, 'lfo'), M.packModule(6, 'lfo'), M.packCable(20, loopCab(5, 6)), M.packCable(21, loopCab(6, 5))]));
    const d3 = M.decodeMod(modBytes());
    check('fm1w_mod_records names the loop a late cable closes: the cable up the rack reads a tick late (both positions in the loop), the one down it runs on time',
      rl.every((c) => c === 0) && d3.loops[20] === 0 && d3.loops[21] === (1 << 5 | 1 << 6) && d3.verdicts[20] === 0 && d3.verdicts[21] === 0 && d3.loops.filter(Boolean).length === 1,
      JSON.stringify({ rl, loops: d3.loops.slice(18, 24), v: d3.verdicts.slice(18, 24) }));
    applyAll(M.concat([M.packCable(20, M.emptyCable()), M.packCable(21, M.emptyCable())]));
    check('with the loop broken no cable is late', M.decodeMod(modBytes()).loops.every((x) => x === 0), '');
    const doc = meta.doc;
    check('the metadata has the 1.2 and 1.3 members the editor reads: marks, source groups, curve points, refusal fixes, the id layout',
      doc.lunar === '1.3' && doc.marks.map((m) => m.mark).join('') === '>v~!-' && mm.groupedSources().length >= 7 && mm.curvePoints.length === mm.curves.length && mm.curvePoints.every((c) => c.length === 33) &&
      meta.refusals.get(38).fix.id === 'global' && meta.refusals.get(37).fix.id === 'global' && !meta.refusals.get(33).fix, JSON.stringify({ lunar: doc.lunar }));
  } else {
    report.ed3 = 'the module predates fm1w_mod_records';
  }
  check('the rack and the matrix name every source and destination from the metadata',
    mm.sourceName(cab.src, snap().rack).startsWith('8 ') && mm.unitKey(cab.unit) === 's1' && mm.unitKey(mm.unitCode('s2.in1')) === 's2.in1' &&
    mm.unitKey(mm.unitCode('m2')) === 'm2' && mm.unitKey(mm.unitCode('p3')) === 'p3', '');
  changes();

  // Refusals change nothing (§17).
  const h0 = stateHash();
  const bad = applyAll(M.concat([M.packVerb(M.T.SWAP, { role: M.ROLE.SOUND, sound: 0, slot: 0 }, { role: M.ROLE.INSERT, sound: 1, slot: 1 }),
    M.packModule(2, 'no-such-kind'), M.packCable(40, cab), M.packUnit(M.ROLE.INSERT, 0, 0, 'no-such-fx'),
    // an effect into an insert of a sound with no engine: no file could hold it
    M.packUnit(M.ROLE.INSERT, 3, 0, metaDoc.engines.find((e) => e.kind === 'audio_fx').id),
    M.packVerb(M.T.SWAP, { role: M.ROLE.MASTER, sound: 0, slot: 0 }, { role: M.ROLE.INSERT, sound: 3, slot: 1 })]));
  check('refused swaps, modules, slots and units leave the state as it was', bad.every((c) => c > 0 && c < 32) && stateHash() === h0,
    JSON.stringify({ bad, same: stateHash() === h0 }));
  // A swap twice is no swap.
  const sw = M.packVerb(M.T.SWAP, { role: M.ROLE.INSERT, sound: 0, slot: 0 }, { role: M.ROLE.MASTER, sound: 0, slot: 0 });
  applyAll(sw);
  const h1 = stateHash();
  applyAll(sw);
  check('a swap undoes by itself', h1 !== h0 && stateHash() === h0, '');

  // Structural undo: random choices, swaps and moves made through chains.js,
  // undone to the first state hash and redone to the last.
  let t = 0;
  const st = { mirror: snap(), live: null, keys: 'edit' };
  const h = new History({ now: () => (t += 5000) });
  let refusedOps = 0;
  const ctx = {
    st, meta, mm, history: h, files: {}, el: null, root: null,
    blockOf: (k) => st.mirror.blocks.get(k) || null,
    engineName: (id) => (meta.engine(id) ? meta.engine(id).name : id),
    sendOps: (bytes, info) => {
      const codes = applyAll(bytes);
      if (info && info.entry && codes.some((c) => c > 0 && c < 32)) { h.drop(info.entry); refusedOps += 1; }
      st.mirror = snap();
      return 1;
    },
    renderHistory() {}, say() {}, showRefusal() {},
  };
  const ch = C.makeChains(ctx);
  let seed = 7;
  const rnd = (n) => { seed = (seed * 1103515245 + 12345) >>> 0; return (seed >>> 8) % n; };
  const fx = [''].concat(metaDoc.engines.filter((e) => e.kind === 'audio_fx').map((e) => e.id));
  const snd = metaDoc.engines.filter((e) => e.kind === 'sound').map((e) => e.id);
  const mfx = metaDoc.engines.filter((e) => e.kind === 'midi_fx').map((e) => e.id);
  const effects = ch.effectKeys();
  const first = stateHash();
  const did = [];
  for (let i = 0; i < 28; ++i) {
    const k = rnd(6);
    if (k === 0) { const key = effects[rnd(effects.length)]; ch.choose(key, fx[rnd(fx.length)]); did.push(`fx ${key}`); }
    else if (k === 1) { const s = 1 + rnd(3); ch.choose(`s${s + 1}`, snd[rnd(snd.length)]); did.push(`engine s${s + 1}`); }
    else if (k === 2) { ch.choose(M.modKey(rnd(8)), rnd(4) ? kinds[rnd(kinds.length)] : ''); did.push('module'); }
    else if (k === 3) { const a = rnd(8), b = rnd(8); if (a !== b) { ch.moveTo(M.modKey(a), M.modKey(b)); did.push('move'); } }
    else if (k === 4) { const a = rnd(effects.length), b = rnd(effects.length); if (a !== b) { ch.moveTo(effects[a], effects[b]); did.push('swap'); } }
    else { ch.choose(`s${1 + rnd(4)}.mfx1`, mfx[rnd(mfx.length)]); did.push('midi'); }
  }
  const last = stateHash();
  const steps = h.entries.length;
  let e;
  while ((e = h.undo())) ch.undoStruct(e, false);
  const back = stateHash();
  while ((e = h.redo())) ch.undoStruct(e, true);
  const again = stateHash();
  report.structural = { steps, refused: refusedOps, first, last, back, again };
  check('undoing every structural step ends at the first state hash', steps >= 15 && last !== first && back === first, JSON.stringify(report.structural));
  check('redoing every structural step ends at the last', again === last, JSON.stringify(report.structural));
}

// ---- RAM by part ----------------------------------------------------------------------------
if (typeof ex.fm1w_ram_part === 'function') {
  const parts = [0, 1, 2, 3, 4, 5].map((k) => ex.fm1w_ram_part(k) >>> 0);
  const total = ex.fm1w_ram() >>> 0;
  report.ram = { total, parts };
  check('RAM by part adds up to the meter\'s figure', parts.reduce((a, b) => a + b, 0) === total && parts[0] > 0 && parts[4] > 0,
    JSON.stringify(report.ram));
} else {
  report.ram = 'the module predates fm1w_ram_part';
}

// ---- every unit is spoken as a word ---------------------------------------------------------------------
{
  const bad = [], seen = new Set();
  for (const e of [...metaDoc.engines, ...metaDoc.mod.kinds]) {
    for (const p of e.params || []) {
      if (p.type === 'enum' || p.unit === 'none') continue;
      const shown = `${M.rawText(p, p.def)} ${M.unitText(p)}`;
      const said = M.spokenText(p, shown);
      seen.add(p.unit);
      const word = M.unitWords(p);
      if (!word || !said.endsWith(word) && !said.endsWith(word.replace(/s$/, '')) || said.endsWith(` ${M.unitText(p)}`) && M.unitText(p) !== word) bad.push(`${e.id}.${p.name}: ${said}`);
    }
  }
  check('every unit in the metadata (semitones, hertz, milliseconds, decibels, percent) is spoken as a word, none as its symbol',
    bad.length === 0 && ['semi', 'hz', 'ms', 'db', 'pct'].every((u) => seen.has(u)), JSON.stringify({ bad: bad.slice(0, 4), seen: [...seen] }));
}

// ---- the id layout and the chain's shape are the metadata's (level 1.3) ------------------------------------
// The editor holds none of them: a metadata with another layout gives another editor, and an older one
// (without them) is refused rather than guessed at.
{
  const real = JSON.stringify([M.SOUNDS, M.INSERTS, M.MASTERS, M.POSITIONS, M.SLOTS, M.SRC_MODULE, M.SRC_STRIDE, M.UNIT_MODULE]);
  const want = JSON.stringify([metaDoc.mod.sounds, metaDoc.mod.inserts, metaDoc.mod.masters, metaDoc.mod.positions, metaDoc.mod.slots,
    metaDoc.mod.source_base, metaDoc.mod.source_stride, metaDoc.mod.unit_base]);
  check('the layout the editor uses is the metadata\'s', real === want && M.SRC_STRIDE > 0 && M.SOUNDS > 0, `${real} against ${want}`);
  // Another layout, not the FM-1's: three sounds with one insert, one master slot, five positions, 20 slots, outputs in fours from 96.
  const alt = JSON.parse(JSON.stringify(metaDoc));
  Object.assign(alt.mod, { source_base: 96, source_stride: 4, unit_base: 100, sounds: 3, inserts: 1, masters: 1, positions: 5, slots: 20 });   // outputs in fours from 96, rack units from 100
  alt.mod.units = alt.mod.units.filter((u) => /^(snd[1-3](\.fx1)?|fx1|host)$/.test(u.name));
  const m2 = new M.Meta(alt);
  const mm2 = new M.ModMeta(m2);
  const code = M.moduleSource(2, 3);
  const rack = ['lfo', 'env', 'lfo', 'env', 'lfo'];
  const k3 = mm2.kind('lfo');
  const alts = {
    code: code === 96 + 4 * 2 + 3 && M.sourcePosition(code) === 2 && M.sourcePort(code) === 3 && M.isModuleSource(96) && !M.isModuleSource(95) && !M.isModuleSource(M.NONE),
    names: mm2.sourceName(M.moduleSource(2, 0), rack).startsWith('3 ') && mm2.sourceList(rack).filter((x) => x.group === 'Modules').every((x) => M.isModuleSource(x.code) && M.sourcePort(x.code) < 4),
    units: mm2.unitKey(100 + 1) === 'p2' && mm2.unitCode('p5') === 100 + 4 && mm2.unitKey(100 + 5) === null && mm2.unitKey(17) === 's2' && mm2.unitKey(21) === null,
    keys: M.parseBlockKey('s4') === null && M.parseBlockKey('s3').sound === 2 && M.parseBlockKey('s1.in2') === null && M.parseBlockKey('m2') === null &&
      M.parseBlockKey('m1').role === M.ROLE.MASTER && M.parseBlockKey('p6') === null && M.parseBlockKey('p5').slot === 4,
    shape: mm2.positions === 5 && mm2.slots === 20 && M.mirrorFromProject(m2, {}, null).rack.length === 5 && M.mirrorFromProject(m2, {}, null).levels.length === 3,
  };
  check('another layout in the metadata moves every source code, unit code and key the editor builds (nothing is hard-coded)', Object.values(alts).every(Boolean), JSON.stringify({ alts, k3: !!k3 }));
  let refused = '';
  try { const old = JSON.parse(JSON.stringify(metaDoc)); delete old.mod.source_base; new M.Meta(old); } catch (e) { refused = e.message; }
  check('a metadata without the layout (older than 1.3) is refused with a clear message, not guessed at', /missing mod\.source_base/.test(refused), refused);
  new M.Meta(metaDoc);                    // back to the module's own layout
}

console.log(JSON.stringify(report, null, 1));
process.exit(report.failed ? 1 : 0);
