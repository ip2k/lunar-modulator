import test from 'node:test';
import assert from 'node:assert/strict';
import { emptySet, emptyClip, parseSet, writeSet } from '../www/editor/sequence-model.js';
import { positionText, timeText, barLimit, neighboringSlot } from '../www/editor/sequence-transport.js';
test('zero-based native PPQN position and native frame time', () => {
  assert.equal(positionText(0), '0:0:0'); assert.equal(positionText(479), '1:0:95'); assert.equal(positionText(383), '0:3:95');
  assert.equal(timeText(44118 * 65.25, 44118), '1:05.250'); assert.equal(timeText(null, 44118), '—');
});
test('bar bounds respect arrangement repeats and selected native clips', () => {
  const m = emptySet(); m.tracks[0].clips[2] = { ...emptyClip(), length: 48 }; m.song = [2, 2, 0];
  assert.equal(barLimit(m, {songFollow:true}), 6);
  assert.equal(barLimit(m, {songFollow:false, tracks:[{active:2}]}), 2);
  assert.equal(barLimit(emptySet()), 0);
});
test('slot navigation skips empty slots and never wraps', () => {
  assert.equal(neighboringSlot([0, 3, 7], 3, -1), 0); assert.equal(neighboringSlot([0, 3, 7], 3, 1), 7);
  assert.equal(neighboringSlot([0, 3, 7], 0, -1), null); assert.equal(neighboringSlot([0, 3, 7], 7, 1), null);
});
test('native tempo and song ending persist with legacy defaults', () => {
  const m = emptySet(); m.bpmX100 = 13742; m.songEnd = 2;
  assert.equal(parseSet(writeSet(m)).bpmX100, 13742); assert.equal(parseSet(writeSet(m)).songEnd, 2);
  assert.equal(parseSet('movy1\nbpm 12000\nswing 50\nlink 0\n').songEnd, 0);
});
