import test from 'node:test';
import assert from 'node:assert/strict';
import { emptySet, emptyClip, parseSet, writeSet } from '../www/editor/sequence-model.js';
import { positionText, timeText, barLimit, neighboringSlot, transportNavigation } from '../www/editor/sequence-transport.js';
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
test('playback counters group repeats and use the playing clip rather than queued active slot', () => {
  const m = emptySet(); m.song = [0, 0, 3, 0];
  m.tracks[0].clips[0] = emptyClip(16); m.tracks[0].clips[3] = emptyClip(32); m.tracks[0].clips[7] = emptyClip(16);
  const transport = {playing:true, songFollow:true, songIndex:1, master_tick:384, tracks:[{playing:0, active:3}]};
  let n = transportNavigation(m, transport, 0);
  assert.deepEqual([n.bar.current,n.bar.total,n.clip.current,n.clip.total,n.scene.current,n.scene.total],[2,5,1,2,1,3]);
  assert.deepEqual(n.scene.next,{scene:3,bar:2}); assert.equal(n.scene.previous,null);
  n = transportNavigation(m,{...transport,songIndex:3,master_tick:384*4,tracks:[{playing:0,active:7}]},0);
  assert.deepEqual([n.scene.current,n.scene.total],[3,3]); assert.deepEqual(n.scene.previous,{scene:3,bar:2});
  assert.equal(n.scene.next,null); assert.deepEqual(n.clip.next,{scene:3});
});
test('independent clips have per-track counters and empty tracks show zero, without inventing playback', () => {
  const m = emptySet(); m.tracks[0].clips[2] = emptyClip(48); m.tracks[0].clips[6] = emptyClip(16);
  const t = {playing:true,songFollow:false,scene:2,tracks:[{playing:6,active:2},{playing:-1,active:0}]};
  const n = transportNavigation(m,t,0);
  assert.equal(n.clip.current,2); assert.equal(n.clip.total,2); assert.deepEqual(n.clip.previous,{scene:2});
  assert.equal(transportNavigation(m,t,1).clip.current,0);
  assert.equal(transportNavigation(m,t,1).clip.total,0);
  assert.equal(transportNavigation(m,{...t,playing:false},0).clip.current,1);
});
