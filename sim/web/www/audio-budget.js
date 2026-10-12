// Browser audio-thread timing only: no inference about device CPU speed.
// record() mutates fixed fields; an envelope is allocated once per >=1 s of audio.
export function elapsedMs(start, end) {
  return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : null;
}
export class AudioBudget {
  constructor(rate, timingSource) {
    this.rate = rate;
    this.timingSource = timingSource;
    this.quanta = 0; this.late = 0; this.maxMs = 0; this.editMs = 0;
    this.resetWindow();
  }
  resetWindow() { this.windowMs = 0; this.busyMs = 0; this.valid = true; }
  record(frames, busyMs, editMs = 0, quantumMs = busyMs) {
    this.quanta++;
    const budget = 1000 * frames / this.rate;
    if (!Number.isFinite(budget) || budget <= 0) { this.valid = false; return false; }
    this.windowMs += budget;
    if (Number.isFinite(busyMs) && busyMs >= 0 && this.timingSource !== 'unavailable') {
      this.busyMs += busyMs;
      this.editMs += Math.max(0, Number.isFinite(editMs) ? editMs : 0);
      // Preserve the existing process-quantum counters; message work contributes
      // to load but does not change what the legacy late/max counters mean.
      if (Number.isFinite(quantumMs) && quantumMs >= 0) {
        this.maxMs = Math.max(this.maxMs, quantumMs);
        if (quantumMs > budget) this.late++;
      }
    } else this.valid = false;
    return this.windowMs >= 1000;
  }
  snapshot() {
    // Legacy counters required performance.now; keep that contract while
    // the new load estimate can use explicitly labeled coarse timing.
    const timed = this.timingSource === 'performance';
    const valid = this.timingSource !== 'unavailable' && this.valid && this.windowMs >= 1000;
    const loadPercent = valid ? 100 * this.busyMs / this.windowMs : null;
    const result = { type: 'stats', quanta: this.quanta, timed,
      late: timed ? this.late : null, maxMs: timed ? this.maxMs : null, editMs: timed ? this.editMs : null,
      timingSource: this.timingSource, windowMs: this.windowMs,
      busyMs: valid ? this.busyMs : null, loadPercent,
      availablePercent: valid ? Math.max(0, 100 - loadPercent) : null };
    this.resetWindow();
    return result;
  }
}
