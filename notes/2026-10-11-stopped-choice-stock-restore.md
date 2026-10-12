# Distinct stock restore after actual stopped-choice RAM evidence

2026-10-11, feature/2026-10-11@installable-firmware. Root owns hardware,
commits and verified pushes. No hardware was opened or command sent by this lane.
The four admission candidate paths are frozen for root checkpoint; this note
and the new restore source/test are a separate closed dependency.

Insight before implementation: exact stock bytes do not identify the current
loader. The new returned-ROM backup must bind the actual consumed RAM-read
lineage and a fresh same-ROM witness before the restore can acquire authority.

## Source and authority

The new module `tools/fm1_stopped_choice_stock_restore.py` pins private unchanged
`tools/fm1_returned_rom_stock_restore.py` at
f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33.
It reuses only that module's Policy, Prepared, transport and strict receipt replay
kernels. A new outer exact-instance WeakSet protects factory/worker/transport
entry points, binding and wire validation. The factory registers its own newly
constructed legacy policy/prepared objects in the private pinned kernel; it never
calls an old opener or changes the original module/file/marker. Python remains a
private-host tool, not a hostile-code sandbox.

The distinct schema 1 kind is `fm1-stopped-choice-stock-restore-only`. Fields
retain adapter source SHA, new backup campaign/manifest/commands SHA and exit0,
original rehearsal campaign SHA and install journal SHA, receipt path and exact
state `stopped-choice-fixed-loader-dual-target-backup-no-later-commands`.
The new worker owns `.stopped-choice-stock-restore.consumed`, preserves
journal-before-restore and writes its own private command/result receipt.
Inherited prepared/completed event names remain bound to the distinct campaign,
adapter source and consumed marker; they alone grant no authority.

`BACKUP_SOURCE_SHA=None` currently closes both live factory and completed-restore
helper before any evidence open. The diagnostic lane owns
`tools/fm1_stopped_choice_backup.py`; it must supply an independently reviewed
completed helper with genuine original policy inputs, original rehearsal/install
journal identities, new USB/SG/loader binding, complete dual df6 target dumps and
all exact negative evidence paths. Historical completion uses the preserved
install journal only; no old absent-marker opener may be called.

## Preserved physical bounds

[verified: unchanged pinned kernels] The first full 4096-page read must match
complete target df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db
before any FB01/FB04. Only the derived 30 sectors can change: 0x5000 through
0x21000 then directory 0x4000 last. Durable intents bind exact erase/program
addresses and stock page bytes. Final complete NOR must equal
96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4.
SPL, OTA/cfg and protected ranges remain exact. Status/echo/residue ambiguity
closes the handle and retains consumption without retry. No upload/reset/eFuse
or application boot/display/recovery claim is included.

The completed-restore helper independently validates new campaign/schema/source,
new marker, completed new backup lineage, preserved install journal and current
complete restore journal, full ordered transcript and exact final result. It
returns new binding/backup receipt/baseline/target/order plus absolute absent
paths for a later separately reviewed reset. Caller exit0 and no later commands
are explicit trusted operator premises, not facts inferred from a filename.

## Verification and pending dependencies

Source and test py_compile passed. Focused injected tests cover closure before
any file open, copied new authority and legacy authority rejection, all-target
read before mutation, binding/wire authority checks, negative evidence appearance
before the first command and exact direct regular dependency reads. A 16-chunk
Hera gate is being staged; no local heavy tests run.

Remaining: accepted new backup literal/API, genuine actual-private full factory
and modeled restore/helper integration, adversarial completed-lineage tests,
final exact source archive and independent source/runtime review. Keep the
production backup pin None until those gates justify a specific candidate.
Semantic servers still select primary checkout, not this worktree; their
readiness does not provide worktree Python semantic coverage. Bounded actual
source/caller inspection is the fallback and selection was preserved.

Insight after implementation: the historical admission and the current loader
connection are different evidence. Reusing a reviewed protocol kernel is useful
only when a distinct factory owns both the new lineage and its one-use receipt.

## Historical closed kernel gate

[verified: Hera injected tests] Source
59dc105171c379703cdd2c7afc0c0e30424aed35167a5cdc542598465728c979 and tests
208fbd274e6e68c9b68df8463967c15d9ccfb8a6ddf319e4230cb216f6f4f2a3 passed
16 unique cases in 16 chunks plus one closure smoke, no failures/errors/skips,
2.82 seconds. `build/stopped-choice-recovery-evidence-hera/evidence-v4` retains
XML/log/run receipts and 18 exact-image container inspections/removals. All 1688
archive pins checked; containers used 2 CPU/2 GiB, network none, no devices,
nonprivileged, all exit0/noOOM; a fresh structured label lookup found no retained
container. Archive a333ffd2f626b4a30318217e7d63891c39117c12ecbc5dbd909bfa2b1f75bcc6;
aggregate edee4bfe8545627cbfbeec9e2079b2d76c2f1431d31662e1ee6440888da577e9;
cleanup 09ccf6d43f40dc2a337f275be9dd667e2e86973961063abf2f50c33c983064f3.
The backup pin remains None. This gate tests closed mechanics and inherited
SG protection with injected authority; it is not genuine successor factory or
physical restoration acceptance.
