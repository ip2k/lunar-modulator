// sysex.mjs -- the browser module's "Load DX7 patches" export, checked in
// Node on the module itself (fm1w_dx7_load, fm1w_dx7_result, fm1w_dx7_name):
// what it loads, what it refuses and why, and that the voices it loads play
// as they should. Runs in the emscripten/emsdk container after the parity
// test (build.sh), never on the Mac:
//
//   node sysex.mjs --wasm build/wasm/fm1.wasm --dx7 test/dx7 [--summary out.json]
//
// --dx7 is the directory of the original test files tools/dx7_bank.py
// --test-bank writes: lunar-test-bank.syx (32 voices, LUNAR 01 to LUNAR 32,
// as one bank dump) and lunar-test-voices.syx (the same voices as 32
// single-voice dumps). Every other file here is made from those by editing
// bytes: a checksum, a length, a closing F7. None is Yamaha's.
//
// Cases: the bank and the singles load, with their names; a single voice
// goes to the slot after the last one, a bank to User 1-32; a bank's data
// without framing loads; a wrong checksum loads and is counted; an empty
// file, text, another maker's SysEx, a dump cut short and a dump of the
// wrong length load nothing and say which; a file past FM6's 64 KiB cap
// (FM1_APP_DX7_FILE_MAX; the text buffer is 256 KiB since stage A1) or past
// the buffer is refused; a refusal leaves the bank as it was; with `play` the current
// sound becomes FM6 on the first voice loaded; an FM6 sound made after a
// load plays the bank; and each of four voices renders the same samples
// from the bank (packed, unpacked by msfa's UnpackPatch) as from its single
// dump. Prints one line per case and a summary; exit 1 on a failure.
// MIT licence.

import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { instantiateFm1, BLOCK } from '../www/fm1-wasm.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
for (const k of ['wasm', 'dx7']) if (!args[k]) throw new Error(`missing --${k}`);

const wasmModule = await WebAssembly.compile(readFileSync(args.wasm));
const BANK = new Uint8Array(readFileSync(join(args.dx7, 'lunar-test-bank.syx')));
const VOICES = new Uint8Array(readFileSync(join(args.dx7, 'lunar-test-voices.syx')));
const VCED = 163, VMEM = 4104;
const single = (k) => VOICES.slice(k * VCED, (k + 1) * VCED);
const cat = (...parts) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
};
const NAME = (k) => `LUNAR ${String(k + 1).padStart(2, '0')}`;
const RATE = 44118;

// One module, powered on as the worklet does, with `engine` as Sound 1.
async function fm1(engine = 'dx7') {
  const w = await instantiateFm1(wasmModule);
  const ex = w.exports;
  const catalog = JSON.parse(w.string(ex.fm1w_catalog()));
  ex.fm1w_init(RATE);
  const index = (id) => catalog.findIndex((e) => e.id === id);
  if (engine && ex.fm1w_select(0, index(engine)) !== 0) throw new Error(`cannot load ${engine}`);
  const load = (bytes, play = 0, len = bytes.length) => {
    if (bytes.length <= ex.fm1w_text_cap()) new Uint8Array(w.memory.buffer, ex.fm1w_text_buf(), bytes.length).set(bytes);
    const n = ex.fm1w_dx7_load(len, play);
    const r = new Int32Array(w.memory.buffer, ex.fm1w_dx7_result(), 13);
    return {
      n, voices: r[1], first: r[2], messages: r[3], bad: r[4], foreign: r[5], truncated: r[6],
      wrongSize: r[7], raw: r[8], outside: r[9], played: r[10], sound: r[11], len: r[12],
    };
  };
  const name = (k) => w.string(ex.fm1w_dx7_name(k));
  const names = () => Array.from({ length: 32 }, (_, k) => name(k));
  const patchIndex = (id) => catalog[index(id)].params.findIndex((p) => p.name === 'Patch');
  // A note on the current sound, rendered as 16-bit samples, as parity does.
  const play = (patch, seconds = 0.4, unit = 0) => {
    if (patch !== null) ex.fm1w_set_param(unit, patchIndex('dx7'), patch);
    ex.fm1w_note_on(60, 110);
    const total = Math.trunc(seconds * RATE);
    const out = new Int16Array(total * 2);
    for (let pos = 0; pos < total; pos += BLOCK) {
      if (pos >= total / 2 && pos < total / 2 + BLOCK) ex.fm1w_note_off(60);
      const n = Math.min(BLOCK, total - pos);
      const f = new Float32Array(w.memory.buffer, ex.fm1w_render(n), 2 * n);
      for (let i = 0; i < 2 * n; ++i) out[2 * pos + i] = Math.round(Math.max(-1, Math.min(1, f[i])) * 32767);
    }
    return out;
  };
  return { w, ex, catalog, index, load, name, names, play, patchIndex };
}

