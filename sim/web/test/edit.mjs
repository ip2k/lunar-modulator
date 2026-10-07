// edit.mjs -- the edit layer (sim/web/src/fm1_edit.h, stage ED1) in the
// browser's module, against the native harness, and its cost on the audio
// thread:
//
//   node edit.mjs --wasm fm1.wasm --sim fm1-sim-render --script edit/verbs.edit \
//        --work DIR [--storm SECONDS] [--summary out.json]
//
// Parity. fm1-sim-render --edit-run plays the script natively; this plays it
// to the module the way the worklet does (each `edit` line packed by
// fm1w_edit_text into the edit buffer, then fm1w_edit, the worklet's call;
// panel gestures through fm1w_button and fm1w_encoder; 64-frame blocks). The
// verdicts, the change ring (gens, sources, tags, records), the view with its
// knob map and the state's hash must be identical, the screens too, and the
// audio within one 16-bit step (a native build's libm is not Emscripten's).
//
// The storm (§12, §17): SECONDS of audio rendered as the worklet renders it,
// 128-frame quanta of two blocks, with the demo song playing, eight editor
// records every quantum (knobs, levels, a cable), the change feed drained
// every sixth quantum and telemetry filled whenever it is due, every row
// subscribed. Each quantum's time is measured; one that takes longer than it
// plays (2.90 ms at 44,118 Hz) is counted late: it would underrun a real-time
// audio thread. Node runs V8, as Chromium's worklet does; Firefox and WebKit
// are not measured here.
// MIT licence, like the rest of this repository.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { performance } from 'node:perf_hooks';
import { instantiateFm1, BUTTONS, ENCODERS } from '../www/fm1-wasm.mjs';

const args = {};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
const RATE = 44118;
const BLOCK = 64;
const REC = 24;
const fails = [];
const check = (ok, what) => { if (!ok) fails.push(what); };

const fm1 = await instantiateFm1(readFileSync(args.wasm));
const ex = fm1.exports;
const text = () => new Uint8Array(fm1.memory.buffer, ex.fm1w_text_buf(), ex.fm1w_text_cap());
const putText = (s) => { const b = new TextEncoder().encode(s); text().set(b); return b.length; };

// ---- parity ----
const work = args.work;
mkdirSync(join(work, 'native'), { recursive: true });
execFileSync(args.sim, ['--edit-run', args.script, join(work, 'native')], { timeout: 120000 });
const native = {
  log: readFileSync(join(work, 'native', 'edit.txt'), 'utf8'),
  screen: readFileSync(join(work, 'native', 'screen.raw')),
  audio: new Float32Array(new Uint8Array(readFileSync(join(work, 'native', 'audio.f32'))).buffer),
};

ex.fm1w_init(RATE);
ex.fm1w_default_chain();
let log = '';
let block = 0;
let tag = 0;
let total = 0;
const audio = [];
const renderTo = (at) => {
  for (; block < at && block < 4096; ++block) {
    const out = new Float32Array(fm1.memory.buffer, ex.fm1w_render(BLOCK), 2 * BLOCK);
    audio.push(Float32Array.from(out));
  }
};
for (const raw of readFileSync(args.script, 'utf8').split('\n')) {
  const line = raw.replace(/\r$/, '');
  if (!line || line.startsWith('#')) continue;
  const m = /^@(\d+) (\S+) ?(.*)$/.exec(line);
  if (!m) continue;
  const [, at, verb, rest] = m;
  if (verb === 'end') { total = Number(at); break; }
  renderTo(Number(at));
  log += `B${block} ${line} ->`;
  if (verb === 'edit') {
    let code = -1;
    if (ex.fm1w_edit_text(putText(rest)) === 1) {
      ex.fm1w_edit(1, ++tag);
      code = new Int8Array(fm1.memory.buffer, ex.fm1w_edit_codes(), 1)[0];
    }
    log += ` ${code}\n`;
  } else {
    const [name, x] = rest.split(' ');
    if (verb === 'button') ex.fm1w_button(BUTTONS.indexOf(name === 'PLAY' ? 'PLAY/STOP' : name), Number(x));
    else if (verb === 'turn') ex.fm1w_encoder(ENCODERS.indexOf(name), Number(x));
    else if (verb === 'note') ex.fm1w_note_on(Number(name), Number(x));
    else if (verb === 'off') ex.fm1w_note_off(Number(name));
    log += ' .\n';
  }
}
renderTo(total);
const n = ex.fm1w_edit_dump();
log += new TextDecoder().decode(text().slice(0, n));
ex.fm1w_draw(0);
const screen = Buffer.from(new Uint8Array(fm1.memory.buffer, ex.fm1w_screen(), 240 * 240 * 2));
writeFileSync(join(work, 'wasm-edit.txt'), log);
check(log === native.log, 'the verdicts, the ring, the view and the hash match the native harness');
check(screen.equals(native.screen), 'the screen matches the native harness');
let maxDiff = 0;
const flat = new Float32Array(audio.length * 2 * BLOCK);
audio.forEach((b, i) => flat.set(b, i * 2 * BLOCK));
check(flat.length === native.audio.length, 'as much audio as the native harness');
for (let i = 0; i < Math.min(flat.length, native.audio.length); ++i) {
  const d = Math.abs(Math.round(flat[i] * 32767) - Math.round(native.audio[i] * 32767));
  if (d > maxDiff) maxDiff = d;
}
check(maxDiff <= 1, `the audio within one 16-bit step of the native harness (max ${maxDiff})`);
check(fm1.calls.length === 0, 'no import calls');

