// meta.mjs -- the editor's static meta.json, written by the module it sits
// beside and checked against it (stage ED0; notes/2026-10-06-web-editor.md
// §6, decision ED4). Runs in the emscripten/emsdk container after the parity
// test (build.sh), never on the Mac:
//
//   node meta.mjs --wasm build/wasm/fm1.wasm --native build/meta-native.json \
//                 --out build/meta.json [--summary out.json]
//
// The module writes its metadata export a buffer at a time (fm1w_meta_read),
// with its own instance bytes, which are the 32-bit module's as its RAM meter
// counts them; this writes that to --out and checks:
//
//   - the file's `meta_id` is its CRC-32 less `made` and `meta_id`
//     (fm1_meta.h), and the module's fm1w_meta_id is that id;
//   - it is the native harness's export (fm1-sim-render --meta, --native) in
//     everything but the instance bytes (`ram`, which a 64-bit build counts
//     with 8-byte pointers) and so the id: one registry, two compilers;
//   - asking costs nothing the module would notice: no import is called, and
//     a module asked first plays what one never asked plays.
//
// The editor fetches meta.json and checks fm1w_meta_id() before it trusts
// it; this is the build's half of that promise. Exit 1 on a failure. MIT
// licence.

import { readFileSync, writeFileSync } from 'node:fs';
import { instantiateFm1, BLOCK } from '../www/fm1-wasm.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
for (const k of ['wasm', 'native', 'out']) if (!args[k]) throw new Error(`missing --${k}`);

const failures = [];
const check = (ok, what) => { if (!ok) failures.push(what); console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); };

// zlib's CRC-32 (reflected 0xEDB88320).
const TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; ++k) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(bytes) {
  let c = 0xFFFFFFFF;
  for (const b of bytes) c = TABLE[(c ^ b) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
const hex = (v) => (v >>> 0).toString(16).padStart(8, '0');

// The export less its `made` line and its `meta_id` line (each one line in
// the canonical layout; `meta_id` the last member, so the line before it
// loses its comma): what the id is the CRC-32 of.
function idOf(text) {
  const kept = text.split('\n').filter((l) => !l.startsWith('  "made": ') && !l.startsWith('  "meta_id": '));
  const last = kept.length - 3;                  // the member before the closing brace
  kept[last] = kept[last].replace(/,$/, '');
  return hex(crc32(new TextEncoder().encode(kept.join('\n'))));
}

// Powered on as the worklet does, a note held, sixteen blocks.
function play(m) {
  const e = m.exports, out = [];
  e.fm1w_init(44118);
  e.fm1w_default_chain();
  e.fm1w_note_on(57, 100);
  for (let k = 0; k < 16; ++k) out.push(...new Float32Array(m.memory.buffer, e.fm1w_render(BLOCK), 2 * BLOCK));
  return out;
}

const wasmModule = await WebAssembly.compile(readFileSync(args.wasm));
const w = await instantiateFm1(wasmModule);
const ex = w.exports;
check(typeof ex.fm1w_meta_id === 'function' && typeof ex.fm1w_meta_read === 'function',
      'the module exports fm1w_meta_id and fm1w_meta_read');
const before = play(w);

// The export, a buffer at a time.
const parts = [];
let total = 0;
for (;;) {
  const n = ex.fm1w_meta_read(total);
  if (!n) break;
  parts.push(new Uint8Array(w.memory.buffer, ex.fm1w_text_buf(), n).slice());
  total += n;
}
const bytes = new Uint8Array(total);
parts.reduce((at, p) => { bytes.set(p, at); return at + p.length; }, 0);
const text = new TextDecoder().decode(bytes);
writeFileSync(args.out, bytes);
const meta = JSON.parse(text);

const moduleId = hex(ex.fm1w_meta_id());
check(hex(ex.fm1w_meta_id()) === moduleId, 'the id is the same at the second call');
check(meta.kind === 'metadata' && meta.made.by === 'simulator', 'the module writes the simulator\'s metadata export');
check(meta.meta_id === idOf(text), `its id is its own CRC-32 less made and meta_id (${meta.meta_id})`);
check(meta.meta_id === moduleId, `the module's fm1w_meta_id is the file's (${moduleId})`);
check(w.calls.length === 0, `no import was called (${w.calls.join(', ') || 'none'})`);

// The native harness's export: the same registry, compiled for 64 bits.
const native = JSON.parse(readFileSync(args.native, 'utf8'));
const modules = (doc) => [...doc.engines, ...doc.mod.kinds];
const strip = (doc) => {
  const d = structuredClone(doc);
  delete d.made;
  delete d.meta_id;
  for (const m of modules(d)) m.ram = 0;
  return d;
};
const ramDiffer = modules(meta).filter((m, i) => m.ram !== modules(native)[i]?.ram).length;
check(JSON.stringify(strip(meta)) === JSON.stringify(strip(native)),
      `it is the native harness's export but for the instance bytes (${ramDiffer} of ${modules(meta).length} modules' differ at 64 bits)`);

// A second module asked before it is powered on gives the same id, and then
// plays what the first played: asking changes nothing that sounds.
const w2 = await instantiateFm1(wasmModule);
check(hex(w2.exports.fm1w_meta_id()) === moduleId, 'a second module, asked first, gives the same id');
const again = play(w2);
check(before.some((v) => v !== 0) && before.every((v, i) => Object.is(v, again[i])),
      'asking for the id leaves the audio as it was');

const summary = { meta_id: meta.meta_id, module_meta_id: moduleId, bytes: total, lunar: meta.lunar,
                  native_meta_id: native.meta_id, ram_differ_at_64_bits: ramDiffer,
                  passed: failures.length === 0 };
if (args.summary) writeFileSync(args.summary, JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary));
if (failures.length) process.exit(1);
