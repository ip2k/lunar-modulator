# Private JL_AC79 dev-board diagnostics

These sources are diagnostic harnesses for the JL_AC79 DevKitBoard V1.2,
not an installable Lunar firmware or the FM-1's audio driver. Build outputs
link the pinned vendor SDK and remain in ignored/private storage.

`benchmark.c` exercises isolated resampling with deterministic checksums.
`sdk_worker.c` runs it after SDK startup with raw oscillator timing. The
[18-case measured baseline](../../notes/2026-10-23-devkit-resampler-results.md)
is not a full engine/mixer cost or audio-output result.

## Drums conversion readiness comparison

`prepare-renderer-devkit.py --drums-ready-convert` enables the conversion-only
Drums path measured in the V183/V184 experiments. It requires resident code,
unrolled resampling and outer-only timing, and rejects the separate outlining
mode. The prepared Drums caller supplies exactly the required input before
entering the shared FIR kernel. Other translation units, PASS/OFF behavior,
coefficients, arithmetic grouping and native engine rates retain their original
paths. The manifest records the option and both source input hashes.

`lunar_voice_budget_init_burst_safety_three` is an explicit 65% pressure / 60%
recovery experiment with a three-voice floor. The existing two-voice policy and
all default initializers remain unchanged. Adaptive results must report their
recorded voice decisions, admitted limit, steals, deadline misses and underruns;
they do not establish fixed-twelve-voice acceptance. V184 completed a 30.4-minute
dev-board soak without deadline misses or detected analog residual anomalies,
subject to the documented quiet/weak-signal detection limits. This is a diagnostic
milestone, not production-path or physical FM-1 acceptance.

## Internal-DAC reference probe

An explicit preparation option replaces the benchmark with a quiet, ramped
997 Hz reference tone. It fills the SDK's 64-frame DAC windows and records
callback/full-IRQ maxima and over-budget counts. It does not render an engine
or count every hardware underrun. The four interleaved DAC channels receive
the same sample; actual jack routing must be measured. UART logging stays
outside the audio interrupt. Temporary DAC calibration avoids its saved-trim
write, and the settings registration range stays empty.

Prepare offline from the pinned SDK commit
`e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d` (V1.2.13):

```sh
python3 tools/jieli/prepare-devkit.py --sdk /private/pinned-sdk \
  --source /absolute/lunar-checkout --out /private/new-build --audio-probe
```

The output must not exist. The preparer records source hashes and disables
the SDK's downloader; use the project's bounded LAN container workflow to
build. This command does not admit or install an image. Review the real ELF,
section layout, vendor disassembly and image before any device operation.
The transaction adapter accepts only separately reviewed exact image hashes
and sector plans, with complete pre/post readbacks. No arbitrary image, SPL,
loader replacement, chip erase or eFuse operation is provided.

## Real FM6 timing benchmark

Use `--fm6-benchmark` instead of `--audio-probe` to link the real FM6 engine
and its Apache-2.0 msfa dependencies. These options are mutually exclusive;
this benchmark produces no DAC output. It runs TINE EP, WARM PAD and SAW
LEAD at 1, 4, 8 and 12 voices, with 256 stereo 64-frame renders per case at
44.1 kHz. Notes release after block 192. The first cold block is included;
note-on and note-off batch costs are measured separately. Output checksums,
finite/nonzero sample checks and UART logging are outside timed regions.
Creation/table setup is not timed. The worker yields between cases.

The preparer hashes the engine inputs, preserves msfa's licence, builds its
translation units separately with integer wrap semantics, and keeps the new
objects' state in internal SRAM. FM6 uses a fixed 64 KiB diagnostic arena;
its actual instance requirement is reported independently. The complete
stereo mixer, effects, sequencer, control traffic and live DMA deadline costs
remain separate tests. Desktop fixture hashes are comparison references,
not target checksum results. No FM6 image is admitted by the flash adapter
merely because it links successfully.

## Shared renderer storage

