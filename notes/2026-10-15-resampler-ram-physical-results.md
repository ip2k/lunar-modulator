# Physical resampler ready-pop RAM comparison

[verified] The one-use ROM99 campaign installed source
`1624974067ec51cf56b443d789ba8568906be8f5`, target
`915131c38619a652bd120af68bd89c050e0a45820f0b8c5eb1e004d2fae0fdb5`.
Fresh paired full-flash reads matched the preceding installed image
`13902c8a762cad580f7e1d779ff51d8c31d7dc8184eedab8d594d70cbc6262fd`.
The transaction changed 210 sectors inside the approved app/directory region,
with the directory last. Root independently checked all 4096 final 256-byte
page hashes against the complete target; every completion was clean. Adapter
transcript SHA256: `4c29575604f1f01c67670404694c2412175bdd804af1acd4e10122ddfcb8087d`.

[verified] The sole boot request had an ambiguous host completion and was
never retried. Native USB device100 appeared independently afterward. Input-only
telemetry completed in 110 seconds and six-channel KA6 audio capture in 180
seconds, both rc0. Subsequent passive enumeration showed automatic recovery
as ROM device101. No notes, PLAY, SAVE, or owner listening acceptance occurred
in this passive campaign. The ROM99 launcher is consumed: never relaunch it.

## Performance

| Metric | Previous image | Candidate |
| --- | ---: | ---: |
| Produced 64-frame blocks/device-second | 446.08 | 447.87 |
| Required blocks/device-second | 689.34 | 689.34 |
| Underruns/device-second | 243.26 | 241.47 |
| Display-strip timer ticks/call | 5909.8 | 5923.5 |
| Sequence-dispatch timer ticks/call | 20324.9 | 20731.6 |

[verified] Throughput improved only 0.40%; underruns decreased 0.74%.
The candidate still supplies about 65% of required blocks and fails the
real-time requirement. This source bundle includes readiness, limiter inlining
and ready-pop RAM placement; the result does not isolate any single change.
Small deltas in these sequential captures can reflect run variability.
The SixOp nested block metric decreased 9.68%, while its outer render metric
increased 1.07%; a faster nested metric did not establish total throughput gain.
Stage timings overlap, and the timer is not calibrated CPU-cycle evidence.

## Reproduction and limits

Private evidence is under `scratch/resampler-ram-result/physical-install/`
and `scratch/resampler-ram-result/physical-capture/`. Raw audio remains on
bench01 in the consumed campaign's `diagnostic-audio/audio.wav`.
Events SHA256: `0474c9578b01876938accffe11a8c201a3657a600161a5b0216adf5f18cbaa7c`;
receipt: `0dba236aa2a9b9cd500c0dafb6358972ba46a9b4b007a692127a1851db385ea5`.
Both receipts/events pass the existing comparison tool's hash/schema/image-pin
checks. The saved comparison is `scratch/resampler-ram-result/comparison-rom99.json`,
SHA256 `a08ab1bb3be7f7292c3dee3e1244d17c1b63aaa25b189ca14ab3bbc4da9de321`.
Receipt identity and hardware acceptance flags remain false; independent
installation/readback evidence does not imply musical or release acceptance.

[verified: owner] Cold boot still produced a very laggy waveform and badly
distorted notes. SAVE remains disarmed and the release goal remains active.
The next offline target at `c0f138a0` combines subsequent resampler RAM work,
the sequencer getter optimization and removal of hidden Session-grid scans.
Its physical performance remains untested. No owner power cycle is needed
for preparation while the unit remains in recovery.
