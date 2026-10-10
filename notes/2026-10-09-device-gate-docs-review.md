# Current device-gate wording review — 2026-10-09

Updated user-facing manual and the sequencer/recovery notes against the staged
hardware policy in `AGENTS.md` and the verified owner bench record
`notes/2026-10-07-fm1-softkey-bench.md`.

The owner’s FM-1_092 has verified soft-key UBOOT entry, reviewed RAM-loader
reads, matching private full-flash backups, and a bounded unused-sector
program/readback/restore. The complete post-test image matched the backups.
This is not a full-image rewrite, recovery-from-nonbooting-app test, or Lunar
installation. The docs retain those limits and require backups, exact
image/ranges, a recovery plan, and a route to USB update mode before any
further erase/program operation. The project's RP2040 dongle has not been
used on the owner’s FM-1.

The README and manual now qualify native Safari claims: automated editor/A-B
checks ran, but the owner reported a Sound 2 switching crackle and the
listening retest remains pending. PR128 was open at head
`1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5` when checked; its Pages build had
passed while CI was still queued/in progress. No PR128 fix or listening
success is claimed here.

The parent’s bounded demo-prerequisite assessment is preserved verbatim at
[`2026-10-09-demo-prerequisite-review.md`](2026-10-09-demo-prerequisite-review.md).
It distinguishes existing source/test contracts from the remaining asset,
full-chain, simulator admission, library, and listening gates. It is a
captured review, not evidence that demo prerequisites have since completed;
PR and branch statuses in it must be refreshed before acting on them.

Validation: `git diff --check` passed. The strict manual/site build could not
run locally: Python-Markdown is absent, and the repository’s documented
Docker build cannot connect because the Colima Docker daemon is stopped. Exact
CI Pages/manual build remains required before integration.