The shared app (`sim/web/src/fm1_app.h`) can be compiled with
`FM1_APP_EXTERNAL_ARENAS=1` consistently across all translation units. This
omits the simulator's four 512 KiB sound reserves and ten 256 KiB effect
reserves. Supply one `fm1_app_arena_t` per unit to `fm1_app_init_arenas`;
unused units use `{NULL, 0}`. Storage remains caller-owned and must stay alive,
16-byte aligned and disjoint from the app, descriptors and other arenas.
Project loads preserve these capacities. Engine selection refuses a module
that does not fit before replacing the previous instance.

The sequencer, modulation, UI and actual render path remain present. Native
tests compare both layouts sample-for-sample with sequencing, two sounds, an
insert, both master slots and live controls, then load a project into the
supplied storage. Run `python3 -m pytest tests/test_sim_arenas.py -q`.
This storage option is preparation for full-renderer device diagnostics; it
does not establish target ABI sizes, linked SRAM fit or hardware deadlines.

## Analog capture

On Bench01, the connected KA6 hardware requires six-channel S32_LE capture;
requesting stereo directly fails. Example passive capture after steady output
has started:

```sh
arecord -D hw:K6,0 -f S32_LE -r 48000 -c 6 -d 30 /private/new-capture.wav
python3 tools/devkit_tone_analysis.py /private/new-capture.wav
```

The analyzer checks inputs 1/2 separately, defaults to skipping two seconds,
and emits JSON with cycle timing, levels, clipping and flags. Startup capture
may need a different explicit skip after inspecting UART/output onset; do not
hide internal defects by trimming them away. Archive the raw capture and its
transport log privately. A clean reference check is only a transport baseline;
actual instrument/effect rendering, deadline/underrun checks, control activity,
sustained soaks and listening remain required. The FM-1 uses an external I2S
codec, so its output path needs separate validation.

See the [active campaign](../../notes/2026-10-23-devkit-audio-performance.md)
and [other FM1 runtime lessons](../../notes/2026-10-23-fm1-audio-runtime-comparison.md).

### Named shared-renderer workloads

`prepare-renderer-devkit.py --workload mixed` remains the default four-sound
stress arrangement. `--workload keys` selects one FM6 instrument, a filter
insert, echo and compressor masters, sequencing, brightness modulation and
filter-envelope modulation. Both retain the 1/4/8/12-note density cycle,
release tails and live level/cutoff edits through the app API. Required module
failure refuses initialization; no automatic fallback changes the workload.
The private build receipt, boot banner and desktop replay identify the name.

Compare each workload with its own desktop PCM fingerprints. A passing keys
deadline or analog soak establishes only that named arrangement; it cannot
accept the mixed stress test or arbitrary combinations. Neither named option
admits a flash image or establishes hardware acceptance by itself.

### Unattended dev-board test cycle

The owner requires routine future dev-board tests to run without physical
button presses. Keep `--boot-control` in diagnostic images. A responsive image
accepts the acknowledged `tools/devkit_boot_control.py --enter-uboot` UART
handshake. Stop the exclusive receive-only UART capture before opening that
control connection; inspect fresh USB enumeration before using the fixed loader.

After a reviewed installation and complete flash readback, arm a fresh UART
capture and use `tools/devkit_loader_reset.py` with that installation receipt
and exact pinned target. It independently re-reads flash before its one reset
attempt. USB disconnection during reset is not a boot confirmation: require a
fresh UART application boot and diagnostic completion. Both directions were
verified on the dev kit on 2026-10-24. Do not request routine Update/Reset presses.
New diagnostic workers reserve 200 OS ticks after starting UART control and
before initializing the workload. Verify acknowledged ROM entry during this
startup window as part of admitting a new diagnostic; a receiver task's startup
message alone does not establish that it can run before an initialization fault.
The delay is outside measured rendering. Timing-v3 startup-window entry was verified on the dev kit on 2026-10-24:
fresh PING/ARM/ENTER acknowledgements were followed by fresh ROM USB
enumeration before the workload ran. This establishes recovery availability
in that image, not renderer timing or audio acceptance.

An unresponsive application's recovery is a separate case; UART control cannot
be assumed available after a crash. This workflow does not authorize FM-1 tests.

## Live FM6 DAC workload

