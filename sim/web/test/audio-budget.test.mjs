import test from 'node:test';
import assert from 'node:assert/strict';
import { AudioBudget, elapsedMs } from '../www/audio-budget.js';
import { cpuPresentation, RAM_ORDER } from '../www/editor/resource-meter.js';
test('load uses the audio frame budget, supports overload and keeps cumulative counters', () => {
  const b = new AudioBudget(1000, 'performance');
  assert.equal(b.record(500, 500, 10), false);
  assert.equal(b.record(500, 500, 10), true);
  const one = b.snapshot();
  assert.equal(one.loadPercent, 100); assert.equal(one.availablePercent, 0); assert.equal(one.editMs, 20);
  assert.equal(one.windowMs, 1000); assert.equal(one.quanta, 2); assert.equal(one.late, 0);
  assert.equal(b.record(1000, 1500, 20), true);
  const two = b.snapshot();
  assert.equal(two.loadPercent, 150); assert.equal(two.availablePercent, 0);
  assert.equal(two.quanta, 3); assert.equal(two.late, 1); assert.equal(two.editMs, 40);
  assert.match(cpuPresentation(two, true).detail, /50.0 % over budget/);
});
test('unavailable or backward timing yields no fabricated load and next window recovers', () => {
  const b = new AudioBudget(1000, 'date-now');
  assert.equal(elapsedMs(7, 6), null); assert.equal(elapsedMs(null, 0), null);
  b.record(1000, elapsedMs(7, 6));
  assert.equal(b.snapshot().loadPercent, null);
  b.record(1000, 300); const recovered = b.snapshot();
  assert.equal(recovered.loadPercent, 30); assert.equal(recovered.timed, false); assert.equal(recovered.late, null); assert.match(cpuPresentation(recovered, true).detail, /coarse Date.now/);
  const missing = new AudioBudget(1000, 'unavailable'); missing.record(1000, 0);
  assert.equal(missing.snapshot().loadPercent, null);
  assert.equal(cpuPresentation(recovered, false).text, '–');
  assert.match(cpuPresentation(null, true).detail, /Waiting/);
  assert.deepEqual(RAM_ORDER, [5, 4, 0, 1, 2, 3]);
});

test('control work enters total load without redefining legacy process-late counters', () => {
  const b = new AudioBudget(1000, 'performance');
  b.record(1000, 1200, 25, 900);
  const s = b.snapshot();
  assert.equal(s.loadPercent, 120); assert.equal(s.late, 0);
  assert.equal(s.maxMs, 900); assert.equal(s.editMs, 25);
});
