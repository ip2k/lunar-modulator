// editor/model.js -- the web editor's data, with no DOM (stage ED2,
// notes/2026-10-06-web-editor.md §5, §6, §11): the packed records and the
// change feed of the edit layer (sim/web/src/fm1_edit.h), the panel's view,
// the metadata export (meta.json) and the controls it asks for, the LOG law
// and the detents, memory as a percentage of the FM-1's budget, and the
// editor's mirror of a project, built from C's canonical JSON.
//
// It names no engine, effect, kind or source: every id, uid, range, list
// and flag comes from the metadata or from C. The rules here are the
// metadata's (§6's table), the screen's rounding (draw_ram_meter) and the
// layout of fm1_edit.h's packed records. Node runs it as is
// (test/editor-unit.mjs). MIT licence, like the rest of this repository.

export const REC = 24;            // FM1_EDIT_REC_BYTES
export const CHANGE = 32;         // FM1_EDIT_CHANGE_BYTES
export const VIEW_BYTES = 40;     // FM1_EDIT_VIEW_BYTES

// fm1_state.h's record types and roles, fm1_edit.h's verbs and sources.
export const T = {
  UNIT: 4, ON: 5, PARAM: 6, LEVEL: 7, MODULE: 11, CABLE: 13,
  SWAP: 0x40, MOVE: 0x41, CURRENT: 0x42, VIEW: 0x43, LOADED: 0x50,
};
export const ROLE = { SOUND: 1, INSERT: 2, MASTER: 3, MFX: 4, MODULE: 5 };
export const SOURCES = ['host', 'panel', 'editor', 'load', 'seq'];
export const SRC_PANEL = 1;
export const SRC_EDITOR = 2;
export const FOCUS_NONE = 0xff;
export const VAL_F32 = 0;
export const VAL_INDEX = 1;
// The view's modes and keys (fm1_state.h's FM1_VIEW_*, FM1_VK_*).
export const MODES = ['home', 'fx', 'glo', 'seq', 'session', 'song', 'rack', 'matrix', 'chain'];
export const VK = { sound: 0, page: 1, unit: 2, track: 3, bar: 4, panel: 5, pos: 6, slot: 7, entry: 8 };
// FX mode's entries (fm1_edit_view's slot): In1, In2, Mix, M1, M2.
export const FX_ENTRIES = ['In1', 'In2', 'Mix', 'M1', 'M2'];
// The Mix's block (it has no unit): its key in the Flow.
export const MIX_KEY = 'the-mix';
export const SOUNDS = 4;
export const INSERTS = 2;
export const MASTERS = 2;
// The Mix page's level, in percent (FM1_APP_LEVEL_MAX): C clamps it.
export const LEVEL_MAX = 100;

const f32 = new Float32Array(1);
const u32 = new Uint32Array(f32.buffer);
export const toF32 = (v) => { f32[0] = v; return f32[0]; };

// ---- packed records (fm1_edit.h) --------------------------------------------

function blank(type, role = 0, sound = 0, slot = 0) {
  const b = new Uint8Array(REC);
  b[0] = type; b[1] = role; b[2] = sound; b[3] = slot;
  return b;
}

// A parameter: an ENUM's entry goes as its index, a float as float32 bits.
export function packParam({ role, sound = 0, slot = 0, uid, focus = FOCUS_NONE, index = null, value = 0 }) {
  const b = blank(T.PARAM, role, sound, slot);
  const dv = new DataView(b.buffer);
  dv.setUint16(4, uid, true);
  b[6] = focus;
  if (index !== null) {
    b[7] = VAL_INDEX;
    dv.setUint32(8, index >>> 0, true);
  } else {
    b[7] = VAL_F32;
    dv.setFloat32(8, value, true);
  }
  return b;
}

export function packLevel(sound, percent) {
  const b = blank(T.LEVEL, 0, sound, 0);
  new DataView(b.buffer).setFloat32(4, percent, true);
  return b;
}

export function packOn(sound, slot, on) {
  const b = blank(T.ON, ROLE.MFX, sound, slot);
  b[4] = on ? 1 : 0;
  return b;
}