Prepare with `--fm6-audio --fm6-ram --boot-control`. All three flags are required
for live FM6: preserve the measured SRAM placement and unattended test cycle.
The same internal-DAC transport now renders real FM6 in its measured callback,
with note events, bounded float-to-PCM conversion, quiet gain and startup ramp.
It cycles three patches at 1/4/8/12 held notes, six seconds held and two seconds
released per case. Release tails may overlap. `LUNAR_LIVE` reports requested
chord size, schedule progress, nonfinite and clipping counts. Callback gap
counts indicate delayed service; they are not hardware underrun counts.

The reference-tone and isolated benchmark modes remain separate comparisons.
Live FM6 alone is still short of the full mixer/effects/control acceptance gate.

The next live diagnostic also latches a PCM fingerprint at each completed
8-second case (`LUNAR_PCM`): FNV-1a over converted stereo PCM16 bytes in
little-endian order. Partial cases are never reported as completed hashes.
Compare the entire schedule with desktop replay before interpreting an analog
template mismatch as a DAC fault. This is diagnostic integrity evidence, not an
audio-quality score; include fingerprinting in the measured callback budget.

Compare a private independent host replay log with a completed target capture:
`python tools/devkit_pcm_compare.py --reference HOST_LOG --uart TARGET_LOG`.
The reference must include at least two complete cycles. Repeated worker
snapshots are allowed; missing, malformed, reordered or conflicting records
fail. The JSON records both input hashes and the exact comparison scope.
Passing this check does not certify the DAC, analog path or full mixer workload.

## Shared-renderer reference workload (integration in progress)

`renderer_live.c` hosts the actual shared app with a 148 KiB caller-owned engine
pool. Its four sound slots, four sequencer tracks, modulation, inserts, master
slots and control edits run through `fm1_app_render`; no substitute mixer is
used. `renderer_reference.c` replays two four-case density cycles and optionally
writes private stereo PCM16 little-endian audio. Run
`python -m pytest tests/test_devkit_renderer.py` for deterministic replay,
buffer guards and refusal when a required effect is unavailable.

`tools/jieli/renderer.mk`, read after the engine and simulator makefiles, exports
`print-devkit-renderer-objs` and builds `fm1-devkit-renderer-ref`. Define
`FM1_APP_EXTERNAL_ARENAS=1` consistently for every object. The selected module
list is `dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance`, with the GPL
switch off. This is not yet an admitted SDK/DAC image or hardware performance
result; see the dated performance note for current evidence and remaining gates.

Prepare the private SDK integration with:

```sh
python3 tools/jieli/prepare-renderer-devkit.py --sdk /private/pinned-sdk \
  --source /absolute/lunar-checkout --out /private/new-renderer-build
```

This preparer always enables UART boot control and disables the downloader.
It reuses the engine/app object lists through a nested build, retaining SDK
LTO so unreachable desktop persistence buffers do not consume target SRAM.
The DAC callback reports `LUNAR_RENDERER` and completed-case
`LUNAR_RENDERER_PCM` telemetry separately from the isolated FM6 diagnostic.
The private receipt hashes its source snapshot and records hardware acceptance
as false. Linking is an offline check: review stack, interrupt liveness, hot
code placement and the exact image before admitting any device test.

Use `--timing-only` for the initial worker-context preflight. It runs one
complete four-case schedule without enabling the DAC, measures render plus
scheduled note/control/conversion/fingerprint work, and yields to the OS every
16 blocks. Case reports include worst/mean ticks and counts at or beyond the
64-frame budget. The worker reports FreeRTOS stack high-water words after each
case. The preparer gives the shared-renderer worker 12 KiB of task stack, over twice the measured 5,400-byte peak;
this is dynamically allocated and must be counted separately from static BSS.
Neither this mode nor a larger task stack establishes interrupt-stack safety
or audio continuity. Keep UART control running throughout the preflight. The prepared app starts and
reserves UART recovery before allocating the worker. UART setup/task failures
prevent workload creation; worker allocation failure leaves recovery allocated.
A fresh acknowledged startup handshake remains mandatory before a measurement run.


### Worker-only callback profiling

