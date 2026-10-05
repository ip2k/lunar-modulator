// app.js -- the virtual FM-1's page: draws the front panel to scale, turns
// mouse, touch, computer-keyboard and Web MIDI input into panel events for
// the firmware in the AudioWorklet (worklet.js), and shows the screen and
// LEDs it sends back. No dependencies. Part of Lunar Modulator; MIT licence,
// like the rest of this repository.

import { BUTTONS, ENCODERS, KEYS } from './fm1-wasm.mjs';

// The lab switch (sim/web/README.md, "The lab switch"): an address with a
// `lab` query parameter or hash (?lab, #lab) turns on sequencer features
// that are still being built; the public page hides them until step entry
// and recording work (the owner's decision O24 in docs/15).
const LAB = (() => {
  try {
    const u = new URL(window.location.href);
    return u.searchParams.has('lab') || u.hash.replace(/^#/, '').split(/[&,;]/).includes('lab');
  } catch (err) {
    return false;
  }
})();

// ---- panel geometry, millimetres --------------------------------------------
// Case 161.5 x 96.5 mm (M-VAVE manual, specifications). Control centres
// measured on the owner's board photo (photos/2026-09-29/3-top.jpg) at
// 12.8 px/mm with the board centred in the case; names and the screen window
// from the manual's panel drawing.
const CASE = { w: 161.5, h: 96.5, r: 7 };
const ROW_TOP = 13.2;
const KNOBS = [
  { enc: 'SELECT', x: 33.09, y: ROW_TOP },
  { enc: 'PRESETS', x: 15.67, y: 29.88 },
  { enc: 'ALGORITHM', x: 32.94, y: 29.88 },
  { enc: 'KNOB1', x: 92.55, y: ROW_TOP },
  { enc: 'KNOB2', x: 110.44, y: ROW_TOP },
  { enc: 'KNOB3', x: 128.33, y: ROW_TOP },
  { enc: 'KNOB4', x: 146.22, y: ROW_TOP },
];
const MASTER = { x: 15.36, y: ROW_TOP };
const KNOB_R = 3.6;
const OCT = [{ id: 'OCT-', x: 19.34 }, { id: 'OCT+', x: 31.38 }];
const OCT_Y = 43.24;
const FN_X = [94.70, 104.46, 114.27, 124.15, 134.03, 143.80];
const FN_ROWS = [
  { y: 30.51, ids: ['FX', 'SEL', 'ENV', 'LFO', 'EDIT', 'GLO'] },
  { y: 40.20, ids: ['HOME', 'SAVE', 'ARP', 'SEQ', 'PLAY/STOP', 'REC'] },
];
const BEZEL = { x: 43.8, y: 6.6, w: 38, h: 36.3 };
const WHITE_X0 = 15.97, WHITE_PITCH = 8.957, WHITE_Y = 77.38, BLACK_Y = 62.15;
const WHITE = { w: 7.4, h: 16 }, BLACK = { w: 6.6, h: 11.5 };
// Semitones above F3 that are white keys; the rest are black.
const WHITE_STEPS = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26];
const COMBO = ['OP1', 'OP2', 'OP3', 'OP4', 'OP5', 'OP6', 'PIT', 'GLO', 'MONO', 'POLY', ''];
const REAR = [
  { label: 'POWER', x: 39.3, w: 7, kind: 'power' },
  { label: 'USB', x: 53.4, w: 8.9, kind: 'usb' },
  { label: 'MIDI IN', x: 64.3, w: 6, kind: 'jack' },
  { label: 'OUT', x: 76.8, w: 6, kind: 'jack' },
];

// Computer keys (event.code) for panel keys 0..18, F3..B4, laid out like a
// piano across two rows.
const KEYMAP = ['KeyA', 'KeyW', 'KeyS', 'KeyE', 'KeyD', 'KeyR', 'KeyF', 'KeyG', 'KeyY', 'KeyH',
  'KeyU', 'KeyJ', 'KeyK', 'KeyO', 'KeyL', 'KeyP', 'Semicolon', 'BracketLeft', 'Quote'];

const NOTE_NAMES = ['F', 'F#', 'G', 'G#', 'A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E'];
const keyName = (k) => `${NOTE_NAMES[k % 12]}${3 + Math.floor((k + 5) / 12)}`;