// The view verb: `keys` by name, 1-based as a file's view.
export function packView(mode, keys = {}) {
  const b = blank(T.VIEW);
  const m = MODES.indexOf(mode);
  if (m < 0) throw new Error(`no such view mode: ${mode}`);
  b[4] = m;
  let has = 0;
  for (const [k, v] of Object.entries(keys)) {
    if (!(k in VK)) throw new Error(`no such view key: ${k}`);
    has |= 1 << VK[k];
    b[8 + VK[k]] = v;
  }
  new DataView(b.buffer).setUint16(6, has, true);
  return b;
}

export function concat(list) {
  const out = new Uint8Array(list.length * REC);
  list.forEach((b, i) => out.set(b, i * REC));
  return out;
}

// One packed record or verb back as an object.
export function unpack(bytes, off = 0) {
  const b = bytes.subarray(off, off + REC);
  const dv = new DataView(b.buffer, b.byteOffset, REC);
  const r = { type: b[0], role: b[1], sound: b[2], slot: b[3] };
  switch (b[0]) {
    case T.PARAM:
      r.uid = dv.getUint16(4, true);
      r.focus = b[6];
      r.vtype = b[7];
      r.value = b[7] === VAL_INDEX ? dv.getUint32(8, true) : dv.getFloat32(8, true);
      break;
    case T.LEVEL: r.value = dv.getFloat32(4, true); break;
    case T.ON: r.on = b[4] !== 0; break;
    case T.UNIT:
    case T.MODULE: {
      let end = 4;
      while (end < 20 && b[end]) ++end;
      r.id = new TextDecoder().decode(b.subarray(4, end));
      break;
    }
    case T.CABLE: r.cable = unpackCable(b, 0); break;
    case T.SWAP:
    case T.MOVE: r.to = { role: b[4], sound: b[5], slot: b[6] }; break;
    default: break;
  }
  return r;
}

// The change feed: {gen, src, tag, rec} per 32-byte entry.
export function decodeChanges(bytes) {
  const out = [];
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let off = 0; off + CHANGE <= bytes.length; off += CHANGE) {
    out.push({
      gen: dv.getUint32(off, true), src: bytes[off + 4], tag: dv.getUint16(off + 6, true),
      rec: unpack(bytes, off + 8),
    });
  }
  return out;
}

// The panel's view (fm1_edit_view_pack): what it shows and what each knob
// turns now (kind 0 nothing, 1 a parameter, 2 a sound's level).
export function decodeView(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const knobs = [];
  for (let k = 0; k < 4; ++k) {
    const o = 8 + 8 * k;
    knobs.push({ kind: bytes[o], role: bytes[o + 1], sound: bytes[o + 2], slot: bytes[o + 3], uid: dv.getUint16(o + 4, true) });
  }
  return { mode: MODES[bytes[0]] || 'home', sound: bytes[1], page: bytes[2], slot: bytes[3], arp: bytes[4] === 1, knobs };
}

// ---- blocks ------------------------------------------------------------------
// A block is one unit of the project: a sound's engine, one of its inserts or
// MIDI effects, or a master slot. Its key is stable text.

export function blockKey(role, sound = 0, slot = 0) {
  switch (role) {
    case ROLE.SOUND: return `s${sound + 1}`;
    case ROLE.INSERT: return `s${sound + 1}.in${slot + 1}`;
    case ROLE.MFX: return `s${sound + 1}.mfx${slot + 1}`;
    case ROLE.MASTER: return `m${slot + 1}`;
    case ROLE.MODULE: return `p${slot + 1}`;
    default: return `r${role}.${sound}.${slot}`;
  }
}

export function parseBlockKey(key) {
  let m = /^s([1-4])$/.exec(key);
  if (m) return { role: ROLE.SOUND, sound: m[1] - 1, slot: 0 };
  m = /^s([1-4])\.in([12])$/.exec(key);
  if (m) return { role: ROLE.INSERT, sound: m[1] - 1, slot: m[2] - 1 };
  m = /^s([1-4])\.mfx([1-4])$/.exec(key);
  if (m) return { role: ROLE.MFX, sound: m[1] - 1, slot: m[2] - 1 };
  m = /^m([12])$/.exec(key);
  if (m) return { role: ROLE.MASTER, sound: 0, slot: m[1] - 1 };
  m = /^p([1-8])$/.exec(key);
  if (m) return { role: ROLE.MODULE, sound: 0, slot: m[1] - 1 };
  return null;
}

