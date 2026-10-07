// shadow.worker.js -- the page's shadow Worker: a second fm1.wasm instance
// with no audio (notes/2026-10-06-state-files.md §10.1 and §12; the web
// editor's ED13). It does the work the audio thread must not: JSON in and
// out, pass 1 of a load, packing JSON into the binary container. Before each
// job it loads the live project (the worklet's binary save) into its own
// instance, so pass 1 judges a file against exactly what is playing: merges,
// free slots and the RAM rule (every instance at 44,118 Hz, ST6) included.
// The worklet then gets the packed file and nothing else.
//
// Requests are { id, op, ... }; each reply is { re: id, ok, ... }.
//   init    { wasm, rate }       the module's bytes and the AudioContext's rate
//   check   { bytes, kind, into, slot, flags, live }
//           pass 1 of `bytes` (a .lunar file, JSON or binary, or a .movy1 set)
//           against `live`; ok with { report, bin }: the file as the binary
//           container (a set as a SET container); or not ok with { report }
//   save    { kind, arg, live }   `live` as `kind` (fm1_state.h's codes) in
//           canonical JSON (a set as .movy1 text): { text }
//   pack    { text }             JSON to the binary container: { bin }
//   start   {}                   the start chain as a binary project: { bin }
// and, for the editor (stage ED1, notes/2026-10-06-web-editor.md §5, §6),
// everything it must not ask the audio thread for:
//   metaId  {}                   the module's metadata id: { id } (a whole
//                                export's work, so never in the worklet)
//   meta    {}                   the metadata export itself: { text }, when
//                                meta.json and the module disagree
//   format  { id, uid, values }  the screen's digits for each value of a
//                                module's parameter: { texts }
//   parse   { id, uid, text }    typed text back to a value (C's parser):
//                                { value } or ok false
//   hash    { bin }              a project's hash: loaded here and saved back
//                                canonical (binary, nothing deflated), CRC-32:
//                                { hash }, for undo's check
//   diff    { a, b, kind }       two projects' differences in `kind` (the
//                                project unless said), member by member of
//                                their canonical JSON: { changes }
// None of them names an engine: ids and uids come from the caller and the
// metadata, and C answers.

import { instantiateFm1 } from './fm1-wasm.mjs';

const QUIET = 4;           // FM1_APP_LOAD_QUIET
let fm1 = null;
let ex = null;
let rate = 0;
let ready = null;
const decoder = new TextDecoder();

function buf() { return new Uint8Array(fm1.memory.buffer, ex.fm1w_text_buf(), ex.fm1w_text_cap()); }
function put(bytes) {
  if (bytes.length > ex.fm1w_text_cap()) throw refusal('TOO_BIG', 'The file is larger than the 256 KiB the simulator reads.');
  buf().set(bytes);
  return bytes.length;
}
function report() { return JSON.parse(fm1.string(ex.fm1w_state_report())); }
function refusal(code, message) {
  const e = new Error(message);
  e.report = { code, message, screen: ['NOT LOADED', ''], percent: 0 };
  return e;
}

// The file's encoding, as fm1_state_sniff reads it: 1 binary, 2 JSON, 3 a
// .movy1 set, 0 anything else.
function sniff(b) {
  if (b.length >= 6 && b[0] === 0x89 && decoder.decode(b.subarray(1, 6)) === 'Lunar') return 1;
  let i = 0;
  while (i < b.length && (b[i] === 0x20 || b[i] === 0x09 || b[i] === 0x0a || b[i] === 0x0d)) ++i;
  if (b[i] === 0x7b) return 2;
  if (decoder.decode(b.subarray(i, i + 5)) === 'movy1') return 3;
  return 0;
}

function mirror(live) {
  if (!live) return;
  const n = put(live);
  if (ex.fm1w_state_load(1, 0, 0, QUIET, n) !== 1) {
    throw refusal('BAD', `The live state could not be mirrored: ${report().message}`);
  }
}

function start() {
  ex.fm1w_init(rate);
  ex.fm1w_default_chain();
}

// A NUL-terminated id, and after it optionally a second string, into the
// text buffer.
function putIds(id, text) {
  const enc = new TextEncoder();
  const a = enc.encode(String(id)).subarray(0, 63);
  const b = text === undefined ? null : enc.encode(String(text)).subarray(0, 63);
  const t = buf();
  t.set(a);
  t[a.length] = 0;
  if (b) {
    t.set(b, a.length + 1);
    t[a.length + 1 + b.length] = 0;
  }
}

// A binary file's canonical JSON as an object (kind 1, the project, unless
// said): loaded quietly, saved back by C's writer.
function canonical(bin, kind) {
  mirror(bin);
  const n = ex.fm1w_state_save(kind || 1, 0, 0);
  if (n < 0) throw refusal('BAD', report().message);
  return JSON.parse(decoder.decode(buf().slice(0, n)));
}

