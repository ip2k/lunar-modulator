# Selected audio-only main-owner binding — 2026-11-01

This opt-in source slice starts from `6ece5032bb4a2e7f3856350c89015725f727a473`.
Previously, the selected return platform applied aggregate controls and rendered
in ALNK IRQ. The new audio-only profile applies accepted input and renders in
main; Timer5 only scans/enqueues, and ALNK copies published PCM or zeros into its
free DMA half. Conversion by 128 occurs once in the existing main render adapter.

The named builder is `tools/native/build_selected_trio_audio_owner.py`. It retains
the complete aggregate PROJECT closure and its one app, 64 KiB startup/offline-stage
arena, permanent owner, 16 input records and two producer PCM slots. The hardware
DMA buffer is a separate 1,024-byte object. No live stage/SAVE/storage operation is
bound. Existing default, selected, return and aggregate plans remain unchanged.

The audio-only owner does not initialize SPI or draw. No fake completion callback,
LCD fill or display register access is introduced. Source PND conventions still
do not establish final-clock or DMA-read retirement; this profile has no UI claim.
The common owner layout still contains its inactive row/SPI storage.

## Startup and lifetime

The new platform prepares with global IRQs and DMA off. Primary IRQ initialization
precedes app/scanner setup. Four actual app renders supply two DMA halves followed
by two queued blocks; each produce/consume must succeed once. The facade publishes
readiness before DMA start and global IRQ enable. Startup is the sole PCM consumer
only until that handover; subsequently ALNK is the sole consumer.

The GPL HAL now exposes prepare/start/final-PC6 helpers. Its legacy initializer
retains the exact original statements, register order and both 5 ms delays.
The new profile leaves the first reset delay before DMA. It services the second
5 ms interval nonblockingly in main, then issues the final PC6-high write once.
No app work, P33 phase feed or busy delay runs between DMA start and IRQ enable.
The existing source-reported Timer4 frequency remains an unqualified assumption.

Preparation reentry and early IRQ access poison the attempt. Every meaningful
startup callback has a post-call poison check, including IRQ enable. Late or
regressed observed main ticks refuse before a health feed or codec-tail write;
main health cadence is half the qualified maximum phase interval, with a strictly
positive tick delta. An underrun zeros output and increments the existing counter;
this finite diagnostic stops on its first main observation rather than hiding it
with continued feeds. Queue-full producer backpressure alone is not a fault.

Terminal publication precedes IRQ masking and best-effort DMA stop. Buffers,
context and leases remain permanent, even after stop or late IRQ. There is no
retry, reinitialization, live pause or claim that clearing DMA enable proves bus
quiescence. The existing fault/return policy remains authoritative.

`FRONTEND_READY` is the same numeric phase as the compatibility name `LCD_READY`.
The new profile means prepared audio and explicitly disabled display; the legacy
profile still means completed LCD initialization. Phase order, qualification,
mailbox, P33/reset policy and deadlines are unchanged. The immutable real target
qualification remains all zero and refuses before functional startup.

## Focused source and host evidence

The actual-app fixture includes the new platform body, the existing target return
binding/policy, real selected app and real scanner. Only register/IRQ dispatch and
clock behavior are injected. The separate reference app is a host-test oracle,
not production storage. Its general PROJECT reader loads the same fixed project;
serial control application and quantized PCM are compared exactly.

Directed runs cover genuine startup halves/queue contents, immediate IRQ after
readiness, actual scanner key/detent hooks, all 41 matrix IDs and seven encoders,
clock wrap, main feed cadence, queue backpressure, underrun, overflow, early IRQ,
startup callback fault/reentry, deferred tail fault, and late IRQ after terminal.
Each normal and ASan/UBSan configuration runs 21 actual-app process cases.
The positive/wrap cases compare 122 consumed blocks, including nonzero held-note
PCM; tail writes occur once. Leak detection is enabled for the preparer and app.
The original publication test supplies the separate mid-copy-fault and scalar
ICFG-restoration proof; the new fixture does not claim to model an interrupt at
every instruction. Legacy interactive/display and offline-stage fixtures are
rerun against the shared owner change.

Reproduce the focused host checks, in a bounded lane with Clang:

```
python3 -m pytest -o addopts= -q -s -p no:cacheprovider \
  tests/test_native_selected_audio_owner.py tests/test_native_selected_interactive.py \
  tests/test_native_selected_persistence.py tests/test_native_selected_aggregate_layout.py \
  tests/test_selected_return_target.py tests/test_native_publication.py --basetemp=<owned>/normal
FM1_SIM_CC=clang FM1_SIM_CXX=clang++ \
FM1_SIM_EXTRA='-fsanitize=address,undefined -fno-omit-frame-pointer' \
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
python3 -m pytest -o addopts= -q -s -p no:cacheprovider \
  tests/test_native_selected_audio_owner.py tests/test_native_selected_interactive.py \
  tests/test_native_selected_persistence.py --basetemp=<owned>/sanitized
```

Local bounded legacy return/aggregate checks passed 13 tests; the new complete-plan
and legacy-HAL normalized statement-order checks passed two. Development actual-app
normal and sanitizer checks passed before the final frozen rerun. Final exact-source
receipts and result logs are retained privately in the performance worktree under
`scratch/devkit-20261023/audit-20261101/selected-audio-owner-binding/`.
The first development fixture omitted a prototype; that compile failure is not a
product finding. A directed clock regression exposed a stale-observation path;
the new adapter now refuses the already-invalid observation before any later read
could conceal it. Fault injection after IRQ enable also added the explicit startup
boundary check. The existing policy and default platforms were not changed.

## Limits and next dependency

No native compiler, device, register execution, USB, MIDI, ROM or physical operation
ran for this source slice. Host order/PCM/fault tests do not establish DMA visibility,
free-half hardware semantics, codec timing, peripheral latency, interrupt nesting,
stack closure or audible output. The real target refuses startup. A separately
reviewed exact target compile/codegen/layout check is next after source review.
The prior aggregate size is not this new profile's measured size.

XIP text plus aggregate BSS exceeds total SRAM; no full-app RAM execution is
promised. The separate 512-byte ROM witness and its unresolved physical inputs
remain the RAM-first dependency. It is not I11 or execution of this app. docs/17
stock-V15 recovery safeguards remain unchanged; no new physical admission is implied.

Rarefaction remains fixed to primary and refuses sibling-checkout traversal. Serena
absolute-path symbol overview matched the owner source without changing shared
selection. Exact checkout reads provide the fallback; neither tool establishes ABI.
Build/test products belong only to this lane and are removed after evidence/review;
source, commands, small logs, manifests and reviewed branch backups are retained.