// ---- SVG ----------------------------------------------------------------------
const SVG = 'http://www.w3.org/2000/svg';
function el(name, attrs = {}, parent = null, text = null) {
  const e = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}

const panel = document.getElementById('panel');
const keyEls = [];
const buttonEls = [];
const encoderEls = {};
let masterEl = null;
let powerEl = null;

function drawPanel() {
  el('rect', { class: 'case', x: 0, y: 0, width: CASE.w, height: CASE.h, rx: CASE.r }, panel);
  el('rect', { class: 'case-inner', x: 1.2, y: 1.2, width: CASE.w - 2.4, height: CASE.h - 2.4, rx: CASE.r - 1 }, panel);

  for (const p of REAR) {
    el('text', { class: 'print small rear', x: p.x, y: -3.2 }, panel, p.label);
    if (p.kind === 'power') {
      powerEl = el('g', { class: 'power', role: 'button', tabindex: 0, 'aria-label': 'Power switch' }, panel);
      el('rect', { class: 'port', x: p.x - p.w / 2, y: -1.5, width: p.w, height: 2.2, rx: 0.6 }, powerEl);
      el('rect', { class: 'lever', x: p.x - p.w / 2 + 0.6, y: -1.1, width: 2.6, height: 1.4, rx: 0.4 }, powerEl);
    } else if (p.kind === 'usb') {
      el('rect', { class: 'port', x: p.x - p.w / 2, y: -1.2, width: p.w, height: 1.8, rx: 0.9 }, panel);
    } else {
      el('rect', { class: 'port', x: p.x - p.w / 2, y: -1.4, width: p.w, height: 2, rx: 0.5 }, panel);
      el('circle', { class: 'port-hole', cx: p.x, cy: -0.4, r: 0.9 }, panel);
    }
  }

  // MASTER (a potentiometer with an index mark) and the seven encoders.
  el('text', { class: 'print', x: MASTER.x, y: MASTER.y - 5.6 }, panel, 'MASTER');
  masterEl = knob(MASTER.x, MASTER.y, 'MASTER volume');
  masterEl.dataset.master = '1';
  masterEl.setAttribute('role', 'slider');
  masterEl.setAttribute('aria-valuemin', '0');
  masterEl.setAttribute('aria-valuemax', '100');
  for (const k of KNOBS) {
    el('text', { class: 'print', x: k.x, y: k.y - 5.6 }, panel, k.enc);
    const g = knob(k.x, k.y, `${k.enc} encoder`);
    g.dataset.encoder = String(ENCODERS.indexOf(k.enc));
    encoderEls[k.enc] = g;
  }

  el('rect', { class: 'bezel', x: BEZEL.x, y: BEZEL.y, width: BEZEL.w, height: BEZEL.h, rx: 3 }, panel);

  el('rect', { class: 'frame', x: 13.3, y: 39.7, width: 24.1, height: 7.1, rx: 2 }, panel);
  for (const o of OCT) button(o.id, o.x, OCT_Y, 9, 5.2);

  el('rect', { class: 'frame', x: 88.7, y: 24.6, width: 61.1, height: 21.5, rx: 3 }, panel);
  for (const row of FN_ROWS) row.ids.forEach((id, i) => button(id, FN_X[i], row.y, 7.2, 7.2));

  el('rect', { class: 'frame', x: 10.2, y: 54.4, width: 145.9, height: 33.3, rx: 4 }, panel);
  let white = 0;
  const whiteX = [];
  for (let s = 0; s < KEYS; ++s) if (WHITE_STEPS.includes(s)) whiteX[s] = WHITE_X0 + WHITE_PITCH * white++;
  let black = 0;
  for (let s = 0; s < KEYS; ++s) {
    const isWhite = WHITE_STEPS.includes(s);
    const x = isWhite ? whiteX[s] : (whiteX[s - 1] + whiteX[s + 1]) / 2;
    const y = isWhite ? WHITE_Y : BLACK_Y;
    const size = isWhite ? WHITE : BLACK;
    const g = el('g', {
      class: `key ${isWhite ? 'white' : 'black'}`, role: 'button', 'aria-label': `Key ${keyName(s)}`,
    }, panel);
    g.dataset.key = String(s);
    el('rect', { class: 'cap', x: x - size.w / 2, y: y - size.h / 2, width: size.w, height: size.h, rx: size.w / 2 }, g);
    const slotH = isWhite ? 6.5 : 4.6;
    el('rect', { class: 'slot', x: x - 0.5, y: y - size.h / 2 + 1.6, width: 1, height: slotH, rx: 0.5 }, g);
    if (!isWhite && COMBO[black]) el('text', { class: 'combo', x, y: y + size.h / 2 - 1.5 }, g, COMBO[black]);
    if (!isWhite) ++black;
    keyEls[s] = g;
  }
}

