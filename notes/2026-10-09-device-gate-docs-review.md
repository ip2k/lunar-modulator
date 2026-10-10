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

Validation: `git diff --check` passed. The strict manual/site build completed
on aeon using the project’s existing cached `lunar-modulator-manual:ubuntu-24.04`
image, in `docker-batch.slice`, bounded to 4 CPUs and 4 GiB memory. It built
the engines and ran `tools/manual/build.py --site /tmp/out --pdf --strict
--no-make` at source commit `15071c8915761df6cd587c48c5d8e3e7f40140a1`.
The result was 17 chapters, 40 engines/effects, a 272-page PDF, and zero
strict-manual errors or warnings. The PDF receipt at
`/tmp/lunar-pr135-manual-15071c8/lunar-modulator-manual.pdf` is 2,386,727
bytes, SHA-256
`f951b3061ae3b83fad479210023ac610d56f63aa9d7b3e9d06466c82e744e0f0`.
The generated HTML contains the planned-workstreams wording and the corrected
installability statement. The aeon GCC engine build printed existing compiler
warnings; the manual builder’s strict validation passed. No local daemon was
restarted, no build artifacts were written into the repository, and no device
or hardware was contacted. PR #135’s GitHub CI and Pages checks were queued at
head `15071c8915761df6cd587c48c5d8e3e7f40140a1`; this LAN receipt does not
replace those checks.

## Bounded full-code-audit disposition for demo work

This is a cross-check of the audit’s findings that intersect project authoring,
state loading, playback, distribution or device readiness, not a rerun or blanket
closure of the full audit. Findings remain in
`notes/2026-10-07-full-code-audit.md`; several entries there predate fixes and
still say “no fix was made”.

- **Resolved on current `main`:** the IndexedDB false-success/data-loss P2 is
  in merged PR #103 (`b6a6b58`), so the browser must not claim a durable save
  when storage failed. The stale cable-target P2 is in merged PR #99, commit
  `dd1ecf2`; `sim/web/test/editor-v1.mjs` now changes a cable after Search
  captures it and asserts the batch refuses the target. The malformed trig
  lane P2 was fixed in merged PR #100, commit `17b7495`; `field_end()` now
  initializes the signed lane and `tests/test_seq_core.py` rejects bad and
  out-of-range lane tokens. The infinite rate/duration P3 in the Room oracle
  is fixed in merged PR #112; its current entry checks finite, positive,
  representable frames before converting/allocation.
- **Still a bounded editor/runtime follow-up:** repeated “Make B from the
  picks” undo/redo P2 is PR #118, open at `b4234c1` when checked; until it
  lands, avoid repeated picks loads inside the history merge interval when
  creating canonical assets. Compare MID’s missed pulse P3 is PR #113, open
  at `b439606`; do not rely on a single-tick sweep through its middle zone in
  demo modulation until the fix passes and lands. Unknown MFX load handling
  remains an app-state P3: demo admission must use the exact integrated
  registry and reject any unknown, refused, left-out or skipped object. That
  existing acceptance rule is in the prerequisite checklist above; a successful
  file read alone is not a load receipt.
- **Not a reason to block offline composition, but still tracked:** remaining
  malformed-input, extreme-value, cleanup, benchmark, CLI, oracle and manual
  publishing findings are mostly developer-tool reliability/safety cases.
  Use known-valid bounded parameters and output paths outside the source tree;
  do not run the destructive `--site` case or untrusted remote-runner arguments.
  The GPL-only X0X signed-shift P2 remains a distribution/runtime concern for
  those modules: keep GPL X0X out of MIT/BSD demo assets and builds until it is
  resolved. Do not describe the remaining audit P3 set as fixed.
- **Separate hardware gate:** device handover/diagnostic work and the full-image
  recovery uncertainty are not required to compose or verify desktop/browser
  demos. PR #124’s bounded offline preparation is merged, but no Lunar
  application has run on the FM-1; no installability, full-image restore or
  firmware-runtime claim follows from the offline evidence.

For composition readiness, the outstanding product-facing gates remain the
exact integrated engine/Wasm artifacts and admission checks, complete project
roundtrips and entire-chain renders, browser load/play/listening for each song,
and the owner’s pending Safari Sound 2 listening retest. This disposition does
not claim those gates complete and does not supersede CI or owner listening.