// Where two canonical files differ: a path and both values per member,
// arrays item by item. Data, not rules: the C writer made both.
function differences(a, b, path, out) {
  if (out.length >= 2000) return out;
  const ta = a === null ? 'null' : Array.isArray(a) ? 'array' : typeof a;
  const tb = b === null ? 'null' : Array.isArray(b) ? 'array' : typeof b;
  if (ta !== tb || (ta !== 'object' && ta !== 'array')) {
    if (ta !== tb || a !== b) out.push({ path, a, b });
    return out;
  }
  const keys = ta === 'array' ? [...Array(Math.max(a.length, b.length)).keys()]
    : [...new Set([...Object.keys(a), ...Object.keys(b)])];
  for (const k of keys) {
    const p = ta === 'array' ? `${path}[${k}]` : (path ? `${path}.${k}` : String(k));
    if (!(k in a)) out.push({ path: p, a: undefined, b: b[k] });
    else if (!(k in b)) out.push({ path: p, a: a[k], b: undefined });
    else differences(a[k], b[k], p, out);
  }
  return out;
}

function crc32(bytes) {
  let c = ~0;
  for (let i = 0; i < bytes.length; ++i) {
    c ^= bytes[i];
    for (let k = 0; k < 8; ++k) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return ~c >>> 0;
}

const ops = {
  async init(m) {
    if (!fm1) {
      fm1 = await instantiateFm1(m.wasm);
      ex = fm1.exports;
    }
    rate = m.rate;
    start();
    return {};
  },
  check(m) {
    mirror(m.live);
    const bytes = m.bytes;
    const enc = sniff(bytes);
    let n = put(bytes);
    const ok = ex.fm1w_state_check(m.kind | 0, m.into | 0, m.slot | 0, m.flags | 0, n) === 1;
    const rep = report();
    if (!ok) return { ok: false, report: rep };
    let bin;
    if (enc === 1) {
      bin = bytes;
    } else if (enc === 2) {
      n = put(bytes);
      const len = ex.fm1w_state_pack(n);
      if (len < 0) return { ok: false, report: report() };
      bin = buf().slice(0, len);
    } else {
      // A .movy1 set: loaded here (with its start rule), saved as a SET
      // container, which the worklet loads as it stands.
      n = put(bytes);
      if (ex.fm1w_state_load(m.kind | 0, m.into | 0, m.slot | 0, (m.flags | 0) | QUIET, n) !== 1) {
        return { ok: false, report: report() };
      }
      const len = ex.fm1w_state_save(7, 0, 1);
      if (len < 0) return { ok: false, report: report() };
      bin = buf().slice(0, len);
    }
    return { ok: true, report: rep, bin };
  },
  save(m) {
    mirror(m.live);
    const n = ex.fm1w_state_save(m.kind, m.arg | 0, 0);
    if (n < 0) return { ok: false, report: report() };
    return { text: decoder.decode(buf().slice(0, n)) };
  },
  pack(m) {
    const n = put(new TextEncoder().encode(m.text));
    const len = ex.fm1w_state_pack(n);
    if (len < 0) return { ok: false, report: report() };
    return { bin: buf().slice(0, len) };
  },
  start() {
    start();
    const n = ex.fm1w_state_save(1, 0, 1);
    if (n < 0) return { ok: false, report: report() };
    return { bin: buf().slice(0, n) };
  },
  metaId() {
    return { id: ex.fm1w_meta_id() >>> 0 };
  },
  meta() {
    const parts = [];
    for (let off = 0; ; ) {
      const n = ex.fm1w_meta_read(off);
      if (!n) break;
      parts.push(buf().slice(0, n));
      off += n;
    }
    return { text: parts.map((p) => decoder.decode(p)).join('') };
  },
  format(m) {
    const texts = [];
    for (const v of m.values || []) {
      putIds(m.id);
      const n = ex.fm1w_param_text(m.uid >>> 0, Number(v));
      texts.push(n ? decoder.decode(buf().slice(0, n)) : null);
    }
    return { texts };
  },
  parse(m) {
    putIds(m.id, m.text);
    if (ex.fm1w_param_parse(m.uid >>> 0) !== 1) return { ok: false };
    return { value: ex.fm1w_param_value() };
  },
  hash(m) {
    mirror(m.bin);
    const n = ex.fm1w_state_save(1, 0, 2);
    if (n < 0) return { ok: false, report: report() };
    return { hash: crc32(buf().subarray(0, n)) };
  },
  diff(m) {
    return { changes: differences(canonical(m.a, m.kind), canonical(m.b, m.kind), '', []) };
  },
};

self.onmessage = async (e) => {
  const m = e.data || {};
  const op = ops[m.op];
  let reply;
  try {
    if (!op) throw new Error(`no such operation: ${m.op}`);
    if (m.op !== 'init') await ready;
    const run = op(m);
    if (m.op === 'init') ready = run;
    reply = { ok: true, ...(await run) };
  } catch (err) {
    reply = { ok: false, error: String(err && err.message || err), report: err && err.report };
  }
  const transfer = reply.bin && reply.bin !== m.bytes ? [reply.bin.buffer] : [];
  self.postMessage({ re: m.id, ...reply }, transfer);
};
