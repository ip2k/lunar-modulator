# Producer-gap physical campaign: starvation persists

[verified: owner observation] The owner cold-booted the preceding installed
Lunar diagnostic and again reported a very laggy waveform and badly distorted
audio. That physical performance acceptance failed; startup alone is not success.

[verified: physical installation/readback] The subsequent one-use
`rom87-producer-gap-cycle`, under private bench base
`/home/claude/fm1-producer-gap-aba42d83-20261015`, completed fresh paired reads,
209 guarded sector writes and full target readback. The completed journal and
original installation-session result agree on target SHA256
`bc593f95bbfc9731dbbc906fb67c06d9882fbd51403cdda3dbe9ab95740fb566`.
Firmware source is `aba42d839f2a68561a3e205e173d2d61b03f27e6`; runtime tools
source is `10e7b41d495b7716ff069090cc3daec015580fb4`. Preparation provenance is
in `2026-10-15-producer-gap-trial.md`.

The single reset reply was ambiguous (`host=7`, `info=1`, `resid=16`) and raised
an exception. It was not retried or counted as protocol success. Separately,
native Lunar USB appeared at bus1/device88/path1-1, input-only telemetry ran
110 seconds, and passive KA6 capture ran 180 seconds. Later passive enumeration
observed mask-ROM USB `4c4a:8057`, device89 at the same path. The old launch is
consumed and must never be reused. No new physical action is required from the
owner for the completed run.

[verified: recorded counters] The capture contains 133 valid frames: 37 each
of schemas1,2,5 and 11 each of clock/PLL schemas3,4. Across 107.743 seconds of
device uptime, production increased by28,872 blocks (267.96 blocks/s), while
underruns increased by45,399 (421.42/s). Their sum is approximately689.38
64-frame output blocks/s. All36 steady schema5 windows sampled queue depth0.
The previous ROM83 capture produced268.88 blocks/s with420.53 underruns/s.
These observational captures show no material throughput improvement; they are
not a paired causal experiment.

Schema5 steady-window medians of observed maxima, in raw timer ticks:

| Observation | Ticks |
| --- | ---: |
| One render call | 103,941 |
| Refill-entry gap | 953,014 |
| Publish gap | 269,814 |
| Display work | 7,869 |
| Display wait | 246 |

These are maxima per reporting window, not duration distributions. Counters use
continuous-uptime/modulo assumptions; schema1/2/5 windows have different reset
boundaries. `sequence_dispatch` includes sound rendering and cannot be added to
its child sound stages. No measured CPU frequency or exclusive DSP time follows
from these raw timings.

[verified: source review] The main-loop render timer includes interrupts. The
earlier engine probe renders inside ALNK0 with `in_audio=1`, while the full app
renders in the main loop with `in_audio=0`. Higher-priority timer5 therefore
performs different USB work during those measurements. Timer5 may nest inside
ALNK0; summing inclusive ISR totals would double-count nested occupancy. Next:
measure nesting-aware interrupt occupancy and compare it with render elapsed
time before attributing the deficit to engines or changing service cadence.
Offline audits of target float code generation and inactive rendering paths
continue. No disabling of input/USB service is justified by this capture.

Private retained evidence in `scratch/producer-gap-result/physical/`:

- `captured-evidence.tar`: 218,316,800 bytes, SHA256
  `3d48ac89d8f494d615087cf2bd64bfb7c4952bb6babc3d6dafd9d8930bdcae77`;
  21 regular files safely extracted and byte-validated.
- `transaction-receipts.tar`: SHA256
  `64cbbb65477329bbb3d683f5c0e23e0e465306129c42e8655f0f5d7df034ed6b`;
  six additional transaction/admission files safely extracted and byte-validated.
- `events.jsonl`: SHA256
  `b62f6d407cb8a12ac31202b476b0ebc9d6e3d44f5acde4fc3cf64c5367c9ff18`.
- `campaign-comparison.json`: SHA256
  `bc7654de4c183c77d050a9b28326690ef5656286641077d4f54283696012f228`.

The audio WAV header and file length agree on six channels, signed32-bit PCM,
48kHz and8,640,000 frames (180seconds); arecord exited0 without reported errors.
That establishes capture completeness, not audio quality acceptance. The input
port and expected image hash are externally bound to the campaign; telemetry
does not independently authenticate executing firmware. Five focused offline
analysis tests pass. SAVE remains disarmed; the firmware/web release goal is
active and unfinished.
