# Private JL_AC79 dev-board diagnostics

These sources are diagnostic harnesses for the JL_AC79 DevKitBoard V1.2,
not an installable Lunar firmware or the FM-1's audio driver. Build outputs
link the pinned vendor SDK and remain in ignored/private storage.

`benchmark.c` exercises isolated resampling with deterministic checksums.
`sdk_worker.c` runs it after SDK startup with raw oscillator timing. The
[18-case measured baseline](../../notes/2026-10-23-devkit-resampler-results.md)
is not a full engine/mixer cost or audio-output result.

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
never sum all twelve as independent costs. `LUNAR_RENDERER_UNIT_WORST` also
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
