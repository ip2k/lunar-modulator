// parity.mjs -- does the browser's WebAssembly build sound like the native
// engines? Runs in the emscripten/emsdk container (build.sh):
//
//   node parity.mjs --native build/native/fm1-render --sim build/native/fm1-sim-render \
//        --wasm build/wasm/fm1.wasm --render-js build/wasm/fm1-render.js \
//        [--musl build/musl/fm1-render] --scenarios scenarios.json \
//        --work build/parity [--summary out.json]
//
// For every scenario it renders the note script up to four ways and compares
// the 16-bit output sample by sample:
//   glibc  native fm1-render (engines/host/render.cc), GCC and glibc
//   musl   the same, GCC and musl, linked static (build-on-aeon.sh builds it
//          in Alpine): musl is the C library Emscripten uses
//   js     render.cc compiled to WebAssembly and run by Node
//   app    fm1.wasm, the browser's module, driven here exactly as fm1-render
//          drives its engines (events at 64-frame block boundaries, controls
//          first, then note-offs, then note-ons)
// and the screen the app draws afterwards against the native harness's
// (less the bottom bar's RAM figure: WebAssembly has 4-byte pointers, so its
// instance sizes are the 32-bit ones, closer to pi32v2's).
//
// A scenario passes when app equals js exactly (the app layer adds nothing),
// app equals musl exactly when musl is given (the compiler adds nothing), app
// is within 1 LSB of glibc unless the scenario is marked libm_sensitive (a
// feedback loop that amplifies glibc's and musl's last-bit differences in
// sinf/expf), the screens match and the module made no import calls.
// MIT licence.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { instantiateFm1, BLOCK } from '../www/fm1-wasm.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
for (const k of ['native', 'sim', 'wasm', 'render-js', 'scenarios', 'work']) {
  if (!args[k]) throw new Error(`missing --${k}`);
}
mkdirSync(args.work, { recursive: true });

const scenarios = JSON.parse(readFileSync(args.scenarios, 'utf8')).scenarios;
const wasmModule = await WebAssembly.compile(readFileSync(args.wasm));

function cliArgs(s) {
  const a = ['--seconds', String(s.seconds), '--rate', String(s.rate ?? 44118), '--engine', s.engine];
  for (const p of s.params ?? []) a.push('--param', p);
  for (const n of s.notes ?? []) a.push('--note', n);
  for (const b of s.bends ?? []) a.push('--bend', b);
  for (const p of s.param_at ?? []) a.push('--param-at', p);
  for (const [id, ps] of s.fx ?? []) {
    a.push('--fx', id);
    for (const p of ps) a.push('--fx-param', p);
  }
  return a;
}

function readWav(path) {
  const b = readFileSync(path);
  return new Int16Array(b.buffer.slice(b.byteOffset + 44, b.byteOffset + b.length));
}