`prepare-renderer-devkit.py --timing-only --profile` enables diagnostic
observers at the shared app's existing sound-render and effect-render call
sites. Descriptors, callbacks and their arguments remain intact. Workload unit
order is sound 1/2/3/4, sound 1 filter, sound 2 drive, master echo, master
compressor. Effects include their host control/segmentation work; sounds count
the engine calls inside the sequencer dispatch. The remaining block time also
includes sequence/modulation/mixer/UI/PCM work and instrumentation overhead.
Counters use unsigned timer differences, sum in 64 bits and reset after each
case report. UART printing stays outside timed blocks. Profiling is refused
for the DAC build. A matching desktop replay and full per-unit frame coverage
are necessary integrity checks; the instrumented image needs its own link,
packing, recovery and installation review. It is not an admitted image merely
because preparation or host tests pass.


The same profile also reports three outer `LUNAR_RENDERER_DETAIL` regions:
0 is note/control preparation,1 is the shared app call (including the six
nested stages), and2 is float-to-PCM conversion and checksum work. Each report
includes per-region aggregates and the values from the exact worst total block.
Four extra clock samples delimit these regions; counter updates follow all four
samples. Their overhead and end-of-block bookkeeping remain in the outer total,
so these measurements do not silently subtract diagnostic cost or first blocks.


### Optional control-path SRAM comparison

`--control-ram` requires the timing-only resident-filter profile. It wraps
only `fm1_app_render`, `fm1_mod_tick`, `sum_slots` and
`fm1_seq_host_dispatch_slots_ticks` in the private prepared source. Source
bodies, arithmetic flags, engine counts, rates, effects and schedule remain
unchanged. The fixed workload uses a 136 KiB caller-owned pool in this
comparison, retaining bounds checks; other profiles keep 148 KiB. The 32-bit
target measured 134,944 bytes in the previous image. Native 64-bit instances
are larger and must not be used to assert that this target budget fits.
A 32-bit replay checks the reduced pool when multilib is available. Actual
linked placement, startup allocation, recovery, PCM parity, stack and target
timing must pass separately before selecting this comparison.


### Optional Plaits table cache comparison

`--plaits-cache` requires `--control-ram` and its timing-only dependencies.
It changes only section annotations on the private prepared copies of
stmlib's two pitch-ratio tables and Plaits' sine table. The existing SDK
cache-data startup copy is retained; cache-way allocation is unchanged.
The coefficient bytes, workload and pool size remain unchanged. Inspect the
linked addresses and bytes before admitting a specific image. A successful
offline build is not a target performance or audio result.

### CPU1 finite arithmetic and paced SRAM ring (offline prototype)

`tools/jieli/prepare-cpu1-devkit.py --paced-ring` prepares a separate UART-first
probe. It reuses the finite, nonzero arithmetic kernels on both pinned tasks,
then publishes 413607 blocks of 64 words through a 16-slot SRAM SPSC ring.
The producer carries the fractional 24 MHz timer interval for 44118 frames/s,
representing 600.001088 seconds. Each block carries a sequence and CRC, and the
consumer independently checks every deterministic sample. `csync` fences
publication and slot reuse. A millisecond clock bounds the whole run to 625 s;
individual waits stop after one second. Permanent storage remains allocated
if a worker is late. The parent reports pacing misses, depth and both task
core histograms/stack high waters. `tools/devkit_cpu1_ring_result.py` rejects
missing, corrupt, incomplete, migrated, late or out-of-duration receipts.

This is an offline prototype, not an admitted image. It does not install an
IRQ or test FPU exception/corner behavior, nor does it drive DAC/audio output.
Finite task arithmetic parity is narrower than full FPU context acceptance.
Exact vendor/clock/synchronization/layout/recovery/cipher/NOR review and a
separate hardware transaction remain necessary before running it.

### Bounded FM6 copied-job mailbox (offline prototype)

`fm6_pair_mailbox.{h,cc}` implements the existing FM6 pair-adapter contract
without retaining caller/engine pointers. CPU0 publishes a private copy of
the second job, computes the first synchronously, then imports the second
only after completion within the total deadline. Rejection, timeout or a
frozen clock permanently disables submission. The object must remain alive
for a late CPU1 worker; it has no reset/reuse or cancellation operation.
The worker accesses only that object's job, and stops accessing it before
publishing completion. Target publication uses reviewed volatile words and
`csync`; the host test build uses standard atomic flags instead.

