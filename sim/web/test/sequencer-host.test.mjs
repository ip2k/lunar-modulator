// Focused transaction/history and existing panel notification regressions. MIT.
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeSequencerHost } from '../www/editor/sequencer-host.js';
import { emptySet, emptyClip, parseSet, writeSet } from '../www/editor/sequence-model.js';

globalThis.document = { visibilityState: 'visible', createElement: () => ({}), head: { append() {} } };
const note = (pitch, tick = 0) => ({ pitch, tick, gate: 24, vel: 96, step: tick / 24 });
function project(notes = []) {
  const set = emptySet(); set.tracks[0].clips[0] = emptyClip(); set.tracks[0].clips[0].notes = notes;
  return { kind: 'project', sounds: [{ level: 50 }, null, null, null], set: writeSet(set) };
}
function harness(initial) {
  let current = structuredClone(initial), hash = 100, loads = 0, checks = 0, settled = 0;
  const notices = [], st = { gen: 7, ab: {}, view: 'sequencer' }, sim = { node: {}, screenListeners: new Set() };
  const files = {
    async projectSnapshot() { return { text: JSON.stringify(current), hash }; },
    async shadow(op, args) {
      if (op === 'pack') return { ok: true, bin: args.text };
      if (op === 'check') { checks++; files.duringCheck?.(); return { ok: true, bin: new TextDecoder().decode(args.bytes) }; }
      if (op === 'save') return { ok: true, text: args.live };
      throw Error(op);
    },
    async load(bytes, options) {
      if (options.expectedHash !== hash) return { ok: false, error: 'Native project changed before load.' };
      loads++; current = JSON.parse(new TextDecoder().decode(bytes)); hash++; return { ok: true };
    },
    fileName: () => 'test.lunar', async saveText() { return JSON.stringify(current); },
  };
  const host = makeSequencerHost({ sim, files, st, history: { record() {} }, snapshot: async () => {},
    say: text => notices.push(text), onSettled: () => settled++ });
  return { host, files, sim, st, notices, get current() { return current; }, get loads() { return loads; }, get checks() { return checks; },
    get settled() { return settled; }, replace(doc) { current = structuredClone(doc); hash++; } };
}
const before = project(), after = project([note(60)]);
const entry = { label: 'Add note', info: { beforeText: JSON.stringify(before), afterText: JSON.stringify(after) } };

test('matching native state permits undo then redo, preserving the atomic hash fence', async () => {
  const h = harness(after);
  assert.equal(await h.host.restoreHistory(entry, false), true);
  assert.equal(parseSet(h.current.set).tracks[0].clips[0].notes.length, 0);
  assert.equal(await h.host.restoreHistory(entry, true), true);
  assert.deepEqual(parseSet(h.current.set).tracks[0].clips[0].notes, [note(60)]);
  assert.equal(h.loads, 2);
});
test('later panel note refuses undo without shadow checking or removing either note', async () => {
  const changed = project([note(60), note(64, 24)]), h = harness(changed);
  assert.equal(await h.host.restoreHistory(entry, false), false);
  assert.deepEqual(h.current, changed); assert.equal(h.loads, 0); assert.equal(h.checks, 0);
  assert.match(h.notices.at(-1), /overwrite later changes/);
});
test('later non-sequencer native values also refuse full-project history restoration', async () => {
  const changed = structuredClone(after); changed.sounds[0].level = 73;
  const h = harness(changed);
  assert.equal(await h.host.restoreHistory(entry, false), false);
  assert.equal(h.current.sounds[0].level, 73); assert.equal(h.loads, 0);
});
test('redo refuses a native edit made after undo', async () => {
  const h = harness(before), changed = project([note(67)]); h.replace(changed);
  assert.equal(await h.host.restoreHistory(entry, true), false);
  assert.deepEqual(h.current, changed); assert.equal(h.loads, 0);
});
test('object key order does not cause a false conflict', async () => {
  const h = harness({ set: after.set, sounds: after.sounds, kind: after.kind });
  assert.equal(await h.host.restoreHistory(entry, false), true);
});
test('a native change during validation is refused by the final audio-thread fence', async () => {
  const h = harness(after), changed = project([note(60), note(65, 24)]);
  h.files.duringCheck = () => h.replace(changed);
  assert.equal(await h.host.restoreHistory(entry, false), false);
  assert.deepEqual(h.current, changed); assert.equal(h.loads, 0); assert.equal(h.checks, 1);
  assert.match(h.notices.at(-1), /changed before load/);
});
test('content generations coalesce and invalidate hidden panel changes without polling snapshots', async () => {
  const original = globalThis.setTimeout, timers = [];
  globalThis.setTimeout = (fn, ms) => { assert.equal(ms, 100); timers.push(fn); return timers.length; };
  try {
    const h = harness(after);
    let snapshots = 0; h.files.projectSnapshot = async () => { snapshots++; throw Error('No polling'); };
    const transport = contentGen => { for (const fn of h.sim.seqListeners) fn({ contentGen, master_tick: Math.random() }); };
    transport(4); transport(4); transport(4); assert.equal(timers.length, 0);
    transport(5); transport(6); transport(6); assert.equal(timers.length, 1);
    await timers.shift()(); assert.equal(h.settled, 1); assert.equal(snapshots, 0);
    transport(6); assert.equal(timers.length, 0);
    h.st.view = 'sound'; document.visibilityState = 'hidden'; transport(7);
    await timers.shift()(); assert.equal(h.settled, 2); assert.equal(snapshots, 0);
    transport(undefined); transport(-1); transport(1.5); assert.equal(timers.length, 0);
  } finally { globalThis.setTimeout = original; document.visibilityState = 'visible'; }
});

