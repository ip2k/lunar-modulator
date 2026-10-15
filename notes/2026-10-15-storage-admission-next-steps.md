# Project-storage admission: remaining blockers and next proof — 2026-10-15

## Result

[verified: source-bound arithmetic] The candidate two-slot layout can hold the
conservative source-derived native collector bound (not a claim that all
independent maxima coexist in one runtime state). Reserving each physical sector's final 256-byte
page leaves 3,840 packed bytes per sector. Twelve sectors yield 46,080 bytes;
the existing journal exposes eleven logical 4 KiB blocks (45,056 bytes), of
which 32 bytes are its header, leaving 45,024 payload bytes. Against the
corrected 43,130-byte collector bound, the margin is 1,894 bytes. The bound's
source paths are unchanged from its stated base `31d2e8c` to this review's
`1322740` for the collector, compact writer, and SAVE bridge. This answers the
capacity question for native SAVE output only; it does not lift the generic
98,304-byte import ceiling or mean every imported file fits.

[verified: code boundary] This layout is still a host-tested adapter, not a
physical profile. `tail_page_io.h` accepts a caller-supplied list of sector
addresses and proves alignment, uniqueness, bounds, and capacity; it does not
prove those sectors belong to Lunar. `project_storage_profile.h` accepts a
caller-supplied `layout_verified` bit and is deliberately not bound to the
SAVE service. The actual SAVE entry still requires `storage_admitted == 1`,
while the application build reports admission false. See
`firmware/native/tail_page_io.h:28-43`,
`firmware/native/project_storage_profile.h:1-5,63-103`,
`firmware/native/project_save.h:44-58`, and
`firmware/native/project_save_service.h:8-18`.

## Why capacity is not admission

[verified: checked-in profile and offline scan analysis] The arithmetic
candidate uses 24 physical sectors drawn from the recorded VM/USR envelope,
excluding the five-sector OTA staging range `[0xE0000,0xE5000)`. That leaves
29 sectors on paper, only five beyond the two slots. The archived FM-1_092
VM/USR content is opaque; erased bytes were not shown to be unallocated. The
current expanded app profile also preserves the opaque suffix beginning at
`0xD9000`, so it has not already reassigned these banks.

[verified: retained SPL disassembly and cleanup-source review] Each candidate
sector contains a record window at `sector+0xF00`. SPL conditionally scans
80 bytes there; the retained Felucca cleanup source scans a subset and can
erase the containing sector when its broader record predicate matches. The
host adapter therefore reserves the complete final 256-byte page. It keeps
the post-format invariant testable, but does not make the first erase of
arbitrary stock bytes safe. See `notes/2026-10-14-spl-record-scan-proof.md`
and `notes/2026-10-14-spl-record-window-mapper.md`.

[verified: historical archive only] The archived device40 inventory found
eight non-FF tail pages in the proposed map. That is useful evidence against
assuming the pages are blank, but it is neither a fresh current-target pair
nor an ownership map. The five spare sectors cannot relocate all eight pages
while preserving both full-capacity slots. Formatting them ROM-held is a
proposed operator-mediated transition: it may recover from interruption only
by re-entering ROM and consulting the off-device snapshot; it is not an
autonomous boot-safe guarantee. The planner currently refuses non-FF pages.
See `notes/2026-10-14-tail-migration-archived40-inventory.md` and
`notes/2026-10-14-tail-migration-interrupted-first-format-recovery.md:19-23,37-56`.

[unresolved] The missing fact is sector ownership and migration semantics, not
payload capacity. No version-matched stock VM/USR allocator or decoder is
established in the repository notes. A raw archive supports byte restoration,
but does not establish that old settings remain usable after Lunar takes those
sectors. The proposed first-format protocol also depends on current-target
fresh paired reads, an exact sector ledger, a same-target ROM recovery witness,
range-specific interrupted-write recovery, and verified full rollback. Those
are separate from the already-formatted host fault tests.

## Read-only ledger increment

