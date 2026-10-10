// Bounded CI scheduling evidence. This observes, and does not retry or grade,
// the storm. Browser-wide tracing includes the out-of-process audio service.
// MIT licence, like the rest of this repository.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { availableParallelism, cpus } from 'node:os';
import { classifyAudioTrace } from './playback-timeline.mjs';

export function resourceSnapshot(read = (path) => readFileSync(path, 'utf8')) {
  const files = {};
  const capture = (path, filter = (s) => s.trim()) => {
    try { files[path] = { text: filter(read(path)), error: null }; }
    catch (e) { files[path] = { text: null, error: e.code || e.message }; }
  };
  // Record the mount/namespace context too: a mounted cgroup may describe an
  // ancestor rather than this process alone. Keep raw counters and provenance.
  capture('/proc/self/cgroup');
  capture('/proc/self/mountinfo', (s) => s.split('\n').filter((l) => / - cgroup2? /.test(l)).join('\n'));
  for (const name of ['cpu.max', 'cpu.stat', 'cpu.pressure']) capture(`/sys/fs/cgroup/${name}`);
  capture('/proc/pressure/cpu');
  capture('/proc/stat', (s) => s.split('\n').filter((l) => /^cpu(?:\d+)? /.test(l)).join('\n'));
  capture('/proc/loadavg');
  capture('/proc/self/status', (s) => s.split('\n').filter((l) => /^Cpus_allowed_list:/.test(l)).join('\n'));
  return {
    utc: new Date().toISOString(), monotonic_ns: process.hrtime.bigint().toString(),
    affinity_parallelism: availableParallelism(), logical_cpus: cpus().length, files,
  };
}

export async function startSchedulingCapture(browser, out, {
  trace = false, snapshot = resourceSnapshot, timeoutMs = 10000, maxEvents = 200000,
  phases = false,
} = {}) {
  const report = {
    schema: 1, trace_requested: trace, trace_started: false, trace_complete: false,
    trace_categories: `audio,webaudio,disabled-by-default-audio${phases ? ',blink.user_timing' : ''}`,
    perturbation: `${trace ? 'CDP tracing and one-second resource reads' : 'One-second resource reads'} can affect scheduling; this is an instrumented run.`,
    trace_window: phases ? 'Diagnostic starts before page navigation/power-on and ends after storm/idle evaluation and snapshot drain. Playback baseline/window and zero gate are unchanged.' : 'Starts before storm page.evaluate and ends after it, including the snapshot drain. Playback counters have their own narrower window.',
    errors: [], samples: [], trace_events_saved: 0, trace_events_dropped: 0,
  };
  const events = [];
  let session;
  const sample = () => report.samples.push(snapshot());
  sample();
  // Persist initial evidence before starting the test, in case it crashes.
  const saveReport = () => writeFileSync(join(out, 'editor-scheduling.json'), JSON.stringify(report, null, 2) + '\n');
  saveReport();
  const timer = setInterval(() => { sample(); saveReport(); }, 1000);
  timer.unref();
  if (trace) {
    try {
      session = await browser.newBrowserCDPSession();
      session.on('Tracing.dataCollected', ({ value }) => {
        const remaining = Math.max(0, maxEvents - events.length);
        for (const event of value.slice(0, remaining)) events.push(event);
        report.trace_events_dropped += Math.max(0, value.length - remaining);
      });
      await session.send('Tracing.start', { categories: report.trace_categories, transferMode: 'ReportEvents' });
      report.trace_started = true;
      await session.send('Tracing.recordClockSyncMarker', { syncId: 'lunar-storm-start' });
    } catch (e) { report.errors.push(`trace start: ${e.message}`); }
  }
  return {
    async finish() {
      clearInterval(timer);
      sample();
      if (report.trace_started) {
        let deadline;
        const completed = new Promise((resolve) => {
          session.once('Tracing.tracingComplete', () => { report.trace_complete = true; resolve(); });
          deadline = setTimeout(resolve, timeoutMs);
        });
        try {
          await session.send('Tracing.recordClockSyncMarker', { syncId: 'lunar-storm-end' });
          await session.send('Tracing.end');
          await completed;
          if (!report.trace_complete) report.errors.push('trace drain timed out; trace is incomplete');
        } catch (e) { report.errors.push(`trace end: ${e.message}`); }
        finally { clearTimeout(deadline); }
      }
      report.trace_events_saved = events.length;
      if (phases) report.audio_classification = classifyAudioTrace(events, {
        complete: report.trace_complete, dropped: report.trace_events_dropped,
      });
      // Write partial evidence even if CDP fails; completeness is explicit.
      if (trace) writeFileSync(join(out, 'editor-audio-trace.json'), JSON.stringify({ traceEvents: events }));
      saveReport();
      if (session) await session.detach().catch(() => {});
      return report;
    },
  };
}