// ---- the storm ----
const seconds = Number(args.storm || 0);
let storm = null;
if (seconds > 0) {
  ex.fm1w_init(RATE);
  ex.fm1w_default_chain();
  ex.fm1w_button(BUTTONS.indexOf('PLAY/STOP'), 1);
  ex.fm1w_button(BUTTONS.indexOf('PLAY/STOP'), 0);
  // The records, packed once by C (as the editor will pack them).
  const ops = [];
  const pack = (line) => {
    check(ex.fm1w_edit_text(putText(line)) === 1, `packs: ${line}`);
    return new Uint8Array(fm1.memory.buffer, ex.fm1w_edit_buf(), REC).slice();
  };
  for (let k = 0; k < 64; ++k) {
    ops.push(pack(`param sound 0 0 ${2 + (k % 3)} ${(k % 17) / 17}`));
    ops.push(pack(`level ${k % 4} ${40 + (k % 50)}`));
    ops.push(pack(`cable 3 64 255 0 1 2 ${(k * 997) % 16000 - 8000} 0`));
    ops.push(pack(`param module 0 0 1 ${(k % 11) / 11}`));
  }
  const mask = new Uint32Array(fm1.memory.buffer, ex.fm1w_tele_mask(), 4);
  mask.set([0xffffffff, 0xffffffff, 0xffffffff, 0x7fffff]);
  ex.fm1w_subscribe();
  const quanta = Math.ceil((seconds * RATE) / 128);
  const deadline = (1000 * 128) / RATE;
  const times = new Float64Array(quanta);
  let late = 0;
  let editMs = 0;
  let gen = ex.fm1w_edit_gen();
  let fills = 0;
  let resyncs = 0;
  let applied = 0;
  const buf = new Uint8Array(fm1.memory.buffer, ex.fm1w_edit_buf(), 64 * REC);
  for (let q = 0; q < quanta; ++q) {
    const t0 = performance.now();
    for (let k = 0; k < 8; ++k) buf.set(ops[(q * 8 + k) % ops.length], k * REC);
    applied += ex.fm1w_edit(8, q & 0xffff);
    const t1 = performance.now();
    ex.fm1w_render(BLOCK);
    ex.fm1w_render(BLOCK);
    const t2 = performance.now();
    if (q % 6 === 0) {
      const c = ex.fm1w_changes(gen, 256) >>> 0;
      if (c === 0xffffffff) { ++resyncs; gen = ex.fm1w_edit_gen() >>> 0; }
      else if (c > 0) gen = new DataView(fm1.memory.buffer, ex.fm1w_changes_buf() + (c - 1) * 32, 4).getUint32(0, true);
      ex.fm1w_view_get();
    }
    if (ex.fm1w_telemetry() > 0) ++fills;
    const t3 = performance.now();
    times[q] = t3 - t0;
    editMs += (t1 - t0) + (t3 - t2);
    if (t3 - t0 > deadline) ++late;
  }
  const sorted = Float64Array.from(times).sort();
  storm = {
    seconds, quanta, deadline_ms: deadline, late, applied, resyncs, telemetry_blocks: fills,
    p50_ms: sorted[Math.floor(quanta * 0.5)], p99_ms: sorted[Math.floor(quanta * 0.99)], max_ms: sorted[quanta - 1],
    edit_us_per_quantum: (1000 * editMs) / quanta,
  };
  check(applied === quanta * 8, 'every storm record applied');
  check(fills <= Math.ceil(seconds * 30) + 1 && fills >= Math.floor(seconds * 30) - 1, `telemetry at 30 a second (${fills})`);
}

const summary = { parity: fails.length === 0 ? 'ok' : 'failed', audio_max_lsb: maxDiff, storm, fails };
if (args.summary) writeFileSync(args.summary, JSON.stringify(summary, null, 1));
console.log(JSON.stringify(summary));
process.exit(fails.length ? 1 : 0);
