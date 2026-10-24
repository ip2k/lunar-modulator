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
