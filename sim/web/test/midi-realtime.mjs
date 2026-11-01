// Run after the actual WASM rebuild: node sim/web/test/midi-realtime.mjs [WASM].
// Exercises the real worklet's dispatcher with the native sequencer exports.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { instantiateFm1 } from '../www/fm1-wasm.mjs';
let Processor;
globalThis.sampleRate = 48000;
globalThis.AudioWorkletProcessor = class { constructor() { this.port = { postMessage() {} }; } };
globalThis.registerProcessor = (_, cls) => { Processor = cls; };
await import('../www/worklet.js');
const fm1 = await instantiateFm1(await readFile(process.argv[2] || new URL('../www/fm1.wasm', import.meta.url)));
const ex = fm1.exports;
assert.equal(typeof ex.fm1w_seq_realtime, 'function', 'Rebuild actual WASM with the realtime bridge first');
ex.fm1w_init(48000);
assert.equal(ex.fm1w_default_chain(), 0);
const p = new Processor(); p.fm1 = fm1; p.sendState = () => {};
const line = text => {
  const bytes = new TextEncoder().encode(text);
  new Uint8Array(fm1.memory.buffer, ex.fm1w_text_buf(), bytes.length).set(bytes);
  assert.equal(ex.fm1w_seq_text(bytes.length), bytes.length, text);
};
const info = () => [...new Uint32Array(fm1.memory.buffer, ex.fm1w_seq_info(), ex.fm1w_seq_words())];
const render = (frames=64) => { for (let off=0; off<frames; off+=64) { p.drainInputs(); ex.fm1w_render(Math.min(64,frames-off)); } };
const rt = status => p.dispatch({type:'rt',status});
line('link 0; bpm 12000; play'); render(4096);
const before = info();
for (const status of [0xfa,0xfb,0xfc,0xf8]) rt(status);
assert.deepEqual(info(), before, 'Default internal clock must ignore incoming realtime entirely');
for (let i=0;i<24;++i) { render(960); rt(0xf8); }
assert.equal(info()[1], 12000); assert.equal(info()[0], 1);
console.log('PASS internal clock ignores incoming realtime transport and tempo');
line('stop'); render(); line('link 1'); render();
rt(0xfa); render(); assert.equal(info()[0], 1, 'Start starts linked transport');
rt(0xf8);
for (let i=0;i<24;++i) { render(960); rt(0xf8); }
render();
assert.equal(info()[5], 1, 'Native clock follows incoming ticks');
assert.ok(Math.abs(info()[1]-12500)<100, `native EMA tempo ${info()[1]}`);
assert.ok(info()[6]>0);
line('pause'); render(); const paused = info(); assert.equal(paused[56], 1);
rt(0xfb); assert.equal(info()[56], 0); assert.equal(info()[6], paused[6], 'Continue retains position');
rt(0xfa); assert.equal(info()[6], 0, 'Start resets position');
render(); rt(0xfc); render(); assert.equal(info()[0], 0, 'Stop stops linked transport');
assert.equal(ex.fm1w_seq_dropped(), 0, 'No native events dropped');
console.log('PASS linked native clock, tempo, Start versus Continue, and Stop');
// Sounding sequencer gates: Stop should match the native Stop verb exactly,
// including its note-offs (the default demo chain has no post-stop effects).
const catalog = JSON.parse(fm1.string(ex.fm1w_catalog()));
const sine = catalog.findIndex(e => e.id === 'test-sine'); assert.ok(sine>=0);
assert.equal(ex.fm1w_select(0,sine),0);
line('tog 0 0 60 100'); render(); rt(0xfa); rt(0xf8); render(64);
rt(0xfc); render(48000);
const out = new Float32Array(fm1.memory.buffer, ex.fm1w_render(64),128);
assert.ok(out.every(x => Math.abs(x)<1e-6), 'Stop releases sequencer notes');
assert.equal(ex.fm1w_seq_dropped(),0);
console.log('PASS Stop releases sounding native sequencer notes');
