# Suspended startup final CI handoff

[verified] PR144 tested `5805ea9cc0a0d655f66c7d30b9d4584c8a615084`:
CI run 38042083160 has all 13 functional jobs successful; Pages run
38042083204 is successful, with deployment skipped for the PR. All 14
checks completed successfully. The candidate is frozen. This receipt is
on a separate checkpoint branch so recording it does not reset candidate CI.

[verified] Both startup cycles in each browser constructed and initialized
the node while suspended, at unchanged audio time zero, then connected
both outputs and ran. The strict 30-second Chromium storm reported 7,260
edits, zero non-OK codes/resyncs and zero underrun events/ms. Firefox and
WebKit passed at 7,224 / 3,757 edits; their raw playback counters are not
available. All had 905 telemetry messages and valid 1,115-byte snapshots.

[verified] External loopback passed in all three browsers for about 32
active seconds, zero nonfinite samples/channel mismatches/bad periods,
and eight project/Sound 2 A/B swaps without transport stops. Chromium
had one zero sample (0.020833 ms); Firefox/WebKit had zero. This passed
the existing unchanged gate and is not described as zero silence.

[verified] Ubuntu and macOS each passed 5,255 tests; 32-bit passed 4,249
engine tests plus 498 app tests. ASan/UBSan passed 4,249 engine tests plus
508 app tests. Existing skips/xfails are retained in the compact receipt.
The actual manual has 17 chapters / 42 entries, zero outline boxes,
manual errors or manual warnings; compiler/action warnings are separate.

Full check URLs, measured JSON, test summaries and SHA256 of downloaded
logs are in `data/2026-10-10-pr144-final-ci.json`. Logs remain locally at
`/tmp/lunar-pr144-{chromium,firefox,webkit,ubuntu,macos,32bit,asan,pages}.log`
and on the named GitHub runs. This run's passing browser artifacts are not
uploaded by the failure-only artifact step. No failed CI was retried.

The original PR143 startup glitch and earlier unassigned failures remain
preserved in `2026-10-10-worklet-suspended-startup.md` and its data files.
Tracing can perturb scheduling; one successful exact-head CI does not
prove absence of every possible browser glitch. Native Safari and the
owner's by-ear retest remain pending. Root owns reviewed integration/main
merge; this receipt does not itself claim a merge, deployment or hardware
acceptance. No hardware traffic occurred in this stream.
