# Passive nested engine profiling on the FM1

Goal ACTIVE; owner cold-boot musical acceptance FAILED; SAVE remains disarmed.
The owner reported that a power cycle booted Lunar but the waveform remained
very laggy and notes distorted. This is not a release candidate.

## Installation and capture [verified]

The once-only ROM95 campaign at bench01
`/home/claude/fm1-engine-render-profile-6b8576bd-20261015`, cycle
`rom95-engine-render-profile-cycle`, is consumed: NEVER RELAUNCH.
Fresh paired 1 MiB reads both matched prior image
`07761c6c8bbe8c706e323d42266196dff5b530113f451bcc8ca7eeaade65f4c7`.
210 application sectors were changed, directory sector 0x4000 last. The
completed journal has null intent. The full target is
`eddc85316ab708255f2f23510b502fc3df90a14dbd4c7122177ef179054dc162`.
The coordinator independently matched every final 256-byte read response hash
against that target: all 4096 pages, with 52 interspersed keepalive commands,
clean SG completions and no retry. The install result was saved before reset.

The one reset acknowledgement was ambiguous and was not retried. Independent
same-port native USB96 enumeration followed. Input-only telemetry completed
110.16 host seconds; six-channel KA6 S32_LE/48 kHz audio completed 180 seconds;
both recorder exits were zero. Passive ROM97 appeared automatically. No notes,
PLAY, MIDI output, SAVE or owner observation was requested for this run.

The generic install sidecar retains conservative `protocol_mock_only:true`,
`hardware_validated:false` and offline scope labels. Those flags are not musical
acceptance or a truthful description of transport by themselves: the separate
SG response log, independent complete readback comparison and USB/capture
observations establish the bounded physical installation facts above. Do not
promote its broader recovery/admission flags.

## Timing [verified; interpretation bounded]

Rates use device uptime. Audio covered 107.949 device seconds: **428.647
produced 64-frame blocks/s and 260.697 underruns/s**, versus 689.344 required.
This still fails the real-time budget. The 27 schema-7 snapshots provide 26
intervals covering 104.81 device seconds, excluding the first snapshot.

| Engine | Outer ticks per outer call | Nested ticks per outer call | Outer-minus-nested share |
| --- | ---: | ---: | ---: |
| Drums | 3802.42 | 668.55 | 82.4% |
| SixOp | 3275.14 | 414.55 | 87.3% |

Nested `RenderBlock` calls occur several times per outer call; their own means
are 115.52 ticks (Drums) and 95.51 ticks (SixOp). Do not confuse these different
denominators. Outer timing includes nested timing: never add them. The residual
contains wrapper/resampler/output-loop work, instrumentation and interruptions;
it does not establish FIR-only cost or prove all residual time is avoidable.

Schema-2 weighted stage ticks/call: Drums3982, SixOp3317, Trio1590, Acid1051,
FX0/Hall10968, FX1/limiter8702, postmix6781. Display5897 is periodic, not per
audio block. Sequence dispatch20608 includes sounds and must not be added to
them as independent work. No calibrated CPU-frequency or audio-quality claim
follows from timer ticks.

## Evidence and next work

Private local evidence is under ignored
`scratch/engine-render-profile-result/physical/`: 27 copied evidence files
(14,714,634 bytes), individually verified against remote size/hash inventory;
private target, independent readback receipt and two analysis summaries.
Telemetry events SHA256
`fd3ed022520f2ae9bbae0415593440091f1af86b5c2cd3e6a912356713783ece`;
adapter log `0a94b9d0662df709c82776da99b959513d556f91a71e9cb65f1bb780f9469743`;
capture log `bfaf241cb7349850458b202832ab67fdb6b14f3358b903d7d4c16e2a2e074cad`.
Audio remains on bench01; recording completion is not listening acceptance.

Next: inspect actual resampler/wrapper machine code; compare the ready 0e024
optimization bundle with fresh backup/readback and matched passive capture.
That bundle includes Hall inlining, postmix advancement inlining and explicit
fabs builtins, so any measured change is not attributable to fabs alone.
Its file-only staging bundle was independently verified and staged at a new
BASE; no candidate construction or further device operation has occurred.
Firmware and web release, persistence/recovery acceptance and owner listening
remain unfinished.