// The short tag a block carries: S2, S2 In1, S2 MIDI 1, M1.
export function blockTag(key) {
  const b = parseBlockKey(key);
  if (!b) return key;
  if (b.role === ROLE.SOUND) return `S${b.sound + 1}`;
  if (b.role === ROLE.INSERT) return `S${b.sound + 1} In${b.slot + 1}`;
  if (b.role === ROLE.MFX) return `S${b.sound + 1} MIDI ${b.slot + 1}`;
  if (b.role === ROLE.MODULE) return `Rack ${b.slot + 1}`;
  return `M${b.slot + 1}`;
}

// The view verb that opens a block's page on the panel (follow, editor to
// panel). A MIDI effect's pages are HOME's entry 2 (stage ED4): the panel's
// ARP pages, as its ARP button opens them.
export function viewFor(key, page = 1) {
  const c = /^c([0-9]+)$/.exec(key);
  if (c) return { mode: 'matrix', keys: { slot: Number(c[1]) } };
  const b = parseBlockKey(key);
  if (!b) return null;
  if (b.role === ROLE.SOUND) return { mode: 'home', keys: { sound: b.sound + 1, page } };
  if (b.role === ROLE.INSERT) return { mode: 'fx', keys: { sound: b.sound + 1, entry: b.slot + 1, page } };
  if (b.role === ROLE.MASTER) return { mode: 'fx', keys: { entry: 4 + b.slot, page } };
  if (b.role === ROLE.MODULE) return { mode: 'rack', keys: { pos: b.slot + 1 } };
  return { mode: 'home', keys: { sound: b.sound + 1, entry: 2, page } };
}

// Where the panel is, as a block and a page (follow, panel to editor), or
// null when it shows something the editor has no block for in this stage.
export function blockOfView(v) {
  if (v.mode === 'home') {
    return { key: v.arp ? blockKey(ROLE.MFX, v.sound, 0) : blockKey(ROLE.SOUND, v.sound), page: v.arp ? null : v.page + 1 };
  }
  if (v.mode === 'fx') {
    if (v.slot < INSERTS) return { key: blockKey(ROLE.INSERT, v.sound, v.slot), page: v.page + 1 };
    if (v.slot === 2) return { key: MIX_KEY, page: null };
    if (v.slot <= 4) return { key: blockKey(ROLE.MASTER, 0, v.slot - 3), page: v.page + 1 };
  }
  if (v.mode === 'rack' && v.slot < 8) return { key: blockKey(ROLE.MODULE, 0, v.slot), page: v.page + 1 };
  if (v.mode === 'matrix' && v.slot < 32) return { key: `c${v.slot + 1}`, page: null };
  return null;
}

// The panel's view in words: "HOME · S2 · page 1".
export function viewWords(v) {
  if (!v) return '';
  const s = `S${v.sound + 1}`;
  switch (v.mode) {
    case 'home': return v.arp ? `ARP · ${s} · page ${v.page + 1}` : `HOME · ${s} · page ${v.page + 1}`;
    case 'fx': {
      const e = FX_ENTRIES[v.slot] || '';
      return v.slot < INSERTS ? `FX · ${s} ${e} · page ${v.page + 1}` : `FX · ${e}${v.slot > 2 ? ` · page ${v.page + 1}` : ''}`;
    }
    case 'rack': return `RACK · position ${v.slot + 1}`;
    case 'matrix': return `MATRIX · slot ${v.slot + 1}`;
    default: return `${v.mode.toUpperCase()} · ${s}`;
  }
}

// ---- the metadata ----------------------------------------------------------

export const UNIT_TEXT = { hz: 'Hz', ms: 'ms', db: 'dB', pct: '%', semi: 'st', none: '' };
const UNIT_WORDS = { hz: 'hertz', ms: 'milliseconds', db: 'decibels', pct: 'percent', semi: 'semitones', none: '' };
const FLAG_WORDS = {
  mod: 'takes modulation', poly: 'per voice', smooth: 'smooth', log: 'log scale',
  nolock: 'rebuilds the voices: sent on release', latch: 'every change reaches the next note',
  focus: 'chooses the pad', per_focus: 'per pad',
};

