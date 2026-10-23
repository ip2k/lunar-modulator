# First dev-board resampler timing run

[verified: received UART capture, 2026-10-23] The diagnostic booted on the
JL_AC79_DevKitBoard V1.2 and completed all eighteen cases, ending with
`LUNAR_DEVKIT complete=1`. The SDK reports CPU 320 MHz, SDRAM 192 MHz and
SFC 80 MHz. These are firmware-reported clocks, not external measurements.
The reset-reason banner says LOW POWER; that label alone does not establish
a brownout or power fault.

## Evidence and scope

- Private capture on bench01:
  `/home/claude/fm1-devkit-captures/uart-v6-repeat-20261023.bin`.
  Snapshot: 5,637 bytes, SHA-256
  `80010643450d410aa89dc7718be16b314e76ac7d92b9239efc6c8a376cfd832f`.
  Mac ignored copy and parsed results: `scratch/devkit-20261023/`.
- Installed full-image SHA-256:
  `e77ee8af309fc57d1a8eddaac95dec253dda031f269021382c9cb1e977baa103`;
  v6 ELF SHA-256:
  `3e313f06be8b12880085a4a43e83820c333767d184c447d4c896cc0d66bc33f1`.
  Build and physical install/restore evidence:
  [bring-up record](2026-10-22-devkit-uart-bringup.md).
- Workload: the repository's public resampler, static SRAM state, synthetic
  input, 64 output frames, IRQs enabled; compiler `-O2`, no LTO for the
  benchmark object, `-ffp-contract=off`. UART/checksums are outside timing.
  Normal cases measure 128 blocks, tail cases eight, after eight warmups.
- Producer fields 12/16 are queue bookkeeping, **not actual instrument
  batching**. No instrument, mixer, codec interrupt, audio output, dropout
  measurement, second-core load or FM-1 hardware is exercised.

## Measurements

Times below use the nominal 24 MHz oscillator timer, not CPU cycle counts.
The ten-OS-tick calibration returned 2,371,096 timer ticks, versus nominal
2,400,000 for 100 ms: about 1.2% lower. OS delay phase/latency is not an
external frequency reference; values remain approximate. The nominal
64-frame deadline at 44,118 Hz is 1,450.7 µs.

Each row spans silence, active input and release tail, across both producer
fields. The 47,872 label represents 47,872.34 Hz in the C workload.

| Input → output rate | Mean per block | Largest observed block | Nominal block budget |
| --- | ---: | ---: | ---: |
| 44,118 → 44,118 Hz | 28.1–29.2 µs | 30.1 µs | 1.94–2.01% |
| 47,872.34 → 44,118 Hz | 395.0–401.0 µs | 412.4 µs | 27.23–27.64% |
| 96,000 → 44,118 Hz | 512.7–514.3 µs | 518.3 µs | 35.34–35.45% |

[verified] For each rate/signal pair, output checksums agree between producer
fields 12 and 16. Silence, active input and tail have similar conversion
costs. All eighteen tuples are present and unique; the completion marker
follows them, with no captured assertion/exception between them.

[verified] A separate desktop build of the same benchmark at `-O2
-ffp-contract=off` matches all eighteen target output checksums and input-frame
counts. The existing sanitized workload test now checks the recorded target
hashes as regression fixtures. Folded hashes are not a full sample-stream
comparison and do not complete the ladder's DSP equivalence requirement.

[inferred] Rate conversion is a substantial contributor to CPU cost. Several
such paths could consume the block budget before instruments/effects are
included. This does not prove it is the sole cause of the FM-1 slowdown or
predict exact costs at the FM-1's clock/cache/audio configuration.

## Next measurement

Compare this baseline with the current performance candidate using the same
workload, build flags and timer calibration, then measure real instrument
production plus resampling at the FM-1's intended clock. Keep separate
results for isolated resampling, complete renderer cost and live underruns.
The full verification ladder, audio-out validation and complete instrument
bring-up remain open; this run closes the first UART benchmark milestone.

## Integration host qualification

[verified: GitHub Actions logs] Main run `39061969073` passed its Linux
Python suite on `ubuntu-24.04`. PR run `39981860538` resolved `ubuntu-latest`
to `ubuntu-26.04`; both native Linux suites failed the same forty DSP
reference/block-split assertions, while macOS passed. This stream changes
no engine implementation. Native CI hosts are pinned to the previously
validated Ubuntu 24.04 image, including the existing Pico SDK compatibility
pin. Numerical assertions remain unchanged; qualifying the newer compiler
is separate work. Browser jobs retain their pinned Playwright container.
The same run's WebKit compact-toolbar test timed out waiting for the Stop
button's state; its other browser checks and Chromium/Firefox passed.
Recheck that failure on the new exact head before integration.
