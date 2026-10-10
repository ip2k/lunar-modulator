import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runInNewContext } from 'node:vm';
import { installPlaybackTimeline, classifyAudioTrace } from './playback-timeline.mjs';
import { playbackDelta } from './playback-stats.mjs';

test('raw publication samples preserve a delayed event in the original baseline delta', () => {
  let tick, cleared = false, now = 0;
  const window = {}, marks = [];
  runInNewContext(`(${installPlaybackTimeline})();`, { window,
    performance: { now: () => now, timeOrigin: 10000, mark: (s) => marks.push(s) },
    setInterval: (f, ms) => { assert.equal(ms, 1000); tick = f; return 8; },
    clearInterval: (id) => { assert.equal(id, 8); cleared = true; } });
  const timeline = window.__lunarPlaybackTimeline;
  const stats = { underrunEvents: 0, underrunDuration: 0, totalDuration: 0 };
  window.fm1 = { ctx: { playbackStats: stats, currentTime: 0, state: 'running', sampleRate: 44100 } };
  const before = { events: 0, seconds: 0, total_seconds: 0 };
  timeline.mark('baseline', before);
  // A pending event publishes later. Observing it does not move the baseline.
  now = 1000; stats.underrunEvents = 1; stats.underrunDuration = 512 / 44100; stats.totalDuration = 1;
  tick();
  timeline.mark('drain-end');
  const report = timeline.stop();
  assert.equal(report.samples[0].raw, null);
  assert.equal(report.samples[1].raw, before);
  assert.equal(report.samples[2].raw.seconds, 512 / 44100);
  assert.equal(report.samples[2].raw.total_seconds, 1);
  assert.equal(playbackDelta(before, report.samples.at(-1).raw).underrun_events, 1);
  assert.equal(playbackDelta(before, report.samples.at(-1).raw).underrun_ms, 1000 * 512 / 44100);
  assert.equal(cleared, true);
  assert.deepEqual(marks, ['lunar-phase:page-init', 'lunar-phase:baseline', 'lunar-phase:drain-end']);
});

test('bounded timeline stops sampling, marks unsupported stats and captures getter errors', () => {
  let tick;
  const window = { fm1: { ctx: { get playbackStats() { throw new Error('unavailable'); } } } };
  runInNewContext(`(${installPlaybackTimeline})();`, { window,
    performance: { now: () => 0, timeOrigin: 1, mark() {} },
    setInterval: (f) => { tick = f; return 1; }, clearInterval() {} });
  for (let k = 0; k < 205; ++k) tick();
  const report = window.__lunarPlaybackTimeline.stop();
  assert.equal(report.samples.length, 200);
  assert.equal(report.samples_dropped, 6);
  assert.equal(report.samples[0].error, 'unavailable');
  assert.equal(report.samples[0].raw, null);
});

test('explicit trace shortages are separated from empty FIFO counters and assigned at phase boundaries', () => {
  const events = [
    { name: 'SyncReader::Read timed out', ts: 5 },
    { name: 'lunar-phase:baseline', ts: 10 },
    { name: 'PushPullFIFO frames', ts: 11, args: { value: 0 } },
    { name: 'lunar-phase:loop-begin', ts: 15 },
    { name: 'PushPullFIFO::Pull underrun', ts: 15, args: { 'missing frames': 128 } },
    { name: 'Glitch!', ts: 16 },
    { name: 'lunar-phase:snapshot-drain', ts: 20 },
    { name: 'SyncReader::Read timed out', ts: 20 },
    { name: 'PushPullFIFO::PullAndUpdateEarmarkedFrames underrun', ts: 21 },
    { name: 'PushPullFIFO overrun', ts: 22 },
  ];
  const r = classifyAudioTrace(events.reverse(), { complete: false, dropped: 7 });
  assert.deepEqual(r.counts, { sync_reader_timeout: 2, glitch: 1, fifo_pull_shortage: 1, fifo_earmarked_shortage: 1, fifo_overrun: 1 });
  assert.equal(r.by_phase.unlocated.sync_reader_timeout, 1);
  assert.equal(r.by_phase['loop-begin'].fifo_pull_shortage, 1);
  assert.equal(r.by_phase['snapshot-drain'].sync_reader_timeout, 1);
  assert.equal(r.fifo_zero_counter_samples, 1);
  assert.equal(r.trace_complete, false);
  assert.equal(r.trace_events_dropped, 7);
  assert.match(r.interpretation, /absence does not prove/);
  const empty = classifyAudioTrace([{ name: 'PushPullFIFO frames', args: { value: 0 } }], { complete: true, dropped: 0 });
  assert.equal(Object.values(empty.counts).reduce((a, b) => a + b), 0);
});
