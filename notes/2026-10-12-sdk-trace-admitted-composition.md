# Canonical trace return through target backup and stock restore

This is the next separate modeled factory gate after closed mechanics V3.
Parent owns source activation, commits, pushes and hardware. Existing frozen
sources and the original read/boot/install snapshots remain unchanged.

Before implementation: returned proof provenance and current connection freshness
have different lifetimes. A restored current journal also cannot be used as a
completed-install journal. The genuine composition must retain the original
snapshot and pre-restore journal while independently replaying current restore.

The two new test files `tests/sdk_trace_admitted_fixture.py` and
`tests/test_sdk_trace_admitted_composed.py` reuse the frozen canonical owned-return
fixture. They call the actual install, boot, reader, native transport, owned
receipt admission, new backup and new restore factories. Only device syscalls,
clocks and capture process lifecycle are modeled; source pins, registries and
Prepared authority are never replaced. Dependency preflight rejects None pins
before the expensive install. AST parsing was checked here; no local tests or
device operations were run [verified].

Two independently parallelizable branches are proposed: complete restore and
an actual durable mutation-intent callback that creates a previously absent
provenance ambiguity. The latter calls real sync_dir first, then inspects the
worker's final durable_intent record. It must produce no erase/program ioctl,
retain consumption and journal-before-restore, close the second handle and refuse
another attempt. The completed branch checks both target dumps, all 4,096 initial
pages before mutation, thirty directory-last sector erases, 480 programs, final
stock bytes, strict completed-helper replay, copied proof rejection, marker/result/
lineage/preserved-journal drift and late negative-evidence appearance.

Admission, current witness and historical completed-helper paths remain separate.
The original ROM snapshot bytes/hash/time are never updated. Completed restore
reconstructs installation from the preserved journal and requires current
complete/restore state independently. Artifacts are copied privately with source
and byte hashes; summaries explicitly keep physical boot, reset cause, hardware
recovery and actual capture-supervisor execution false.

Required before a runtime archive: parent independently accepts canonical
admission candidate `5ca132fc2f2595400bc9ccb231c3e5cd44ecc9886cd830e201272b33a677b34a`
and its 75-case gate; then separately reviews literal-only backup PROOF_SOURCE_SHA
and restore BACKUP_SOURCE_SHA/POLICY_SOURCE_SHA successors. Exact trace policy
`54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835` was accepted for
offline installer/model scope. Current production pins stay None until that
review. No test monkeypatch may activate those pins. The two source-contract
assertions of literal None belong to the retained closed V3 gate; a successor
runtime selection must explicitly distinguish them from remaining unit mechanics.

After implementation: source-backed tests are saved but not executed. They are
not evidence of loader access after a corrupt application's reset. CPU/SPL and
USB_KEY physical availability remain unresolved. Runtime is Hera-only, thirty
chunks, exact image 7e32, 2 CPU/2 GiB with combined 4 GiB memory/swap, source RO,
network/device none. Parent must approve the exact successor archive before run.


The preparation text above is historical. Parent accepted the canonical 75-case
admission runtime and the exact three literal-only candidate assignments before
this modeled run. Tracked backup6f50 and restore41ef production files still have
None activation pins; the candidate source archive uses backup7e9dbf and
restore683275 without monkeypatching factories, source guards or registries.

V1 retained 54 passing mechanics cases and one separate cheap witness smoke,
then failed both expensive cases on the test-owned native fd-only flock callback
reaching the ordinary journal lock. Both completed matching dual target backups;
each stopped with zero restore SG intents and no mutation. The exact failed
XML, source and full owned stages remain under ignored
`build/sdk-trace-admitted-composed-hera/failed-retained-v1/`; its private archive
SHA is `4c95a41d4de8e5f15493d1f9ed2b32016b55bf49020b5eb9d925ae1702dc93c7`.
All 32 V1 containers were inspected and removed without OOM. Root reviewed the
four-line own-fixture correction, then committed/pushed it with remote SHA
verified at `f1ec7467ea72f87c25c53ca12a9f1607de738cae` [verified]. The fixture
captures ordinary flock before native reading and restores it after the native
worker closes and proof validation completes, before the NOR model captures it.
No production or shared canonical fixture changed.

The two affected heavy cases passed in two separate Hera containers on V2;
there were zero failures, errors or skips. Their durations were 518.214 s and
358.809 s; supervisor duration was 519.608 s, exit 0. Image 7e32, source and all
inputs RO, 2 CPU, 2 GiB RAM, explicit 4 GiB combined memory/swap, no network,
no devices and no privilege were verified. Both exited without OOM and were
removed. Original 1,823 mounted regular input hashes remained unchanged; FIFO
and symlink evidence is metadata only and never read or followed [verified].

