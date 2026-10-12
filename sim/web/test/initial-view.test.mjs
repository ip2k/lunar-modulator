import assert from 'node:assert/strict';
import test from 'node:test';
import { hasSequenceContent, makeInitialView } from '../www/editor/initial-view.js';
import { emptySet, emptyClip, writeSet } from '../www/editor/sequence-model.js';
const doc = change => { const set = emptySet(); change?.(set); return { set: writeSet(set) }; };
test('canonical defaults and sounds are not a sequence; clips and arrangement are', () => {
  assert.equal(hasSequenceContent(doc()), false);
  assert.equal(hasSequenceContent({ sounds: [{ engine: 'FM6' }] }), false);
  assert.equal(hasSequenceContent(doc(m => m.song = [0])), true);
  assert.equal(hasSequenceContent(doc(m => m.tracks[7].clips[7] = emptyClip())), true);
  assert.equal(hasSequenceContent({ set: ['broken'] }), false);
});
test('default settles once; user choice and same-project restores win', () => {
  const view = makeInitialView('one'), song = doc(m => m.song = [0]);
  assert.equal(view.fromProject('one', song), 'sequencer');
  assert.equal(view.fromProject('one', doc()), null);
  view.choose(); assert.equal(view.project('one'), false);
  assert.equal(view.fromProject('one', song), null);
  assert.equal(view.project('two'), true);
  assert.equal(view.fromProject('one', song), null, 'stale project snapshot');
  assert.equal(view.fromProject('two', doc()), 'flow');
});
test('explicit selection during initial read beats the delayed default', () => {
  const view = makeInitialView('one'); view.choose();
  assert.equal(view.fromProject('one', doc(m => m.song = [0])), null);
  assert.equal(view.pending, false);
  view.project('two'); view.choose();
  assert.equal(view.fromProject('two', doc()), null);
});
