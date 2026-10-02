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
//
// A scenario with `cmd` plays a sequencer verb script (fm1-render --cmd).
// Every leg applies each line at the first 64-frame block starting at or
// after its frame, after the notes; the app gets it through fm1w_seq_text.
// This file reads the script itself (as seq_script.c's fm1_script_load
// does), so before any audio is compared, its list of applied (block, line)
// pairs must equal the one the native harness logged (--log-cmds), and the
// module must have dropped no sequencer event.
//
// A scenario with `panel` (and `lab`, the lab switch) plays the sequencer
// from the panel (docs/15 S3, §6.3): the native harness runs first with
// --panel and --log-cmds, and the glibc, js and musl legs replay what it
// logged, the script lines and the panel's typed commands, with the
// arguments of its sidecar (.args: the engine and effects, and a --param-at
// for each knob turn), while the module presses the same buttons and turns
// the same encoders (fm1w_button, fm1w_encoder). So the panel scenario is
// two-step parity in WebAssembly, and the module's screen at the end (the
// Track view) is compared with the harness's.
//
// A scenario with `sounds`, `inserts`, `levels` or `sound_notes` (and `lab`)
// plays several sound units (docs/15 §3.16): fm1-render gets --sound,
// --insert, --level and --sound-note, and --slots for any lab scenario, so
// its tracks play the unit their route names as the module's do; the module
// loads the same units through fm1w_sound_unit and fm1w_insert_unit, in the
// same order, and plays those notes with fm1w_unit_note_on.
// MIT licence.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
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
const cmdPath = (s) => resolve(dirname(args.scenarios), s.cmd);
const panelPath = (s) => resolve(dirname(args.scenarios), s.panel);

function cliArgs(s) {
  const a = ['--seconds', String(s.seconds), '--rate', String(s.rate ?? 44118), '--engine', s.engine];
  if (s.cmd) a.push('--cmd', cmdPath(s));
  for (const p of s.params ?? []) a.push('--param', p);
  for (const n of s.notes ?? []) a.push('--note', n);
  for (const b of s.bends ?? []) a.push('--bend', b);
  for (const p of s.param_at ?? []) a.push('--param-at', p);
  for (const [id, ps] of s.fx ?? []) {
    a.push('--fx', id);
    for (const p of ps) a.push('--fx-param', p);
  }
  // Multi-sound (docs/15 §3.16): the other sound units, every unit's inserts
  // and levels, and notes on a given unit.
  for (const [k, id, ps] of s.sounds ?? []) {
    a.push('--sound', `${k}:${id}`);
    for (const p of ps) a.push('--sound-param', `${k}:${p}`);
  }
  for (const [k, id, ps] of s.inserts ?? []) {
    a.push('--insert', `${k}:${id}`);
    for (const p of ps) a.push('--insert-param', `${k}:${p}`);
  }
  for (const lv of s.levels ?? []) a.push('--level', lv);
  for (const n of s.sound_notes ?? []) a.push('--sound-note', n);
  return a;
}

// A 16-bit stereo WAV at `rate`, like render.cc's, so the app's output can
// sit next to the native renders (readme-screenshots.mjs plots one pair).
function writeWav(path, samples, rate) {
  const data = Buffer.from(samples.buffer, samples.byteOffset, samples.byteLength);
  const h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + data.length, 4); h.write('WAVE', 8);
  h.write('fmt ', 12); h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(2, 22);
  h.writeUInt32LE(rate, 24); h.writeUInt32LE(rate * 4, 28); h.writeUInt16LE(4, 32); h.writeUInt16LE(16, 34);
  h.write('data', 36); h.writeUInt32LE(data.length, 40);
  writeFileSync(path, Buffer.concat([h, data]));
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

