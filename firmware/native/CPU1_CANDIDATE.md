# CPU1 offline candidate

This is a separately compiled **unadmitted stock-SPL witness candidate**. It is
not a production backend, installer profile, package, execution authorization or
claim that Lunar runs on the FM-1. `LUNAR_NATIVE_PIPELINE_ENABLE=1` still errors;
`lunar_pipeline_native_hardware_admitted()` always returns zero. The default
diagnostic CRT, linker, app and HAL are unchanged and do not select these hooks.

The build requires explicit `OFFLINE_CANDIDATE=1 STOCK_SPL=1`, a pinned existing
pi32v2 toolchain, an owned output directory and the separate makefile:

```
make -f firmware/native/cpu1_candidate.mk ROOT=. TOOLCHAIN=<pinned-existing-path> \
  BUILD=<owned-private-output> OFFLINE_CANDIDATE=1 STOCK_SPL=1 -j4
```

This command only compiles/links. It provides no upload, device or execution
operation. Target hooks reject host selection and require the explicit pi32v2
flag set by this makefile. Host tests instead use the existing TEST_PLATFORM_HEADER
seam, C11 atomic words, mocked hardware and the actual candidate `.c` separately
linked with the actual native adapter/common core. They do not execute MMIO.

The exact source closure is five translation units: candidate, target operations,
profile, native adapter (includes common core once), entry assembly. There are no
SDK archives, OS, app, engine, DSP, transport, GUI, audio, flash writer, reset,
power/voltage or cache-reconfiguration dependencies. All code is XIP; this
candidate performs no flash operation and supplies only its own byte-memory
functions. MPL platform provenance/license is in
`../third_party/felucca-cpu1-candidate/`; the reusable core/adapter remain MIT.

The stock-SPL route is an explicit envelope, not detected hardware identity.
CPU0 rejects a different core/boot argument, establishes its initial stack,
preserves the boot argument and debug causes across register-only early hold,
then alone copies/zeros C storage. It marks permanent CPU1 stacks/canaries and
installs the 128 shared vectors once, with only exception source 1 enabled.
IRQ126's word is the temporary entry slot, restored to a fatal handler after
setup ACK or terminal hold; it is never permanent context storage. CPU1 never
initializes primary vectors or clears shared C storage.

The one-attempt launch saves access/top/PC-window/divider/entry state, clears
CPU1 sources, releases the fixed RTI bootstrap, waits for its nonce-matched
setup ACK for at most 480000 raw ticks or 1000000 polls, restores those guards,
then returns to the adapter which alone grants RUN after READY. Any failure
permanently refuses. Best-effort cleanup failures are recorded, not described
as successful restoration. No retry/restart/reclamation exists. Normal finish
uses the real core's drain/exit ACK and leaves permanent storage alive;
`port_wake_abort` never holds a core. Terminal hold is CPU0-only and separate.

The linker reserves per core an 8192-byte user stack, 2048-byte supervisor stack
and 1024-byte emergency fault stack, with 64-byte canaries. These are provisional
budgets for this small deterministic 24-tag callback, not native DSP stack proof.
The EMU outer window includes all three stacks and their gaps; it does not enforce
separation between them. Software canaries are checked before READY and at exit.
Assembly records original USP/SSP/ICFG/SP/RETI/RETE before switching to an emergency
stack. Per-core first-fault claims park nested faults without overwriting the
first raw record. Both cores park without display/reset/CPU1 hold. Fault records
and static control/arena storage remain alive for image lifetime.

TIMER4 is configured as OSC 24 MHz, /1 if its source/period is incompatible, without
system clock-tree changes. Each core owns a separate 32-bit ms accumulator from
one CPU0 raw origin. Correct elapsed time requires each owner to sample in less
than one raw wrap (~178.957 s); callbacks/IRQs must not reenter the same accumulator.
Modulo-ms arithmetic then supports the core's 35-minute lifetime. Frozen delay
polling is capped and poisons; hooks/bus operations must still return. A hung
hardware transaction or arbitrary callback cannot be cancelled by a C deadline.

## Outstanding target witnesses

No hardware witness has run. A future separately approved experiment must first
establish the exact stock-SPL entry identity and inherited RTI/privilege/cache,
clock/rails/guard state. The secondary RTI sequence does not fabricate missing
status bits. Then demonstrate actual stack/core/local-exception setup, fresh
nonce/READY/RUN chronology and pre-RUN restoration with independent observation.
Prove first/nested core-specific fault records and a bounded terminal hold,
including delayed bus causes; 256 settle operations are source-backed, not a
worst-case drain guarantee. Do not attempt warm restart as a supported feature.

Next qualify the exact compiled aligned volatile-word/csync extension against
real SRAM/compiler/cache behavior under adversarial two-way payload/PCM traffic,
with fresh heartbeat and canaries, not just a quiet error counter. No cache
flush/invalidate or rail adjustment is hidden here. Host atomics cannot prove
that contract. Measure the 24 MHz source, raw wrap, per-core origin and 35-minute
lifetime on the selected route. Finally qualify the actual common core and
later real DSP/RAM/stack/PCM/output deadlines. Successful offline compilation or
finite target checks do not establish a general silicon memory model or release
acceptance. The private backend plan lists the ordered experiments and provenance.
