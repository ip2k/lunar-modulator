// Web MIDI parsing and actual AudioWorklet message/queue code, without DSP.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../www/app.js', import.meta.url), 'utf8');
const onMidi = source.slice(source.indexOf('function onMidi('), source.indexOf('// On a narrow screen', source.indexOf('function onMidi(')));
function page() {
  const sent = [], learned = [];
  const context = vm.createContext({ send: m => sent.push(m), setMaster: value => sent.push({ master: value }),
    midiLearn: { handle: (id, data) => { learned.push([...data]); return false; } } });
  vm.runInContext(onMidi, context);
  return { sent, learned, emit: data => context.onMidi({ data }, 'controller') };
}

test('only the four exact single-byte realtime statuses bypass MIDI learn', () => {
  const p = page();
  for (const b of [0xf8, 0xfa, 0xfb, 0xfc]) p.emit(new Uint8Array([b]));
  assert.equal(p.learned.length, 0);
  assert.deepEqual(p.sent.map(m => m.status), [0xf8, 0xfa, 0xfb, 0xfc]);
  for (const data of [[], [0xf8, 1], [0xf9], [0xfe], [0xff], [0x90], [0x90, 60], [0x90, 60, 128], [0, 60, 127]]) p.emit(data);
  p.emit(null);
  assert.equal(p.sent.length, 4);
});

test('realtime and channel input retain arrival order, with note-on zero as note-off', () => {
  const p = page();
  for (const data of [[0xfa], [0x90, 60, 100], [0xf8], [0x90, 60, 0], [0xfc]]) p.emit(data);
  assert.deepEqual(p.sent.map(m => m.type), ['rt', 'note-on', 'rt', 'note-off', 'rt']);
});

let Processor;
globalThis.sampleRate = 48000;
globalThis.AudioWorkletProcessor = class { constructor() { this.port = { messages: [], postMessage(m) { this.messages.push(m); } }; } };
globalThis.registerProcessor = (name, cls) => { Processor = cls; };
await import('../www/worklet.js');
function worklet() {
  const p = new Processor(), calls = [];
  p.sendState = () => {};
  let room = true;
  p.fm1 = { exports: {
    fm1w_seq_realtime: s => { if (!room) return 0; calls.push(`rt:${s}`); return 1; },
    fm1w_note_on: (n, v) => calls.push(`on:${n}:${v}`), fm1w_note_off: n => calls.push(`off:${n}`),
    fm1w_all_notes_off: () => calls.push('panic')
  } };
  return { p, calls, room: value => { room = value; } };
}

test('native backpressure holds following notes; retry preserves every message once', () => {
  const { p, calls, room } = worklet();
  room(false);
  for (const m of [{type:'rt', status:0xfa}, {type:'note-on',note:60,velocity:100}, {type:'rt',status:0xf8}, {type:'note-off',note:60}, {type:'rt',status:0xfc}]) p.dispatch(m);
  p.drainInputs(); assert.deepEqual(calls, []); assert.equal(p.inputs.length, 5);
  room(true); p.drainInputs(); p.drainInputs();
  assert.deepEqual(calls, ['rt:250', 'on:60:100', 'rt:248', 'off:60', 'rt:252']);
  assert.equal(p.inputs.length, 0);
});

test('malformed worklet realtime is ignored; disconnect/panic clears stale inputs and releases notes', () => {
  const { p, calls, room } = worklet();
  for (const status of [undefined, -1, 0xf9, '248', 256]) p.dispatch({type:'rt',status});
  assert.deepEqual(calls, []);
  room(false); p.dispatch({type:'rt',status:0xfa}); p.dispatch({type:'note-on',note:60,velocity:100});
  p.dispatch({type:'midi-reset'}); assert.deepEqual(calls, ['panic']);
  assert.deepEqual(p.inputs, [{type:'rt',status:0xfc}]);
  room(true); p.drainInputs(); assert.deepEqual(calls, ['panic', 'rt:252']);
  room(false); p.dispatch({type:'rt',status:0xfa}); p.dispatch({type:'panic'});
  assert.equal(p.inputs.length, 0); assert.equal(calls.at(-1), 'panic');
});

test('hostile burst has a finite queue and an observable fail-safe note release', () => {
  const { p, calls, room } = worklet(); room(false);
  for (let i=0; i<1025; ++i) p.dispatch({type:'rt',status:0xf8});
  assert.equal(p.inputs.length, 0); assert.deepEqual(calls, ['panic']);
  assert.match(p.port.messages[0].message, /overflow/);
});
