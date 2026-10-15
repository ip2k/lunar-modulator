# Matched Hall optimization preparation

Owner cold-boot listening acceptance remains FAILED: Lunar boots, but the
waveform display is very laggy and individual notes sound badly distorted.
The goal remains ACTIVE; SAVE and autoplay remain disarmed.

## Source and offline verification [verified]

Hera branch `codex/2026-10-15-hall-o2-cpu-baseline`, commit
`493a432c8c109df0f99ebba6e93b71c3ac646c22`, directly follows the physically
measured CPU diagnostic source `8a8fb2b86219bc339d70c2e790659e8426b74159`.
Root fetched it and backed it up to the same branch on origin; `ls-remote`
matched the complete commit SHA. It is not integrated into the coordinator
branch. Its three-file change adds explicit Hall `-O2` selection, records the
selection in compilation receipts, and requires matching link receipts.
The default build policy is unchanged.

Root reviewed the source diff and ran the optimization, receipt, image
catalogue and preload catalogue suites in isolated detached checkout
`/Users/likwid/.codex/worktrees/hall-o2-cpu-review`; all passed. An initial
command named nonexistent `test_native_catalogue.py` and collected no tests;
the corrected commands used the actual suites. No device acceptance follows.

Worker build handoff:
`/home/claude/.local/share/codex-coordination/handoffs/lunar--hall-o2-cpu-baseline-20261015.md`.
The raw receipt is
`4a0814b00519b77812266b39ffe6a91c9be2bb28f9ead09607288c313c7620ef`.
App: 855,712 bytes,
`645b5b48b58bbaf09b1fa2b109d3e4557ff2e163c7db45862e0d29c5c71f1981`.
Worker compared 167 catalogue objects with the exact CPU control: only
`our/src/fx_hall.o` differs. App growth is 1,292 bytes. These are offline
build/codegen facts, not runtime speed or musical acceptance.

## New campaign boundary

Root passively confirmed port `1-1`, bus 1/device 111, `4c4a:8057`.
Expected current image remains
`5b3ebc0b4a1672662137677bb08de5017c17319ebc25290a676d548654dfa7aa`.
No new flash or reset operation has been issued. Previous campaigns are
consumed and must never be retried.

Offline preparation uses new BASE
`/home/claude/fm1-hall-o2-cpu-493a432c-20261015` and cycle
`rom111-hall-o2-cpu-cycle`. Candidate construction, sealed build/runtime pins,
file-only preflight, independent lifecycle review and fresh matching paired
backups are still required before a physical write. The complete install
result must be durable and audio capture ready before the sole reset.
Ambiguous reset completion is terminal; no retry.

## Other reviewed work

Compact route getter matched target builds succeeded for parent `e844f6bc`
and candidate `f9dc614f`. The app remains 854,340 bytes. Disassembly removes
the full 44-byte track snapshot from the route-refresh loop and reduces its
stack allocation by 40 bytes. It is already source-integrated, but has no
physical speed measurement and is not part of the isolated Hall comparison.
Hera handoff:
`handoffs/lunar--compact-route-getter-target-20261015.md`, SHA-256
`a0bc1bfc4e43edd790ac88f9181970c163d98e44d3e4b96aee1484215b7ff360`.

Read-only render-cost and wrapper/resampler audits found no justified large
exact-work elimination. Saved under `scratch/cpu8a-render-cost-review/` and
`scratch/cpu8a-wrapper-resampler-review/`. They do not justify skipping tails,
changing filter quality, or claiming current limiter code matches the older
CPU target. Hardware performance, listening, persistence/recovery, installer,
review/CI, integration and shipment remain unfinished.

## Staged-destination preflight caught manifest mismatch [verified]

The v1 package passed nine focused synthetic checks and independent file-only
review, but did not pass the actual destination preflight. Root staged its
313 files from archive22e4c842c070f13c03e57b5f32bc87a872349d181b3f09030d0358c86dfd26e2
into the new BASE, verified the312-entry deployment inventory and restored
archive modes; staged61 native source files via its verified helper. No device
operation or launch occurred. The first helper call refused a missing ordinary
firmware parent; root created that directory and source staging then passed.

The actual file-only preflight refused build/source-tree-manifest.json:
its full manifest SHA7d815fa894446912d5b44c34fb9cb841476219ca84d374b47f31c378d8d14580
was incorrectly pinned as the compact export manifest
4d9f9f2b9c49827a6925128d4064696fc93007fa759a574b1ce8935982a342e5.
The compact manifest belongs to archive staging; the full manifest belongs to
source/build verification. The original archive/package remains preserved.
Worker prepares a separate v2 package correcting that pin and dependent hash
chain, with an explicit full-versus-compact path regression check. This failure
was before USB, flash or reset. Actual destination preflight is still required;
synthetic/package hash checks alone do not establish readiness.

## V2 destination preflight stopped at stale capture verifier [verified]

Root applied only the six independently reviewed v2 package files after
verifying the original staged inventory, no launch marker, and the delta archive
SHA3c41862ea6d47f5fe33cbeafe381d7ef3bc5c73ce9f013902b0dedd5f9bd3efd.
All312 v2 deployment hashes matched. Independent review report SHA
2953daf8ab8438e21c90d7342669b08e7b77b18d9e1b50b36f24386302a9dc88
and ten focused tests passed. Actual destination file-only preflight with
campaign92a1cbb1f4449aaef465f3e9c7cda1fa8aa7104dab3d73926d8f746af9fa4c66
then refused: Runtime digest does not equal the externally frozen manifest pin.
No device operation, launch marker, erase/program, or reset occurred.

