# Open pull request reconciliation — 2026-10-10

Read-only snapshot of all 25 open PRs in `ip2k/lunar-modulator`, captured before
PR #140 merged. Source of
truth for this snapshot: GitHub PR metadata, exact-head checks, and local
ancestry comparisons against PR #140 head
`9a5fb72a54f5117169840f331fd1f756071e6fd5`. The PR's base was
`bdba4476570b0a77d13c76a38dfb3bcfd364277b` (`main`). It was open and its
required checks were still running or queued. Nothing below authorizes merging
or closing a PR before the replacement actually lands.

## Snapshot and disposition

`Included` means the exact PR head is an ancestor of #140, so its committed
work is present in the combined candidate. It does not mean that old PR's
failed or cancelled checks passed. Run #140's complete exact-head checks before
root's authorized merge decision; keep the individual PRs open until then.

| PR | Head | Base | Draft / merge state | Exact-head check snapshot | Reconciliation |
| --- | --- | --- | --- | --- | --- |
| [#140](https://github.com/ip2k/lunar-modulator/pull/140) | `9a5fb72a54f5117169840f331fd1f756071e6fd5` | `bdba4476570b` | no / UNSTABLE | 1 success (manual), 3 running (Ubuntu, macOS, 32-bit), 10 queued, Pages skipped | **Integration candidate.** Require every applicable exact-head job to finish successfully; Pages skip is not a deploy receipt. |
| [#139](https://github.com/ip2k/lunar-modulator/pull/139) | `4acd3a55ce3f2bc3c6dc71de36da962b0f5b63d3` | `bdba4476570b` | yes / UNSTABLE | 3 success, 6 running, 4 queued, MIT/BSD-off failure | PSX Verb source fix is in #140. Its sole commit missing from #140 adds `notes/2026-10-10-pr130-webkit-trace.md`; preserve or explicitly disposition this unique trace before closing as superseded. Do not use this branch's failing check to waive #140 checks. |
| [#138](https://github.com/ip2k/lunar-modulator/pull/138) | `75aaf658324f119f413090d0e989ddfe44bf41b4` | `c5fd5e9e01d5` | no / UNSTABLE | 12 success, WebKit failure | Included; its effect-integration review is part of the candidate evidence. |
| [#137](https://github.com/ip2k/lunar-modulator/pull/137) | `e1416ac0578bde81192362554089c88ece65c3f9` | `c5fd5e9e01d5` | no / UNSTABLE | 8 success, 1 running, failures: Ubuntu, macOS, 32-bit, MIT/BSD-off, WebKit | Repeat implementation and parameter fixture corrections are included in #140. The standalone source checkpoint failed several checks; candidate's rebuilt source/module and exact CI are the acceptance gate. |
| [#136](https://github.com/ip2k/lunar-modulator/pull/136) | `1299c590408e6d919181294bdadc8c28b4b7503a` | `9cfc46dc35c2` | no / UNSTABLE | 12 success, WebKit failure | **Independent firmware/tooling stream.** Offline Python classifier compares linked diagnostic RAM with the exact pinned stock SPL; reports layout evidence only, ownership unresolved, no package/device action. Keep separate from #140 and obtain a green exact-head check before merge. |
| [#135](https://github.com/ip2k/lunar-modulator/pull/135) | `475c859c5187ecf94a6881f4620b93ae4d8fb614` | `c5fd5e9e01d5` | no / UNSTABLE | 10 success, 3 running, WebKit failure | Device-gate documentation is included. Do not transfer its historical claims without the newer #140 text. |
| [#134](https://github.com/ip2k/lunar-modulator/pull/134) | `67cc933c10552f44f5f6707c89155be785848a9f` | `9cfc46dc35c2` | no / UNSTABLE | 12 success, WebKit failure | **Independent firmware stream.** Optional panel protocol calls a RAM-only event sink that hashes/stores a bounded trace; source explicitly has no MMIO/SPI/GPIO/IRQ/flash backend. It is not panel output or a device test. Keep separate; root should sequence its artifact provenance with #136, which audits linked variants from this stream. |
| [#133](https://github.com/ip2k/lunar-modulator/pull/133) | `a5bac822d9ed9b938393ca1ef5e575d453616775` | `c5fd5e9e01d5` | no / UNSTABLE | 12 success, WebKit failure | Old-doc reconciliation and Movy factual corrections are included. |
| [#132](https://github.com/ip2k/lunar-modulator/pull/132) | `c6db9587c1d8d1ca6f993d8f433875761f3b2b6e` | `7eb55b1fd05b` | yes / UNSTABLE | 13 success, Chromium cancelled, Pages skipped | Headless audio lifecycle test/config is included. Cancelled job is not a pass; #140 reruns Chromium. |
| [#131](https://github.com/ip2k/lunar-modulator/pull/131) | `78101317052b2eb990d7a24fbe855dbb506ce1eb` | `cafd77e0216b` | no / UNSTABLE | 12 success, Chromium failure | SDK/licensing evaluation is included. |
| [#130](https://github.com/ip2k/lunar-modulator/pull/130) | `d7170e043b1824f537613b65efddcb3de72d12e2` | `67d5e12dee56` | no / UNSTABLE | 12 success, WebKit failure | Effects research is included. #139's one additional WebKit scheduling trace is a separate evidence delta. |
| [#129](https://github.com/ip2k/lunar-modulator/pull/129) | `ac3d9571b8a2db6860db60b1afb5f10246134e26` | `67d5e12dee56` | no / UNSTABLE | 13 success, WebKit failure, Pages skipped | Scope continuity fix is included. |
| [#128](https://github.com/ip2k/lunar-modulator/pull/128) | `1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5` | `67d5e12dee56` | no / UNSTABLE | 13 success, WebKit failure, Pages skipped | A/B state fix and automated capture evidence are included. Owner's Sound 2 crackle report still needs by-ear retest; CI cannot resolve it. |
| [#127](https://github.com/ip2k/lunar-modulator/pull/127) | `3cf5f771c40a5cf042a6b473636bfb1c66771b38` | `9cfc46dc35c2` | no / UNSTABLE | 10 success, 2 running, WebKit failure | Integration policy and demo prerequisites are included; candidate says human listening and final full-song validation remain. |
| [#125](https://github.com/ip2k/lunar-modulator/pull/125) | `7fe4e6cd10e5d4aa895c5df18d0273364788be5d` | `9cfc46dc35c2` | yes / UNSTABLE | 13 success, WebKit failure, Pages skipped | Native screen-pixel fix is included. |
| [#123](https://github.com/ip2k/lunar-modulator/pull/123) | `0e43e503be47737446c1ccd03915f1a888ce9803` | `67d5e12dee56` | yes / UNSTABLE | 13 success, WebKit failure, Pages skipped | Warble effect is included in rebuilt combined candidate, with effect manual sections. |
| [#121](https://github.com/ip2k/lunar-modulator/pull/121) | `32d4747f900a47de4054618195ffe269f73ccef6` | `cafd77e0216b` | no / UNSTABLE | 12 success, WebKit failure | Four-song requirements are included; no song assets or per-song acceptance are represented by that brief. |
| [#118](https://github.com/ip2k/lunar-modulator/pull/118) | `b4234c1b816d71f777796404eb4f0a5190f4eace` | `67d5e12dee56` | yes / UNSTABLE | 13 success, WebKit failure, Pages skipped | Picks undo/redo fix is included. |
| [#114](https://github.com/ip2k/lunar-modulator/pull/114) | `a97659f56cd54499a09e99f7689df4aff74cf7b3` | `67d5e12dee56` | no / UNSTABLE | 12 success, WebKit failure | Movy oracle bounds fix is included. |
| [#113](https://github.com/ip2k/lunar-modulator/pull/113) | `b43960680760092bf1eb13ad2371b2039326abd9` | `67d5e12dee56` | no / UNSTABLE | 13 success, WebKit failure, Pages skipped | Compare MIDI pulse fix is included in combined rebuild. |
| [#109](https://github.com/ip2k/lunar-modulator/pull/109) | `c69f9af06cbf977d26285f724d8f8604976d7221` | `32b321ff5674` | no / DIRTY | 12 success, WebKit failure | Remaining-work ledger/HANDOFF update is included via normal history in #140. Old base and dirty merge state make this a poor independent merge target. |
| [#105](https://github.com/ip2k/lunar-modulator/pull/105) | `cc43875c7b205fcfbe530c04e4e7950cd6370bae` | `67d5e12dee56` | no / UNSTABLE | 13 success, WebKit failure, Pages skipped | Test-server path containment fix is included. |
| [#102](https://github.com/ip2k/lunar-modulator/pull/102) | `962e8ba900f7c223b46f7dd058874fabe96ace20` | `67d5e12dee56` | no / UNSTABLE | 12 success, WebKit failure | Recovery-status documentation is included. |
| [#58](https://github.com/ip2k/lunar-modulator/pull/58) | `3629a358340ba120fb42e2acb6e0297c7a7b17b5` | `64209e3c0822` | no / DIRTY | 13 success, manual cancelled, Pages skipped | Stale-doc snapshot is not safe wholesale. Its still-useful Movy commit/tag and control-count corrections are present through #133/#140; outdated counts and blanket recovery language are not. Reconciliation evidence is in `notes/2026-10-09-pr22-pr58-reconciliation.md` in the candidate. |
| [#22](https://github.com/ip2k/lunar-modulator/pull/22) | `82f4235c5caaed327be77e2942a551c233f1928b` | `64209e3c0822` | no / DIRTY | 13 success | Historical HANDOFF snapshot through #98. Current HANDOFF and dated reconciliation are included through #109/#133/#140; do not merge the old snapshot. |

The many old WebKit failures remain failures on their original heads. They are
not treated as transient or waived here; #140's exact-head WebKit run is still
queued. Likewise, old successful checks do not validate a later combined
artifact.

## Current status refresh — 2026-10-10 UTC

PR #140 merged as `40c94300428acfc5688a203c2c928723ed98270a`; PR #118 later
merged as `dd9b329211109bf07b05594a941da8451f762615`, which is an ancestor of
the current `origin/main`. The picks undo/redo correction is therefore now on
main. The table above remains the earlier pre-merge snapshot and its old PR
check results are historical.

At this refresh, the open PRs are #139, #134, #136 and #141. PR #141 head
`9ecd5ad2373ad0bd15106f31a44f50d68bc9c28e` had one completed Chromium page-test
failure, with its ASan/UBSan job still running; other completed checks shown by
GitHub were successful. Preserve that failure as an unresolved exact-head CI
result. The audit-boundary fixes in this branch have not yet been merged to
main. The PSX Verb correction is separately on open PR #139; neither a focused
test nor a candidate build closes its full acceptance gates.

## Independent firmware review and merge order

PR #134's inspected code adds a bounded abstract panel event sequence and an
offline capture sink. The capture stores event counts, wait totals, a rolling
hash and protocol error state in RAM. The interface comments explicitly say
there is no MMIO implementation. I found no physical transport or flash-write
path in the reviewed files; this is a source review, not execution evidence.
Its checks have one WebKit failure, irrelevant to this firmware-only code but
still unresolved for exact-head CI.

PR #136 adds an offline tool that re-runs the SDK-free link audit, checks the
exact pinned stock SPL size/hash/header/CRCs, and derives RAM ranges from the
ELF. It rejects overlap with protected boot data, measures overlap with the
loaded SPL body, and marks the result as requiring non-returning execution;
it does not reject every SPL-overlapping section. Its output keeps
`private_ram_proven=false`, device execution unverified, and runtime gates
unresolved. Focused tests include malformed ranges, CRC/header damage, profile
mismatch, audit recomputation and no-success-JSON refusal. This is layout
evidence, not proof the RAM is safe to execute from. Its exact-head checks
also have one WebKit failure.

The #136 receipt explicitly audits linked artifacts from #134 commit
`7385bee77d70e81d0bf588e7479c016ee5a9e154`; preserve that provenance if root
merges both streams. Suggested order is #134 then #136, after their exact-head
checks are resolved, so the source variant precedes its recorded layout
audit. Neither PR authorizes device traffic or installation. Rarefaction was
ready only at the original checkout; Serena's active project belonged to the
separate Repeat worktree. I did not switch either shared semantic root for
this read-only PR inventory, so these source observations used exact Git refs
and direct file inspection rather than LSP navigation.

## Next actions

1. Let #140 exact-head CI finish. If all required checks pass, root may merge
   the combined candidate under the owner's standing authorization; retain
   Sound 2 by-ear listening as a separate open acceptance item.
2. After merge, close only PRs whose full heads are represented by #140, with
   a short supersession note. For #139, first retain or explicitly decline its
   unique WebKit trace file. Do not close #134/#136 as duplicates; root should
   review their independent offline firmware value and resolve their exact
   failed WebKit checks.
3. Dispose of #22/#58 only after confirming the merged HANDOFF and factual
   corrections in #140; neither old branch is suitable for wholesale merge.
4. Keep the requested song work distinct from firmware readiness. The current
   notes say schema/runtime APIs support authoring, but four songs, full-chain
   native/Wasm receipts, browser save/reload/scene-takeover acceptance, and
   human listening are still outstanding. Do not claim those deliverables
   from PR integration or CI alone.

This ledger is a point-in-time reconciliation, not a blanket audit closure.