This is not attached to the SDK or shared renderer. No device image is
generated by adding it. Host differential tests exercise the real FM6 kernel
on two threads; separate fault tests cover late/rejected jobs, timer wrap,
deadline expiry and a stalled clock. Neither verifies the target ABI,
coherence, task lifetime, heap/stack budget, IRQ behavior or audio continuity.


### Optional note/control cost diagnostic

`--prep-profile` requires `--timing-only --profile`. It retains the existing
note/control calls and their order, adding counters around note-on/off batches,
level/filter edits, and (in private prepared copies) engine note-on, modulation
live-note, voice-start and modulation-plan rebuilding. Four additional private
regions observe sequencer flush, advance, dispatch and post-dispatch inserts/
mixing. Setup calls before the
measured renderer are excluded. Counters reset after each case; last-block sums
are copied with the exact worst total-block snapshot into `LUNAR_RENDERER_PREP`
rows. Calls count invocations, not audio frames. A last-block sum may exceed the
maximum individual call when several notes run in one block. Regions are nested;
never sum nested regions as independent costs. `LUNAR_RENDERER_UNIT_WORST` also
reports each unit's callback sum from that same worst block, accumulating split
callbacks rather than substituting their independent per-call maxima. Observer clock and bookkeeping cost
remains in the measured total. The option changes no production source behavior
and is refused for DAC builds. Exact vendor code, stack/layout, image admission,
startup recovery, target PCM and deadline checks remain separate requirements.

The private `--hook-ram` comparison additionally places the unchanged sequencer
begin/tick callbacks, modulation glue begin/tick callbacks, modulation block
begin, voice runner and voice-output helper in startup-copied SRAM. It requires
timing-only profiled resident dispatch; it does not alter production renderer
source, PCM math, tick rates, voice state transitions or event ordering. Inspect
the actual linked ranges, heap and stack before admitting each exact image.

The preparation profile also splits dispatch into MIDI effects, hook begin/tick,
modulation tick, voice-write collection, system-input handling, module/sink/voice
loops, voiced/ticked callbacks and hook-write conversion (regions12–23). These
are observations in guarded private copies, preserving original calls and their
order. Counts and sums are retained at the exact worst total block; nested
regions must not be added as independent work. Observer overhead remains charged
to total block time, and no timing or analog acceptance follows from profiling.

The separate private `--module-ram` experiment places the unchanged module
runner and parameter/gate/output helpers in startup-copied SRAM. It requires
`--hook-ram` in the timing-only profiled experiment. Placement does not change
the rack, module process functions, tick rate, gate edges, math or event order.
Its per-image manifest records the original prepared source; exact linked
placement, heap/stack and target PCM/timing remain admission/acceptance checks.

The separate private `--kind-ram` experiment places the existing default LFO,
envelope and chance hot processors and their LFO/envelope process and value
primitives in SRAM. It requires timing-only profiled resident module helpers. Bodies,
random state, rates and event order are unchanged; original source hashes are
retained. Vendor layout/stack and exact target PCM/timing remain required.

The separate private `--event-ram` experiment places unchanged note dispatch,
modulation input feeding and control-edit/automation-target helpers in SRAM.
It requires timing-only preparation profiling and resident kinds. The existing
outer and preparation counters attribute cold-block work without moving events
or excluding first blocks. Original prepared hashes are retained; compiled
size, remaining heap, stack, PCM and target deadlines still gate this experiment.

The opt-in timing-only `--external-pixels` build uses
`FM1_TFT_EXTERNAL_PIXELS=1` to replace the desktop's embedded115200-byte
framebuffer with a caller-owned pointer. This diagnostic never draws or binds
pixels; its UI synchronization remains in the audio workload. A real drawing
caller must bind at least240x240 RGB565 pixels with `fm1_tft_bind_pixels` and
retain their lifetime. Unattached app drawing refuses without marking a redraw
complete. All translation units must agree on the setting. Desktop/browser
builds retain embedded storage by default. This is a memory-ownership option,
not a panel transport, display timing test or analog-audio acceptance result.