[verified: source inspection] There was no hash-bound per-sector ownership
ledger in the existing tools. `storage_backup.py` archives an exact whole
image and named opaque banks; `storage_window.py` proves byte preservation in
a caller-chosen window; `tail_migration_plan.py` inventories the reserved
record pages only; and `first_format_recovery_model.py` records the proposed
sector hashes and recovery events. None classifies every candidate sector
against both recorded bank geometry and protected ranges, or accounts for
opaque non-FF bytes at sector granularity.

[verified: new read-only analyzer] `tools/native/storage_ownership_ledger.py`
now accepts two matching complete 1 MiB image files, an explicit full-image
SHA-256, a recorded-profile JSON file and its external file SHA-256. It checks
the profile's internal digest and exact VM/BTIF/USR extents, and reports all
24 proposed sectors with raw sector hashes, non-FF byte counts, declared bank
and protected-range overlaps, OTA-stage overlap, and tail-page record
predicates. It consumes a separately hash-pinned profile baseline as well as
the matching current full-image pair, and reports candidate-sector equality,
hashes, and differing-byte counts against that historical baseline. It emits
no write plan. For every row it sets logical ownership to unresolved and
erase-safe false, including fully erased sectors. These are classifications
against the supplied recorded profile; they do not certify a fresh device
read or prove that a bank's bytes are semantically disposable.

[verified: focused tests] `tests/test_storage_ownership_ledger.py` covers
blank-but-unowned sectors, opaque byte accounting, bank overlap, and refusal
for mismatched images, malformed or changed profile evidence, and incorrect
hash pins. The profile-preservation endpoint is derived from the recorded
profile source expression `APP_BASE + 692032` in
`tools/jieli/raw_flash_profile.py`; the test fixture pins the resulting
decimal value independently. The three focused suites were run with the
repository interpreter:
`/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -m pytest -q
tests/test_storage_ownership_ledger.py tests/test_native_tail_migration_plan.py
tests/test_native_first_format_recovery_model.py` (46 passed). No hardware or
SAVE admission path was touched.

[verified: retained-file smoke run] The analyzer was run against the retained
recorded profile (`recorded-profile.json`, SHA-256
`51d89970d09e58c261a967abf7e57d62445afc7d4c570e927042ce0f9a032650`), its
profile-baseline image (`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`),
and the supplied paired image files (`c240999ca08479defa07b10b0ed8d4a07891155c37ea84572629212efcaddbe8`).
It emitted 24 rows: 33,123 non-FF bytes in both current candidate sectors and
profile-baseline candidate sectors, zero differing bytes in the candidate
map, no OTA-stage overlap, and 24 overlaps with the profile's raw-byte
preservation range. The report SHA-256 is
`d8b35677c0aac79cc33d00159745d3eb42d15a068b5116661a71d27db0e4bdff`.
The analyzer checks bytes and hashes, not how either current-pair file was
acquired; this retained-file run is not fresh-read provenance. Matching the
recorded bytes does not establish logical ownership or permission to erase.

The ledger is a useful inventory input, not the missing ownership proof. The
next concrete step remains decoding or losslessly exporting every displaced
VM/USR byte with version-matched stock semantics, then mapping each candidate
sector's contents to that result and reviewing OTA, SPL, cleanup, and rollback
interactions. The ledger deliberately cannot decide erase permission from
all-FF status alone.

Only if that ledger establishes an exact, authorized sector set should the
coordinator assess the already-authorized ROM-held first-format and rollback
procedure against that list. Then a profile-specific SAVE binding can be
considered, retaining the existing 43,130-byte native bound and 45,024-byte
payload ceiling. The unbound fault harness is not evidence for NOR timing,
XIP-off RAM closure, interrupt/watchdog safety, physical power-cut behavior,
or successful settings migration; those checks remain downstream gates.

## Scope and validation

[verified] The analyzer and tests are in the coordinator-owned working tree; no commit or push was made by this worker. No production SAVE source, device, flash, or admission state changed. The report is offline analysis only; source/profile ownership and semantic migration remain unproven.
