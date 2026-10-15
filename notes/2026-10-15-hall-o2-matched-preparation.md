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