The exact mixed timing candidate `b8f8e24b…` is admitted only for138 sectors
`[0x4000,0x8e000)`, independently of V22's139-sector restore plan. Offline
machine-code/layout, SDK, independent app copy, cipher/CRC and interrupted NOR
restore checks pass. This admission does not establish target timing, recovery,
DAC output or sustained analog acceptance.

### Ordered whole-engine queue (offline experiment)

`renderer_queue.{h,cc}` records four independent sound-operation streams in
fixed storage. Each stream holds at most128 render/note/parameter/bend/per-note
operations; a render holds at most64 frames. One caller executes sounds0/2/3
while one worker executes sound1. The caller waits before any insert processing
or ordered mixing consumes the buffers. This is an offline scheduling primitive,
not an enabled SDK task, audio path, or generally safe engine/model combination.
The existing copied FM6 kernel worker must not be nested inside it.

The recording caller exclusively owns engine selection, command storage and
buffers until publication; the worker exclusively owns sound1's instance and
output while executing. All engine state, callbacks and output buffers must
remain alive through acknowledgement, including after a timeout. Eligible
engines must have no shared mutable global state. The host backend uses C++11
atomics; the target publication spelling uses pi32v2 `csync` and still requires
actual vendor-code review before use. No heap allocation or task creation occurs
inside this primitive. Its timeout is a protocol bound, not audio acceptance;
outer64-frame render deadlines remain unchanged.

Overflow before publication refuses the entire batch. State, command, deadline
and poll-limit faults permanently disable future submission. Late completion
never permits storage reuse. The caller must stop the diagnostic and retain
all referenced storage after failure; this is not a fallback audio renderer.
Tests exercise concurrent operation order, already-running and not-yet-started
late workers, clock wrap, duplicate submission, overflow and invalid commands.
Normal and address/undefined-behavior sanitized host tests pass. Private full-app
replay preserves11,290,624 PCM bytes over44,104 batches, with queue peaks3/6/3/3.
These facts do not establish target timing, race freedom, analog quality or
hardware acceptance. ThreadSanitizer cannot start in the current container.

The whole-engine queue has a permanent-storage C bridge in
`renderer_queue_bridge.{h,cc}` and a finite static CPU1 backend in
`renderer_queue_sdk.{h,c}`. Explicit `--engine-queue` preparation is restricted
to the mixed timing-only resident O3 outer-timing experiment, conflicts with
the FM6 worker, and records only the fixed dx7/Macro model0/drums/dx7 streams.
It is experimental: host PCM/fault checks and vendor linking do not establish
target independence, cache publication, deadlines or stack acceptance.
Its protocol timeout is not the audio deadline. Queue failures stop before
audio consumption and retain all engine/output storage through recovery.

`--engine-queue-drums` additionally requires `--engine-queue` and selects the
experimental CPU1 partition `[1,2]`: Macro model0 followed by Drums. CPU0 keeps
both DX7 instances `[0,3]`. The original `[1]` worker partition remains the
default. Preparation records the selected sounds and emits the explicit
`LUNAR_QUEUE_WORKER_DRUMS` define; it does not change the workload or deadline.
Drums temporarily uses stmlib's global noise generator. Its worker-side calls
must remain serialized, while concurrent caller paths must not touch that
state. Host PCM and ownership tests cover both partitions; target transitive
independence, generated instructions, stack and timing require a fresh review.

`--engine-queue-profile` requires the same guarded `--engine-queue` experiment
and adds only `LUNAR_QUEUE_PROFILE`, leaving the older internal profilers off.
Each `LUNAR_QUEUE_REGION` reports per-case mean, maximum, and duration in the
worst outer block. Regions0..4 partition that outer block: before queue Begin
(including control/sequence advance), command recording, caller execution,
waiting/acquiring worker ACK, and after dispatch (including effects/mix/UI and
output conversion/hash). Region5 is overlapping worker execution; **do not add
it to regions0..4**. Caller/publication/fence overhead belongs to those measured
regions. Worker duration is stored before ACK and read only after acquisition;
idle worker polling adds no timer reads. Failed or stale batches cannot emit a
profile sample. Default builds contain none of these extra clocks or storage.
These diagnostic measurements include observer overhead and do not establish
race/cache safety or replace final uninstrumented deadline/analog acceptance.


