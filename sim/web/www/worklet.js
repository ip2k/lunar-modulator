// worklet.js -- the virtual FM-1's audio thread. One fm1.wasm instance runs
// the whole firmware here, as the FM-1 runs UI and audio on one core: panel
// input arrives as port messages between render quanta (so at block
// boundaries), each 128-frame quantum is rendered as two 64-frame host
// blocks, and the screen and LEDs go back to the page when they change.
//
// process() allocates as little as it can: the module's memory never grows
// (-sALLOW_MEMORY_GROWTH=0), so the views on its output, LEDs and screen are
// made once, and screens travel in two buffers that the page hands back
// after drawing. A screen waits (the firmware keeps it dirty) while both are
// with the page. Posting a message still allocates its envelope, and an LED
// change (a few a second) copies its 41 bytes.
// MIT licence, like the rest of this repository.

import { instantiateFm1, BLOCK, SCREEN, KEYS, BUTTONS } from './fm1-wasm.mjs';

const SCREEN_EVERY = 4;          // quanta between screen checks (~12 ms)
const LIVE_FRAMES = 1470;        // a live scope redraws at most every ~33 ms
const SCREEN_BUFFERS = 2;
const LEDS = KEYS + BUTTONS.length;

class FM1Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.fm1 = null;
    this.pending = [];
    this.quanta = 0;
    this.views = null;
    this.free = [];              // screen buffers not with the page
    this.port.onmessage = (e) => this.onMessage(e.data);
  }

  async onMessage(m) {
    if (m.type === 'screen-buffer') {
      this.free.push(new Uint16Array(m.buffer));
      return;
    }
    if (m.type === 'init') {
      try {
        const fm1 = await instantiateFm1(m.wasm);
        const ex = fm1.exports;
        ex.fm1w_init(sampleRate);
        const chain = ex.fm1w_default_chain();
        ex.fm1w_master(m.master, 0);
        this.fm1 = fm1;
        this.free = Array.from({ length: SCREEN_BUFFERS }, () => new Uint16Array(SCREEN * SCREEN));
        const catalog = JSON.parse(fm1.string(ex.fm1w_catalog()));
        this.port.postMessage({ type: 'ready', rate: sampleRate, catalog, imports: fm1.imports });
        if (chain !== 0) {         // e.g. Macro at a host rate above 47,872 Hz
          const index = catalog.findIndex((e) => e.id === 'macro');
          this.port.postMessage({ type: 'refused', unit: 0, index, code: chain, rate: sampleRate, start: true });
        }
        for (const p of this.pending) this.apply(p);
        this.pending = [];
        this.sendState();
      } catch (err) {
        this.port.postMessage({ type: 'error', message: String(err && err.message || err) });
      }
      return;
    }
    if (this.fm1) this.apply(m); else this.pending.push(m);
  }

  apply(m) {
    const ex = this.fm1.exports;
    switch (m.type) {
      case 'key': ex.fm1w_key(m.key, m.down ? 1 : 0, m.velocity | 0); break;
      case 'button': ex.fm1w_button(m.button, m.down ? 1 : 0); break;
      case 'encoder': ex.fm1w_encoder(m.encoder, m.delta | 0); break;
      case 'master': ex.fm1w_master(m.position, m.show ? 1 : 0); break;
      case 'note-on': ex.fm1w_note_on(m.note, m.velocity); break;
      case 'note-off': ex.fm1w_note_off(m.note); break;
      case 'bend': ex.fm1w_pitch_bend(m.semitones); break;
      case 'param': ex.fm1w_set_param(m.unit, m.index, m.value); break;
      case 'panic': ex.fm1w_all_notes_off(); break;
      case 'select': {
        const r = ex.fm1w_select(m.unit, m.index);
        if (r !== 0) this.port.postMessage({ type: 'refused', unit: m.unit, index: m.index, code: r, rate: sampleRate });
        break;
      }
      default: break;
    }
    this.sendState();
  }

  sendState() {
    const ex = this.fm1.exports;
    this.port.postMessage({
      type: 'state',
      units: [0, 1, 2].map((u) => ex.fm1w_unit_index(u)),
      bytes: [0, 1, 2].map((u) => ex.fm1w_unit_bytes(u)),
      ram: ex.fm1w_ram(),
      mode: ex.fm1w_mode(),
    });
  }

  // Views on the module's memory: made once, again only if it ever moved.
  getViews(outPtr) {
    const v = this.views;
    const mem = this.fm1.memory.buffer;
    if (v && v.mem === mem && v.outPtr === outPtr) return v;
    const ex = this.fm1.exports;
    this.views = {
      mem,
      outPtr,
      out: new Float32Array(mem, outPtr, 2 * BLOCK),
      leds: new Uint8Array(mem, ex.fm1w_leds(), LEDS),
      screen: new Uint16Array(mem, ex.fm1w_screen(), SCREEN * SCREEN),
    };
    return this.views;
  }

  process(inputs, outputs) {
    const out = outputs[0];
    const left = out[0];
    const right = out[1] || out[0];
    if (!this.fm1) {
      left.fill(0);
      right.fill(0);
      return true;
    }
    const ex = this.fm1.exports;
    let v = null;
    for (let off = 0; off < left.length; off += BLOCK) {
      const n = Math.min(BLOCK, left.length - off);
      v = this.getViews(ex.fm1w_render(n));   // always the app's one buffer
      const lr = v.out;
      for (let i = 0; i < n; ++i) {
        left[off + i] = lr[2 * i];
        right[off + i] = lr[2 * i + 1];
      }
    }
    if (ex.fm1w_leds_changed()) {
      const leds = v.leds.slice();
      this.port.postMessage({ type: 'leds', leds }, [leds.buffer]);
    }
    if (++this.quanta % SCREEN_EVERY === 0 && this.free.length && ex.fm1w_draw(LIVE_FRAMES)) {
      const px = this.free.pop();
      px.set(v.screen);
      this.port.postMessage({ type: 'screen', px }, [px.buffer]);
    }
    return true;
  }
}

registerProcessor('fm1', FM1Processor);
