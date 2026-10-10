# Repeat effect implementation note

Branch: `feature/2026-10-09@repeat-effect`  
Base: `7eb55b1fd05b8e03fc9dcaf663ce194019299dbf` (`origin/main` when work began)

## Design contract

Repeat is an original MIT stutter/hold effect. Its inspiration is the open
performance-FX work credited in
`notes/2026-10-01-arp-modulation-effects-options.md`; no upstream code is
copied. It uses the existing API v3 `render_ext` host events, not a new clock.

- One per-instance ring has 16,384 stereo frames of signed 16-bit samples
  (65,536 bytes), plus state. That entire allocation is reported by
  `instance_size`, so existing patch admission counts it even when no loop is
  held. Capture waits for all 16,384 frames so any later supported window
  change can read initialized history; at 8 kHz the first capture can therefore
  take 2.048 seconds. The instance refuses sample rates outside finite
  8,000–192,000 Hz.
- Controls are `Hold` (Off/On), `Max slice` (`1/8 max`, `1/16 max`, `1/32 max`)
  and `Mix`. The value returned for a saved parameter remains the value last
  set; the engine does not pretend an effective slice is the requested one.
- A requested note division uses `sample_rate * 240 / bpm / denominator`
  frames. At each beat boundary the effect halves that exact duration by
  powers of two until it fits the ring, down through `1/256` note. It never
  truncates a beat window to an arbitrary number of frames. The effective
  denominator and frame count are exposed in focused native test output.
- A running Hold-on arms a capture at the next explicit BEAT event, after a
  complete ring of input history exists. A stopped Hold-on captures as soon as
  a complete ring exists. No partially filled history is latched. Once held,
  the ring is frozen and the selected slice loops; it cannot be overwritten
  during playback. The selected window starts at `ring_write - loop_frames`,
  so playback is the newest requested slice ending at that beat, not the old
  region at the start of the ring. A nonperiodic native fixture distinguishes
  these cursors.
- Turning Hold off releases the wet signal over 5 ms, then recording resumes.
  STOP releases and clears/disarms history; a still-high Hold does not
  recapture while stopped. An explicit Hold set or a later START can arm it
  again. START clears history; if Hold is high it waits for a full new ring
  and a subsequent BEAT. At a shared frame, event ordering is STOP, START,
  BEAT as defined by `fm1_engine.h`.
- BPM and slice-size changes apply only at host beat boundaries. A held loop
  is not written while its play window changes; old and new read positions
  crossfade over 5 ms using the same frozen ring. The final 5 ms loop region
  fades toward the first sample and meets it exactly at wrap without shortening
  the loop; a discontinuous fixture checks the seam against the raw jump. The effect does not infer
  that preset loading or panic sends RESET: current hosts document RESET but
  do not emit it yet. Direct extension tests cover RESET handling.
- Mix has an exact dry bypass at settled Mix=0. Hold transitions and window
  changes are smoothed to avoid abrupt output edges. The direct `render`
  fallback has stopped-transport semantics. `get_param` remains NULL because
  the host owns the clamped values passed through `set_param`; the requested
  Max slice is saved as selected, while the effective subdivision depends on
  current tempo and sample rate.

## Verification boundary

This note records design and focused progress, not completion. Meaningful checks cover the
supported rate/tempo edges, effective divisions, initial history, stopped
capture, beat alignment, frozen storage, re-trigger, STOP/START/RESET, tempo
jumps, event offsets, chunk invariance, deterministic finite output, and
bit-exact zero-mix dry. Native and WebAssembly checks use the project's
bounded LAN build path. They do not establish FM-1 runtime CPU/SRAM use,
installability, or hardware behavior.

Semantic tooling was checked for this task. Serena was activated at this
worktree and its symbol overview located Echo's render implementation.
Rarefaction is available but its configured root remains the primary checkout
(`~/Developer/mvave-fm1-firmware/engines`), not this worktree; its fx-host
orientation is useful for the shared API contract, but is not treated as
index evidence for this branch. File inspection remains the source check for
this new worktree.
