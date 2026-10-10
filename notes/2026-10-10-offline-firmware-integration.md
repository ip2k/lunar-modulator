# Offline firmware PR integration checkpoint

2026-10-10 07:28 UTC. This is a reviewable integration branch, not a merge to
`main` and not a device-readiness claim. It starts at `origin/main`
`bdba4476570b0a77d13c76a38dfb3bcfd364277b` and preserves normal merge
histories in the requested order: combined candidate PR #140
(`9a5fb72a54f5117169840f331fd1f756071e6fd5`), offline panel-protocol PR #134
(`67cc933c10552f44f5f6707c89155be785848a9f`), then the dependent stock-SPL
layout audit PR #136 (`1299c590408e6d919181294bdadc8c28b4b7503a`). All three
merges were conflict-free. The resulting integration commits are visible in
branch history.

## Candidate and evidence carried forward

The combined candidate's checked-in `sim/web/www/fm1.wasm` SHA-256 is
`c88938845cd93e52f5cb99c53a650b4eaf559833e5f39fb58ecc0f0c4ab09502`, matching
`notes/data/combined-3519-build-receipt.json`. That receipt records source
reference `3519c3857d9bddb8007e14de7ef84525ef8df96a`, engine/simulator hashes
`b97e01d8…7036ad38` / `4d861ada…85fe4377`, metadata `5d726997` (native
`53ec1875`), 108/108 parity cases, and 4,658 screens with no reported faults.
The actual Wasm byte count is 1,561,111. This confirms artifact/receipt
agreement only; it does not establish this new integration branch's full CI.

PR #134 adds an optional bounded panel-protocol event capture sink to an
offline handover link. Source inspection finds no MMIO/SPI/GPIO/IRQ backend;
the wait callback records requested delay rather than waiting, and the target
loop does not return. PR #136 checks linked ELF RAM sections against the
exact pinned stock SPL, rejects protected boot-data overlap, marks loaded-SPL
overlap as requiring non-returning execution, and leaves ownership unresolved
(`private_ram_proven=false`, `device_execution=unverified`). Its report says
layout evidence only. The audit references ignored local linked artifacts
from PR #134; their private build outputs are not committed by these merges.
Neither stream performs package creation, device traffic or installation.

PR #139's sole useful delta not already in #140 is preserved as
`2026-10-10-pr130-webkit-trace.md`. It records the frozen WebKit audio clock
and prompt editor update after worklet resumption, with cause unproven; it
does not waive the exact-head browser check. The read-only 25-PR snapshot from
branch `chore/2026-10-10@demo-readiness-ledger` is preserved verbatim at
`2026-10-10-open-pr-reconciliation.md`; its CI rows are a point-in-time
inventory, not a current status assertion.

The root checkpoint commit `5fb5c314b32a417da0b570bb5f1af0c52db35276` was
reviewed but not wholesale merged. Its only change updates the already
present `notes/2026-10-09-completed-work-integration.md` with an earlier
status snapshot. PR #140 carries the newer version of that file, including
corrections to the artifact-hash explanation and exact candidate results;
replacing it with the checkpoint would restore superseded statements. Its
unique current outcome is represented here by the updated PR inventory and
the three parent commits above.

## Exact-head checks at integration time

GitHub reported PR #140 open at the exact head above, base `bdba4476`, with
Pages build successful and deploy skipped. Its Linux/macOS, 32-bit, sanitizer,
GPL/profile and Chromium checks were in progress or queued; Firefox, WebKit,
dongle and one fork-image check were queued. No failures were shown in that
snapshot, but the full matrix had not completed.

PR #134's old exact-head run `38029909928` had 12 successful jobs and the
WebKit editor job failed. PR #136's old exact-head run `38028091040` had 12
successful jobs and the WebKit editor job failed. These failures remain
recorded; they are neither waived nor treated as passes on this assembled
head. Exact integrated-branch CI must decide whether the combined browser
fixes resolve them. The current host lacks `pytest` in Python 3.14, so the
two focused local Python suites could not run (`No module named pytest`). This
is an environment limitation, not a test pass; the old PR checks above are
the available test evidence until root reviews the integrated diff and starts
fresh CI.

`git diff --check origin/main...HEAD` passed before this note was added. No
hardware traffic, MMIO, loader, flash, package, or install operation was
performed. Root review is required before opening a replacement PR or
dispatching its full CI. Keep the source PRs and all their historical failed
receipts intact until that review and replacement acceptance are complete.
