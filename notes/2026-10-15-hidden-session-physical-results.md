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
claim applies to that build. A matched profiler-off build from exact c0 is now complete,
retaining base telemetry/clock snapshots and disabled autoplay, to measure the
combined cost of detailed timing instrumentation and its USB reporting.
SAVE remains disarmed; overall firmware/installer goal remains ACTIVE.

[verified: offline only] Matched c0 profiling-off output: all16 shards/link PASS,
app853408 bytes (696 smaller), .ram_dsp11812 bytes (104 smaller). Receipt
70b8331ddf9b28e357c38e50937d9af29e46fb8ddffdacc2d420cf636c334c78;
app4dc4de1be6be39a999a352761e96cab2aba1870790b36c9111a255c8ab71b300.
Root independently passed5 export integrity tests. Only the detailed engine and
render-stage profiling options differ from c0 ON; this is a size/build result,
not physical throughput evidence. Export: scratch/c0-profiler-off-export/HANDOFF.md.


## ROM103 preparation checkpoint

[verified: physical read only] Two new full-flash reads through the pinned fixed
RAM loader matched the installed c7afa08c target above. The read campaign made
8,757 commands, zero flash operations and zero resets. Campaign:
`/home/claude/fm1-c0-profiler-off-precampaign-rom103-20261015/read-campaign.json`,
SHA256 `4c12029de3fa88c56aee36fa0829a8c78e5266124416066d315fa62f61ec2280`.
The USB binding remained bus1/port1-1/device103. This is a preparation read;
installation must take another fresh paired backup and verify the device again.

[verified: file-only preparation] The exact c0 OFF bundle (SHA256
`032e11025a777b688eb80f73109ac08fc63dec7191728324d0555228458d1376`)
was staged on bench01 under `/home/claude/fm1-c0-profiler-off-20261015`.
All 249 runtime-tool files and 60 native-source files passed their manifests.
The constructor checked the complete 175-path runtime manifest, then refused
before candidate creation: runtime commit15a requires Limiter::BoxStep in its
RAM function list; exact c0 has the older seven-function list without BoxStep.
Runtime configuration is still song-diagnostic/120s and all SAVE admission flags
are false. A bounded verifier compatibility fix is under independent review;
no candidate, flash write, boot request or new performance result occurred.
The first stager invocation from /tmp failed during path initialization before
staging; unchanged pinned bytes ran successfully from a sufficiently deep path.
Two source-stage argument/precondition refusals happened before any source write;
the native manifest and explicit private parent directory resolved those errors.

[verified: host only] Exact c0 stopped Event Horizon ran five times on Hera;
zero note events, active voices, modulation writes or MFX activity. Five unrouted
modulation modules still advanced each modulation tick. Median desktop render
block cost was 10,393.2ns; this is not FM1 timing. An empty-rack A/B is next;
any optimization must preserve phase/RNG and later connection behavior.
Private evidence: scratch/eh-stopped-host-profile/ and
scratch/native-dispatch-cost-review.md. Current hardware acceptance remains FAILED.
