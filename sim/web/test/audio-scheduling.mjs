// Offline scheduling probe: a browser oscillator, without Lunar or a worklet.
// Run only in a bounded LAN container. Node workers add CPU pressure in
// the second phase; this is diagnostic evidence, not a replacement CI gate.
// PLAYWRIGHT_DIR=/pw node audio-scheduling.mjs OUT [SECONDS_PER_PHASE] [WORKERS]
// MIT licence, like the rest of this repository.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { Worker } from 'node:worker_threads';
import { launch } from './launch.mjs';
import { playbackDelta } from './playback-stats.mjs';

const [out, secondsArg, workersArg] = process.argv.slice(2);
const seconds = Number(secondsArg || 10);
const workers = Number(workersArg || 2);
if (!out || !Number.isFinite(seconds) || seconds < 1 || seconds > 60 ||
    !Number.isInteger(workers) || workers < 1 || workers > 4) {
  throw new Error('Expected OUT, 1..60 seconds per phase, and 1..4 pressure workers');
}
mkdirSync(out, { recursive: true });
const cgroup = (name) => {
  try { return readFileSync(`/sys/fs/cgroup/${name}`, 'utf8').trim(); }
  catch { return null; }
};
const { browser, name } = await launch();
const page = await browser.newPage();
const session = await browser.newBrowserCDPSession();
const events = [];
session.on('Tracing.dataCollected', (e) => events.push(...e.value));
await session.send('Tracing.start', {
  categories: 'audio,webaudio,disabled-by-default-audio',
  transferMode: 'ReportEvents',
});
await page.evaluate(async () => {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  osc.connect(ctx.destination);
  osc.start();
  await ctx.resume();
  window.probeContext = ctx;
});
await page.waitForTimeout(1000);
const snapshot = () => page.evaluate(() => {
  const s = window.probeContext.playbackStats;
  if (!s) throw new Error('This probe requires Chromium playbackStats');
  return { events: s.underrunEvents, seconds: s.underrunDuration };
});
const drainMs = 250;
const report = { browser: name, seconds, workers, drain_ms: drainMs, cpu_max: cgroup('cpu.max'), phases: [] };
for (const pressure of [false, true]) {
  const before = await snapshot();
  const cpuBefore = cgroup('cpu.stat');
  await session.send('Tracing.recordClockSyncMarker', { syncId: pressure ? 'pressure-start' : 'idle-start' });
  const activeWorkers = pressure ? Array.from({ length: workers }, () => new Worker('while (true) {}', { eval: true })) : [];
  await page.waitForTimeout(seconds * 1000);
  await Promise.all(activeWorkers.map((worker) => worker.terminate()));
  // Let audio service glitch counters reach the renderer after CPU pressure
  // stops; this does not remove any event from the cumulative counter.
  await page.waitForTimeout(drainMs);
  const after = await snapshot();
  await session.send('Tracing.recordClockSyncMarker', { syncId: pressure ? 'pressure-end' : 'idle-end' });
  report.phases.push({
    pressure, playback: playbackDelta(before, after),
    cpu_before: cpuBefore, cpu_after: cgroup('cpu.stat'),
  });
}
await page.evaluate(() => window.probeContext.close());
const complete = new Promise((resolve) => session.once('Tracing.tracingComplete', resolve));
await session.send('Tracing.end');
await complete;
report.trace = {
  fake_worker_reads: events.filter((e) => e.name === 'Worker::DoRead').length,
  reader_timeouts: events.filter((e) => e.name === 'SyncReader::Read timed out').length,
};
for (const phase of report.phases) {
  const prefix = phase.pressure ? 'pressure' : 'idle';
  const marker = (suffix) => events.find((e) => e.name === 'clock_sync' && e.args.sync_id === `${prefix}-${suffix}`).ts;
  const start = marker('start'), end = marker('end');
  phase.reader_timeouts = events.filter((e) => e.name === 'SyncReader::Read timed out' && e.ts >= start && e.ts <= end).length;
}
writeFileSync(join(out, 'trace.json'), JSON.stringify({ traceEvents: events }));
writeFileSync(join(out, 'probe.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
await browser.close();
