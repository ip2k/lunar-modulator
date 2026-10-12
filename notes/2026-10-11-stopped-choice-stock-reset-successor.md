# Literal successor reset after accepted stopped-choice stock restoration

2026-10-11, feature/2026-10-11@installable-firmware. Root owns physical traffic,
commits and verified pushes; this lane opens no hardware.

Insight before implementation: complete stock restoration identifies NOR bytes,
while the original consumed RAM receipt and fresh loader backup identify the
session authorized to send the one reset. A reset reply cannot establish boot.

The exact source successor changes only RESTORE_SOURCE_SHA from None in historical
c0a75545faa6d14a2ff03d706ad9257c60bbcfec9061e6590bc2b3e73edb9995 to accepted
26f9117c4e6ccd9b2ed765596db2c065abe00c6ef98b98e88b96f1353b7bfc4c.
New source is 9f6bdf10e56134b32a061c9d86417bd261ed453ef13139a2f55a62656b4b58d3.
Restore source/runtime was independently accepted in report
build/stopped-choice-stock-restore-independent-review.md SHA
61b1a10d927b57389719b90e68680866cd96ddbe95f1427b534ce873b840216c.
Old baseline, rehearsal, returned-stock reset and old provenance sources remain
unchanged. The distinct schema/state/marker and exact-instance factories remain
those reviewed in the historical c0a gate. FC0C arg1 is the sole native operation,
IN16; no upload/read/erase/program/eFuse/retry or automatic identity command.

Unit source 1a871c1e4a7d9ff5a2b7cb6a1aac70f7543486800436ab89069be1015c7be1b9
retains all 62 existing cases and explicit None closure regressions. Only its
header description changes to explain the final literal and injected verifier.
Separate actual test a2b2f480a6044f5a28e13e36a5f2162e74f351e4952a890dbdabc86d81ea5ad7
uses frozen successor_factory/actual physical RAM receipt, exact original private
SDK/stock/target/source checks and full modeled backup+restore. It captures the
first actual completed helper result without replaying its seven corruptions,
then calls the unchanged real reset factory with no activation pin override.
Only SG/NOR/reply are modeled; sole literal request, three closed handles,
retained consumption, no second request and false boot claims are asserted.

Source/test py_compile passed. [verified: Hera] All 62 unique focused cases passed in 16 chunks, plus one
separate genuine composed smoke, with no failures/errors/skips, in 247.734774
seconds (composed smoke 246.08 seconds). The 62 injected cases and one composed
case are distinct; the expensive actual case ran only once. No physical reset, boot/display or recovery conclusion follows. Final independent
source/runtime acceptance passed within the offline scope below.
Semantic servers retain primary checkout selection; worktree Python semantic
coverage is unavailable, so bounded source and known caller inspection is used.

Insight after implementation: pinning the completed verifier adds session lineage
to the reset factory without expanding the native command inventory. Its success
remains request completion; normal enumeration and stock identity need separate
physical observation owned by root. Partial/corrupt-app warm recovery and USB_KEY
are still unproven and no physical fault injection is performed.

## Final exact runtime artifacts

Local successor evidence is distinct at
`build/stopped-choice-stock-reset-successor-hera/`; remote is
`/home/claude/mvave-fm1/stopped-choice-stock-reset-20261011`. All 1694 archive
entries were checked, exact XML coverage was checked in order with no duplicates,
and all 18 containers (collection, smoke, 16 chunks) exited0 without OOM using
image sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d,
2 CPU/2 GiB, source/jobs read-only, network none, devices none, nonprivileged.
Named removal receipts and a fresh structured label lookup with exit0, empty
container_ids and empty stderr are retained.

Archive 5b1b58d4ad96a712f32c40698a760bf0fafb4aa459470fdc1ea4bad6883c53e9;
snapshot 40688e3767df85c3cf1dfdd4acb908e72d456c037080fa3575ace03a8aa4ea69;
aggregate 4e21dd71b5b958384d2e8624d6b3cf8281e357437630954ef2d84ba3d884110d;
coverage check 795f0cb939d05ef9ab5eaf95d6017b1bdd16631ecd90cb0456320cd199a66ebb;
fresh cleanup 781cab2774ab748a001d7dd4ba0eee49e78aff85cd124dce7d1d228f356aad1a.
The actual summary `evidence-v1/smoke/actual-stock-reset-summary.json` SHA
279f016994a96b9d1bfc4e60a7fc7e05b182f228640a59ac1b4c1a0f898bc9b5 records
8757 backup commands and 19410 modeled commands before one reset, three open/closed
handles, 32 retained absent paths and unchanged production pins. Original journal
0d797 is preserved. Stock bytes are unchanged by the reset model; all physical
reset/boot/display/recovery fields remain false.

The initial local output directory collided with the historical closed c0a gate;
reviewer caught the collision. Final successor files were moved to the distinct
path above, and original historical files were recovered exactly from untouched
remote `/home/claude/mvave-fm1/stopped-choice-stock-reset-20261012-v1`. Original
local archive9e65/snapshotb1ea/planb894/aggregatec73 pins were verified after
restoration; a full `historical-closed-v1` mirror is also retained. Neither gate
shares authority or immutable output names now. Provenance index
`build/stopped-choice-stock-reset-successor-hera/provenance-index.json` SHA
e5cb7f50fd6b15986ac4611793fb6a07ccf95c46e04a1004303c27474b836acf records
both explicit source scopes. This focused gate is not a fresh whole-suite/CI gate.

Root owns checkpoint/push and concrete physical packet review; source/units/actual
test remain frozen after final independent evidence acceptance. The next
dependency is root-owned exact current-session reset campaign after actual backup
and restoration, followed by separate normal enumeration/stock identity evidence.

## Independent final acceptance

[verified: independent source/evidence replay] Startup resolution accepted the exact
9f6b source / 1a87 units / a2b actual composition gate. Report
`build/stopped-choice-stock-reset-successor-hera/independent-review.md` SHA
1a1327f8e27fb13e7bb99aebf706572a090e8a0dc5eca8e86120e2922e761b48; own checker
e0573f682ba5b3bb9b31d8cdce1e666583265967732a172fa1853c6d815d5bd3.
It independently verified all 1694 pins, 62 unique cases in 16 chunks, one genuine
composed smoke, all 18 isolation/removal receipts and the fresh empty lookup.
The genuine composition contains 19410 modeled commands before one FC0C request,
three handles closed, unchanged production pins and false boot claims. Actual
completed stock restoration and an exact concrete reset packet remain separate
physical dependencies; this acceptance authorizes no agent device operation.