const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const peak = (x) => x.reduce((m, v) => Math.max(m, Math.abs(v)), 0) / 32767;
const results = [];
async function check(name, fn) {
  let detail;
  try {
    detail = await fn();
  } catch (err) {
    detail = { error: String(err && err.stack || err) };
  }
  const pass = detail && detail.pass === true;
  results.push({ name, pass, ...detail });
  console.log(`${pass ? 'pass' : 'FAIL'} ${name}${pass ? '' : `: ${JSON.stringify(detail)}`}`);
}

await check('a 32-voice bank fills User 1-32 with its names', async () => {
  const m = await fm1();
  const r = m.load(BANK);
  const names = m.names();
  return {
    pass: r.n === 32 && r.voices === 32 && r.first === 0 && r.messages === 1 && r.bad === 0 &&
      r.raw === 0 && r.outside === 0 && r.played === 1 && names.every((n, k) => n === NAME(k)),
    r, names,
  };
});

await check('32 single-voice dumps in one file fill User 1-32', async () => {
  const m = await fm1();
  const r = m.load(VOICES);
  return { pass: r.n === 32 && r.messages === 32 && r.first === 0 && m.names().every((n, k) => n === NAME(k)), r };
});

await check('single voices go to the slot after the last; a bank resets to User 1', async () => {
  const m = await fm1();
  const a = m.load(single(4));
  const b = m.load(single(9));
  const twoSingles = [m.name(0), m.name(1)];
  const c = m.load(BANK);
  const d = m.load(single(2));
  return {
    pass: a.n === 1 && a.first === 0 && b.first === 1 && twoSingles.join() === [NAME(4), NAME(9)].join() &&
      c.first === 0 && d.first === 0 && m.name(0) === NAME(2) && m.name(1) === NAME(1),
    firsts: [a.first, b.first, c.first, d.first], twoSingles,
  };
});

await check('a bank\'s data without SysEx framing loads', async () => {
  const m = await fm1();
  const r = m.load(BANK.slice(6, 6 + 4096));
  return { pass: r.n === 32 && r.raw === 1 && r.outside === 0 && m.name(31) === NAME(31), r };
});

await check('a wrong checksum loads and is counted', async () => {
  const m = await fm1();
  const v = single(6);
  v[161] ^= 0x01;
  const r = m.load(v);
  return { pass: r.n === 1 && r.bad === 1 && m.name(0) === NAME(6), r };
});

await check('a bank with a wrong checksum loads and is counted', async () => {
  const m = await fm1();
  const b = BANK.slice();
  b[VMEM - 2] ^= 0x7f;
  const r = m.load(b);
  return { pass: r.n === 32 && r.bad === 1, r };
});

await check('an empty file loads nothing', async () => {
  const m = await fm1();
  const r = m.load(new Uint8Array(0));
  return { pass: r.n === 0 && r.voices === 0 && r.messages === 0 && r.outside === 0 && r.len === 0, r };
});

await check('text loads nothing, every byte outside SysEx', async () => {
  const m = await fm1();
  const text = new TextEncoder().encode('LUNAR MODULATOR, not a patch\n'.repeat(10));
  const r = m.load(text);
  return { pass: r.n === 0 && r.outside === text.length && r.messages === 0, r };
});

await check('another maker\'s SysEx loads nothing and is named foreign', async () => {
  const m = await fm1();
  const r = m.load(new Uint8Array([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7, 0xF0, 0x41, 0x10, 0x42, 0x12, 0x00, 0xF7]));
  return { pass: r.n === 0 && r.foreign === 2 && r.truncated === 0 && r.wrongSize === 0, r };
});