// A verb script as engines/host/seq_script.c's fm1_script_load reads it:
// lines trimmed of trailing CR, spaces and tabs and of leading spaces and
// tabs; `#!` header keys anywhere (decimal values only); other `#` lines
// skipped, `#?@` test directives kept but never applied; `@<frame> <ops>`;
// commands stably sorted by frame, then line.
function loadScript(path) {
  const s = { rate: 44118, block: 128, tracks: 8, end: null, cmds: [] };
  readFileSync(path, 'latin1').split('\n').forEach((raw, i) => {
    let p = raw.replace(/[\r \t]+$/, '').replace(/^[ \t]+/, '');
    if (!p) return;
    if (p[0] === '#' && !(p[1] === '?' && p[2] === '@')) {
      if (p[1] === '!') {
        for (const tok of p.slice(2).split(/[ \t]+/)) {
          const eq = tok.indexOf('=');
          if (eq < 0 || !/^[0-9]+$/.test(tok.slice(eq + 1))) continue;
          const key = tok.slice(0, eq), v = Number(tok.slice(eq + 1));
          if (key === 'rate') s.rate = v >>> 0;
          else if (key === 'block') s.block = v >>> 0;
          else if (key === 'tracks') s.tracks = v & 255;
          else if (key === 'end') s.end = v;
        }
      }
      return;
    }
    const snap = p[0] === '#';
    if (snap) p = p.slice(2);
    const m = /^@([0-9]+)(?:[ \t]+|$)/.exec(p);
    if (!m) throw new Error(`${path}:${i + 1}: expected '@<frame> <ops>'`);
    s.cmds.push({ frame: Number(m[1]), ops: p.slice(m[0].length), line: i + 1, snap });
  });
  s.cmds.sort((x, y) => x.frame - y.frame || x.line - y.line);
  return s;
}

// A --panel file as fm1-sim-render reads it (read_panel, add_panel): one
// --key, --button, --turn or --note (MIDI IN) and its value per line, '#'
// comments; events in file order, a button's, key's or note's press then
// its release.
const BUTTON_NAMES = ['OCT-', 'OCT+', 'FX', 'SEL', 'ENV', 'LFO', 'EDIT', 'GLO', 'HOME', 'SAVE', 'ARP',
  'SEQ', 'PLAY/STOP', 'REC'];
const ENCODER_NAMES = ['SELECT', 'PRESETS', 'ALGORITHM', 'KNOB1', 'KNOB2', 'KNOB3', 'KNOB4'];
function loadPanel(path) {
  const controls = [], keys = [];
  readFileSync(path, 'latin1').split('\n').forEach((raw, i) => {
    const p = raw.replace(/[\r \t]+$/, '').replace(/^[ \t]+/, '');
    if (!p || p[0] === '#') return;
    const m = /^(--key|--button|--turn|--note)[ \t]+(.*)$/.exec(p);
    if (!m) throw new Error(`${path}:${i + 1}: want --key, --button, --turn or --note`);
    const parts = m[2].split(':');
    const t = parseFloat(parts[0]);
    if (m[1] === '--button') {
      const id = BUTTON_NAMES.indexOf(parts[1]);
      const dur = parts.length > 2 ? parseFloat(parts[2]) : 0;
      if (id < 0) throw new Error(`${path}:${i + 1}: unknown button ${parts[1]}`);
      controls.push({ t, button: id, down: 1 }, { t: t + dur, button: id, down: 0 });
    } else if (m[1] === '--turn') {
      const id = ENCODER_NAMES.indexOf(parts[1]);
      if (id < 0) throw new Error(`${path}:${i + 1}: unknown encoder ${parts[1]}`);
      controls.push({ t, encoder: id, delta: parseInt(parts[2], 10) });
    } else {
      const [key, vel, dur] = parts.slice(1).map(Number);
      const midi = m[1] === '--note';
      keys.push({ t, on: true, key, vel, midi }, { t: t + dur, on: false, key, midi });
    }
  });
  return { controls, keys };
}

// A line as the harness's --log-cmds writes it: less trailing ';' and blanks.
const logged = (ops) => ops.replace(/[ \t;]+$/, '');

