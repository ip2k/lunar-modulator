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