await check('a bank cut short loads nothing and is named truncated', async () => {
  const m = await fm1();
  const r = m.load(BANK.slice(0, 3000));
  return { pass: r.n === 0 && r.truncated === 1 && r.wrongSize === 0, r };
});

await check('a voice dump one byte short loads nothing and is named the wrong size', async () => {
  const m = await fm1();
  const v = cat(single(0).slice(0, 100), single(0).slice(101));
  const r = m.load(v);
  return { pass: r.n === 0 && r.wrongSize === 1 && r.foreign === 0, r };
});

await check('a dump whose byte count disagrees with its header is the wrong size', async () => {
  const m = await fm1();
  const v = single(0);
  v[5] = 0x1A;                                    // 154, not 155
  const r = m.load(v);
  return { pass: r.n === 0 && r.wrongSize === 1, r };
});

await check('several dumps and other messages: the dumps load, the rest is counted', async () => {
  const m = await fm1();
  const r = m.load(cat(single(3), new Uint8Array([0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]), single(8),
    new TextEncoder().encode('xy'), single(5).slice(0, 50)));
  return {
    pass: r.n === 2 && r.messages === 2 && r.foreign === 1 && r.truncated === 1 && r.outside === 2 &&
      m.name(0) === NAME(3) && m.name(1) === NAME(8),
    r,
  };
});

await check('a file past 64 KiB or the buffer is refused, and a refusal keeps the bank', async () => {
  const m = await fm1();
  m.load(BANK);
  const cap = m.ex.fm1w_text_cap();
  const over = m.load(new Uint8Array(65537));
  const big = m.load(new Uint8Array(0), 0, cap + 1);
  const junk = m.load(new TextEncoder().encode('nothing here'));
  return {
    pass: cap === 262144 && over.n === -1 && big.n === -1 && junk.n === 0 && m.names().every((n, k) => n === NAME(k)),
    over,
    big,
  };
});

await check('64 KiB of single voices is read whole', async () => {
  const m = await fm1();
  const reps = Math.floor(65536 / VCED);
  const file = new Uint8Array(65536);
  for (let i = 0; i < reps; ++i) file.set(single(i % 32), i * VCED);
  const r = m.load(file);
  return { pass: r.n === reps && r.messages === reps && r.outside === 65536 - reps * VCED, r };
});

await check('with play, the current sound becomes FM6 on the first voice loaded', async () => {
  const m = await fm1('macro');
  const dx7 = m.index('dx7');
  m.load(single(0));                               // User 1, then the bank's next: User 2 on
  const r = m.load(cat(single(11), single(12)), 1);
  const unit = m.ex.fm1w_sound_unit(m.ex.fm1w_unit_current());
  const patch = m.ex.fm1w_get_param(unit, m.patchIndex('dx7'));
  const out = m.play(null);
  return {
    pass: r.n === 2 && r.first === 1 && r.played === 0 && m.ex.fm1w_unit_index(unit) === dx7 && patch === 33 &&
      peak(out) > 0.01,
    r, patch, peak: peak(out),
  };
});

await check('an FM6 sound made after a load plays the bank', async () => {
  const a = await fm1('macro');
  a.load(BANK);
  a.ex.fm1w_select(0, a.index('dx7'));
  const late = a.play(32 + 20);
  const b = await fm1('dx7');
  b.load(BANK);
  const early = b.play(32 + 20);
  return { pass: same(late, early) && peak(early) > 0.01, peak: peak(early) };
});

await check('each voice sounds the same from the bank as from its single dump', async () => {
  const peaks = [];
  for (const k of [0, 6, 19, 31]) {
    const a = await fm1();
    a.load(BANK);
    const b = await fm1();
    b.load(VOICES);
    const x = a.play(32 + k), y = b.play(32 + k);
    if (!same(x, y) || peak(x) < 0.01) return { pass: false, voice: k + 1, peak: peak(x) };
    peaks.push(Math.round(peak(x) * 1000) / 1000);
  }
  return { pass: true, peaks };
});

const summary = {
  passed: results.filter((r) => r.pass).length,
  failed: results.filter((r) => !r.pass).length,
  cases: results.map((r) => ({ name: r.name, pass: r.pass })),
};
if (args.summary) writeFileSync(args.summary, JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify({ passed: summary.passed, failed: summary.failed }));
process.exit(summary.failed ? 1 : 0);