`--engine-queue-detail` additionally requires `--engine-queue-profile`. It emits
`LUNAR_QUEUE_DETAIL` records for ten CPU0 subsets: sequence setup/advance,
recorded callbacks, sound inserts/meters, sound levels/mix, master effects,
amp, click/limiter, scope, UI, and output conversion/hash. Sound insert and mix
intervals accumulate over the four sounds without changing their order. The
preparer inserts hooks only into the private staged application copy; ordinary
application builds are unchanged. Each successful block must supply every
category, with no nested/unclosed intervals, before a detail sample is accepted.
Unsigned timer subtraction supports wraparound. Detail intervals are subsets of
the six outer regions, **not additional render time**; do not add them to those
regions or to overlapping worker execution. Observer overhead remains included.


`--engine-queue-micro` additionally requires queue detail and emits twenty-six
`LUNAR_QUEUE_MICRO` records per case. Regions 0–5 time the six command-recording
kinds in bridge enum order; regions 6–19 time `fm1_fx_render` calls for shared-app
unit indices 0–13. Sound-unit regions have zero calls because this bank measures
only effects. Regions 20–25 time the begin, event, lock, tick, lock-slot and
note-on control hooks, respectively, including modulation evaluation. Their
wrappers preserve each original hook's arguments, return value and output
pointers. Counts distinguish inactive slots from sub-tick calls. Recording
includes instance lookup and queue publication preparation; effect intervals
include the effect host wrapper, but exclude app routing scans and meters.
Intervals are non-nested within this independent bank and **overlap enclosing
detail/outer totals**. Never add the banks together. Timer overhead remains;
these diagnostic results do not establish uninstrumented deadline acceptance.
Malformed, unfinished, overflowing or missing samples refuse case completion.
The option changes only the private prepared application, with default builds
and the existing worker partition unchanged.

`--engine-queue-mod-micro` requires `--engine-queue-micro` and replaces only
regions 20–25 with system-event intake, global module execution, sink writes,
voice execution, global glue conversion, and voice glue conversion/callbacks.
Global module time includes parameter/gate preparation and output sanitation.
The six whole-hook wrappers are omitted in this mode, so internal intervals
never nest in the flat micro bank. Region count and result arrays stay unchanged;
the preparation receipt records the alternative labels and both transformed
modulation-source hashes. Default builds and the original micro mode are
unchanged. These subsets exclude tick bookkeeping/plan rebuild and include
observer overhead; they are not a complete replacement for whole-tick timing.
The voice-glue interval includes optional callbacks; the measured mixed app has
none installed. Host equality and timer balance do not establish target timing,
stack, cache or race acceptance.

`--engine-queue-module-micro` additionally requires modulation micro mode and
replaces its six intervals with system intake plus global-module parameter
routing, gate preparation, output initialization/IO setup, process callback,
and output sanitation. The enclosing module-loop and glue timers are omitted;
these intervals must not nest in the flat bank. The fixed mixed rack has five
global modules: each component's call count is five times the system-tick count.
No module is skipped, and no algorithm, order, parameter or state is changed.
The preparation receipt labels this alternative explicitly. Host replay must
still match the full PCM and refuse queue faults before an image is considered
for the independent target admission gates. This is diagnostic-only, not a
performance improvement or hardware acceptance.


`--engine-queue-insert` is an optional timing-only preparation mode for the
existing fixed mixed arrangement. CPU1 runs sound1 Macro model0, then that sound's
Drive/empty insert slots, raw/insert/level meters and mix-level pass before its
completion ACK. CPU0 joins before summing sounds in the original order. Runtime
checks refuse unsupported inserts, nonzero Macro model, null/overlapping instance
storage and invalid capacities before publication. Inline mix buffers and distinct
meter/level rows remain owned by their sound. All route/event/control inputs must
stay immutable until ACK; after timeout retain app/context/arenas and permanently
refuse reuse, including after a late ACK. No synchronous fallback is permitted.
The queue post callback and storage compile only with `LUNAR_QUEUE_POST`.