export class Meta {
  constructor(doc) {
    this.doc = doc;
    this.budget = doc.build && doc.build.ram_budget ? doc.build.ram_budget : 1;
    this.byId = new Map();
    for (const e of doc.engines || []) this.byId.set(e.id, e);
    // The rack's kinds share the lookups (their ids never meet an engine's).
    for (const k of (doc.mod && doc.mod.kinds) || []) if (!this.byId.has(k.id)) this.byId.set(k.id, { ...k, kind: 'mod' });
    this.groups = new Map((doc.effect_groups || []).map((g) => [g.id, g.name]));
    this.refusals = new Map(((doc.refusals && doc.refusals.codes) || []).map((r) => [r.code, r]));
    this.pagesCache = new Map();
  }

  engine(id) { return id ? this.byId.get(id) || null : null; }
  param(id, uid) {
    const e = this.engine(id);
    return e ? e.params.find((p) => p.uid === uid) || null : null;
  }
  paramByName(id, name) {
    const e = this.engine(id);
    return e ? e.params.find((p) => p.name === name) || null : null;
  }

  // The parameters the panel shows, by its pages, with the page's name (the
  // MIDI effects' PLAY ... SEED) or its number, and the knobs it uses.
  pages(id) {
    if (this.pagesCache.has(id)) return this.pagesCache.get(id);
    const e = this.engine(id);
    const out = [];
    if (e) {
      const by = new Map();
      for (const p of e.params) {
        if (p.hidden || !(p.page >= 1)) continue;
        if (!by.has(p.page)) by.set(p.page, []);
        by.get(p.page).push(p);
      }
      for (const page of [...by.keys()].sort((a, b) => a - b)) {
        const params = by.get(page).sort((a, b) => (a.knob || 0) - (b.knob || 0));
        const knobs = params.map((p) => p.knob).filter((k) => k >= 1);
        const lo = Math.min(...knobs), hi = Math.max(...knobs);
        const name = (e.page_names || [])[page - 1] || null;
        out.push({
          page, name, params,
          knobs: knobs.length ? (lo === hi ? `KNOB${lo}` : `KNOB${lo}–${hi}`) : '',
        });
      }
    }
    this.pagesCache.set(id, out);
    return out;
  }

  refusalWords(code) {
    const r = this.refusals.get(code);
    return r ? r.words : `refused (code ${code})`;
  }
  groupName(id) { return this.groups.get(id) || ''; }
}

// ---- controls (§6's table) ----------------------------------------------------

export function controlKind(p) {
  if (p.type === 'enum') {
    const n = (p.entries || []).length;
    if (n <= 4) return 'segments';
    if (n <= 8) return 'grid';
    if (n <= 24) return 'list';
    return 'search';
  }
  return 'slider';
}

export const isLog = (p) => (p.flags || []).includes('log') && p.min > 0 && p.max > p.min;
export const isBipolar = (p) => p.type === 'float' && p.min < 0 && p.max > 0;
export const hasFlag = (p, f) => (p.flags || []).includes(f);

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// A value's place on its slider, 0..1: the LOG law u = log2(v/min) /
// log2(max/min) for a LOG parameter, linear otherwise.
export function toPos(p, v) {
  if (p.type === 'enum') {
    const n = (p.entries || []).length;
    return n > 1 ? clamp(v, 0, n - 1) / (n - 1) : 0;
  }
  if (p.max === p.min) return 0;
  if (isLog(p)) return clamp(Math.log2(clamp(v, p.min, p.max) / p.min) / Math.log2(p.max / p.min), 0, 1);
  return clamp((v - p.min) / (p.max - p.min), 0, 1);
}

export function fromPos(p, u) {
  u = clamp(u, 0, 1);
  if (p.type === 'enum') return Math.round(u * Math.max(0, (p.entries || []).length - 1));
  if (isLog(p)) return clamp(p.min * Math.pow(p.max / p.min, u), p.min, p.max);
  return clamp(p.min + u * (p.max - p.min), p.min, p.max);
}

// The zero mark's place, for a bipolar slider.
export const zeroPos = (p) => (isBipolar(p) ? toPos(p, 0) : 0);