V2 archive `0470db72550990d21cccff5d9449e2e53e68528da8eb3eeb80f446570d1229f6`
and snapshot `130b4c8cf39357c162954f17632975355e7b56b5acdb6a50b04f0df3b801cf86`
contain the exact immutable V1 source with only fixture497 to fixture1106:
1,761 other regular source files are identical. This is explicitly a mixed
56-node gate: 54 V1 mechanics plus 2 V2 heavy cases, each once, and separate V1
smoke; it is not an all-V2 run. The later checkpoint's HANDOFF-only delta is
outside the source basis. Runner b7dd and guard e715 were reviewed before launch;
actual executor PATH, guard and real Docker hashes are retained. An evidence-only
supervisor inventory typo stopped before any container and was corrected to the
unchanged runner's actual native mount. A pure metadata verifier subsequently
used the wrong historical cleanup filename, then replayed the retained failed-V1
cleanup correctly; both failed helper sources and records are saved. Neither
repair reran tests or changed source/runner/guard authority.

Author pure replay verified 8,757 paired backup commands and two matching full
1 MiB target dumps in each case. The completed case has 10,653 restore commands,
4,096 initial target page hashes, 30 directory-last erases, 480 exact CRC/payload
programs, 4,096 final stock page hashes and the genuine completed restore helper.
The negative case has 4,113 restore commands, complete initial target readback,
a durable mutation intent followed by provenance absence drift, zero erase or
program CDBs, no result, retained consumption and closed handles. Original ROM
snapshot and install journal bytes are preserved; strict historical replay,
copied authority, marker/result/lineage/journal drift and late absence assertions
passed [verified, modeled]. Device/clock/owned capture are modeled; actual
capture supervisor, physical boot/display/recovery and CPU/SPL cause stay false.

Private retained V2 evidence is at
`build/sdk-trace-admitted-composed-hera/retained-v2/`: 95 regular hash/size checked
artifacts and 2 nonregular metadata records. Aggregate SHA
`6d388095785975150ce9fd1eccfb3e57323cde4871e2174c2272735c5bed7563`;
plan `da15cbddb779ba1329c4e0e8786805e077187590296bb722b20bfd6027b8e0ac`;
author replay `06ac6f66518423fe0d51e315f8d10855660c7bbe3101a306008467b255d6feed`;
explicit mixed-node map
`ea95e9356a6903d247593e164166f7dcb90af677fcc7f102dbdfcbb33ef98204`;
index `777cf44254cac184c042284c9b7110f01ae8eb0a5348992514d60bd237480cb2`;
private export `fad367b683f34a9060ddff3a6104fa08aaebb07c113dfe25db9151d5a6cd2e00`.
A separate fresh structured exact-label lookup has exit 0 and container_ids []:
`final-cleanup-v2.json` SHA
`3e1a739336eca19a767b36a7006b8cd98b010798c81be3fad05add0cc0fd3713`.
Independent wire review and root runtime acceptance remain pending. Root alone
owns literal activation, updating both None AST contracts to reviewed literals,
checkpoint/push and CI. Physical campaigns remain separate and partial-NOR
recovery availability after actual CPU/SPL reset is not established.


Root fully read and accepted independent review8244bc97/check8e459ba8; all15
retained-evidence checks pass. Acceptance is saved at
`build/sdk-trace-admitted-composed-hera/retained-v2/root-runtime-acceptance-v2.json`
SHA60961da26dc2e7a38e41d521153f7cef3222de63137df2f62a73ac32236d13db.
Production now matches the reviewed literal-only backup7e9dbf15 and restore683275d7
candidates exactly [verified]. The two source-contract tests now check exact
reviewed literals and the actual dependency hashes; their Hera successor check
is pending. This supersedes the preceding pending-review/None-pin statements.
Input posthashes were independently verified as receipt chains/counts only; the
original remote roots were not rehashed by the independent reviewer.

The separate actual frozen preparation-helper composition is running once on
Hera using archive7926d20f, runnerbc137b9c and helper43c0d72f/test0d8581c7.
Root fully read the test/helper/runner/guard/supervisor and verified all1764
archive entries:1762 unchanged V2 files plus those two additions. Root launch
receipt4f2c1391 records that scope. This is one additional modeled case, with
no repetition of prior passing cases and no physical access. Runtime acceptance
is pending. The interrupted-NOR adapter remains closed pending its separate
30-chunk mechanics and genuine factory runs.

## Frozen preparation-helper composition accepted

[verified, modeled] The separate V3 helper case passed once on Hera in 494.87 s.
It used the actual frozen preparation helper followed by canonical backup and
restore: 8,757 backup exchanges, matching full 1 MiB target dumps, 10,653 restore
exchanges, 30 directory-last erases, 480 programs and complete stock readback.
The original install journal and ROM snapshot remained exact; the live journal
correctly became complete RESTORE. Earlier V1/V2 failures remain retained.

Root rehashed all 116 indexed artifacts and 117 regular archive members and
checked the sole JUnit result, pinned isolated container, unchanged 1,823 mounted
regular inputs and empty cleanup. A separate stdlib retained-evidence checker
passed 152 checks, including full command reconstruction, payload CRCs, page
hashes and journal boundaries. Receipts are under
`build/sdk-trace-admitted-helper-composed-hera/v3-envelope/`: evidence archive
`2f92b148`, root integrity `b1922cf7`, independent receipt `1cb98855`.
The independent checker is a separate implementation by the same delegated
agent; root owns acceptance. SG, USB and capture lifecycle were modeled. No
physical boot, display, reset cause or corrupt-application recovery is proved.