This mode conflicts with the Drums worker partition and queue detail/micro or
legacy per-unit profiling. Queue outer-region profiling is permitted; worker
execution overlaps CPU0 and must not be added to its totals. Host PCM and sanitizer
checks do not establish target timing, memory ordering, cache behavior or stack
sufficiency. A new vendor image still needs the full existing admission review and
protected startup/recovery cycle before any device measurement.

### Caller track post overlap (diagnostic only)

`--engine-queue-caller-post --engine-queue-insert` opts into caller-owned
sound0/2/3 inserts, meters and level before the worker join. CPU1 still owns
sound1; ordered summation and shared master effects stay after ACK. The fixed
fixture permits Filter/empty on sound0, Drive/empty on sound1 and empty inserts
on sounds2/3. All moved sound/insert arenas must be disjoint, capacity-valid
and instance-owned before publication. Unsupported layouts permanently refuse.
Outer profiling only; no worker Drums or nested profilers. Default insert mode
retains its prior scheduling. Host PCM/ownership checks do not establish target
speed, stack, cache coherence or dropout-free acceptance.

### Paired FM sine-table loads

The timing-only `--msfa-sine-pair` preparation option requires hot code and
`--msfa-sine32` (and its existing narrow-add prerequisites). It copies adjacent
sine delta/base words with a fixed eight-byte `memcpy`; the reviewed pi32v2
build emits one paired load. Interpolation, gain products and sample order stay
unchanged. The preparer records the input-header hash and rejects layout drift;
vendored files in the checkout stay unchanged. V58's heavy mixed mean improved
from 1732.500 to 1714.125 us in one run, but the 34829-tick deadline still fails.
This is an optimization result, not sustained or physical audio acceptance.


### Opt-in adaptive burst policy

`voice_budget.h` exposes `lunar_voice_budget_init_burst_safety()` for the
explicitly reduced-polyphony 65% pressure / 60% recovery experiment. It starts
at twelve voices, has a two-voice floor and retains the existing four-sample
pressure and 1024-observation recovery hysteresis. Every note-on still executes
or steals; it is not an admission cap. Existing initializers keep their original
thresholds and four-voice floor, and inclusion alone enables no policy.

The private V176 dev-board image used equivalent policy behavior during its
30.4-minute soak; see `notes/2026-10-23-devkit-audio-performance.md`. The new named
initializer has host policy/equivalence tests; those do not establish new target
code generation or fixed-polyphony acceptance. Log the selected policy, actual
limit changes, steals, deadline misses and underruns when integrating it.

### Finite producer/consumer pipeline backend

`LUNAR_DEVKIT_RENDERER_PIPELINE=1` selects `renderer_pipeline_sdk.c` in the
renderer make fragment. This opt-in backend separates two immutable work slots
from eight leased PCM output slots. CPU0 retires completed work before reusing
its arena; an acquired PCM buffer remains immutable until its matching output
retirement. Callback failure, invalid ownership or a protocol timeout permanently
refuses further work and retains storage for any late worker.

Task wake notifications are hints: drain tokens before checking progress, then
wait only when no progress is possible. The public header documents CPU0/CPU1
task ownership; blocking wake calls are task-only. Native DAC notification and
lease handoff require the reviewed pinned SDK IRQ path, not a generic ISR-safety
assumption. The 100 ms guard
bounds protocol failure, not the audio deadline. The backend reserves a static
1536-word CPU1 task with a finite 35-minute lifetime and refuses nested SDK
workers. This is backend selection only: no tracked application adapter or
preparer enables it yet, and default builds do not change.

The implementation follows the private V185 pipeline, whose scoped adaptive
floor-three target run and preceding V184 soak are recorded in the dated notes.
Host ownership/failure tests use a C11 atomic/pthread model, plus a separately
compiled public-header client; they do not prove native cache, IRQ or stack
behavior. Compiling the tracked backend with JieLi's compiler is not a linked
image or new hardware acceptance. Integrate the producer/consumer adapter and
continuous DAC drain before claiming the tracked runtime reproduces that soak.
