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
  If Hold is re-enabled before that release completes, the old frozen capture is
  cleared at the dry endpoint and the effect requires a full new ring plus a
  BEAT before latching. This deliberately adds the normal full-ring warm-up to
  a quick re-hold so the released segment cannot return.
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

Independent source review found three ramp/repeated-write defects and one quick-rehold
lifecycle defect in the initial implementation.
When a transport/release action requested wet=0 while already dry, a zero-delta wet
ramp ended by inferring its target from the sign of the step and incorrectly set wet=1.
Also, resending an unchanged Mix target restarted an in-flight ramp. The implementation
now tracks the explicit wet target at ramp completion, cancels already-settled wet ramps,
and leaves unchanged Mix and Hold targets' original deadlines intact. Repeated Hold-Off
does not restart release or discard STOP's clear request; explicitly setting unchanged
Hold-On after STOP still rearms capture. A rapid re-hold during a
release now clears the frozen ring at the dry endpoint and waits for a new full capture
before accepting BEAT while running (stopped capture latches when that ring fills).
Native regressions cover
START, STOP, RESET and Hold-Off while dry with nonzero Mix, same-target Mix and Hold-Off
writes five frames into their ramps, and a re-hold followed by both an early BEAT and a
fresh-ring BEAT. The tests also preserve STOP's clear request through repeated Hold-Off
and verify an explicit unchanged Hold-On can rearm after STOP. Current focused native
self-test: 13 passed, 0 failed. Generated GPL-on metadata reports a **65,648-byte Repeat
instance**: the 65,536-byte ring plus aligned effect state. That is distinct from total
renderer scenario memory.

The final bounded aeon build used pinned Alpine 3.22 and Emscripten 6.0.10 images. Its
106 scenarios all passed: 106/106 identical to JavaScript and musl, 103/106 identical to
glibc with the established three libm-sensitive cases. `four-sounds-repeat-admission`
loaded Macro, Drums, DX7 and Six-Op as four active sounds, Comp and Repeat in the two
MASTER slots, and one Crush insert. It passed with **185,840 bytes wasm32 renderer RAM**
(200,472 bytes native64), zero audio differences and zero screen pixels; this is desktop
simulator admission evidence, not target-device SRAM admission. The separate
`seq-repeat-beat-hold` scenario passed with zero dropped events and 105,116 bytes total
scenario memory. Module: 1,557,830 bytes, SHA-256
`edda579cc762bc225246cd8204a0652729e7d24d65bea13b5d2eeb8360898b6f`; generated metadata
id `0d1d0b8b`; engine source hash `12db9e486085c7545fa3fe3abd2708692d3b9142cf02731e49909355f00f9db3`, simulator source hash
`4f03098ea5cd44fbacccff518241acf8b665281f054e4bd5a8c75e3040b3ad30`. The edit-layer
parity check passed with max audio delta 0; a 30-second storm completed 10,341 quanta
with zero late quanta. Build used GPL modules enabled, and Repeat remains MIT / GPL-off.

Native and WebAssembly checks use the project's bounded LAN build path. They do not
establish FM-1 runtime CPU/SRAM use, installability, or hardware behavior. Browser
screenshot/editor checks were not part of this `--no-screenshot` build.

A separate GPL-off build compiled a 1,298,505-byte Wasm (`fc2030d44f34de5bf02140e74d1b7144fc445d90212d90b2351f71805aed0860`). Focused parity for `seq-repeat-beat-hold` and `four-sounds-repeat-admission` passed 2/2 against JS, musl, and glibc. The Wasm metadata test passed, with GPL disabled, Repeat still present as MIT, and 65,648-byte instance RAM (metadata id `0d94de44`). The full GPL-off parity script reaches an existing GPL-only Acid Bass scenario and exits when that module is unavailable; the full script currently does not filter GPL scenarios for this profile. The focused GPL-off cases establish Repeat's profile behavior, not full GPL-off suite coverage.

Semantic tooling was checked for this task. Serena was activated at this
worktree and its symbol overview located Echo's render implementation.
Rarefaction is available but its configured root remains the primary checkout
(`~/Developer/mvave-fm1-firmware/engines`), not this worktree; its fx-host
orientation is useful for the shared API contract, but is not treated as
index evidence for this branch. File inspection remains the source check for
this new worktree.

## Parameter contract correction

[verified: exact source and bounded native tests] Review of source head
`9b2d80c4c6a9df47c794fa4d413a72e12b645225` found that Repeat's controls were
missing from `tests/fixtures/param-uids.json`, and Hold / Max slice had no
recorded ENUM flag decisions in `tests/test_engine_params.py`. The unchanged
checks failed for the extra `repeat` module and those two enum entries in the
combined Warble / Repeat native build (2 failures, 11 passes).

The correction appends only Repeat's existing UID 1 Hold, UID 2 Max slice and
UID 3 Mix pins, and records the two enum controls as modulatable. Hold ramps
wet/dry; Max slice hands over through the loop crossfade. All existing pins,
effect source and generated artifacts are retained. An exact tracked-tree
export of this Repeat branch, with this correction, passed all 15 tests in
`test_engine_params.py` and `test_engines_repeat.py` on aeon in the pinned
Emscripten 6.0.10 image (four CPUs, 8 GiB, batch slice); the Repeat self-test
still reports 13 passing checks. This is a native contract check, not browser
or device evidence. Recovery receipt: aeon
`/home/claude/mvave-fm1/repeat-param-contract-20261009/src/params-after.log`.
