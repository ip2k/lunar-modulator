// Pure mapping engine: the same dispatcher used by Web MIDI and the overlay.
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import test from 'node:test';
const source = readFileSync(new URL('../www/midi-map.js', import.meta.url), 'utf8');
const { MidiMap, validMidiMap, midiMessage, MAX_BINDINGS } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const b = (target = 'button', input = 'A', channel = 0, kind = 'note', number = 60) => ({ target, source: input, channel, kind, number });
const data = (kind, channel, number, value) => [kind + channel, number, value];
const saved = (bindings) => ({ version: 1, bindings });
function learn(m, target, input = 'A', message = [0x90, 60, 100]) { m.learn(true); m.select(target); assert.equal(m.handle(input, message), true); m.learn(false); }

test('learning is silent, consumes unsupported messages, replaces conflicting addresses, and clears', () => {
  let pressed = 0, edits = 0;
  const m = new MidiMap({ edited: () => edits++ });
  m.register('a', { press: () => pressed++ }); m.register('b', { press: () => pressed++ });
  m.learn(true); assert.equal(m.handle('A', [0xe0, 0, 64]), true);
  m.select('a'); m.handle('A', [0x90, 60, 100]); assert.equal(pressed, 0);
  learn(m, 'b'); assert.deepEqual(m.export(), saved([b('b')])); assert.equal(edits, 2);
  m.clear('b'); assert.deepEqual(m.export(), saved([])); assert.equal(edits, 3);
  assert.equal(m.handle('A', [0x90, 60, 100]), false);
});
test('held notes dispatch once, accept velocity-zero note-off, and release on blur/disconnect/mode changes', () => {
  const calls = [], m = new MidiMap();
  m.register('button', { press: (v) => { calls.push(['down', v]); return () => calls.push(['up']); } });
  m.import(saved([b()]));
  m.handle('A', [0x90, 60, 99]); m.handle('A', [0x90, 60, 98]); m.handle('A', [0x90, 60, 0]);
  assert.deepEqual(calls, [['down', 99], ['up']]);
  m.handle('A', [0x90, 60, 100]); m.release('B'); assert.equal(calls.length, 3);
  m.release('A'); assert.deepEqual(calls.at(-1), ['up']);
  m.handle('A', [0x90, 60, 100]); m.learn(true); assert.deepEqual(calls.at(-1), ['up']);
});
test('CC buttons use threshold edges, continuous controls scale all values, relative encoders use deltas', () => {
  let clicks = 0; const values = [], turns = [], m = new MidiMap();
  m.register('button', { press: () => { clicks++; } });
  m.register('slider', { kind: 'value', value: (u) => values.push(u) });
  m.register('encoder', { kind: 'relative', turn: (d) => turns.push(d) });
  m.import(saved([b('button', 'A', 0, 'cc', 1), b('slider', 'A', 0, 'cc', 2), b('encoder', 'A', 0, 'cc', 3)]));
  for (const v of [63, 64, 80, 127, 0, 90]) m.handle('A', [0xb0, 1, v]); assert.equal(clicks, 2);
  for (const v of [0, 64, 127]) m.handle('A', [0xb0, 2, v]); assert.deepEqual(values, [0, 64 / 127, 1]);
  for (const v of [64, 70, 60]) m.handle('A', [0xb0, 3, v]); assert.deepEqual(turns, [6, -10]);
});
test('source, channel and message kind form distinct addresses; unmatched MIDI passes through', () => {
  const counts = [0, 0, 0, 0], m = new MidiMap();
  counts.forEach((_, i) => m.register(String(i), { press: () => counts[i]++ }));
  m.import(saved([b('0'), b('1', 'B'), b('2', 'A', 1), b('3', 'A', 0, 'cc', 60)]));
  m.handle('A', [0x90, 60, 100]); m.handle('B', [0x90, 60, 100]); m.handle('A', [0x91, 60, 100]); m.handle('A', [0xb0, 60, 100]);
  assert.deepEqual(counts, [1, 1, 1, 1]);
  for (const d of [[0x90, 61, 100], [0xe0, 0, 64], [0xb0, 7, 100], [0xb0, 123, 0]]) assert.equal(m.handle('A', d), false);
});
test('reload and replacement redraw keep semantic targets, typing/dialog guards consume without dispatch', () => {
  let text = null, blocked = false, old = 0, fresh = 0;
  const storage = { getItem: () => text, setItem: (_, value) => { text = value; } };
  const m = new MidiMap({ storage }); m.register('button', { press: () => old++ }); learn(m, 'button');
  const next = new MidiMap({ storage, blocked: () => blocked });
  next.register('button', { press: () => fresh++ }); blocked = true;
  assert.equal(next.handle('A', [0x90, 60, 100]), true); assert.equal(fresh, 0);
  next.handle('A', [0x80, 60, 0]); blocked = false; next.handle('A', [0x90, 60, 100]);
  assert.equal(fresh, 1); assert.equal(old, 0);
  next.import(null); assert.deepEqual(next.export(), saved([]));
});
test('native-shared limits reject oversized, duplicate and malformed tables atomically', () => {
  assert.equal(validMidiMap(saved([b()])), true);
  const ids = Array.from({ length: MAX_BINDINGS }, (_, i) => b(`t${i}`, 'A', 0, 'cc', i));
  assert.equal(validMidiMap(saved(ids)), true); assert.equal(validMidiMap(saved([...ids, b('extra', 'B')])), false);
  for (const bindings of [[b(), b('other')], [b(), b('button', 'B')], [b('x'.repeat(193))], [b('🎹')], [b('x', 'x'.repeat(129))],
    [b('x', 'A', 16)], [b('x', 'A', 0, 'bend')], [b('x', 'A', 0, 'note', 128)], ids.map((v, i) => ({ ...v, target: `${i}${'x'.repeat(100)}` }))]) assert.equal(validMidiMap(saved(bindings)), false);
  const m = new MidiMap(); m.import(saved([b()])); assert.equal(m.import(saved([b('x'.repeat(193))])), false); assert.deepEqual(m.export(), saved([b()]));
  assert.equal(midiMessage('A', [0x90, 60, 1.1]), null);
});

test('mode-changing CC buttons retain their triggering edge after synchronous release', () => {
  let clicks = 0; const m = new MidiMap();
  m.register('mode', { press: () => { clicks++; m.release(); } });
  m.import(saved([b('mode', 'A', 0, 'cc', 10)]));
  for (const v of [64, 70, 100, 127, 0, 100]) m.handle('A', [0xb0, 10, v]);
  assert.equal(clicks, 2);
});

test('semantic legacy Play resolves without rewriting metadata; ambiguous toolbar ordinals stay inert', () => {
  let presses = 0; const m = new MidiMap();
  m.register('seq:transport:play-pause', { press: () => presses++ });
  m.register('seq:transport:stop', { press: () => { throw Error('ambiguous old ordinal dispatched'); } });
  const oldPlay = 'ed/layout=editor/testid=seq-play/BUTTON.sq-button:0';
  const old = saved([b(oldPlay, 'A', 0, 'cc', 29), b('ed/layout=editor/BUTTON.sq-button:7', 'A', 0, 'cc', 30)]);
  m.import(old); m.handle('A', [0xb0, 29, 127]); m.handle('A', [0xb0, 30, 127]);
  assert.equal(presses, 1); assert.deepEqual(m.export(), old);
  learn(m, 'seq:transport:play-pause', 'A', [0xb0, 29, 127]);
  assert.equal(m.export().bindings.length, 2, 'relearning replaces the old logical Play binding');
  m.clear(oldPlay); assert.equal(m.export().bindings.length, 1);
});
