# Returned stock-reset scaffold — 2026-10-11

[verified: source and retained Hera evidence] `tools/fm1_returned_stock_reset.py`
SHA `0ed8c82f1725d8f1231ed26f1ab71898904dd6674bea9b3f89b922b3fa4fbc0f`
is an explicitly closed WIP factory: `RESTORE_SOURCE_SHA` is `None`. It cannot
admit a production campaign until the separate completed-restore evidence helper
freezes and passes its own genuine receipt gate and independent review.

The intended authority is a genuine returned-ROM backup, followed by the exact
30-sector, directory-last stock restoration and complete 1 MiB stock readback.
The helper must validate that history without opening any device. The reset
adapter uses the new returned-loader USB/SG binding and its own origin marker
`.returned-stock-core-reset.consumed`, durably written before discovery/open.
Only `FC0C` argument 1, `fc0c00000001ffffffffffffffffffff`, IN16/OUT0 is available;
no flash, upload, read probe, retry or invented completion is available.

[verified: retained injected tests; no physical acceptance]
`tests/test_returned_stock_reset.py` SHA
`5fc3cce0046f0eeebe5faefbaeb3838e7bf401857713eaeae0111df48cc8588b`
passed 44 unique cases exactly once in 16 Hera containers plus a separate
one-case modeled syscall smoke. Zero failures, errors or skips. The completed-
restore helper was injected; the actual previously reviewed reset/backup/SG
sources were loaded. This establishes only the new authority and syscall
mechanics under modeled outcomes, not genuine restore provenance or a device
reset/boot. Production source remained closed throughout.

Cases cover copied authority, unauthorized open permits, receipt/marker misuse,
changed evidence or restoration plans, live connection replacement, lost or
malformed SG replies and storage failures before marker, marker sync or reset
intent durability. A completed transport still records boot as unobserved;
a failed reply stays consumed and cannot silently repeat the command.

Private evidence is `build/returned-stock-reset-hera/`; source archive
`9040c64ae539c9cdec84335bf67ef16dd24e68248666be2d98320ccdcdec54c5`,
evidence archive
`87926c182b7a6fc0b799547d720615537ae82f28820b7f52e0df10beac4de13e`.
Root replayed the exact 44 XML node identities and all 18 collect/smoke/shard
Docker inspections: four CPUs, 4 GiB, no network, devices or privilege, pinned
image `7e32dd6d…`, exit zero and no OOM. Containers were removed and a fresh
session-label lookup was empty; the structured lookup receipt is retained.
Independent review accepted this injected mechanics boundary in
`build/returned-stock-reset-independent-review.md` (initial report SHA
`5d198ac98c8397cf1a2c044993699d705eefae6c953df6737c1cdebad93708b1`).
Genuine restoration provenance and physical acceptance remain pending.

[verified: tooling limit] Bounded Rarefaction worktree orientation was rejected
as outside its primary workspace; Serena did not find the worktree Python file.
Shared server project selection was preserved. Direct file inspection was used;
neither semantic tool established the device ABI or this source's behavior.

Next: freeze and independently accept the genuine restore helper, bind its
literal source pin, add an actual-private modeled full lineage gate, rerun the
focused 16 chunks, then review a concrete one-shot bench packet. This scaffold
has not opened a USB/SG device or issued any hardware request.
