// Read-only visual projections of native clip positions and parameter locks. MIT.
const TICKS_PER_STEP = 24;
export function clipPlayback(c, track, playing, scene) {
  if (!playing || !c || track?.playing !== scene || !Number.isFinite(track.posTick)) return null;
  const tick = track.posTick - c.loopStart * TICKS_PER_STEP;
  const span = c.length * TICKS_PER_STEP;
  // Native already advances at scaleNum/scaleDen and wraps at loop end.
  // Do not apply the ratio again or derive positions from the master clock.
  if (tick < 0 || tick >= span) return null;
  return { fraction: tick / span, step: track.posTick / TICKS_PER_STEP };
}
export function automationSteps(c, lane, base, start, end) {
  const locks = new Map(c.locks.filter(l => l.lane === lane).map(l => [l.step, l.value]));
  const notes = new Set(c.notes.map(n => n.step));
  const loopEnd = c.loopStart + c.length;
  // Native effective_at scans back cyclically inside the loop. Locks win
  // over a note on the same step; a note without a lock resets to base.
  function effective(step) {
    if (step < c.loopStart || step >= loopEnd) return base;
    for (let d = 0; d < c.length; d++) {
      const at = c.loopStart + ((step - c.loopStart - d) % c.length + c.length) % c.length;
      if (locks.has(at)) return locks.get(at);
      if (notes.has(at)) return base;
    }
    return base;
  }
  return Array.from({ length: Math.max(0, end - start) }, (_, i) => {
    const step = start + i;
    return { step, value: effective(step), lock: locks.get(step), reset: notes.has(step) && !locks.has(step),
      inLoop: step >= c.loopStart && step < loopEnd };
  });
}