function knob(x, y, label) {
  const g = el('g', { class: 'knob', tabindex: 0, 'aria-label': label, transform: `translate(${x} ${y})` }, panel);
  el('circle', { class: 'body', r: KNOB_R }, g);
  el('circle', { class: 'ring', r: KNOB_R - 0.5 }, g);
  const rot = el('g', { class: 'rot' }, g);
  el('line', { class: 'mark', x1: 0, y1: -KNOB_R + 0.9, x2: 0, y2: -KNOB_R + 2.2 }, rot);
  g.dataset.angle = '0';
  return g;
}

function button(id, x, y, w, h) {
  const g = el('g', { class: 'btn', role: 'button', tabindex: 0, 'aria-label': id }, panel);
  g.dataset.button = String(BUTTONS.indexOf(id));
  el('rect', { class: 'cap', x: x - w / 2, y: y - h / 2, width: w, height: h, rx: 1.4 }, g);
  if (id === 'PLAY/STOP') {
    // 0.7 mm between each word and the divider (about 6 px on a desktop).
    el('text', { class: 'label two', x, y: y - 0.65 }, g, 'PLAY');
    el('line', { class: 'divider', x1: x - 2.1, x2: x + 2.1, y1: y + 0.05, y2: y + 0.05 }, g);
    el('text', { class: 'label two', x, y: y + 1.9 }, g, 'STOP');
  } else {
    el('text', { class: 'label', x, y: y + 0.65 }, g, id);
  }
  buttonEls[BUTTONS.indexOf(id)] = g;
  return g;
}

function setAngle(g, deg) {
  g.dataset.angle = String(deg);
  g.querySelector('.rot').setAttribute('transform', `rotate(${deg})`);
}

// ---- audio and the worklet -------------------------------------------------------
const tft = document.getElementById('tft');
const mirror = document.getElementById('tft-mirror');
const statusEl = document.getElementById('status');
const overlay = document.getElementById('power-overlay');
const selects = [document.getElementById('sel-sound'), document.getElementById('sel-fx1'),
  document.getElementById('sel-fx2')];
const image = new ImageData(240, 240);

const sim = {
  ctx: null, node: null, analyser: null, catalog: null, state: null, master: 0.75,
  requestedRate: null, screens: 0, midi: null, notice: '', lab: LAB, seq: null,
};
window.fm1 = sim;    // for the headless screenshot test and the console

// Macro, Macro Heavy and Six-Op run Plaits at 47,872.34 Hz and resample to
// the host, so they refuse faster hosts (engines/resampler.md).
const PLAITS_RATE = 47872;

function send(msg) { if (sim.node) sim.node.port.postMessage(msg); }

// The worklet and the module sit next to this script. Resolving them from
// it, not from the document, keeps them found wherever the page is served
// (a subdirectory, a static host that wraps the page, https or localhost).
const asset = (name) => new URL(name, import.meta.url).href;

async function makeContext() {
  let last = null;
  for (const rate of [44118, 44100]) {
    try {
      const ctx = new AudioContext({ latencyHint: 'interactive', sampleRate: rate });
      if (ctx.sampleRate <= PLAITS_RATE) {
        sim.requestedRate = rate;
        return ctx;
      }
      await ctx.close();          // the browser ignored the rate it was asked for
    } catch (err) {
      last = err;
    }
  }
  // Last resort, the device's own rate. Above 47,872 Hz the firmware starts
  // with the first sound that runs and says which ones refused.
  try {
    const ctx = new AudioContext({ latencyHint: 'interactive' });
    sim.requestedRate = null;
    return ctx;
  } catch (err) {
    throw last || err;
  }
}

