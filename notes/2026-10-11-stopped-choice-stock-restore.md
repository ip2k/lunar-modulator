# Distinct stock restore after actual stopped-choice RAM evidence

2026-10-11, feature/2026-10-11@installable-firmware. Root owns hardware,
commits and verified pushes. No hardware was opened or command sent by this lane.
The admission source 8875 and actual RAM receipt are independently accepted.
This note and the new restore source/tests record the distinct successor gate.

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

`BACKUP_SOURCE_SHA` now pins independently accepted
`tools/fm1_stopped_choice_backup.py` at
c1b0f5539f2f47eb70300ba8ba19e35ec9e3b822dc00a792070cd34a31406798.
The backup source/runtime review is `build/stopped-choice-backup-independent-review.md`
SHA d39ddee9c68d3863885bd79dcc1e981a78395e2d45d03e0da031910c441f7b27:
76 unique cases in 16 chunks plus one genuine private factory/mocked8757 smoke.
Its completed helper binds genuine original policy inputs, original rehearsal/install
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
before the first command and exact direct regular dependency reads. The historical closed gate is retained below; no local heavy tests ran.

The final exact candidate runtime passed as recorded below. Independent final
source/runtime review and the root-owned concrete campaign/hardware gate remain
separate acceptance boundaries. Source pinning alone does not authorize physical
execution.
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
The historical backup pin was None. This gate tested closed mechanics and inherited
SG protection with injected authority; it is not genuine successor factory or
physical restoration acceptance.


## Final pinned successor candidate and completed runtime

Source 26f9117c4e6ccd9b2ed765596db2c065abe00c6ef98b98e88b96f1353b7bfc4c
changes only the historical 59dc backup literal None to accepted c1b0 and updates
the closure docstring. Unit tests 10efaea56a345873a5a4b16453e45d39ecf5c0e0d464cf9f6e370b9f916f888e
explicitly inject None for the closure regression. Actual fixture
0b588a468b2865fd6c3588782cdb62f743402c4d8d314cdd08088e9bd86a3577
uses the exact physical two-read receipt and unchanged production source pins;
only SG syscalls/flash are modeled. It clears only the disposable first-party
module cache before private exact-source imports. No original marker is removed.

The full model exercises 8757 successor backup requests and matching dual target
dumps, 4096 initial target pages, 30 stock sectors directory-last, 4096 final stock
pages, actual completed journal and preserved original install journal 0d797.
The completed helper is checked after the live journal becomes complete/restore.
Seven caller-hash-consistent source/marker/schema/log/result/journal corruptions
and late negative evidence are rejected. The separate intent-drift model creates
an exact forbidden artifact only after the real durable intent directory sync;
it demands zero FB01/FB04 ioctls, retained consumption and both handles closed.

V5 collection failed because the explicit actual-admission fixture was omitted
from the archive; no modeled transport ran. Failure/inspection/removal evidence
is preserved. V6 uses closed 59dc with disposable-only new restore pin substitution;
all 19 unique cases in 16 chunks plus one genuine preflight smoke passed with no
failures/errors/skips, including full restore and post-durable-intent absence,
in 276.1964 seconds. All 1691 archive pins and 18 isolated exit0/noOOM container
inspections/removals checked. Historical archive
4048cd41b2ffc3057cfa3f02f9c605639c7c98b16462a26a7819e3a9e28816d6;
aggregate fb54b5c3a6e55e2dad1cf5e9685d52c417964b7809b0f7132c65ba3fda32b0c1;
fresh structured cleanup 1946b680257bafb79fec2488473350a68b9645a071028ed8ed225794d7778660.
This historical substituted-pin gate does not replace the final literal candidate.

[verified: Hera final literal candidate] V7 passed all 19 unique cases in 16
chunks plus one genuine private preflight smoke, with no failures/errors/skips,
in 276.911126852 seconds. The two expensive actual cases occupied separate
chunks 1/2. All 1691 archive pins and exact ordered XML coverage were checked.
The genuine composed model admitted the preserved actual physical RAM receipt,
used unchanged production literal pins and original private factories, executed
8757 backup requests and 19410 total modeled commands, verified complete stock
restoration and the completed helper after the current journal changed to
restore, and froze 1093 files plus 32 negative paths. No activation pin was
rewritten in V7. SG syscalls and NOR were modeled inside device-free containers;
physical NOR restoration, reset, boot, display and physical recovery remain false.

Local evidence directory `build/stopped-choice-recovery-evidence-hera/` retains
`source-v7.tar.gz`, `snapshot-v7.json`, `aggregate-v7.json`, `plan-v7.json`,
`coverage-check-v7.json`, harness/check scripts and `evidence-v7/` XML/log/run
receipts. Remote directory is
`/home/claude/mvave-fm1/stopped-choice-recovery-evidence-20261011`.
Archive SHA 1221be1be640493e13aa275574712ab9db710d79efda628299c4e92272d2f73e;
snapshot cda34fc18d335fe0a2f4fc146032a91b1a7516e61be7f8193b3a3cd24744a8ef;
aggregate d19cb42acb882d3f403f9142efbb85b411cf51903d69f66fe6a5abe0a0add411;
local coverage check 4204a3bd9bc30fbf11da2803062cbeb815c176eef52627876773e047f3ad2ae7.
The actual composed summary `evidence-v7/1/actual-successor-summary.json` is
3a381e1d3616ba191480eb98d7c49b339a08426fdd4a1e07639d30c9c356232e.

All 18 containers (collection, smoke and 16 chunks) used exact image
sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d,
2 CPU/2 GiB, network none, no devices and nonprivileged mode. All exited0 with no
OOM. Inspection and named removal receipts are retained. A fresh structured
label lookup exited0 with empty container_ids and empty stderr; receipt
`evidence-v7/removal-lookup.json` SHA
2633b5bf075a1569995a965a19ecbba8c30281196f9bb11f3bdb7832ebe569ad.
Final independent review was requested with these exact artifacts and is pending.
Root alone commits and pushes; preceding checkpoint
adcfdfbddc6c17e706d2dda03bd8d2b2971f84fa was reported pushed with exact remote
SHA verified. Source/tests remain frozen through the next root checkpoint.

Insight after the final binding: the same complete target and stock hashes do
not authorize an old loader session. The successor factory checks the actual
RAM receipt, a distinct current witness, new backup receipt and its own marker.
Physical corrupted-app SPL fallback, USB_KEY entry and recovery without a power
cycle remain unproven; this lane neither injected a fault nor opened hardware.
