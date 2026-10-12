// Native track-name format/model contracts. MIT.
import test from 'node:test';
import assert from 'node:assert/strict';
import { emptySet, parseSet, writeSet, validateSet } from '../www/editor/sequence-model.js';

test('track names persist as native hex lines including significant spaces', () => {
  const m = emptySet(); m.tracks[0].name = ' Bass 1 '; m.tracks[7].name = '1234567890123456';
  m.sceneNames[0] = 'Intro';
  const lines = writeSet(m);
  assert(lines.includes('tn 0 2042617373203120'));
  assert.deepEqual(parseSet(lines), m);
  assert.equal(parseSet('movy1\ntn 0 4C4541442031').tracks[0].name, 'LEAD 1');
});
test('legacy sets use empty numbered fallbacks and clearing omits tn', () => {
  const m = parseSet(['movy1', 'tk 0 0 0']);
  assert(m.tracks.every(t => t.name === ''));
  m.tracks[0].name = 'Bass'; m.tracks[0].name = '';
  assert(!writeSet(m).some(l => l.startsWith('tn ')));
});
test('invalid native names are rejected rather than silently shortened', () => {
  for (const hex of ['123', '42zz', '00', '0a', '7f', 'c3a9', '3132333435363738393031323334353637']) {
    assert.throws(() => parseSet(`movy1\ntn 0 ${hex}`));
  }
  for (const line of ['tn 0', 'tn 8 4142', 'tn 0 4142 extra']) assert.throws(() => parseSet(`movy1\n${line}`));
  for (const name of ['12345678901234567', 'bad\n', 'é']) {
    const m = emptySet(); m.tracks[0].name = name;
    assert.equal(validateSet(m).valid, false); assert.throws(() => writeSet(m));
  }
});
test('tn is a known native field while other extension lines survive', () => {
  const m = parseSet('movy1\ntn 0 42617373\nfuture opaque');
  assert.deepEqual(m.unknown, ['future opaque']); assert.deepEqual(parseSet(writeSet(m)), m);
  m.unknown.push('tn 1 41'); assert.equal(validateSet(m).valid, false);
});