// One detent of the panel's knob (the metadata's `step`: an entry, a part
// of a linear range, or 0.01 of a LOG parameter's position), times `mult`
// (⇧ ten, ⌥ a tenth). A float lands on the nearest whole step from min, as
// the knob's; LOG moves its position.
export function stepValue(p, v, dir, mult = 1) {
  if (p.type === 'enum') return clamp(Math.round(v) + dir * Math.max(1, Math.round(mult)), 0, (p.entries || []).length - 1);
  const step = p.step > 0 ? p.step : (p.max - p.min) / 100;
  if (isLog(p)) return fromPos(p, toPos(p, v) + dir * step * mult);
  const d = step * mult;
  const n = Math.round((v - p.min) / d) + dir;
  return clamp(p.min + n * d, p.min, p.max);
}

// What a value reads as before C's text arrives: the raw number.
export function rawText(p, v) {
  if (p.type === 'enum') return (p.entries || [])[Math.round(v)] ?? String(v);
  if (!Number.isFinite(v)) return '–';
  const a = Math.abs(v);
  return a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toFixed(2);
}

export function unitText(p) { return UNIT_TEXT[p.unit] ?? ''; }
export function unitWords(p) { return UNIT_WORDS[p.unit] ?? ''; }
export function flagWords(p) {
  return (p.flags || []).filter((f) => FLAG_WORDS[f]).map((f) => FLAG_WORDS[f]);
}

// The default, as a mirror value (an ENUM's entry index).
export function defaultValue(p) { return p.def; }

// ---- memory, in percent of the FM-1's budget (§11, §19) ------------------------

// Rounded up, as the screen's meter rounds (fm1_app_ram_percent).
export function ramPercent(bytes, budget) {
  return Math.floor((bytes * 100 + budget - 1) / budget);
}

export function ramWords(bytes, budget) {
  if (!(bytes > 0)) return '0 %';
  if (bytes * 100 < budget) return 'under 1 %';
  return `${ramPercent(bytes, budget)} %`;
}

// ---- the mirror -------------------------------------------------------------
// The editor's copy of the records it draws: each block's engine and values
// (by uid; an ENUM's as its entry index), each sound's level and its MIDI
// effects' on. Built from C's canonical JSON of the project (the shadow
// Worker's), then kept by the change feed.

function valueOf(p, v) {
  if (p.type === 'enum') {
    const entries = p.entries || [];
    const i = entries.indexOf(String(v));
    if (i >= 0) return i;
    const n = Number(v);
    return Number.isInteger(n) && n >= 0 && n < entries.length ? n : p.def;
  }
  const n = Number(v);
  return Number.isFinite(n) ? toF32(n) : p.def;
}

function blockFrom(meta, unit, pad) {
  if (!unit || !unit.engine) return null;
  const e = meta.engine(unit.engine);
  const values = new Map();
  if (e) {
    const params = unit.params || {};
    for (const p of e.params) {
      if (hasFlag(p, 'per_focus') && pad && p.name in pad) values.set(p.uid, valueOf(p, pad[p.name]));
      else if (p.name in params) values.set(p.uid, valueOf(p, params[p.name]));
      else values.set(p.uid, p.def);
    }
  }
  return { engine: unit.engine, values, on: unit.on !== false };
}

