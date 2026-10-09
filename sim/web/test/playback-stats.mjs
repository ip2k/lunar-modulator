// AudioContext.playbackStats uses seconds for duration, unlike our ms report.
// Keep the browser's integer event count unchanged, including single events.
// MIT licence, like the rest of this repository.
export function playbackDelta(before, after) {
  if (!after) return null;
  return {
    underrun_events: after.events - (before ? before.events : 0),
    underrun_ms: 1000 * (after.seconds - (before ? before.seconds : 0)),
  };
}