test('worklet posts content-only changes immediately and keeps old-module transport compatibility', async () => {
  let Worklet;
  globalThis.AudioWorkletProcessor = class {};
  globalThis.registerProcessor = (_name, type) => { Worklet = type; };
  globalThis.sampleRate = 44100;
  await import('../www/worklet.js');
  const worker = Object.create(Worklet.prototype), messages = [], seq = new Uint32Array(56);
  let generation = 4;
  worker.fm1 = { exports: { fm1w_seq_info() {}, fm1w_seq_gen: () => generation } };
  worker.seqLast = new Uint32Array(56); worker.seqAge = 0;
  worker.port = { postMessage: message => messages.push(message) };
  worker.postSeq({ seq }); assert.equal(messages.length, 1); assert.equal(messages[0].contentGen, 4);
  worker.postSeq({ seq }); assert.equal(messages.length, 1);
  generation = 5; worker.postSeq({ seq }); assert.equal(messages.length, 2); assert.equal(messages[1].contentGen, 5);
  seq[6] = 1; worker.postSeq({ seq }); assert.equal(messages.length, 2); // PPQN-only change stays throttled
  delete worker.fm1.exports.fm1w_seq_gen;
  seq[1] = 12500; worker.postSeq({ seq }); assert.equal(messages.length, 3);
  assert.equal(messages[2].bpm_x100, 12500); assert.equal('contentGen' in messages[2], false);
  assert.equal(messages[2].playbackFrames, null); // no fabricated browser elapsed time
  const extended = new Uint32Array(61); extended.set(seq);
  extended[56] = 1; extended[57] = 12345; extended[58] = 2; extended[59] = 44118; extended[60] = 1;
  worker.seqLast = new Uint32Array(61); worker.postSeq({seq:extended});
  const native = messages.at(-1);
  assert.equal(native.paused, true); assert.equal(native.playbackFrames, 2 * 4294967296 + 12345);
  assert.equal(native.sampleRate, 44118); assert.equal(native.metronome, true);
});
test('toolbar and keyboard actions issue native pause, resume, rewind and locate verbs', () => {
  const h = harness(before), sent = []; h.sim.node.port = { postMessage: m => sent.push(new TextDecoder().decode(m.bytes)) };
  h.host.play(); h.host.pause(); h.host.stop(); h.host.seekBar(4);
  h.sim.seq = {playing:true}; h.host.playPause(); h.sim.seq = {paused:true}; h.host.playPause(); h.host.restart();
  assert.deepEqual(sent, ['resume', 'pause', 'rewind', 'seekbar 4', 'pause', 'resume', 'rewind', 'resume']);
});
test('project transactions preserve native metronome settings', async () => {
  const doc = project(); doc.settings = {metronome:1}; const h = harness(doc);
  const next = structuredClone(doc); const model = parseSet(next.set); model.bpmX100 = 13742; model.songEnd = 2; next.set = writeSet(model);
  await h.host.applyProject(next, 'Transport settings');
  assert.equal(h.current.settings.metronome, 1); assert.equal(parseSet(h.current.set).songEnd, 2);
});
