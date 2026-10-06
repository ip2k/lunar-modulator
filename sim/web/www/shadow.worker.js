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
// MIT licence, like the rest of this repository.

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
