// Pure MIDI/model tests, no browser or third-party fixtures needed.
// node sim/web/test/midi-import.mjs [WWW_DIR]
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const www = process.argv[2] || resolve(dirname(fileURLToPath(import.meta.url)), '../www');
const M = await import(pathToFileURL(resolve(www, 'editor/sequence-model.js')));
const I = await import(pathToFileURL(resolve(www, 'editor/midi-import.js')));
const be16 = n => [n >> 8 & 255, n & 255], be32 = n => [n >>> 24, n >>> 16 & 255, n >>> 8 & 255, n & 255];
const ascii = s => [...s].map(c => c.charCodeAt(0));
function vlq(n) { const a = [n & 127]; while ((n = Math.floor(n / 128))) a.unshift((n & 127) | 128); return a; }
const chunk = (id, data) => [...ascii(id), ...be32(data.length), ...data];
const ev = (delta, ...data) => [...vlq(delta), ...data];
const meta = (delta, type, data = []) => ev(delta, 255, type, ...vlq(data.length), ...data);
function midi(tracks, ppqn = 96, format = tracks.length > 1 ? 1 : 0) {
  return new Uint8Array([...chunk('MThd', [...be16(format), ...be16(tracks.length), ...be16(ppqn)]), ...tracks.flatMap(t => chunk('MTrk', t.flat()))]);
}
const end = delta => meta(delta, 0x2f);
const basic = (ppqn = 96) => midi([[
  meta(0, 3, ascii('Piano')), meta(0, 0x51, [7, 161, 32]), ev(0, 0xc0, 4), ev(0, 0x90, 60, 100), ev(ppqn, 0x80, 60, 0), end(0)
]], ppqn);
function plan(bytes, options) { return I.planMidiImport(I.parseMidi(bytes, 'Test.mid'), options); }