// One start at a time: a second click while the first is still awaiting the
// worklet gets the same promise, not a second AudioContext.
let starting = null;
function powerOn() {
  if (sim.ctx) return Promise.resolve();
  if (!starting) starting = start().finally(() => { starting = null; });
  return starting;
}

async function start() {
  // Browsers hide AudioWorklet (and Web MIDI) from pages that are not a
  // secure context: plain http from another machine's address, say.
  if (!window.isSecureContext) {
    statusEl.textContent = 'This page needs a secure context for its audio: open it over https, ' +
      'or from http://localhost on the machine that serves it.';
    return;
  }
  if (!window.AudioWorkletNode) {
    statusEl.textContent = 'This browser has no AudioWorklet; the simulator needs it (and a page served over http://localhost or https).';
    return;
  }
  statusEl.textContent = 'Starting...';
  let ctx = null;
  try {
    ctx = await makeContext();
    await ctx.audioWorklet.addModule(asset('worklet.js'));
    const res = await fetch(asset('fm1.wasm'));
    if (!res.ok) throw new Error(`fm1.wasm: HTTP ${res.status}`);
    const wasm = await res.arrayBuffer();
    const node = new AudioWorkletNode(ctx, 'fm1', {
      numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [2],
    });
    node.port.onmessage = (e) => onWorklet(e.data, node);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    node.connect(ctx.destination);
    node.connect(analyser);
    Object.assign(sim, { ctx, node, analyser, notice: '' });
    node.port.postMessage({ type: 'init', wasm, master: sim.master, lab: LAB }, [wasm]);
    await ctx.resume();
    overlay.hidden = true;
    powerEl.classList.add('on');
    document.getElementById('power-off').disabled = false;
  } catch (err) {
    if (ctx && ctx !== sim.ctx && ctx.state !== 'closed') await ctx.close();
    await powerOff();
    statusEl.textContent = `Could not start audio: ${err.message || err}`;
  }
}

async function powerOff() {
  releaseEverything();
  if (sim.ctx) await sim.ctx.close();
  Object.assign(sim, { ctx: null, node: null, analyser: null, state: null, seq: null });
  overlay.hidden = false;
  powerEl.classList.remove('on');
  document.getElementById('power-off').disabled = true;
  for (const s of selects) s.disabled = true;
  for (const g of [...keyEls, ...buttonEls]) g.classList.remove('lit');
  for (const c of [tft, mirror]) c.getContext('2d').clearRect(0, 0, 240, 240);
  statusEl.textContent = 'Powered off.';
}

function onWorklet(m, node) {
  switch (m.type) {
    case 'ready':
      sim.catalog = m.catalog;
      fillSelects();
      if (m.imports.length) console.warn('fm1.wasm imports', m.imports);
      break;
    case 'seq':
      sim.seq = m;
      showStatus();
      break;
    case 'state':
      sim.state = m;
      selects.forEach((s, u) => { s.value = String(m.units[u]); });
      showStatus();
      break;
    case 'screen':
      drawScreen(m.px);
      // Hand the buffer back, so the audio thread reuses two buffers rather
      // than allocating 115 KB per screen.
      node.port.postMessage({ type: 'screen-buffer', buffer: m.px.buffer }, [m.px.buffer]);
      break;
    case 'leds':
      m.leds.forEach((on, i) => {
        const g = i < KEYS ? keyEls[i] : buttonEls[i - KEYS];
        if (g) g.classList.toggle('lit', on !== 0);
      });
      break;
    case 'refused': {
      const entry = sim.catalog && sim.catalog[m.index];
      const name = entry ? entry.name : `Engine ${m.index}`;
      const why = m.code === -2 ? 'it is too large for its slot'
        : m.code === -3 ? `it does not run at ${Math.round(m.rate).toLocaleString('en')} Hz ` +
          `(Macro, Macro Heavy and Six-Op need ${PLAITS_RATE.toLocaleString('en')} Hz or less)`
          : `error ${m.code}`;
      sim.notice = `${name} was refused: ${why}.` +
        (m.start ? ' The first sound that runs was loaded instead.' : '');
      showStatus();
      break;
    }
    case 'error':
      statusEl.textContent = `The firmware did not start: ${m.message}`;
      break;
    default:
      break;
  }
}