export function mirrorFromProject(meta, doc, modBytes) {
  const m = { current: 0, blocks: new Map(), levels: [0, 0, 0, 0], title: doc.title || doc.name || '',
    rack: new Array(8).fill(''), cables: [], verdicts: [], loops: [], pads: new Map() };
  m.current = doc.session && Number.isInteger(doc.session.current) ? doc.session.current - 1 : 0;
  (doc.sounds || []).slice(0, SOUNDS).forEach((s, k) => {
    if (!s) return;
    // A kit's per-pad values are the focused pad's (the focus parameter).
    const e = meta.engine(s.engine);
    let pad = null;
    if (e && Array.isArray(s.pads)) {
      const fp = e.params.find((p) => hasFlag(p, 'focus'));
      const fi = fp ? valueOf(fp, (s.params || {})[fp.name]) : 0;
      pad = s.pads[fi] || null;
    }
    const b = blockFrom(meta, s, pad);
    if (b) m.blocks.set(blockKey(ROLE.SOUND, k), b);
    // Every pad's own values, for undo (API v4: a kit's per-pad parameters).
    if (b && pad && e) {
      const per = e.params.filter((p) => hasFlag(p, 'per_focus'));
      b.pads = s.pads.map((pd) => new Map(per.map((p) => [p.uid, pd && p.name in pd ? valueOf(p, pd[p.name]) : p.def])));
    }
    m.levels[k] = Number(s.level) || 0;
    (s.inserts || []).slice(0, INSERTS).forEach((u, j) => {
      const ib = blockFrom(meta, u, null);
      if (ib) m.blocks.set(blockKey(ROLE.INSERT, k, j), ib);
    });
    (s.midi_fx || []).forEach((u, j) => {
      const mb = blockFrom(meta, u, null);
      if (mb) m.blocks.set(blockKey(ROLE.MFX, k, j), mb);
    });
  });
  (doc.master || []).slice(0, MASTERS).forEach((u, j) => {
    const b = blockFrom(meta, u, null);
    if (b) m.blocks.set(blockKey(ROLE.MASTER, 0, j), b);
  });
  // The rack (its parameters by name, as an engine's) and the matrix (C's
  // packed slots, fm1w_mod_records).
  for (const r of (doc.mod && doc.mod.rack) || []) {
    const b = blockFrom(meta, { engine: r.kind, params: r.params }, null);
    if (b && r.pos >= 1 && r.pos <= 8) m.blocks.set(blockKey(ROLE.MODULE, 0, r.pos - 1), b);
  }
  if (modBytes && modBytes.length >= (POSITIONS + SLOTS) * REC + SLOTS) {   // an older module's 32 bytes: no loops
    const d = decodeMod(modBytes);
    m.rack = d.rack;
    m.cables = d.cables;
    m.verdicts = d.verdicts;
    m.loops = d.loops;
  } else {
    m.cables = Array.from({ length: SLOTS }, emptyCable);
    m.verdicts = new Array(SLOTS).fill(0);
    m.loops = new Array(SLOTS).fill(0);
  }
  return m;
}

// One change-feed record into the mirror. Returns what it touched
// ({key, uid, before, after}), 'structure' when the editor must take a new
// snapshot (a unit, a module, a cable, a swap, a load), or null.
export function applyToMirror(meta, m, rec) {
  switch (rec.type) {
    case T.PARAM: {
      const key = blockKey(rec.role, rec.sound, rec.slot);
      const b = m.blocks.get(key);
      if (!b) return rec.role === ROLE.MODULE ? null : 'structure';
      const p = meta.param(b.engine, rec.uid);
      if (!p) return null;
      const before = b.values.has(rec.uid) ? b.values.get(rec.uid) : p.def;
      const after = rec.vtype === VAL_INDEX ? rec.value : (p.type === 'enum' ? Math.round(rec.value) : rec.value);
      b.values.set(rec.uid, after);
      return { key, uid: rec.uid, before, after };
    }
    case T.LEVEL: {
      const before = m.levels[rec.sound];
      m.levels[rec.sound] = rec.value;
      return { key: blockKey(ROLE.SOUND, rec.sound), uid: 'level', before, after: rec.value };
    }
    case T.ON: {
      const key = blockKey(ROLE.MFX, rec.sound, rec.slot);
      const b = m.blocks.get(key);
      if (!b) return 'structure';
      const before = b.on;
      b.on = rec.on;
      return { key, uid: 'on', before, after: rec.on };
    }
    case T.CURRENT:
      m.current = rec.sound;
      return null;
    case T.CABLE: {
      if (!m.cables || rec.slot >= m.cables.length) return 'structure';
      const before = m.cables[rec.slot];
      const after = rec.cable;
      m.cables[rec.slot] = after;
      return { key: `c${rec.slot + 1}`, uid: 'all', before: JSON.stringify(before), after: JSON.stringify(after), cable: rec.slot, was: before, now: after };
    }
    case T.VIEW:
      return null;
    default:
      return 'structure';
  }
}

// ---- chains and modulation (stage ED3, §5, §10) --------------------------------
// The records and verbs that change structure, the rack and the matrix as
// C packs them (fm1w_mod_records), and their names from the metadata. The
// cable's fields are fm1_mod.h's slot layout (fm1_mod_slot_t); which cable
// may run, and why not, is C's (the planner's verdicts).

