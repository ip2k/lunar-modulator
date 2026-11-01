# Selected Trio interactive checkpoint A

Personal, non-commercial. Source base `ca45926a0cfdbfc6ebf45573446c80b270ea2b92`.
Tested production and fixture checkpoint: `83c59549e943021f71f83c4c9db43abee3b79174`.
This note follows that checkpoint; no source or test blob changes accompany it.

[verified] This opt-in host source proof composes the actual fixed Trio app,
existing SPSC transport/display leases, ordered accepted scanner events, an
injected startup facade and a bounded nonblocking SPI protocol model. No shared
builder, wrapper, target profile, MMIO binding or hardware activation is added.
The default selected diagnostic remains unchanged unless
`LUNAR_SELECTED_INTERACTIVE_PROOF` is explicitly defined; the new composition
also requires the existing `LUNAR_DIAGNOSTIC_OFFLINE_PROOF` boundary.

[verified] The sole main owner applies a bounded prefix of accepted events,
renders one real 64-frame block, publishes immutable PCM, and services drawing
and one SPI operation. Full PCM storage applies backpressure before input or app
mutation. Timer/scanner callbacks only enqueue accepted events. Audio only copies
published PCM or zeroes; it cannot render/apply/draw. Startup loads the generated
hash-bound fixed project, initializes the scanner, publishes the first actual
64-frame block, then calls injected audio-start before exposing either simulated
IRQ. Existing native rate 44,118 Hz, Q15 conversion followed once by x128, fixed
velocity 100 and visual divisor 1470 remain explicit in the oracle.

[verified] Accepted scanner hooks default to no-op. They preserve the existing
Dinghy decoder, debounce and aggregate state while recording chronological key
transitions and detents; scan sequence is provenance, never a sorting key. The
vendored file inventory and provenance record this local change. The linked
scanner remains GPL-3.0-only; this private host proof does not grant distribution
rights or a shareable firmware profile.

[verified] Display storage is retained across the entire 240-row frame. One
480-byte row is borrowed until exact ticket completion after final deselect.
The injected protocol performs CASET, RASET and RAMWR with clear, barrier,
fresh-low observation, barrier, launch, fresh completion and deselect. Finite
step and wrap-safe clock bounds quarantine frozen-clock/stale-DONE/errors.
Timeout, reentry, app or transport poison never implies completion or abort:
frame/row/unpublished PCM leases stay retained, and later calls issue no writes.
Every external SPI callback has a model post-hook poison check; the owner bridge
checks transport/app poison before and after each callback. These are observable
host callback boundaries, not atomic exclusion of arbitrary physical IRQ timing.

[verified] Two causal ownership corrections have RED/GREEN evidence: fault
publication during the first input callback must block the next callback, and a
fault during drawing must block row submission. Independent review additionally
found final-deselect reentry could release a poisoned row and clock-callback
transport poison could permit one further bus action. The final model retains
phase/source/ticket on poison, and the owner callback bridge closes the latter
boundary. These corrections touch only new checkpoint-A sources.

[verified] Normal and Clang ASan/UBSan runs both pass all five focused pytest
cases at the tested checkpoint, with leak detection enabled for every actual
app, shared reader, Trio engine, owner, model and fixture object. The actual-app
oracle compares 12,960 exact PCM blocks, 216 ordered controls, all 14 parameters,
level/info, unit selection/values, LEDs, scope and RGB565 pixels against a
separately initialized/driven app using the general PROJECT loader. It checks
first prefill before audio-start, actual scanner-to-queue-to-app composition,
queue wrap/backpressure, modifier-prefix splitting, REC/Capture/PLAY and no-store
SAVE behavior; all 240 transmitted rows (including first/last) match frozen
actual pixels. Seven actual-app modes cover positive, overflow, SPI failure,
repeated start, scanner startup failure, audio startup failure and bad config.

[verified] Small probes additionally pass 12 SPI scenarios, 60 operation errors,
62 hook reentries (including submit/poll clocks), wrong/late tickets, all 41
matrix IDs and seven detents with 93 scanner events/bounce/debounce, owner
apply/draw/clock/reentry poison, and transport poison at all 48 immediate-mode
row operations including final deselect. These negative-only owner probes use a
stub app; positive PCM/control/draw acceptance always uses actual Trio.

[verified] The actual host layout is app 241,536 bytes, owner 784 bytes and
platform 832 bytes; the bridge adds 56 bytes of owner storage on this host.
The fixture supplies 16 input records (128 bytes) and two PCM blocks (1,024
bytes). Actual app/sound/startup-reader storage stays static; new step paths use
scalar locals, no large scratch arrays or dynamic allocation. Capacities,
timeout/step bounds and callback lifetime are explicit caller-owned host proof
parameters, not a chosen production queue/deadline budget. Target size, stack,
publication code generation, IRQ priority/latency and aggregate fit remain untested.

[verified] The strict preparer is built separately without sanitizer flags for
the sanitized oracle. An earlier sanitized packing CLI run exposed two retained
4,096-byte allocations at process exit; its full LSan stderr/argv/source binding
are retained and assigned separately. No CLI sanitizer pass is claimed. All
owner/app/reader/engine/model objects retain ASan/UBSan and detect_leaks=1.
The current strict preparer still checks source, metadata/tool hashes, 597 packed
bytes and packed SHA `dc3c50d8da761fdfe36d17e1368d99f40740652192f14649230a9f8d7e3d58d4`.

Reproduce the lightweight probes with repository Python/pytest:

```sh
python3 -m pytest -s -q tests/test_native_spi_model.py --basetemp=<owned-path>
```

Actual-app proof additionally runs `tests/test_native_selected_interactive.py`
and `tests/test_native_diagnostic.py::test_current_input_manifest_and_vendor_pins`.
Use allocated LAN resources for that build. Sanitizer environment:
`FM1_SIM_CC=clang FM1_SIM_CXX=clang++ FM1_SIM_EXTRA='-fsanitize=address,undefined -fno-omit-frame-pointer' ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`.

[verified] Private evidence is under performance worktree
`scratch/devkit-20261023/audit-20261101/native-interactive-a/`: exact commands,
source hashes/diff, normal/sanitizer logs, preparation receipts, causal RED/GREEN
logs and `selected-trio.png`. The saved actual app frame was rendered and
inspected: Trio HOME labels/values have clear spacing and no clipping/overlap.
It proves host rendering, not a physical screen. The stage and temporary build
products are reproducible and removed after small evidence is copied; the Git
worktree remains for review/integration, then follows normal worktree cleanup.

Next dependency: independent exact-head source review, then coordinator
integration/CI. Target selection/build, concrete MMIO completion/quiescence,
publication/IRQ admission, runtime deadline/memory checks and physical
screen/control/audio acceptance are separate later milestones. This checkpoint
does not enable save, USB, MIDI, CPU1, ROM, reset, watchdog or any device traffic,
and does not complete the release goal.