test('type 0 preserves program, track name, velocity, gate and quarter-note timing', () => {
  const f = I.parseMidi(basic(480), 'Piano.mid'); assert.equal(f.format, 0); assert.equal(f.ppqn, 480);
  assert.equal(f.parts[0].program, 4); assert.equal(f.parts[0].name, 'Piano');
  assert.deepEqual(f.parts[0].notes, [{ tick: 0, end: 480, pitch: 60, vel: 100 }]);
  const p = I.planMidiImport(f); assert.equal(p.valid, true); assert.equal(p.set.bpmX100, 12000);
  assert.deepEqual(p.set.tracks[0].clips[0].notes, [{ tick: 0, gate: 96, pitch: 60, vel: 100, step: 0 }]);
});
test('type 1 shared timeline and per-channel programs/banks identify instrument parts', () => {
  const f = I.parseMidi(midi([
    [meta(0, 3, ascii('Conductor')), meta(0, 0x51, [7, 161, 32]), end(768)],
    [meta(0, 3, ascii('Strings')), ev(0, 0xb1, 0, 2), ev(0, 0xb1, 32, 3), ev(0, 0xc1, 48), ev(96, 0x91, 64, 81), ev(96, 0x81, 64, 0), end(576)],
    [ev(0, 0x99, 36, 110), ev(24, 0x89, 36, 0), end(744)]
  ]));
  assert.equal(f.parts.length, 2); assert.deepEqual(f.parts[0].bank, [0, 0]); assert.equal(f.parts[0].drums, true);
  const strings = f.parts.find(p => p.program === 48); assert.deepEqual(strings.bank, [2, 3]); assert.equal(strings.channel, 2);
  const p = I.planMidiImport(f, { barsPerScene: 1 }); assert.equal(p.valid, true); assert.equal(p.set.song.length, 2);
  assert.equal(p.set.tracks[p.parts.findIndex(part => part.id === strings.id)].clips[0].notes[0].tick, 96);
});
test('running status, velocity-zero offs and FIFO pairing of overlapping repeated pitches', () => {
  const f = I.parseMidi(midi([[ev(0, 0x90, 60, 80), ev(12, 60, 90), ev(12, 60, 0), ev(12, 60, 0), end(0)]]));
  assert.deepEqual(f.parts[0].notes.map(n => [n.tick, n.end, n.vel]), [[0, 24, 80], [12, 36, 90]]);
  const p = I.planMidiImport(f); assert.equal(p.valid, true); assert.match(p.warnings.join('\n'), /overlapping repeated pitches/);
});
test('sustain spans channels/tracks and releases deferred notes at pedal-up', () => {
  const f = I.parseMidi(midi([
    [ev(0, 0xb0, 64, 127), ev(96, 0xb0, 64, 0), end(0)],
    [ev(0, 0x90, 60, 80), ev(24, 0x80, 60, 0), end(72)],
    [ev(0, 0x91, 65, 70), ev(24, 0x81, 65, 0), end(72)]
  ]));
  assert.equal(f.parts.find(p => p.channel === 1).notes[0].end, 96);
  assert.equal(f.parts.find(p => p.channel === 2).notes[0].end, 24);
  assert.match(f.warnings.join('\n'), /Sustain pedal baked/);
});
test('all-notes-off honors sustain; all-sound-off ends held and sustained notes immediately', () => {
  const f = I.parseMidi(midi([[ev(0, 0xb0, 64, 127), ev(0, 0x90, 60, 80), ev(24, 0xb0, 123, 0), ev(24, 0xb0, 120, 0), end(0)]]));
  assert.equal(f.parts[0].notes[0].end, 48);
});
test('SysEx and metadata are retained; running status is cleared across both', () => {
  const f = I.parseMidi(midi([[ev(0, 0xf0, 3, 1, 2, 0xf7), meta(0, 1, ascii('marker')), ev(0, 0x90, 60, 80), ev(96, 0x80, 60, 0), end(0)]]));
  assert.equal(f.unsupported.sysex, 1); assert.equal(f.metadata.find(e => e.type === 1).text, 'marker');
  assert.throws(() => I.parseMidi(midi([[ev(0, 0x90, 60, 80), meta(0, 1, [65]), ev(24, 60, 0), end(0)]])), /running status/);
  assert.throws(() => I.parseMidi(midi([[ev(0, 0x90, 60, 80), ev(0, 0xf7, 1, 0), ev(24, 60, 0), end(0)]])), /running status/);
});
test('tempo changes require explicit initial-tempo policy and 3/4 is refused', () => {
  const f = I.parseMidi(midi([[meta(0, 0x51, [7, 161, 32]), ev(0, 0x90, 60, 80), meta(96, 0x51, [6, 26, 128]), ev(96, 0x80, 60, 0), end(0)]]));
  assert.equal(I.planMidiImport(f).valid, false); const accepted = I.planMidiImport(f, { tempoPolicy: 'first' });
  assert.equal(accepted.valid, true); assert.equal(accepted.set.bpmX100, 12000); assert.match(accepted.warnings.join('\n'), /elapsed timing changes/);
  const badMeter = midi([[meta(0, 0x58, [3, 2, 24, 8]), ev(0, 0x90, 60, 80), ev(96, 0x80, 60, 0), end(0)]]);
  assert.match(plan(badMeter).errors.join('\n'), /4\/4/);
});
test('default tempo before first tempo event is respected', () => {
  const f = I.parseMidi(midi([[ev(0, 0x90, 60, 80), meta(96, 0x51, [6, 26, 128]), ev(96, 0x80, 60, 0), end(0)]]));
  const p = I.planMidiImport(f, { tempoPolicy: 'first' }); assert.equal(p.set.bpmX100, 12000); assert.match(p.warnings.join('\n'), /tempo changes/);
});
test('batch mapping preserves synchronous tracks and conflicts need explicit policy', () => {
  const a = I.parseMidi(basic(), 'a.mid'), b = I.parseMidi(midi([[meta(0, 0x51, [6, 26, 128]), ev(24, 0x90, 67, 80), ev(96, 0x80, 67, 0), end(0)]]), 'b.mid');
  const mapping = [{ fileIndex: 0, partId: a.parts[0].id, track: 2, sound: 1 }, { fileIndex: 1, partId: b.parts[0].id, track: 5, sound: 3 }];
  assert.equal(I.planMidiImport([a, b], { mapping }).valid, false);
  const p = I.planMidiImport([a, b], { mapping, tempoPolicy: 'first' }); assert.equal(p.valid, true);
  assert.equal(p.set.tracks[5].clips[0].notes[0].tick, 24); assert.deepEqual(p.set.tracks[2].route, { kind: 1, index: 1 });
});
test('long notes split at synchronized scenes without losing total gate or trailing silence', () => {
  const p = plan(midi([[ev(300, 0x90, 60, 100), ev(300, 0x80, 60, 0), end(168)]]), { barsPerScene: 1 });
  assert.equal(p.valid, true); assert.equal(p.set.song.length, 2); assert.equal(p.set.tracks[0].clips[0].notes[0].gate, 84);
  assert.equal(p.set.tracks[0].clips[1].notes[0].gate, 216); assert.match(p.warnings.join('\n'), /split and retrigger/);
  const sum = p.set.tracks[0].clips.flatMap(c => c?.notes || []).reduce((n, x) => n + x.gate, 0); assert.equal(sum, 300);
});
test('repeated scene columns are deduplicated and encoded as song presses', () => {
  const events = [];
  for (let bar = 0; bar < 12; ++bar) { events.push(ev(bar ? 360 : 0, 0x90, 60, 100), ev(24, 0x80, 60, 0)); }
  events.push(end(360)); const p = plan(midi([events]), { barsPerScene: 1 });
  assert.equal(p.valid, true); assert.deepEqual(p.set.song, Array(12).fill(0)); assert.equal(p.usage.notes, 1);
  assert.deepEqual(M.arrangementEntries(p.set), [{ scene: 0, presses: 12, index: 0, songIndex: 0, startBar: 0, bars: 12 }]);
});
test('96 PPQN rounds endpoints, keeps positive short gates and last-step anchors', () => {
  const p = plan(midi([[ev(3839, 0x90, 60, 100), ev(1, 0x80, 60, 0), end(0)]], 960), { barsPerScene: 1 });
  assert.equal(p.valid, true); const note = p.set.tracks[0].clips[1].notes[0]; assert.equal(note.gate, 1); assert.equal(note.step, 0);
  assert.match(p.warnings.join('\n'), /rounded/);
});
test('single scene refuses truncation; occupied target can be protected; model is immutable', () => {
  const long = I.parseMidi(midi([[ev(0, 0x90, 60, 100), ev(768, 0x80, 60, 0), end(0)]]));
  assert.equal(I.planMidiImport(long, { mode: 'scene', scene: 3, barsPerScene: 1 }).valid, false);
  const p = I.planMidiImport(long, { mode: 'scene', scene: 3, barsPerScene: 2 }); assert.equal(p.valid, true);
  const m = M.emptySet(); m.song = [2]; const after = I.applyMidiImport(m, p); assert.equal(m.tracks[0].clips[3], null); assert.deepEqual(after.song, [2]);
  assert.throws(() => I.applyMidiImport(after, p, { onlyEmpty: true }), /contains a clip/);
});
test('more than eight parts require explicit selection; collisions and invalid routes are refused', () => {
  const tracks = Array.from({ length: 9 }, (_, c) => [ev(0, 0x90 + c, 60, 80), ev(96, 0x80 + c, 60, 0), end(0)]), f = I.parseMidi(midi(tracks));
  assert.equal(I.planMidiImport(f).valid, false);
  const p = I.planMidiImport(f, { mapping: [{ fileIndex: 0, partId: f.parts[0].id, track: 0, sound: 0 }] }); assert.equal(p.valid, true); assert.match(p.warnings.join('\n'), /8 unmapped parts/);
  assert.equal(I.planMidiImport(f, { mapping: [{ partId: f.parts[0].id, track: 0, sound: 0 }, { partId: f.parts[1].id, track: 0, sound: 0 }] }).valid, false);
  assert.equal(I.planMidiImport(f, { mapping: [{ partId: f.parts[0].id, track: 0, sound: 4 }] }).valid, false);
});
test('clip/global/gate/scene/song capacity overflows refuse the entire plan', () => {
  const dense = []; for (let i = 0; i < 513; ++i) dense.push(ev(i ? 1 : 0, 0x90, i % 128, 100), ev(1, 0x80, i % 128, 0)); dense.push(end(0));
  assert.match(plan(midi([dense]), { barsPerScene: 4 }).errors.join('\n'), /512 notes/);
  const simultaneous = []; for (let i = 0; i < 65; ++i) simultaneous.push(ev(0, 0x90, i, 100)); for (let i = 0; i < 65; ++i) simultaneous.push(ev(i ? 0 : 96, 0x80, i, 0)); simultaneous.push(end(0));
  assert.equal(plan(midi([simultaneous])).valid, false);
  const scenes = []; for (let i = 0; i < 9; ++i) scenes.push(ev(i ? 360 : 0, 0x90, 60 + i, 80), ev(24, 0x80, 60 + i, 0)); scenes.push(end(360));
  assert.match(plan(midi([scenes]), { barsPerScene: 1 }).errors.join('\n'), /eight distinct/);
  assert.match(plan(midi([[ev(0, 0x90, 60, 80), ev(96, 0x80, 60, 0), end(65 * 384 - 96)]]), { barsPerScene: 1 }).errors.join('\n'), /64/);
  const m = M.emptySet(); for (let t = 0; t < 4; ++t) { const c = M.emptyClip(256); c.notes = Array.from({ length: 400 }, (_, i) => ({ tick: i, gate: 1, pitch: i % 128, vel: 80, step: Math.floor(i / 24) })); m.tracks[t].clips[0] = c; }
  assert.match(M.validateSet(m).errors.join('\n'), /1536/);
});
test('movy1 complete-tag round trip preserves clip properties, trigs, filters, labels/routes/extensions', () => {
  const source = ['movy1', 'bpm 13125', 'swing 57', 'link 1', 'key 9 1', 'dq 35', 'sg 0 0 3', 'se 2', 'sn 0 Intro',
    'tk 0 3 1', 'pm 0 36', 'ps 0 40', 'au 0 2 44 synth:Decay', 'rt 0 1 3',
    'cl 0 3 24 8 193:96:64:81:8;240:24:67:110:10', 'cp 0 3 3 2 -7 25', 'lk 0 3 2:8:33;2:10:127', 'tg 0 3 8:-1:70:2:3:1;10:67:100:1:2:0', 'future xyz 123'];
  const m = M.parseSet(source), out = M.writeSet(m); assert.deepEqual(M.parseSet(out), m); assert(out.includes('future xyz 123'));
  assert.equal(m.tracks[0].clips[3].scaleNum, 3); assert.equal(m.tracks[0].clips[3].trigs[1].lane, 67);
  const legacy = M.parseSet('movy1\nbpm 12000\ncl 0 0 16 0 25:20:60:90\ncp 0 0 1 1 0\n'); assert.equal(legacy.tracks[0].clips[0].notes[0].step, 1);
});
test('existing first-orbit project survives model round trip without losing musical state', () => {
  const project = JSON.parse(readFileSync(resolve(www, 'examples/first-orbit.lunar'), 'utf8'));
  const m = M.parseSet(project.set); assert.deepEqual(M.parseSet(M.writeSet(m)), m); assert.equal(M.validateSet(m).valid, true);
});
test('strict MIDI/model malformed bounds reject rather than hang, clamp, or drop', () => {
  const good = basic(); for (let i = 0; i < good.length; ++i) assert.throws(() => I.parseMidi(good.subarray(0, i)), undefined, `truncation ${i}`);
  assert.throws(() => I.parseMidi(midi([[end(0)]], 0)), /PPQN/); assert.throws(() => I.parseMidi(midi([[end(0)]], 0xe728)), /SMPTE/);
  assert.throws(() => I.parseMidi(midi([[end(0)]], 96, 2)), /type 2/);
  assert.throws(() => I.parseMidi(midi([[ev(0, 0x90, 60, 80)]])), /End of Track/);
  assert.throws(() => I.parseMidi(midi([[[0xff, 0xff, 0xff, 0xff, 0], ...end(0)]])), /four bytes/);
  assert.throws(() => I.parseMidi(midi([[meta(0, 0x51, [1, 2]), end(0)]])), /meta event/);
  assert.throws(() => I.parseMidi(midi([[end(0), ev(0, 0x90, 60, 100)]])), /after End/);
  assert.throws(() => I.parseMidi(midi([[ev(0, 0x90, 128, 80), end(0)]])), /channel event/);
  assert.throws(() => M.parseSet(['movy1', 'cl 0 8 16 0']), /outside/); assert.throws(() => M.parseSet(['movy1', 'cp 0 0 0 1 0']), /speed ratio/);
  assert.throws(() => M.parseSet(['movy1', 'cl 0 0 16 0 0:65536:60:100:0']), /invalid note/);
  assert.throws(() => M.parseSet(['movy1', 'cl 0 0 257 0']), /256 steps/); assert.throws(() => M.parseSet(['movy1', 'cl 0 0 16 0 0:24:60:100:256']), /invalid note/);
});