function fillSelects() {
  const sounds = sim.catalog.filter((e) => e.kind === 'sound');
  const fx = sim.catalog.filter((e) => e.kind === 'audio_fx');
  const opts = (list, none) => (none ? '<option value="-1">(none)</option>' : '') +
    list.map((e) => `<option value="${e.index}">${e.name}</option>`).join('');
  selects[0].innerHTML = opts(sounds, false);
  selects[1].innerHTML = opts(fx, true);
  selects[2].innerHTML = opts(fx, true);
  for (const s of selects) s.disabled = false;
}

selects.forEach((s, unit) => s.addEventListener('change', () => {
  sim.notice = '';
  send({ type: 'select', unit, index: Number(s.value) });
  // Give the keyboard back to the instrument: a focused select would turn
  // the note keys into type-ahead and pick another sound or effect.
  s.blur();
}));

function showStatus() {
  const st = sim.state;
  if (!sim.ctx || !st) return;
  const rate = sim.ctx.sampleRate;
  const fellBack = sim.requestedRate !== 44118 ? ` (the browser refused 44,118 Hz)` : '';
  const latency = sim.ctx.outputLatency || sim.ctx.baseLatency || 0;
  const ram = (b) => `${Math.ceil(b / 1024)} KB`;
  const q = sim.seq;
  const seq = LAB && q ? ` Sequencer: ${(q.bpm_x100 / 100).toFixed(2)} BPM, ` +
    `${q.recording ? 'recording' : q.counting_in ? 'counting in' : q.playing ? 'playing' : 'stopped'}` +
    `${q.following ? ' (external clock)' : ''}.` : '';
  statusEl.textContent = `Running at ${rate.toLocaleString('en')} Hz${fellBack}, 64-frame blocks, ` +
    `${(latency * 1000).toFixed(0)} ms output latency. Chain RAM ${ram(st.ram)} of the ` +
    `${ram(387924)} the stock layout leaves free.${seq}${sim.notice ? ' ' + sim.notice : ''}`;
}

function drawScreen(px) {
  const d = image.data;
  for (let i = 0; i < px.length; ++i) {
    const p = px[i];
    d[4 * i] = ((p >> 11) & 31) * 255 / 31;
    d[4 * i + 1] = ((p >> 5) & 63) * 255 / 63;
    d[4 * i + 2] = (p & 31) * 255 / 31;
    d[4 * i + 3] = 255;
  }
  tft.getContext('2d').putImageData(image, 0, 0);
  if (!document.getElementById('mirror').hidden) mirror.getContext('2d').putImageData(image, 0, 0);
  ++sim.screens;
}

// ---- pointer input ---------------------------------------------------------------
const active = new Map();   // pointerId -> release function
const scroller = document.getElementById('device-scroll');

// On a narrow screen the panel is wider than the page and scrolls sideways
// in its own box (style.css); dragging the case pans it, since the device
// takes every touch on the controls for itself.
function startPan(e) {
  if (scroller.scrollWidth <= scroller.clientWidth && e.pointerType !== 'touch') return;
  e.preventDefault();
  panel.setPointerCapture(e.pointerId);
  let lastX = e.clientX, lastY = e.clientY;
  const move = (ev) => {
    if (ev.pointerId !== e.pointerId) return;
    scroller.scrollLeft -= ev.clientX - lastX;
    if (ev.pointerType === 'touch') window.scrollBy(0, lastY - ev.clientY);
    lastX = ev.clientX;
    lastY = ev.clientY;
  };
  panel.addEventListener('pointermove', move);
  active.set(e.pointerId, () => panel.removeEventListener('pointermove', move));
}