The campaign relocated three telemetry paths in the runtime manifest, producing
8c6431ddb63f4f5d289676ed25de962ad653388c595d429a9cdccc5e0c3b6025,
but its copied strict verifier retained the old CPU campaign manifest digest
a795da42 and old telemetry paths. Worker prepares distinct v3 with consistently
rebound campaign-local verifier/expected documents and refreshed hash chain.
The maintained249-file runtime source archive/tree and175 dependency hashes
must stay unchanged. Destination preflight remains mandatory before hardware.

## Combined optimization build [verified; no hardware performance claim]

Hera source48b5664a375b78785b76b681469864c7797d29fd build passed16 catalogue
shards and all ten output hashes. Receipt29c82036de5b7e9536ecc061115d9dab56d36d41273a0223846007dd467e6531;
app855912B SHA d1722912d7d4595aca9b3193ee403ea341d2498ec499741395be4e2572d9443c.
Review /home/claude/mvave-fm1/hall-o2-led-target-48b5664a-20261015/review-handoff.md
SHA b7c8c4cdc77f20bf1fd2b95eb3f0c418f2993f5a48448aab6065cc5943bcf157.
Bounds checks precede octave LED seconds conversion; localized codegen evidence,
not a whole-image parent A/B or runtime speedup. Hall-only matched candidate
remains separate. Goal ACTIVE; cold-boot listening FAILED, SAVE/autoplayoff.

## V3 actual destination preflight passed [verified]

Separate v3 preserves old package copies and rebinds the strict generated verifier
to the already-reviewed relocated manifest8c6431dd and three telemetry paths.
All175 runtime dependency hashes and249 maintained tools source files remain
unchanged. Root independently reviewed the verifier/capture/test diff, reran
12 tests, verified312 package hashes and applied11-file delta archive
840bbdf5bfb50ac44d7cb2ca0d21e3078c8ac9d0a539f6c9ef3709335e78e8dd
over the hash-verified v2 staged files, with no launch marker or cycle.
Campaign3cc1d6c92bf5d12b2604d6034b64563e46e0daa56fd25f0b55d6077f1f8e46b5;
inventorya3789145d377f3bcbcdfc1b2edf3d94ac076bea1a373998158d42e140e870d55.
Actual preflight then caught0775 directory modes introduced by root staging
parent creation; restored exactly the ten directories inventoried in pinned
tools-source-manifest3567aeae to required0755. No files or checks changed.
Actual destination run-cycle --mode preflight now prints FILE_ONLY_PREFLIGHT_OK.
This is a file-only result; no USB transport, device write, reset or launch yet.
Fresh passive sysfs still port1-1/bus1/dev111/4c4a:8057. Final independent
review and immediately rechecked live identity precede the one-use campaign.

## One-use campaign launched [verified; outcome pending]

Independent final review SHA68b411eca6a4960fd9f91609b7566a2413a60574950b88eb6bf1c9d68326214f
found no blockers. Root immediately rechecked exact passive ROM111 identity,
then invoked launch-once.py once under sudo-n. Its own file-only preflight
passed; persistent PID282595 began FRESH_PAIRED_READ_START. No outcome or
performance claim yet. This campaign is consumed: never relaunch or retry
an ambiguous reset; inspect existing process/artifacts and independent capture.

## Completed physical measurement [verified; musical acceptance still failed]

Fresh paired full-flash dumps matched5b3ebc0b4a1672662137677bb08de5017c17319ebc25290a676d548654dfa7aa.
Install wrote210 sectors,0x4000 directory last. Root's independent final-page
transcript verifier matched4096 consecutive256-byte page hashes against target
28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f;
all SG completions were clean, with63 keepalives since the last write.
Adapter log3d91ad0ee2712749f0d2b92200eb48129517f99a2110d523e8ba0c5cf2ce5690.
Install result was durably written before capture READY and sole FC0C reset.
Reset returned host7/resid16/info1: runner stopped without retry. Independent
capture observed native112 and completed normally (110s telemetry,180s KA6
audio, rc0, children cleaned up). Passive sysfs subsequently observed ROM113
on the same port1-1,4c4a:8057. The campaign remains consumed permanently.

Root independently decoded all134 raw SysEx frames and matched their recorded
schemas/values.109 schema1 frames span108 intervals,109.250 device seconds
and109.240131 host seconds:54456 produced blocks,20855 underruns, zero accepted
note-ons. Throughput498.453089 blocks/s versus CPU8a baseline488.145253
(+2.111633%); underruns190.892449/s versus201.192781/s. Required689.343750
blocks/s;27.691650% throughput shortfall remains. This is a measured small gain,
not real-time audio or listening acceptance. No PLAY/song/note test occurred.

Local evidence under scratch/hall-o2-cpu-result/:

- fresh-read-evidence.tar SHA9cc0e19d217e8a05ef001490c036253cc4a742b1136d3cbaa5c124ac66dba9b4
- capture-evidence.tar SHA81321c34bfaaaed8d440be805b9bdc15d691c190680260cbe3719fa09a54de31
- events.jsonl SHA6aef02f2c8289f2c4c7c40666233fc3ed5507661bf55c9585c0149f9f0a921d2
- raw.syx SHAe8822286ddbce9f707d80451883150b4893ad892edcba240087c3e8caec47a42
- capture.jsonl SHAc55cb03ad028ff7b2dcb48d43dc25388a38849270281abe0ce557775c511c261
- root-independent-summary.json and root-independent-readback.json preserve calculations/checks.

Audio remains on bench01 at BASE/rom111-hall-o2-cpu-cycle/diagnostic-audio/audio.wav.
Successful capture does not establish useful sound; the owner cold-boot report
remains severe waveform lag and distorted audio. No further power cycle needed
for the next recovery-mode investigation. SAVE/autoplay remain off.
