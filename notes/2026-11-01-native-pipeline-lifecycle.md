# Disabled native pipeline lifecycle — 2026-11-01

[verified: source] This slice wraps the unchanged MIT two-work/eight-output
renderer_pipeline_core in an SDK-free adapter. It does not start a native CPU1,
change the app or SDK wrapper, allocate a target stack, or enable hardware.
Base: 08326f9ace07c35bfbd4dd2521260e5b2bcf4466. The separately integrated
native diagnostic at foundation 9d08bfc7 has no colliding file names.

The adapter includes the actual common core once. Its permanent static launch
context is distinct from the platform's temporary startup-vector slot. CPU0
must first acknowledge completion of primary IRQ initialization; this function
performs no hardware initialization itself. One launch attempt is allowed per
boot. The entry callback validates its context and CPU identity, publishes
ENTERED, completes platform setup, then publishes READY. CPU0 alone grants RUN
before the startup deadline. Timeout permanently refuses the grant. Late entry
or delayed setup cannot resurrect it; all storage stays alive. Worker callbacks
remain under the common core's publication/ACK/poison ownership protocol.

There is no restart/reset/free API, generation rollover, semaphore dependency,
worker allocation, or duplicate protocol implementation. Since there is exactly
one attempt after BSS initialization, nonzero preexisting acknowledgements are
rejected rather than recycled as another generation. The backend must invoke
exactly one CPU1 entry context; its synchronous launch function must return
promptly, without awaiting READY. Waiting uses a monotonic wrapping uint32 clock
and an exclusive 1000 ms deadline. A stalled platform clock or blocking launch
hook cannot be bounded by C polling; these are explicit backend prerequisites.
Worker setup may finish late, but may not run DSP or touch/reinitialize the
primary vector table. READY is meaningful only after those platform obligations.

[verified: source/tests] Production launch remains unconditionally disabled.
The default backend performs no register writes, IRQ manipulation or clock read;
start fails before publication. Its nonconcurrent word/clock/IRQ placeholders
are solely for compiling that refusal path, not a usable target port. Defining
LUNAR_NATIVE_PIPELINE_ENABLE=1 fails compilation. The test platform override is
host-only; hardware_admitted() stays zero even when host tests run the core.

## Integration dependencies and acceptance limits

Before a real backend can replace the disabled one, establish and independently
review: reset/RTI entry state; linker-owned permanent CPU1 user/supervisor stacks,
guards, work arenas and exception storage; exact shared SRAM ordering/cache
visibility; CPU1 IRQ/exception setup that does not repeat primary fm1_irq_init;
clock progress and IRQ save/restore; CPU0 output ownership/deadlines. The temporary
startup pointer aliases IRQ126, so primary vector initialization must finish
before publication and must never run again while CPU1 can read the pointer.
No launch register implementation is supplied by this slice. Historical SDK
launcher analysis and disassembly remain private research, not linked code.

The current default source can be compiled for pi32v2 to check compatibility,
but that cannot prove a runnable concurrent backend or any of these contracts.
Host C11 atomics prove only the tested host adapter/core behavior. No current
native image is linked or admitted here, and no full app, eight-voice target
soak, thirteen-engine runtime or output-latency acceptance is claimed.

## Focused verification and source navigation

Run tests/test_native_pipeline_lifecycle.py for actual adapter/core host fault
coverage plus default-backend refusal. It executes normal and ASan/UBSan modes,
including ENTERED-before-READY, setup/launch failure, deadline, stale ACK,
late entry/READY, IRQ ordering/refusal, clock wrap and PCM streaming. Existing
tests/test_devkit_renderer_pipeline.py retains the shared protocol regression.
Tests use pytest-owned build folders; retain logs and remove those products.

Rarefaction status selects primary /Users/likwid/Developer/mvave-fm1-firmware;
it rejects an external sibling worktree project path. Serena's current shared
root is also primary and a query of the new absolute worktree returned empty.
Neither root was changed. Actual source/header/known test callers were inspected
through bounded absolute-checkout reads; neither empty result establishes a
caller absence or target ABI correctness. Foundation names were collision-checked
with git ls-tree. No GPL HAL or proprietary source was copied into this adapter.

## Results

[verified] Source checkpoint ca8f9e798ccc33966dc89f240894db3270a8da78 passed
15 focused pytest cases: 15 lifecycle modes in each of normal and ASan/UBSan
builds (30 process executions), default refusal/compile gate, and the existing
SDK/host protocol suite (22 modes across four builds, 88 process executions).
The stream fixture verifies callback order and PCM through the actual adapter.
This is bounded synthetic callback coverage, not an eight-voice DSP render.

[verified] The same source compiled with existing vendor clang for pi32v2/r3,
-mfprev1, C11, -Oz, freestanding, -fno-builtin and warnings as errors. The
initial compile omitted the toolchain standard include directory and failed
on string.h; adding the native builder's existing pi32v2/include path resolved
it without copied/configured headers or SDK libraries. Object SHA-256:
7c5ed20cb076d1a7b970a3aed7d72d23462861eea4ad02038bead53c0314e17f.
Vendor disassembly confirms native_start returns zero and hardware_admitted is
constant zero; optimized disabled code removes the runnable worker path. nm
lists only memcpy/memset as unresolved runtime dependencies. This is an object
compile, not a linked firmware, full toolchain archive revalidation or active
backend machine-code proof. The exact command, compiler/objdump/input hashes,
relocations, raw listing and host logs are private under the worker worktree's
scratch/native-pipeline-20261101/logs. No vendor output is tracked.

Next dependency: independent adapter review, then parent integration with native
foundation/corrections. The next platform slice must establish the listed target
contracts and own concrete entry/linker/platform changes; it must not simply
flip ENABLE or reuse these disabled hooks as real hardware operations.