panel.addEventListener('pointerdown', (e) => {
  // Playing the panel takes the keyboard back from a select or button.
  const focused = document.activeElement;
  if (focused && focused !== document.body && !panel.contains(focused) && focused.blur) focused.blur();
  const target = e.target.closest('[data-key], [data-button], [data-encoder], [data-master], .power');
  if (!target) {
    startPan(e);
    return;
  }
  e.preventDefault();
  if (target.classList.contains('power')) {
    if (sim.ctx) powerOff(); else powerOn();
    return;
  }
  if (!sim.node) return;
  target.setPointerCapture(e.pointerId);
  if (target.dataset.key !== undefined) {
    const key = Number(target.dataset.key);
    const r = target.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
    send({ type: 'key', key, down: true, velocity: Math.round(30 + 97 * frac) });
    active.set(e.pointerId, () => send({ type: 'key', key, down: false }));
  } else if (target.dataset.button !== undefined) {
    const button = Number(target.dataset.button);
    target.classList.add('down');
    send({ type: 'button', button, down: true });
    active.set(e.pointerId, () => {
      target.classList.remove('down');
      send({ type: 'button', button, down: false });
    });
  } else {
    let lastY = e.clientY;
    let acc = 0;
    const isMaster = target.dataset.master !== undefined;
    const move = (ev) => {
      if (ev.pointerId !== e.pointerId) return;
      const dy = lastY - ev.clientY;
      lastY = ev.clientY;
      if (isMaster) {
        setMaster(sim.master + dy / 180);
      } else {
        acc += dy;
        const detents = Math.trunc(acc / 6);
        if (detents) {
          acc -= detents * 6;
          turn(target, detents);
        }
      }
    };
    target.addEventListener('pointermove', move);
    active.set(e.pointerId, () => target.removeEventListener('pointermove', move));
  }
});

for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
  panel.addEventListener(type, (e) => {
    const release = active.get(e.pointerId);
    if (release) {
      active.delete(e.pointerId);
      release();
    }
  });
}

// Scrolling over an encoder: the first wheel event of a gesture turns it one
// detent at once (a single mouse notch, however small its delta), then the
// gesture turns one detent per 60 px of vertical scroll, at most one per
// event, so a trackpad flick or a fast wheel does not race the encoder.
// Horizontal scrolling turns nothing.
const WHEEL_DETENT_PX = 60;
const WHEEL_GESTURE_GAP_MS = 200;
const wheel = { target: null, acc: 0, last: -Infinity };

panel.addEventListener('wheel', (e) => {
  const target = e.target.closest('[data-encoder], [data-master]');
  if (!target || !sim.node) return;
  e.preventDefault();
  if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  const px = e.deltaY * (e.deltaMode === 1 ? 100 / 3 : e.deltaMode === 2 ? 300 : 1);
  const fresh = target !== wheel.target || e.timeStamp - wheel.last > WHEEL_GESTURE_GAP_MS;
  wheel.last = e.timeStamp;
  let dir = 0;
  if (fresh) {
    wheel.target = target;
    wheel.acc = 0;
    dir = px < 0 ? 1 : -1;
  } else {
    if (Math.sign(px) !== Math.sign(wheel.acc)) wheel.acc = 0;
    wheel.acc += px;
    if (Math.abs(wheel.acc) >= WHEEL_DETENT_PX) {
      dir = wheel.acc < 0 ? 1 : -1;
      wheel.acc = Math.sign(wheel.acc) * Math.min(Math.abs(wheel.acc) - WHEEL_DETENT_PX, WHEEL_DETENT_PX - 1);
    }
  }
  if (!dir) return;
  if (target.dataset.master !== undefined) setMaster(sim.master + dir * 0.02);
  else turn(target, dir);
}, { passive: false });

function turn(g, delta) {
  send({ type: 'encoder', encoder: Number(g.dataset.encoder), delta });
  setAngle(g, Number(g.dataset.angle) + 15 * delta);
}

function setMaster(pos) {
  sim.master = Math.min(1, Math.max(0, pos));
  setAngle(masterEl, -150 + 300 * sim.master);
  masterEl.setAttribute('aria-valuenow', String(Math.round(sim.master * 100)));
  send({ type: 'master', position: sim.master, show: true });
}

