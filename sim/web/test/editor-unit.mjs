// editor-unit.mjs -- the web editor's data and history (stage ED2,
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
// adds up to the whole (when the module has fm1w_ram_part). Prints a JSON
// report; exits 1 on any failure. MIT licence, like the rest of this
// repository.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

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

console.log(JSON.stringify(report, null, 1));
process.exit(report.failed ? 1 : 0);
