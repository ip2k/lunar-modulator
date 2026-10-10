// Opt-in observation of published browser counters, not an acceptance window.
// MIT licence, like the rest of this repository.

// Passed to Playwright addInitScript; deliberately self-contained in the page.
export function installPlaybackTimeline() {
  const samples = [];
  let dropped = 0;
  const sample = (phase, supplied) => {
    const ctx = window.fm1?.ctx;
    let raw = null, error = null;
    try {
      if (supplied !== undefined) raw = supplied;
      else {
        const stats = ctx?.playbackStats;
        raw = stats ? { events: stats.underrunEvents, seconds: stats.underrunDuration,
          total_seconds: stats.totalDuration } : null;
      }
    } catch (e) { error = e.message; }
    const row = { phase, page_ms: performance.now(), time_origin_ms: performance.timeOrigin,
      audio_seconds: ctx?.currentTime ?? null, state: ctx?.state ?? null,
      sample_rate: ctx?.sampleRate ?? null, raw, error };
    if (samples.length < 200) samples.push(row); else dropped++;
    return row;
  };
  const mark = (phase, supplied) => {
    performance.mark(`lunar-phase:${phase}`);
    return sample(phase, supplied);
  };
  mark('page-init');
  // Chromium's getters take the graph lock. One-second observation is bounded
  // but still perturbs scheduling and may miss publications between samples.
  const timer = setInterval(() => sample('tick'), 1000);
  window.__lunarPlaybackTimeline = { mark, stop() {
    clearInterval(timer);
    return { schema: 1, interval_ms: 1000, samples, samples_dropped: dropped,
      interpretation: 'Raw cumulative published counters; sample times are not glitch times. Getter graph-lock access and tracing perturb scheduling.' };
  } };
}

// Exact Chromium 153 trace names; ordinary zero-after-pull FIFO counters are
// separate observations, never classified as a shortage or a glitch.
export function classifyAudioTrace(events, { complete, dropped }) {
  const markers = events.filter((e) => e.name?.startsWith('lunar-phase:') && Number.isFinite(e.ts))
    .sort((a, b) => a.ts - b.ts);
  const kinds = {
    'SyncReader::Read timed out': 'sync_reader_timeout', 'Glitch!': 'glitch',
    'PushPullFIFO::Pull underrun': 'fifo_pull_shortage',
    'PushPullFIFO::PullAndUpdateEarmarkedFrames underrun': 'fifo_earmarked_shortage',
    'PushPullFIFO overrun': 'fifo_overrun',
  };
  const counts = Object.fromEntries(Object.values(kinds).map((k) => [k, 0]));
  const by_phase = {}, explicit_events = [];
  let zero_counters = 0;
  for (const e of events) {
    if (e.name === 'PushPullFIFO frames' && e.args?.value === 0) zero_counters++;
    const kind = kinds[e.name];
    if (!kind) continue;
    counts[kind]++;
    const marker = Number.isFinite(e.ts) ? markers.findLast((m) => m.ts <= e.ts) : null;
    const phase = marker ? marker.name.slice('lunar-phase:'.length) : 'unlocated';
    by_phase[phase] ??= Object.fromEntries(Object.values(kinds).map((k) => [k, 0]));
    by_phase[phase][kind]++;
    // The source trace remains authoritative if this compact list is capped.
    if (explicit_events.length < 200) explicit_events.push({ kind, phase,
      ts_us: e.ts ?? null, pid: e.pid ?? null, tid: e.tid ?? null, args: e.args ?? {} });
  }
  return { counts, by_phase, explicit_events, explicit_events_dropped: Object.values(counts).reduce((a, b) => a + b, 0) - explicit_events.length,
    fifo_zero_counter_samples: zero_counters, markers: markers.map((m) => ({ phase: m.name.slice(12), ts_us: m.ts })),
    trace_complete: complete, trace_events_dropped: dropped,
    interpretation: 'Counts only explicit named events in saved trace. Zero FIFO occupancy is not a shortage; absence does not prove no glitch, especially in incomplete traces.' };
}