// ---- keyboard ---------------------------------------------------------------------
// Each held computer key remembers what it pressed, so its release reaches
// the same key or button whatever has focus or which modifiers are down by
// then.
const heldKeys = new Map();   // event.code -> release function
const OCT_KEYS = { KeyZ: 'OCT-', KeyX: 'OCT+' };
// Lab, SEQ mode (the owner's decision O19 in docs/15): the 16 steps, white
// keys 1-16, on keys the instrument does not use, and Shift as SEL (SHIFT).
const STEP_KEYS = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8',
  'KeyC', 'KeyV', 'KeyB', 'KeyN', 'KeyM', 'Comma', 'Period', 'Slash'];
const SEQ_MODE = 3;
const inSeq = () => LAB && sim.state && sim.state.mode === SEQ_MODE;

function releaseKeys() {
  const releases = [...heldKeys.values()];
  heldKeys.clear();
  for (const release of releases) release();
}

// Window blur, a hidden tab, power off: let go of everything held, keys,
// buttons and pointers, or the firmware keeps them down (a held OCT button
// turns ALGORITHM into transpose; a held FX swallows the next press).
function releaseEverything() {
  releaseKeys();
  const releases = [...active.values()];
  active.clear();
  for (const release of releases) release();
}

function hold(code, down, up) {
  if (heldKeys.has(code)) return;
  down();
  heldKeys.set(code, up);
}

function keydown(e) {
  // macOS does not deliver the keyup of a key released while Cmd is down,
  // so Cmd lets go of every held key first.
  if (e.key === 'Meta') { releaseKeys(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey) return;     // browser and system shortcuts
  if (e.target.closest && e.target.closest('select, input, textarea')) return;
  const focused = document.activeElement;
  if (focused && focused.dataset && (focused.dataset.encoder !== undefined || focused.dataset.master !== undefined) &&
      ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) {
    const d = e.code === 'ArrowUp' || e.code === 'ArrowRight' ? 1 : -1;
    if (focused.dataset.master !== undefined) setMaster(sim.master + d * 0.02); else turn(focused, d);
    e.preventDefault();
    return;
  }
  if (focused && focused.dataset && focused.dataset.button !== undefined && (e.code === 'Enter' || e.code === 'Space')) {
    e.preventDefault();
    if (e.repeat) return;
    const g = focused;
    const button = Number(g.dataset.button);
    hold(e.code, () => { g.classList.add('down'); send({ type: 'button', button, down: true }); },
      () => { g.classList.remove('down'); send({ type: 'button', button, down: false }); });
    return;
  }
  // Lab: Space is PLAY/STOP, unless a button (the panel's, handled above,
  // the page's or the power switch) has focus and Space presses that.
  if (LAB && e.code === 'Space' && !(focused && (focused.tagName === 'BUTTON' ||
      (focused.classList && focused.classList.contains('power'))))) {
    e.preventDefault();
    if (e.repeat) return;
    const button = BUTTONS.indexOf('PLAY/STOP');
    const g = buttonEls[button];
    hold(e.code, () => { g.classList.add('down'); send({ type: 'button', button, down: true }); },
      () => { g.classList.remove('down'); send({ type: 'button', button, down: false }); });
    return;
  }
  // Lab, SEQ mode: Shift holds SEL, which is SHIFT there; the step keys
  // press white keys 1-16. Their releases go where the press went, whatever
  // the mode is by then.
  if (inSeq() && (e.code === 'ShiftLeft' || e.code === 'ShiftRight')) {
    e.preventDefault();
    if (e.repeat) return;
    const button = BUTTONS.indexOf('SEL');
    const g = buttonEls[button];
    hold(e.code, () => { g.classList.add('down'); send({ type: 'button', button, down: true }); },
      () => { g.classList.remove('down'); send({ type: 'button', button, down: false }); });
    return;
  }
  const step = inSeq() ? STEP_KEYS.indexOf(e.code) : -1;
  if (step >= 0) {
    e.preventDefault();
    if (e.repeat) return;
    const key = WHITE_STEPS[step];
    hold(e.code, () => send({ type: 'key', key, down: true, velocity: 100 }),
      () => send({ type: 'key', key, down: false }));
    return;
  }
  const k = KEYMAP.indexOf(e.code);
  if (k >= 0) {
    e.preventDefault();
    if (e.repeat) return;
    hold(e.code, () => send({ type: 'key', key: k, down: true, velocity: 100 }),
      () => send({ type: 'key', key: k, down: false }));
    return;
  }
  if (OCT_KEYS[e.code]) {
    e.preventDefault();
    if (e.repeat) return;
    const button = BUTTONS.indexOf(OCT_KEYS[e.code]);
    hold(e.code, () => send({ type: 'button', button, down: true }),
      () => send({ type: 'button', button, down: false }));
    return;
  }
  const encoders = {
    ArrowLeft: ['SELECT', -1], ArrowRight: ['SELECT', 1], ArrowUp: ['PRESETS', 1],
    ArrowDown: ['PRESETS', -1], Minus: ['ALGORITHM', -1], Equal: ['ALGORITHM', 1],
  };
  if (encoders[e.code]) {
    e.preventDefault();
    const [name, d] = encoders[e.code];
    turn(encoderEls[name], d);
    return;
  }
  if (e.code === 'Escape') {
    releaseKeys();
    send({ type: 'panic' });
  }
}

function keyup(e) {
  if (e.key === 'Meta') { releaseKeys(); return; }
  const release = heldKeys.get(e.code);
  if (!release) return;
  heldKeys.delete(e.code);
  release();
  e.preventDefault();
}

window.addEventListener('keydown', keydown);
window.addEventListener('keyup', keyup);
window.addEventListener('blur', releaseEverything);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') releaseEverything();
});