test('equal-pitch/equal-onset notes retain distinct velocities and gates', () => {
  const p = plan(midi([[ev(0, 0x90, 60, 80), ev(0, 0x90, 60, 100), ev(24, 0x80, 60, 0), ev(24, 0x80, 60, 0), end(0)]]));
  assert.equal(p.valid, true); assert.deepEqual(p.set.tracks[0].clips[0].notes.map(n => [n.vel, n.gate]), [[80, 24], [100, 48]]);
  assert.deepEqual(M.parseSet(M.writeSet(p.set)), p.set);
});
test('program changes divide instrument parts, keeping existing held-note releases', () => {
  const f = I.parseMidi(midi([[ev(0, 0xc0, 4), ev(0, 0x90, 60, 80), ev(24, 0xc0, 48), ev(0, 0x90, 65, 100), ev(24, 0x80, 60, 0), ev(24, 0x80, 65, 0), end(0)]]));
  assert.deepEqual(f.parts.map(p => p.program), [4, 48]); assert.equal(f.parts[0].notes[0].end, 48); assert.equal(f.parts[1].notes[0].tick, 24);
});
test('unsupported controllers/expression, complete SysEx and unknown metadata survive preview data', () => {
  const payload = Array.from({ length: 200 }, (_, i) => i % 128);
  const f = I.parseMidi(midi([[meta(0, 0x7f, payload), ev(0, 0xf0, ...vlq(payload.length), ...payload), ev(0, 0xb0, 1, 33), ev(0, 0xe0, 0, 70), ev(0, 0x90, 60, 100), ev(96, 0x80, 60, 0), end(0)]]));
  assert.deepEqual(f.metadata.find(e => e.type === 0x7f).data, payload);
  assert.deepEqual(f.metadata.find(e => e.kind === 'sysex').data, payload);
  assert(f.channelEvents.some(e => e.kind === 0xb && e.a === 1 && e.b === 33));
  const p = I.planMidiImport(f); assert.equal(p.valid, true); assert.deepEqual(p.metadata[0].channelEvents, f.channelEvents);
  assert.match(p.warnings.join('\n'), /CC1/); assert.match(p.warnings.join('\n'), /pressure/);
});
test('apply refuses changes that exceed combined pools or alter imported scene durations', () => {
  const p = plan(basic(), { barsPerScene: 1 }), m = M.emptySet();
  m.tracks[3].clips[0] = M.emptyClip(32);
  assert.throws(() => I.applyMidiImport(m, p), /unmapped longer clip/);
  m.tracks[3].clips[0] = M.emptyClip(16); assert.equal(I.applyMidiImport(m, p).tracks[3].clips[0].length, 16);
  const dense = M.emptySet(); for (let t = 1; t <= 3; ++t) { dense.tracks[t].clips[0] = M.emptyClip(16); dense.tracks[t].clips[0].notes = Array.from({ length: 512 }, (_, i) => ({ tick: i, gate: 1, pitch: i % 128, vel: 80, step: Math.floor(i / 24) })); }
  assert.equal(M.validateSet(dense).valid, true); assert.throws(() => I.applyMidiImport(dense, p), /1536/);
  const extension = M.parseSet(['movy1', 'future 123']); assert.throws(() => I.applyMidiImport(extension, p), /unknown extension/);
});
test('combined native gates include retained notes and preserve the source on refusal', () => {
  const p = plan(midi([[...Array.from({ length: 32 }, (_, i) => ev(0, 0x90, 40 + i, 100)), ...Array.from({ length: 32 }, (_, i) => ev(i ? 0 : 96, 0x80, 40 + i, 0)), end(0)]]), { barsPerScene: 1 });
  assert.equal(p.valid, true);
  const m = M.emptySet(), c = m.tracks[1].clips[0] = M.emptyClip(16);
  c.notes = Array.from({ length: 40 }, (_, i) => ({ tick: 0, gate: 96, pitch: 30 + i, vel: 100, step: 0 }));
  const before = structuredClone(m);
  assert.throws(() => I.applyMidiImport(m, p), /64 sounding-note gate pool/);
  assert.deepEqual(m, before);
  c.notes.length = 32; assert.doesNotThrow(() => I.applyMidiImport(m, p));
});
test('capacity accounts for gates surviving loop wraps, clip speed and transposed pad filters', () => {
  const p = plan(basic(), { barsPerScene: 1 }), m = M.emptySet(), track = m.tracks[1], c = track.clips[0] = M.emptyClip(1);
  c.notes = [{ tick: 0, gate: 24 * 64, pitch: 60, vel: 100, step: 0 }];
  c.scaleNum = 1; c.scaleDen = 8; c.transpose = 12;
  assert.throws(() => I.applyMidiImport(m, p), /64 sounding-note gate pool/);
  track.padMutes = [60]; assert.throws(() => I.applyMidiImport(m, p), /64 sounding-note gate pool/);
  track.padMutes = [72]; assert.doesNotThrow(() => I.applyMidiImport(m, p));
  track.padMutes = []; c.notes[0].gate = 24 * 63;
  assert.doesNotThrow(() => I.applyMidiImport(m, p));
  c.scaleNum = 4; c.scaleDen = 1;
  assert.doesNotThrow(() => I.applyMidiImport(m, p));
});
test('capacity preserves quantization and loop anchors without summing sequential notes', () => {
  const p = plan(basic(), { barsPerScene: 1 }), m = M.emptySet(), c = m.tracks[1].clips[0] = M.emptyClip(16);
  c.notes = Array.from({ length: 100 }, (_, tick) => ({ tick, gate: 1, pitch: 60, vel: 100, step: 0 }));
  assert.doesNotThrow(() => I.applyMidiImport(m, p));
  c.quant = 100; assert.throws(() => I.applyMidiImport(m, p), /64 sounding-note gate pool/);
  c.loopStart = 1; assert.doesNotThrow(() => I.applyMidiImport(m, p));
});
test('capacity includes held gates at scene transitions and native track processing order', () => {
  const p = plan(basic(), { barsPerScene: 1, mode: 'scene', scene: 1 }), m = M.emptySet();
  m.song = [0, 1]; m.songEnd = 2;
  const old = m.tracks[1].clips[0] = M.emptyClip(16);
  old.notes = Array.from({ length: 64 }, (_, i) => ({ tick: 360, gate: 96, pitch: 30 + i, vel: 100, step: 15 }));
  m.tracks[1].clips[1] = M.emptyClip(16);
  assert.throws(() => I.applyMidiImport(m, p), /64 sounding-note gate pool/);
  // Missing next clip flushes that track before any new notes are scanned.
  m.tracks[1].clips[1] = null; assert.doesNotThrow(() => I.applyMidiImport(m, p));
});
test('native wasm imports and exports every supported model field without musical loss', async () => {
  const { instantiateFm1 } = await import(pathToFileURL(resolve(www, 'fm1-wasm.mjs')));
  const fm1 = await instantiateFm1(readFileSync(resolve(www, 'fm1.wasm'))), ex = fm1.exports;
  ex.fm1w_init(44100); ex.fm1w_default_chain();
  const m = M.parseSet(['movy1', 'bpm 13125', 'swing 57', 'link 1', 'key 9 1', 'dq 35', 'sg 0 0 3', 'se 2', 'sn 0 Intro',
    'tk 0 3 1', 'pm 0 36', 'ps 0 40', 'au 0 2 44 synth:Decay', 'rt 0 1 3',
    'cl 0 3 24 8 193:96:64:81:8;193:24:64:110:8;240:24:67:110:10', 'cp 0 3 3 2 -7 25', 'lk 0 3 2:8:33;2:10:127', 'tg 0 3 8:-1:70:2:3:1;10:67:100:1:2:0']);
  const project = JSON.parse(readFileSync(resolve(www, 'examples/first-orbit.lunar'), 'utf8')); project.set = M.writeSet(m);
  const bytes = new TextEncoder().encode(JSON.stringify(project)); assert(bytes.length <= ex.fm1w_text_cap());
  new Uint8Array(fm1.memory.buffer, ex.fm1w_text_buf(), ex.fm1w_text_cap()).set(bytes);
  assert.equal(ex.fm1w_state_load(1, 0, 0, 4, bytes.length), 1, fm1.string(ex.fm1w_state_report()));
  const n = ex.fm1w_state_save(1, 0, 0); assert(n > 0);
  const actual = JSON.parse(new TextDecoder().decode(new Uint8Array(fm1.memory.buffer, ex.fm1w_text_buf(), n)));
  assert.deepEqual(M.parseSet(actual.set), m);
});