// lrintf(clamp(x) * 32767.0f), as render.cc's WriteWav: float multiply, then
// round half to even.
function toInt16(x) {
  if (Number.isNaN(x)) x = 0;
  x = Math.min(1, Math.max(-1, x));
  const v = Math.fround(x * 32767);
  const f = Math.floor(v);
  const d = v - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

function splitParam(arg) {
  const eq = arg.indexOf('=');
  return [arg.slice(0, eq), Math.fround(parseFloat(arg.slice(eq + 1)))];
}

async function renderApp(s) {
  const w = await instantiateFm1(wasmModule);
  const ex = w.exports;
  const catalog = JSON.parse(w.string(ex.fm1w_catalog()));
  const rate = Math.fround(s.rate ?? 44118);
  const indexOf = (id) => catalog.findIndex((e) => e.id === id);
  const paramOf = (id, name) => catalog[indexOf(id)].params
    .findIndex((p) => p.name.toLowerCase() === name.toLowerCase());
  ex.fm1w_init(rate);
  if (ex.fm1w_select(0, indexOf(s.engine)) !== 0) throw new Error(`cannot load ${s.engine}`);
  for (const p of s.params ?? []) {
    const [n, v] = splitParam(p);
    ex.fm1w_set_param(0, paramOf(s.engine, n), v);
  }
  (s.fx ?? []).forEach(([id, ps], k) => {
    if (ex.fm1w_select(1 + k, indexOf(id)) !== 0) throw new Error(`cannot load ${id}`);
    for (const p of ps) {
      const [n, v] = splitParam(p);
      ex.fm1w_set_param(1 + k, paramOf(id, n), v);
    }
  });
  ex.fm1w_master(1, 0);

  // Events as render.cc builds them: --bend and --param-at in argv order
  // (cliArgs puts bends first), notes as on/off pairs.
  const controls = [
    ...(s.bends ?? []).map((b) => {
      const [t, st] = b.split(':');
      return { t: parseFloat(t), bend: true, v: Math.fround(parseFloat(st)) };
    }),
    ...(s.param_at ?? []).map((p) => {
      const c = p.indexOf(':');
      const [n, v] = splitParam(p.slice(c + 1));
      return { t: parseFloat(p.slice(0, c)), bend: false, idx: paramOf(s.engine, n), v };
    }),
  ];
  const events = [];
  for (const n of s.notes ?? []) {
    const [t, key, vel, dur] = n.split(':').map(Number);
    events.push({ t, on: true, key, vel }, { t: t + dur, on: false, key });
  }
  const total = Math.trunc(s.seconds * rate);
  const out = new Int16Array(total * 2);
  for (let pos = 0; pos < total; pos += BLOCK) {
    const now = pos / rate;
    const n = Math.min(BLOCK, total - pos);
    for (const c of controls) {
      if (c.done || c.t > now) continue;
      if (c.bend) ex.fm1w_pitch_bend(c.v); else ex.fm1w_set_param(0, c.idx, c.v);
      c.done = true;
    }
    for (const on of [false, true]) {
      for (const e of events) {
        if (e.done || e.on !== on || e.t > now) continue;
        if (on) ex.fm1w_note_on(e.key, e.vel); else ex.fm1w_note_off(e.key);
        e.done = true;
      }
    }
    const ptr = ex.fm1w_render(n);
    const f = new Float32Array(w.memory.buffer, ptr, 2 * n);
    for (let i = 0; i < 2 * n; ++i) out[2 * pos + i] = toInt16(f[i]);
  }
  ex.fm1w_draw(0);
  const screen = new Uint16Array(w.memory.buffer, ex.fm1w_screen(), 240 * 240).slice();
  return { out, screen, imports: w.imports, calls: w.calls, ram: ex.fm1w_ram() };
}

function readPpmAs565(path) {
  const b = readFileSync(path);
  const header = 'P6\n240 240\n255\n'.length;
  const px = new Uint16Array(240 * 240);
  for (let i = 0; i < px.length; ++i) {
    const r = b[header + 3 * i], g = b[header + 3 * i + 1], bl = b[header + 3 * i + 2];
    // invert the harness's 565 -> 888 expansion
    px[i] = (Math.round(r * 31 / 255) << 11) | (Math.round(g * 63 / 255) << 5) | Math.round(bl * 31 / 255);
  }
  return px;
}

// The bottom bar's right half shows the chain's RAM, which differs between a
// 64-bit native build and 32-bit WebAssembly; it is reported separately.
const masked = (i) => (i % 240) >= 120 && Math.floor(i / 240) >= 216;

function compare(a, b, skip = () => false) {
  let max = 0, differing = 0, first = -1;
  if (a.length !== b.length) return { max: Infinity, differing: Math.abs(a.length - b.length), first: 0 };
  for (let i = 0; i < a.length; ++i) {
    if (skip(i)) continue;
    const d = Math.abs(a[i] - b[i]);
    if (d) {
      ++differing;
      if (d > max) max = d;
      if (first < 0) first = i;
    }
  }
  return { max, differing, first };
}

function writePpm(path, px) {
  const header = Buffer.from('P6\n240 240\n255\n');
  const body = Buffer.alloc(240 * 240 * 3);
  for (let i = 0; i < px.length; ++i) {
    const p = px[i];
    body[3 * i] = Math.floor(((p >> 11) & 31) * 255 / 31);
    body[3 * i + 1] = Math.floor(((p >> 5) & 63) * 255 / 63);
    body[3 * i + 2] = Math.floor((p & 31) * 255 / 31);
  }
  writeFileSync(path, Buffer.concat([header, body]));
}

const quiet = { stdio: ['ignore', 'pipe', 'inherit'] };
const results = [];
let imports = null;
for (const s of scenarios) {
  const dir = join(args.work, s.name);
  mkdirSync(dir, { recursive: true });
  const cli = cliArgs(s);
  execFileSync(args.native, [...cli, '--out', join(dir, 'glibc.wav')], quiet);
  execFileSync(process.execPath, [args['render-js'], ...cli, '--out', join(dir, 'js.wav')], quiet);
  if (args.musl) execFileSync(args.musl, [...cli, '--out', join(dir, 'musl.wav')], quiet);
  const native = JSON.parse(execFileSync(args.sim, [...cli, '--screen', join(dir, 'screen.ppm')], quiet)
    .toString().trim().split('\n').pop());
  const glibc = readWav(join(dir, 'glibc.wav'));
  const js = readWav(join(dir, 'js.wav'));
  const app = await renderApp(s);
  writePpm(join(dir, 'app-screen.ppm'), app.screen);
  imports = app.imports;
  const r = {
    name: s.name,
    samples: glibc.length,
    libm_sensitive: !!s.libm_sensitive,
    app_vs_js: compare(js, app.out),
    app_vs_musl: args.musl ? compare(readWav(join(dir, 'musl.wav')), app.out) : null,
    app_vs_glibc: compare(glibc, app.out),
    screen: compare(readPpmAs565(join(dir, 'screen.ppm')), app.screen, masked),
    ram: { wasm32: app.ram, native64: native.ram },
    calls: app.calls.length,
  };
  r.pass = r.app_vs_js.differing === 0 &&
    (!r.app_vs_musl || r.app_vs_musl.differing === 0) &&
    (r.app_vs_glibc.max <= 1 || r.libm_sensitive) &&
    r.screen.differing === 0 && r.calls === 0;
  results.push(r);
  const fmt = (c) => c ? `${c.differing} differ (max ${c.max})` : 'not run';
  console.log(`${r.pass ? 'pass' : 'FAIL'} ${s.name}: of ${r.samples} samples, vs js ${fmt(r.app_vs_js)}, ` +
    `vs musl ${fmt(r.app_vs_musl)}, vs glibc ${fmt(r.app_vs_glibc)}${r.libm_sensitive ? ' [libm-sensitive]' : ''}; ` +
    `screen ${r.screen.differing} px; RAM ${r.ram.wasm32} B (wasm32) / ${r.ram.native64} B (native 64-bit)`);
}
const summary = {
  passed: results.filter((r) => r.pass).length,
  failed: results.filter((r) => !r.pass).length,
  identical_to_js: results.filter((r) => r.app_vs_js.differing === 0).length,
  identical_to_musl: args.musl ? results.filter((r) => r.app_vs_musl.differing === 0).length : null,
  identical_to_glibc: results.filter((r) => r.app_vs_glibc.differing === 0).length,
  max_lsb_vs_glibc_exact_scenarios: Math.max(0, ...results.filter((r) => !r.libm_sensitive).map((r) => r.app_vs_glibc.max)),
  imports,
  scenarios: results,
};
if (imports.length) {
  console.log(`FAIL fm1.wasm imports ${imports.join(', ')}`);
  summary.failed += 1;
}
if (args.summary) writeFileSync(args.summary, JSON.stringify(summary, null, 2) + '\n');
const { scenarios: _, ...brief } = summary;
console.log(JSON.stringify(brief));
process.exit(summary.failed ? 1 : 0);
