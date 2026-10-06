// worklet.js -- the virtual FM-1's audio thread. One fm1.wasm instance runs
// the whole firmware here (the stock FM-1 renders its voices on its second
// core and the UI and effects on the first, docs/11 section 2): panel
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
//
// The module's start chain loads the demo pattern (owner decision O4), and
// once per quantum the worklet reads the sequencer's transport
// (fm1w_seq_info) and posts it only when it changed: a song's end, an
// external clock's stop or a new tempo reach the status line without a
// message per event. The page's Sound dropdown is the current sound's
// (multi-sound, docs/15 §3.16), and follows the panel. A .syx file the page
// read (Load DX7 patches) arrives as its bytes and goes to the firmware
// through the module's text buffer (fm1w_dx7_load); what it held goes back
// for the page's message.
//
// Saved state (stage W1, notes/2026-10-06-state-files.md §12): the audio
// thread reads and writes only the binary container. `state-save` hands the
// page the whole project as binary (fm1w_state_save); the page's shadow
// Worker (shadow.worker.js) turns it into JSON, checks files against it
// (pass 1) and packs them, and `state-load` takes the packed file and runs
// fm1w_state_load (pass 1 again, then pass 2). Anything that is not the
// binary container is refused here, so JSON is never parsed on this thread
// (the editor's ED3 and ED13). Reports go back as the module's JSON text,
// unparsed. SAVE on the panel is fm1w_save_gen counting up, posted as
// `save-pressed`; the page's store answers with `saved`. Nothing here
// reaches a device.
// MIT licence, like the rest of this repository.

import { instantiateFm1, BLOCK, SCREEN, KEYS, BUTTONS } from './fm1-wasm.mjs';

const SCREEN_EVERY = 4;          // quanta between screen checks (~12 ms)
const LIVE_FRAMES = 1470;        // a live scope redraws at most every ~33 ms
const SCREEN_BUFFERS = 2;
const LEDS = KEYS + BUTTONS.length;
const SEQ_WATCHED = 6;           // fm1w_seq_info's words compared each quantum

