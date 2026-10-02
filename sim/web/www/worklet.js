// worklet.js -- the virtual FM-1's audio thread. One fm1.wasm instance runs
// the whole firmware here, as the FM-1 runs UI and audio on one core: panel
// input arrives as port messages between render quanta (so at block
// boundaries), each 128-frame quantum is rendered as two 64-frame host
// blocks, and the screen and LEDs go back to the page when they change.
// MIT licence, like the rest of this repository.

import { instantiateFm1, BLOCK, SCREEN } from './fm1-wasm.mjs';

const SCREEN_EVERY = 4;          // quanta between screen checks (~12 ms)
const LIVE_FRAMES = 1470;        // a live scope redraws at most every ~33 ms

class FM1Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.fm1 = null;
    this.pending = [];
    this.quanta = 0;
    this.port.onmessage = (e) => this.onMessage(e.data);
  }

  async onMessage(m) {
    if (m.type === 'init') {
      try {
        const fm1 = await instantiateFm1(m.wasm);
        const ex = fm1.exports;
        ex.fm1w_init(sampleRate);
        ex.fm1w_default_chain();
        ex.fm1w_master(m.master, 0);
        this.fm1 = fm1;
        this.port.postMessage({
          type: 'ready',
          rate: sampleRate,
          catalog: JSON.parse(fm1.string(ex.fm1w_catalog())),
          imports: fm1.imports,
        });
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
        if (r !== 0) this.port.postMessage({ type: 'refused', unit: m.unit, index: m.index, code: r });
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
    for (let off = 0; off < left.length; off += BLOCK) {
      const n = Math.min(BLOCK, left.length - off);
      const lr = new Float32Array(this.fm1.memory.buffer, ex.fm1w_render(n), 2 * n);
      for (let i = 0; i < n; ++i) {
        left[off + i] = lr[2 * i];
        right[off + i] = lr[2 * i + 1];
      }
    }
    if (ex.fm1w_leds_changed()) {
      const leds = new Uint8Array(this.fm1.memory.buffer, ex.fm1w_leds(), 41).slice();
      this.port.postMessage({ type: 'leds', leds }, [leds.buffer]);
    }
    if (++this.quanta % SCREEN_EVERY === 0 && ex.fm1w_draw(LIVE_FRAMES)) {
      const px = new Uint16Array(this.fm1.memory.buffer, ex.fm1w_screen(), SCREEN * SCREEN).slice();
      this.port.postMessage({ type: 'screen', px }, [px.buffer]);
    }
    return true;
  }
}

registerProcessor('fm1', FM1Processor);