// ---- Web MIDI -----------------------------------------------------------------------
async function connectMidi() {
  const btn = document.getElementById('midi');
  if (!navigator.requestMIDIAccess) {
    statusEl.textContent = 'This browser has no Web MIDI.';
    return;
  }
  try {
    const access = await navigator.requestMIDIAccess();
    const attach = () => {
      const names = [];
      for (const input of access.inputs.values()) {
        input.onmidimessage = onMidi;
        names.push(input.name);
      }
      btn.textContent = names.length ? `MIDI: ${names.join(', ')}` : 'MIDI: no inputs';
    };
    access.onstatechange = attach;
    attach();
    sim.midi = access;
  } catch (err) {
    statusEl.textContent = `MIDI was not allowed: ${err.message || err}`;
  }
}

function onMidi(e) {
  const [status, a = 0, b = 0] = e.data;
  const type = status & 0xf0;
  if (type === 0x90 && b > 0) send({ type: 'note-on', note: a, velocity: b });
  else if (type === 0x80 || (type === 0x90 && b === 0)) send({ type: 'note-off', note: a });
  else if (type === 0xe0) send({ type: 'bend', semitones: (((b << 7) | a) - 8192) / 8192 * 2 });
  else if (type === 0xb0 && a === 7) setMaster(b / 127);
  else if (type === 0xb0 && a === 123) send({ type: 'panic' });
}

// On a narrow screen the panel opens scrolled just far enough to show the
// whole screen: the case's left edge, which has no controls, goes first.
function revealScreen() {
  if (scroller.scrollWidth <= scroller.clientWidth) return;
  const need = tft.getBoundingClientRect().right + 8 - scroller.getBoundingClientRect().right;
  if (need > 0) scroller.scrollLeft += need;
}

// ---- wiring --------------------------------------------------------------------------
if (LAB) {
  for (const e of document.querySelectorAll('[data-lab]')) e.hidden = false;
  for (const e of document.querySelectorAll('[data-lab-off]')) e.hidden = true;
}
drawPanel();
setAngle(masterEl, -150 + 300 * sim.master);
revealScreen();
document.getElementById('power-on').addEventListener('click', powerOn);
document.getElementById('power-off').addEventListener('click', powerOff);
document.getElementById('midi').addEventListener('click', connectMidi);
document.getElementById('zoom').addEventListener('click', (e) => {
  const box = document.getElementById('mirror');
  box.hidden = !box.hidden;
  e.currentTarget.setAttribute('aria-pressed', String(!box.hidden));
  if (!box.hidden) mirror.getContext('2d').putImageData(image, 0, 0);
});
powerEl.addEventListener('keydown', (e) => {
  if (e.code === 'Enter' || e.code === 'Space') {
    e.preventDefault();
    if (sim.ctx) powerOff(); else powerOn();
  }
});
if (window.matchMedia('(max-width: 720px)').matches) document.getElementById('zoom').click();