export const POSITIONS = 8;           // FM1_MOD_POSITIONS (the metadata's mod.positions)
export const SLOTS = 32;              // FM1_MOD_SLOTS (mod.slots)
export const NONE = 0xff;             // FM1_MOD_NONE: no source, no VIA
export const ANY = 0xff;              // FM1_EDIT_ANY: the first empty slot or position
// fm1_mod_slot_t's flags and codes (fm1_mod.h).
export const SLOT_ON = 0x01, POL_MASK = 0x06, POL_SHIFT = 1, GATE_DST = 0x08, CURVE_MASK = 0x70, CURVE_SHIFT = 4, VOICE = 0x80;
export const SRC_MODULE = 64;         // 64 + 8 x position + port
export const UNIT_MODULE = 8;         // 8 + position: a module's parameters or gates
export const Q14 = 16384;             // amount and offset: Q1.14 of the destination's range

export function packUnit(role, sound, slot, id) {
  const b = blank(T.UNIT, role, sound, slot);
  b.set(new TextEncoder().encode(String(id || '')).subarray(0, 15), 4);
  return b;
}
export function packModule(pos, id) {
  const b = blank(T.MODULE, ROLE.MODULE, 0, pos);
  b.set(new TextEncoder().encode(String(id || '')).subarray(0, 15), 4);
  return b;
}
// A matrix slot: s as unpack gives it ({src, via, unit, flags, dst, amount, offset, uid}).
export function packCable(slot, s) {
  const b = blank(T.CABLE, 0, 0, slot);
  const dv = new DataView(b.buffer);
  b[4] = s.src; b[5] = s.via; b[6] = s.unit; b[7] = s.flags;
  dv.setUint16(8, s.dst, true);
  dv.setInt16(10, s.amount, true);
  dv.setInt16(12, s.offset, true);
  dv.setUint16(14, s.uid || 0, true);
  return b;
}
// swap and move: two blocks ({role, sound, slot}).
export function packVerb(type, a, b2) {
  const b = blank(type, a.role, a.sound, a.slot);
  b[4] = b2.role; b[5] = b2.sound; b[6] = b2.slot;
  return b;
}
export function packCurrent(sound) { return blank(T.CURRENT, 0, sound, 0); }

export function unpackCable(bytes, off = 0) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset + off, REC);
  return { src: bytes[off + 4], via: bytes[off + 5], unit: bytes[off + 6], flags: bytes[off + 7],
    dst: dv.getUint16(8, true), amount: dv.getInt16(10, true), offset: dv.getInt16(12, true), uid: dv.getUint16(14, true) };
}
export const emptyCable = () => ({ src: 0, via: NONE, unit: 0, flags: 0, dst: 0, amount: 0, offset: 0, uid: 0 });
export const cableEqual = (a, b) => a.src === b.src && a.via === b.via && a.unit === b.unit && a.flags === b.flags &&
  a.dst === b.dst && a.amount === b.amount && a.offset === b.offset && a.uid === b.uid;
// A slot the panel shows as empty: nothing aimed and off (fm1_mod_ui_empty's sense).
export const cableEmpty = (s) => !(s.flags & SLOT_ON) && s.dst === 0 && s.amount === 0 && s.src === 0 && s.unit === 0;
export const pctOfQ14 = (q) => (q >= 0 ? Math.floor((q * 100 + 8192) / Q14) : -Math.floor((-q * 100 + 8192) / Q14));
export const q14OfPct = (p) => Math.max(-Q14, Math.min(Q14, Math.round((p / 100) * Q14)));

// The module keys: p1 ... p8, a rack position's block.
export const modKey = (pos) => `p${pos + 1}`;
export function parseModKey(key) {
  const m = /^p([1-8])$/.exec(key);
  return m ? m[1] - 1 : -1;
}