// The harness's --log-cmds file: [frame, ops] for every line it applied.
function readCmdLog(path) {
  return readFileSync(path, 'latin1').split('\n').filter((l) => l.startsWith('@')).map((l) => {
    const m = /^@([0-9]+) (.*)$/.exec(l);
    return [Number(m[1]), m[2]];
  });
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
  if (s.lab) ex.fm1w_set_lab(1);                  // as fm1-sim-render --lab, after init
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
  // Multi-sound, in the harness's and fm1-render's order: the other sound
  // units, then each unit's inserts in order, then the levels.
  for (const [k, id, ps] of s.sounds ?? []) {
    const unit = ex.fm1w_sound_unit(k);
    if (ex.fm1w_select(unit, indexOf(id)) !== 0) throw new Error(`cannot load ${id} as sound ${k}`);
    for (const p of ps) {
      const [n, v] = splitParam(p);
      ex.fm1w_set_param(unit, paramOf(id, n), v);
    }
  }
  const insertsOf = [0, 0, 0, 0];
  for (const [k, id, ps] of s.inserts ?? []) {
    const unit = ex.fm1w_insert_unit(k, insertsOf[k]++);
    if (ex.fm1w_select(unit, indexOf(id)) !== 0) throw new Error(`cannot load ${id} as an insert of sound ${k}`);
    for (const p of ps) {
      const [n, v] = splitParam(p);
      ex.fm1w_set_param(unit, paramOf(id, n), v);
    }
  }
  for (const lv of s.levels ?? []) {
    const [k, v] = lv.split(':');
    ex.fm1w_unit_set_level(Number(k), Math.fround(parseFloat(v)));
  }
  ex.fm1w_master(1, 0);

  // The sequencer, as fm1-sim-render sets it up for --cmd: an instance at the
  // script's track count, and the default route (track 0 plays the sound).
  const script = s.cmd ? loadScript(cmdPath(s)) : null;
  const applied = [];
  let nextCmd = 0;
  if (script) {
    if (script.block !== BLOCK) throw new Error(`${s.cmd}: block=${script.block}, not ${BLOCK}`);
    if (ex.fm1w_seq_reset(script.tracks) !== 0) throw new Error(`${s.cmd}: tracks=${script.tracks}`);
  }
  const textBuf = script ? new Uint8Array(w.memory.buffer, ex.fm1w_text_buf(), ex.fm1w_text_cap()) : null;

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
  for (const n of s.sound_notes ?? []) {           // after --note, as cliArgs passes them
    const [sound, t, key, vel, dur] = n.split(':').map(Number);
    events.push({ t, on: true, key, vel, sound }, { t: t + dur, on: false, key, sound });
  }
  // The panel, after every other argument as parity passes it to the
  // harness: its buttons and encoders with the controls, its keys with the
  // notes.
  if (s.panel) {
    const panel = loadPanel(panelPath(s));
    controls.push(...panel.controls);
    events.push(...panel.keys.map((k) => ({ ...k, panel: !k.midi })));
  }
  const total = Math.trunc(s.seconds * rate);
  const out = new Int16Array(total * 2);
  for (let pos = 0; pos < total; pos += BLOCK) {
    const now = pos / rate;
    const n = Math.min(BLOCK, total - pos);
    for (const c of controls) {
      if (c.done || c.t > now) continue;
      if (c.button !== undefined) ex.fm1w_button(c.button, c.down);
      else if (c.encoder !== undefined) ex.fm1w_encoder(c.encoder, c.delta);
      else if (c.bend) ex.fm1w_pitch_bend(c.v);
      else ex.fm1w_set_param(0, c.idx, c.v);
      c.done = true;
    }
    for (const on of [false, true]) {
      for (const e of events) {
        if (e.done || e.on !== on || e.t > now) continue;
        if (e.panel) ex.fm1w_key(e.key, on ? 1 : 0, e.vel | 0);
        else if (e.sound !== undefined) {
          if (on) ex.fm1w_unit_note_on(e.sound, e.key, e.vel);
          else ex.fm1w_unit_note_off(e.sound, e.key);
        } else if (on) ex.fm1w_note_on(e.key, e.vel);
        else ex.fm1w_note_off(e.key);
        e.done = true;
      }
    }
    while (script && nextCmd < script.cmds.length && script.cmds[nextCmd].frame <= pos) {
      const c = script.cmds[nextCmd++];
      if (c.snap) continue;                       // fm1-seq's test directives
      if (c.ops.length > textBuf.length) throw new Error(`${s.cmd}: line ${c.line} too long`);
      for (let i = 0; i < c.ops.length; ++i) textBuf[i] = c.ops.charCodeAt(i) & 255;
      const took = ex.fm1w_seq_text(c.ops.length);
      if (took !== c.ops.length) {
        throw new Error(`${s.cmd}: line ${c.line} took ${took} of ${c.ops.length} bytes (event room)`);
      }
      applied.push([pos, logged(c.ops)]);
    }
    const ptr = ex.fm1w_render(n);
    const f = new Float32Array(w.memory.buffer, ptr, 2 * n);
    for (let i = 0; i < 2 * n; ++i) out[2 * pos + i] = toInt16(f[i]);
  }
  ex.fm1w_draw(0);
  const screen = new Uint16Array(w.memory.buffer, ex.fm1w_screen(), 240 * 240).slice();
  const seq = script ? { applied: applied.filter(([, ops]) => ops), dropped: ex.fm1w_seq_dropped() } : null;
  return { out, screen, imports: w.imports, calls: w.calls, ram: ex.fm1w_ram(), seq };
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
  // The native harness first: a panel scenario's render legs replay its log.
  const simArgs = [...cli, '--screen', join(dir, 'screen.ppm')];
  if (s.cmd) simArgs.push('--log-cmds', join(dir, 'cmds.verbs'));
  if (s.lab) simArgs.push('--lab');
  if (s.panel) simArgs.push('--panel', panelPath(s));
  const native = JSON.parse(execFileSync(args.sim, simArgs, quiet).toString().trim().split('\n').pop());
  // The lab switch routes tracks by slot (fm1-render --slots); a panel run's
  // sidecar says so itself.
  const renderCli = s.panel
    ? ['--seconds', String(s.seconds), '--rate', String(s.rate ?? 44118), '--cmd', join(dir, 'cmds.verbs'),
      ...readFileSync(join(dir, 'cmds.args'), 'latin1').split('\n').filter((l) => l !== '')]
    : [...cli, ...(s.lab ? ['--slots'] : [])];
  execFileSync(args.native, [...renderCli, '--out', join(dir, 'glibc.wav')], quiet);
  execFileSync(process.execPath, [args['render-js'], ...renderCli, '--out', join(dir, 'js.wav')], quiet);
  if (args.musl) execFileSync(args.musl, [...renderCli, '--out', join(dir, 'musl.wav')], quiet);
  const glibc = readWav(join(dir, 'glibc.wav'));
  const js = readWav(join(dir, 'js.wav'));
  const app = await renderApp(s);
  let seq = null;
  if (s.cmd) {
    // The third reader of the script (above) against the harness's own:
    // the same lines at the same blocks, before any audio counts. The
    // harness's log also holds the panel's typed commands, which it lists
    // in its summary (seq_ui_cmds): those come out, in order, first.
    const ui = (native.seq_ui_cmds ?? []).map(([f, t]) => JSON.stringify([f, t]));
    let k = 0;
    const harness = readCmdLog(join(dir, 'cmds.verbs')).filter((line) => {
      if (k < ui.length && JSON.stringify(line) === ui[k]) { ++k; return false; }
      return true;
    });
    seq = {
      lines: app.seq.applied.length,
      lines_match: k === ui.length && JSON.stringify(harness) === JSON.stringify(app.seq.applied),
      ui_cmds: ui.length,
      replayable: native.replayable === 1,
      dropped: app.seq.dropped,
      native_dropped: native.seq_dropped,
    };
  }
  writePpm(join(dir, 'app-screen.ppm'), app.screen);
  writeWav(join(dir, 'app.wav'), app.out, Math.round(s.rate ?? 44118));
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
    cmd: s.cmd ?? null,
    panel: s.panel ?? null,
    seq,
  };
  r.pass = (!seq || (seq.lines_match && seq.dropped === 0 && seq.native_dropped === 0 &&
                     (!s.panel || (seq.replayable && seq.ui_cmds > 0)))) &&
    r.app_vs_js.differing === 0 &&
    (!r.app_vs_musl || r.app_vs_musl.differing === 0) &&
    (r.app_vs_glibc.max <= 1 || r.libm_sensitive) &&
    r.screen.differing === 0 && r.calls === 0;
  results.push(r);
  const fmt = (c) => c ? `${c.differing} differ (max ${c.max})` : 'not run';
  const seqNote = seq ? `; ${seq.lines} script lines${seq.lines_match ? '' : ' NOT as the harness applied them'}, ` +
    `${seq.ui_cmds ? `${seq.ui_cmds} panel commands${seq.replayable ? '' : ' NOT replayable'}, ` : ''}` +
    `${seq.dropped} events dropped` : '';
  console.log(`${r.pass ? 'pass' : 'FAIL'} ${s.name}: of ${r.samples} samples, vs js ${fmt(r.app_vs_js)}, ` +
    `vs musl ${fmt(r.app_vs_musl)}, vs glibc ${fmt(r.app_vs_glibc)}${r.libm_sensitive ? ' [libm-sensitive]' : ''}; ` +
    `screen ${r.screen.differing} px; RAM ${r.ram.wasm32} B (wasm32) / ${r.ram.native64} B (native 64-bit)${seqNote}`);
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
