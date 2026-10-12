// Native RAM part indices stay unchanged; only their display order changes.
export const RAM_ORDER = [5, 4, 0, 1, 2, 3];
export function cpuPresentation(stats, powered) {
  const load = stats?.loadPercent;
  const ready = powered && Number.isFinite(load) && load >= 0 && stats.windowMs >= 1000;
  const source = stats?.timingSource === 'date-now' ? 'coarse Date.now timing' : 'high resolution timing';
  const explanation = 'Browser DSP estimate; FM-1 CPU usage is unmeasured.';
  if (!ready) return { text: '–', percent: 0, over: false,
    detail: `${explanation} ${!powered ? 'Audio is off.' : stats ? 'Timing unavailable.' : 'Waiting for an audio timing window.'}` };
  return { text: `${load.toFixed(1)} %`, percent: Math.min(100, load), over: load > 100,
    detail: `${explanation} ${load.toFixed(1)} % used, ${Math.max(0, 100 - load).toFixed(1)} % available${load > 100 ? `, ${(load - 100).toFixed(1)} % over budget` : ''}; ${stats.busyMs.toFixed(1)} ms busy / ${stats.windowMs.toFixed(1)} ms audio, ${source}. Includes render, control and editor work.` };
}
