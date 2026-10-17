# W7: observe stalled asynchronous LCD transfers

2026-10-17. Source-only diagnostic on the native installable stream, based on
`1f12ad5b8d6a865268af94179a3442183a680602`. **No display recovery, audio fix,
boot repair, target admission or physical timing claim.**

## Evidence and change

[verified: pinned source] `firmware/native/app_probe.c::display_strip` preserves
`cv_px` DMA ownership while DONE is low, but previously never recorded a stall.
The main loop continues audio refill, USB/platform polling and watchdog service.
The Dinghy `lcd_sync`/HAL wait is not an admitted abort primitive: its bounded
wait ACKs without an explicit DMA stop, then the caller releases busy/CS. This
change preserves the readiness guard and does not modify third-party code.

[verified: this source] `lcd_pending_deadline.h` records a submission timestamp,
then latches at most one accounting event while that transfer remains pending.
`display_strip` checks DONE before checking the deadline; after a low-DONE
expiry it retains busy, CS, row and DMA-buffer ownership and returns. A later
DONE follows the existing sync/next-strip path. The row still advances on
submission, as before. If a startup transfer predates this application's first
submission, the observation starts conservatively at its first busy poll.
Invalid framebuffers cannot release ownership; they still permit observation
of a stalled pending transfer. A completed synchronous owner such as SAVE can
clear the stale observer state on a later idle poll.

[verified: native `hal/fm1_time.h`] TIMER4 is documented as a free-running 24 MHz
uint32 clock (`FM1_TICKS_PER_US=24`). The explicit **100,000 microsecond**
diagnostic policy is therefore 2,400,000 ticks. This is a generous observation
threshold, not an inferred hardware maximum, cancellation deadline, or a copy
of the vendor's 20 ms recovery policy. Detection occurs on the first low-DONE
poll at/after the threshold. Unsigned subtraction handles timer wrap, assuming
at least one poll per full approximately 178.9 second timer period before first
expiry. Once latched, further wraps cannot produce another event. The retained
`lunar_lcd_pending_timeouts` volatile symbol counts events cumulatively modulo
uint32; no existing telemetry schema, UI or hardware command changes.

The independent vendor kit informed the investigation, not this code. Its SPI
stop/reset/retry sequence has no proven ownership contract for Lunar. No vendor
code was copied. The native branch is GPL-3.0-only; these new native/test files
retain that licence and must stay on the native stream. A small local observer
fits the existing free-running timer and DMA ownership contract; introducing a
timer framework or the vendor sealed runtime would add unnecessary dependencies.

## Checks executed on Aeon

[verified: host only] `LUNAR_HOST_SANITIZERS=1 python3
tests/test_native_lcd_pending_deadline.py -v` passed with Ubuntu GCC 15.2.0.
The driver extracts the complete production display state/body without rewriting
it and compiles the production helper. Four render-stage/producer-gap profile
combinations pass ASan/UBSan and warnings-as-errors. Cases include idle/invalid
framebuffer, normal submit, exact deadline, DONE priority at/after deadline,
10,000 stalled polls (including multiple clock wraps) with one accounting event,
late completion, rearm, unchanged source-buffer contents/CS/busy/row while
pending, startup observation, external completion, and row wrap. A service
surrogate returns after each display poll; this is not a compiled main loop or
proof of actual USB/audio scheduling.

[verified: host only] The unchanged `save_quiesce_test.c` and production helpers,
using exact USB functions extracted by the existing `verify_save_quiesce.py`
prefix, passed ASan/UBSan for shard 0 / 1,000 cycles. Its DONE-low refusal to sync
or enter the SAVE critical section remains intact. This is one host shard,
not the original full 30-container receipt.

[verified: partial target compilation] The initial shorthand toolchain path was
empty, but the exact recorded SDK path resolves the existing approved compiler:
`/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`.
Its clang SHA-256 matches the recorded pin
`42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`.
Actual modified `app_probe.c` compiled successfully with `-target pi32v2
-mcpu=r3 -mfprev1 -Oz -flto -ffreestanding -fno-builtin` and the native builder's
include/arena/runtime settings, both baseline and render-stage plus producer-gap
profiling. The platform/libc substitutions were regenerated from this exact
checkout using the builder's existing rules. Existing schema-9 generated module
selection headers were mounted read-only; their freshness against a newly built
catalogue was **not** established. The ordinary platform graphics/font sources
were used, rather than the builder's size-compacted variants.

The two LTO object compilations ran in existing image
`lunar-jieli-check:bookworm`, ID
`sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`,
with network disabled, read-only source/toolchain/selection mounts, a private
output mount, read-only rootfs, 1 CPU, 512 MiB memory and equal total swap,
and `docker-batch.slice`. No toolchain was installed or modified. Full commands,
generated inputs, logs, object hashes and selection-header hashes are saved at
`/home/claude/.local/share/workbench-pilot-output/lcd-pending-deadline/target-compile.json`.
This is target translation-unit/LTO validation, **not whole-application linking,
final machine-code inspection, map/resource proof or hardware acceptance**.

Rarefaction and Serena select the shared older Mac primary checkout, where the
native file is absent; their bounded queries cannot cover this Aeon worktree.
Their shared roots/config were left unchanged. Exact pinned source and the
host compiler supply the evidence here; target ABI/code generation remain open.

## Required next dependency

Coordinator reviews the actual diff with an independent reviewer, backs up the
returned branch to GitHub, and opens a separate PR against the installable native
stream when authorized. Do not merge into docs/main or merge without review/CI.
A fresh source-bound catalogue plus the approved toolchain must later establish
whole native application link/code-generation/resource checks. No firmware image
or device traffic is authorized by this source-only diagnostic. Automatic LCD
recovery would need a separately reviewed DMA cancellation/ownership contract.