class FM1Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.fm1 = null;
    this.pending = [];
    this.quanta = 0;
    this.views = null;
    this.free = [];              // screen buffers not with the page
    this.soundLast = 0;
    this.seqLast = new Uint32Array(SEQ_WATCHED);
    this.seqLast[1] = 0xffffffff;   // nothing posted yet
    this.saveGen = 0;
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
        this.saveGen = ex.fm1w_save_gen();
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
      case 'dx7-load': this.loadDx7(m); break;
      case 'state-save': this.stateSave(m); break;
      case 'state-load': this.stateLoad(m); break;
      case 'seq-line': this.seqLine(m.bytes); break;
      case 'store-ready': ex.fm1w_store_ready(m.on ? 1 : 0); break;
      case 'saved': {
        // A refusal's reason goes in the text buffer, NUL-terminated.
        if (!m.ok && m.reason instanceof Uint8Array) {
          const cap = ex.fm1w_text_cap();
          const b = new Uint8Array(this.fm1.memory.buffer, ex.fm1w_text_buf(), cap);
          const n = Math.min(m.reason.length, 63);
          b.set(m.reason.subarray(0, n));
          b[n] = 0;
        }
        ex.fm1w_saved(m.ok ? 1 : 0);
        break;
      }
      case 'select': {
        // The Sound dropdown is the current sound's (multi-sound, docs/15
        // §3.16); the others are the master slots, units 1 and 2.
        const unit = m.unit === 0 ? ex.fm1w_sound_unit(ex.fm1w_unit_current()) : m.unit;
        const r = ex.fm1w_select(unit, m.index);
        if (r !== 0) {
          this.port.postMessage({ type: 'refused', unit: m.unit, index: m.index, code: r, rate: sampleRate });
        }
        break;
      }
      default: break;
    }
    this.sendState();
  }

  // A .syx file's bytes into FM6's user bank; the current sound then plays
  // the first voice (fm1w_dx7_load with play). The page refuses larger files
  // before sending; a length past the buffer would be refused here too.
  loadDx7(m) {
    const ex = this.fm1.exports;
    const cap = ex.fm1w_text_cap();
    const bytes = m.bytes instanceof Uint8Array ? m.bytes : new Uint8Array(0);
    const len = bytes.length > cap ? cap + 1 : bytes.length;
    if (len <= cap) new Uint8Array(this.fm1.memory.buffer, ex.fm1w_text_buf(), cap).set(bytes);
    ex.fm1w_dx7_load(len, 1);
    const result = Array.from(new Int32Array(this.fm1.memory.buffer, ex.fm1w_dx7_result(), 13));
    const names = [];
    for (let k = 0; k < 32; ++k) names.push(this.fm1.string(ex.fm1w_dx7_name(k)));
    this.port.postMessage({ type: 'dx7-loaded', file: m.file, size: bytes.length, result, names });
  }

  // The text buffer, as a view (the module's memory never grows).
  text() {
    const ex = this.fm1.exports;
    return new Uint8Array(this.fm1.memory.buffer, ex.fm1w_text_buf(), ex.fm1w_text_cap());
  }

  // The whole project (or m.kind with m.arg) as the binary container.
  stateSave(m) {
    const ex = this.fm1.exports;
    const n = ex.fm1w_state_save(m.kind || 1, m.arg | 0, 1);
    const bytes = n > 0 ? this.text().slice(0, n) : null;
    this.port.postMessage({
      type: 'state-saved', id: m.id, ok: n > 0, bytes,
      report: n > 0 ? null : this.fm1.string(ex.fm1w_state_report()),
    }, bytes ? [bytes.buffer] : []);
  }

  // A packed file: binary only (the shadow Worker packed it and ran pass 1).
  stateLoad(m) {
    const ex = this.fm1.exports;
    const b = m.bytes;
    const binary = b instanceof Uint8Array && b.length >= 6 && b[0] === 0x89 && b[1] === 0x4c;
    if (!binary || b.length > ex.fm1w_text_cap()) {
      this.port.postMessage({ type: 'state-loaded', id: m.id, ok: false, binary, report: null });
      return;
    }
    this.text().set(b);
    const ok = ex.fm1w_state_load(m.kind | 0, m.into | 0, m.slot | 0, m.flags | 0, b.length) === 1;
    this.port.postMessage({ type: 'state-loaded', id: m.id, ok, binary, report: this.fm1.string(ex.fm1w_state_report()) });
  }

  // One sequencer verb (a link's play and entry hints): bytes, not a string.
  seqLine(bytes) {
    if (!(bytes instanceof Uint8Array) || !bytes.length) return;
    const ex = this.fm1.exports;
    if (bytes.length > 256) return;
    this.text().set(bytes);
    ex.fm1w_seq_text(bytes.length);
  }

  sendState() {
    const ex = this.fm1.exports;
    // The dropdowns: the current sound and the two master slots.
    const current = ex.fm1w_unit_current();
    const units = [ex.fm1w_sound_unit(current), 1, 2];
    this.port.postMessage({
      type: 'state',
      units: units.map((u) => ex.fm1w_unit_index(u)),
      bytes: units.map((u) => ex.fm1w_unit_bytes(u)),
      ram: ex.fm1w_ram(),
      budget: ex.fm1w_ram_budget(),
      mode: ex.fm1w_mode(),
      sound: current,
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
      seq: new Uint32Array(mem, ex.fm1w_seq_info(), 8),
    };
    return this.views;
  }

  // The transport, posted only when it changed.
  postSeq(v) {
    this.fm1.exports.fm1w_seq_info();       // refreshes v.seq
    const s = v.seq, last = this.seqLast;
    let changed = false;
    for (let i = 0; i < SEQ_WATCHED; ++i) {
      if (s[i] !== last[i]) { last[i] = s[i]; changed = true; }
    }
    if (!changed) return;
    this.port.postMessage({
      type: 'seq', playing: s[0] !== 0, bpm_x100: s[1], recording: s[2] !== 0, watch_track: s[3],
      counting_in: s[4] !== 0, following: s[5] !== 0, master_tick: s[6] + s[7] * 4294967296,
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
    this.postSeq(v);
    // The panel changes the current sound (SHIFT + PRESETS) without a
    // message from the page: the dropdown follows it.
    const current = ex.fm1w_unit_current();
    if (current !== this.soundLast) {
      this.soundLast = current;
      this.sendState();
    }
    const gen = ex.fm1w_save_gen();
    if (gen !== this.saveGen) {           // SAVE pressed on the panel
      this.saveGen = gen;
      this.port.postMessage({ type: 'save-pressed', gen });
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
