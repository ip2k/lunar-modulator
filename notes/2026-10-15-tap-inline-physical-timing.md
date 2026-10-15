# Tap-inline passive physical timing comparison

[verified] The owner's cold boot still produced a very laggy waveform display
and distorted, sluggish sound. Musical acceptance remains FAILED. The captures
below are passive, with no injected MIDI notes or transport. They cannot establish
active-note quality or song performance.

## Installed image and recovery

[verified] The ROM93 campaign installed source
`2b9178c42494c5cbb112718857665e9c9a27634c` with 210 changed sectors and complete
flash readback SHA-256
`07761c6c8bbe8c706e323d42266196dff5b530113f451bcc8ca7eeaade65f4c7`.
Two fresh pre-write reads matched
`1c04fadcbf4a682214e7e4370ac54a1fa4a09ef57a6f9f527da77bffd2f7a291`.
The single reset reply was ambiguous; the runner refused and no retry was sent.
The helper armed before reset observed Lunar USB94, captured telemetry for 110
seconds and KA6 audio for 180 seconds, and both processes exited successfully.
The coordinator subsequently observed ROM95 after the bounded diagnostic's
automatic recovery. The consumed campaign must not be relaunched.

## Device counter comparison

[verified] Rates use unsigned differences between the first and last schema-1
counters divided by device uptime differences, rather than USB delivery timing.
Both runs accepted zero note-ons and recorded zero USB/UART MIDI activity.

| Image | Device interval | Produced blocks/s | Underruns/s |
| --- | ---: | ---: | ---: |
| Exact-zero baseline, source44fbb17f | 107.914 s | 419.890 | 269.455 |
| Tap-inline, source2b9178c4 | 107.965 s | 422.581 | 266.753 |
| Required at 44,118 samples/s and 64 frames/block | — | 689.344 | 0 |

[verified] The measured throughput difference is +0.641%; underruns changed
by -1.003%. This single pair does not demonstrate a meaningful gain. Both remain
severely below the required rate even without active notes. The clock register
snapshot tuples match (`CLK_CON0=449`, `CLK_CON2=6`, `SYS_DIV=66048`); matching
configuration does not establish measured core frequency.

[verified] Across 23 steady schema-2 windows spanning about 88 seconds, weighted
stage costs moved in mixed directions. Hall was about 10,977 timer ticks/call,
master effect1 about 9,096, and postmix about 6,837. Sequence dispatch is inclusive
of engine rendering and tick hooks; do not add it to those nested sound costs.
Observed IRQ-attribution ratios were 9.29% and 9.20%, with no mismatch/overflow
deltas in the analyzed window. That ratio is not removable overhead or proof
that IRQs cause the overload.

## Retained private evidence and limits

[verified] Evidence is retained locally under
`scratch/tap-inline-only-result/physical/`, with the full source-bound campaign on
bench01 under `/home/claude/fm1-tap-inline-only-2b9178c4-20261015/`.
The complete capture archive SHA-256 is
`f4e6987f6ce2c349e764565785eb7ede8bce74f7e3906c61dbbd38def5cfe579`;
telemetry events SHA-256 is
`1e31712d89945e27b5ce63e622823bd4b1c3d0f63ae68358834cc6b189667659`.

[verified] Audio contains 8,640,000 six-channel signed-32-bit frames at 48 kHz.
In the passive 15–110 second window, inputs1/2 peak at 0.004876/0.005279 full
scale and RMS at 0.000507/0.000529, with no rail samples. These idle statistics
neither test nor contradict the owner's distorted-note report. WAV SHA-256:
`7b3cd6f7f2a5aa16617f726c8c829e7d070065500daa13b4d46ff1e2e2e479be`.

[inferred] Next measurement should separate Drums/SixOp Render from nested
RenderBlock cost using schema7, while a separate combined Hall/postmix build
checks code generation and fit with the current compilation settings. SAVE stays
disarmed. No release, playable performance, or musical acceptance is claimed.