// What fm1w_mod_records writes: the rack (kind ids), the slots, a verdict a
// slot, and a loop mask a slot (the rack positions of the loop a cable read a
// tick late closes, as a bit mask; 0 for a cable that is not late).
export function decodeMod(bytes) {
  const rack = [], cables = [], verdicts = [], loops = [];
  for (let i = 0; i < POSITIONS; ++i) rack.push(unpack(bytes, i * REC).id || '');
  for (let i = 0; i < SLOTS; ++i) cables.push(unpackCable(bytes, (POSITIONS + i) * REC));
  for (let i = 0; i < SLOTS; ++i) verdicts.push(bytes[(POSITIONS + SLOTS) * REC + i] || 0);
  for (let i = 0; i < SLOTS; ++i) loops.push(bytes[(POSITIONS + SLOTS) * REC + SLOTS + i] || 0);
  return { rack, cables, verdicts, loops };
}

// The rack and matrix of the metadata: kinds, sources, units, curves.
export class ModMeta {
  constructor(meta) {
    const m = meta.doc.mod || {};
    this.meta = meta;
    this.kinds = new Map((m.kinds || []).map((k) => [k.id, k]));
    this.sources = new Map((m.sources || []).map((s) => [s.id, s]));
    this.units = new Map((m.units || []).map((u) => [u.code, u.name]));
    this.host = m.host || [];
    this.polarities = m.polarities || [];
    this.curves = m.curves || [];
    this.positions = m.positions || POSITIONS;
    this.slots = m.slots || SLOTS;
  }
  kind(id) { return this.kinds.get(id) || null; }
  // A unit code's block key in the editor (a sound, an insert, a master
  // slot), 'host', a module's key, or null; by the metadata's unit names.
  unitKey(code) {
    if (code >= UNIT_MODULE && code < UNIT_MODULE + this.positions) return modKey(code - UNIT_MODULE);
    const name = this.units.get(code);
    if (!name) return null;
    if (name === 'host') return 'host';
    let r = /^snd([1-4])$/.exec(name);
    if (r) return blockKey(ROLE.SOUND, r[1] - 1);
    r = /^snd([1-4])\.fx([1-4])$/.exec(name);
    if (r) return blockKey(ROLE.INSERT, r[1] - 1, r[2] - 1);
    r = /^fx([1-4])$/.exec(name);
    if (r) return blockKey(ROLE.MASTER, 0, r[1] - 1);
    return null;
  }
  unitCode(key) {
    const pos = parseModKey(key);
    if (pos >= 0) return UNIT_MODULE + pos;
    for (const [code, name] of this.units) if (this.unitKey(code) === key && name !== 'snd') return code;
    return -1;
  }
  // A source code's name: a fixed source by the metadata, or a module's
  // output ("2 Env Out"); `rack` is the kind id at each position.
  sourceName(code, rack) {
    if (code === NONE) return '–';
    if (code < SRC_MODULE) { const s = this.sources.get(code); return s ? s.name : `#${code}`; }
    const pos = (code - SRC_MODULE) >> 3, port = (code - SRC_MODULE) & 7;
    const k = this.kind(rack[pos]);
    const out = k && k.outs ? k.outs[port] : null;
    return `${pos + 1} ${k ? k.abbr : 'empty'} ${out ? out.name : `out ${port + 1}`}`;
  }
  // Every source a cable can start from now: the fixed ones, then each
  // module's outputs. {code, name, kind (cv_uni, cv_bi, gate), group}.
  sourceList(rack) {
    const out = [];
    for (const s of this.sources.values()) out.push({ code: s.id, name: s.name, kind: s.kind, group: 'Sources' });
    rack.forEach((id, pos) => {
      const k = this.kind(id);
      (k && k.outs ? k.outs : []).forEach((o, port) => out.push({ code: SRC_MODULE + 8 * pos + port,
        name: `${pos + 1} ${k.abbr} ${o.name}`, kind: o.kind, group: 'Modules' }));
    });
    return out;
  }
  // A cable's polarity, curve and the rest, from its flags.
  pol(s) { return this.polarities[(s.flags & POL_MASK) >> POL_SHIFT] || ''; }
  curve(s) { return this.curves[(s.flags & CURVE_MASK) >> CURVE_SHIFT] || ''; }
}
export const withPol = (flags, i) => (flags & ~POL_MASK) | ((i << POL_SHIFT) & POL_MASK);
export const withCurve = (flags, i) => (flags & ~CURVE_MASK) | ((i << CURVE_SHIFT) & CURVE_MASK);
export const withBit = (flags, bit, on) => (on ? flags | bit : flags & ~bit);
