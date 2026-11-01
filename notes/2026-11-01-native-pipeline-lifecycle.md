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
