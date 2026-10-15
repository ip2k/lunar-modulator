# Hidden Session work: physical timing result

[verified] The one-use ROM101 campaign installed source
`c0f138a09eac30ae187cb764617bac7e03df06e9`, target
`c7afa08c1a66fe82458359cd0750133b755d7247e0904e6fedd18402f71418c6`.
Fresh paired backups matched the preceding installed target
`915131c38619a652bd120af68bd89c050e0a45820f0b8c5eb1e004d2fae0fdb5`.
The transaction changed 210 sectors inside the approved app/directory region,
directory last. Root independently checked all 4096 final 256-byte page hashes:
all matched the target and every SG read completion was clean. Adapter transcript
SHA256: `5b167fd3ffa68a3e96ae55a843904ffbb5803c01661717b0eea7a88c372de58b`.

[verified] The sole reset reply was ambiguous and was never retried. The armed
passive helper observed native USB102 independently, completed 110 seconds of
input-only telemetry and 180 seconds of six-channel KA6 audio (both rc0), and
the device subsequently returned to ROM103 automatically. No MIDI output,
PLAY, autoplay, SAVE, or owner musical acceptance occurred in this campaign.
ROM101 is consumed: never relaunch it. No physical intervention is needed now.

| Metric | Previous image | Candidate |
| --- | ---: | ---: |
| Produced 64-frame blocks/device-second | 447.867 | 464.450 |
| Required blocks/device-second | 689.344 | 689.344 |
| Underruns/device-second | 241.473 | 224.879 |
| Postmix timer ticks/call | 6053.812 | 4580.211 |
| Display-strip timer ticks/call | 5923.513 | 5946.783 |

[verified] This sequential comparison shows 3.70% more produced blocks and
6.87% fewer underruns. The candidate still supplies only about 67.4% of required
blocks and fails real-time acceptance. The source bundle includes additional
resampler RAM work and sequencer getter optimization as well as removal of
hidden Session-grid scans, so the total gain cannot be attributed to one change.
Detailed stage timers overlap: dispatch includes sound callbacks. TIMER4 ticks
are not calibrated CPU cycles. Cold-boot owner musical acceptance remains FAILED.

## Evidence and next experiment

Private evidence: `scratch/hidden-session-result/physical-install/`,
`scratch/hidden-session-result/physical-capture/`, and
`scratch/hidden-session-result/comparison-rom101.json`. Raw audio stays at
`/home/claude/fm1-hidden-session-c0f138a0-20261015/rom101-engine-render-profile-cycle/diagnostic-audio/audio.wav`
on bench01. No binaries or owner audio are committed.

- Events SHA256: `93f9c850e3a8bbc431693a4fc81edfcc633577432b5a69b8a0e1cf115b56e53d`.
- Telemetry receipt: `f8bf1509c9f34bd9ca325a5230f3136552c434fc7ac8f9dd324e7d54ad334e44`.
- Capture log: `ca027fa3c428e51920fedc35da01e50f4c585ced11644c9c5d13ca928807427a`.
- Completed capture logs archive: `56e332b710dfa441fa5dcfe8712f688531ad04c9d7aa1914125135ee88837f3c`.

[verified: offline only] The limiter-only Os build from exact `df415599`
passed all sixteen bounded Hera shards and link: app854572 bytes, SHA256
`32ce09a225b0c0673e0be096e5f27a9703bf16e4c9ec847163e825d9fdffe17a`.
Root independently passed all six export integrity tests. No physical timing
claim applies to that build. A matched profiler-off build is assigned next,
retaining base telemetry/clock snapshots and disabled autoplay, to measure the
combined cost of detailed timing instrumentation and its USB reporting.
SAVE remains disarmed; overall firmware/installer goal remains ACTIVE.
