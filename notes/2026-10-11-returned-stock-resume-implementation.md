# Interrupted returned-stock restore: closed evidence kernel

2026-10-11. Personal, non-commercial. Separate WIP behind closed execution; no
hardware request, device opener, retry or reset authority. Root owns commits and
pushes. Accepted afeefe/f583 returned backup/restore and all inherited guards and
markers remain unchanged. The architecture is in
`notes/2026-10-11-returned-stock-resume-design.md`.

[verified: source] New `tools/fm1_returned_stock_resume.py` strictly replays the
caught-stop prefix of the existing f583 single restore. It uses literal-pinned
b846 native-framing transcript code, seals stock96006 and targetdf6, checks all
initial-page hashes, stock-derived program CRC/payloads, command indexes/order,
completion/status/residue/sense shape, directory last and exact stop claims.
It reconstructs expected NOR and retains the union of attempted write spans
until actual matching FD05 readback verifies each256-byte page:4KiB for erase
and256B per program. Native completion and operation_returned do not prove NOR
accepted the write. Multiple program pages can remain uncertain in the current
sector until sector readback; preceding sectors have complete matching readback.
This is conservative attempted-request scope, not observed transmission. Query/
read failure adds no write uncertainty. Current dual full matching dumps must preserve stock-protected
bytes and match every reconstructed byte outside the remaining uncertain spans.
The exact replay-created instance is required; dataclass copying grants nothing.

[verified] Execution is unconditionally closed: prepare_campaign rejects before
any file/device access. No evidence-only prefix may be used as loader provenance
or opener authority. Historical SDK provenance, consumed prior marker, journal,
owned stop/capture, result absence, inherited negative evidence and live loader
acquisition remain required next gates. All old files/markers must stay frozen.
Two loaders paths remain distinct: retained active fixed loader needs fresh new
FD/exact USB/SG plus reviewed quiescence/no-later-command premise; new ROM needs
new witness and separately reviewed fixed upload/partial-state backup. A partial
NOR must not be labeled a complete target backup. Source publication and passing
model tests do not prove actual loader/reset/boot/display/recovery.

Initial frozen WIP pins: source
4a877f61b377a55fb53bb17054f464ddb48e2c5559207b9284cf8a7a5fb4a11b;
tests415fe3e23e0534373870d68bf4d8352809fccb544fad8bf91487e37cfb5b9d3f.
Both py_compile checks passed. The historical V1 focused16 Hera gate ran against source
archive57a08e0a1cae012eb1f81bd2ee0f76e065a09d8baee4ae2820144f4d925141ae
(1676 actual tracked/new files) in
`/home/claude/mvave-fm1/returned-stock-resume-20261011`; local evidence destination
`build/returned-stock-resume-hera`. The established pinned recovery pytest image,
2CPU/2GiB/network-none/nonprivileged/no-devices isolation and named cleanup are
retained. This gate needs no private fixture or physical adapter.

Next dependency: finish focused XML/isolation/cleanup receipt, then independently
review this kernel and implement actual-file stopped-lineage/current journal
admission and a distinct partial-NOR backup provenance envelope while execution
remains closed. A genuine interruption model should reuse one complete inherited
fixture instead of repeating six expensive completed chains. Root will choose the
physical acquisition envelope separately. No hardware action is authorised here.


## Independent semantic repair

[verified: native/source review] Startup-resolution identified that native
FB01/FB04 ignore flash-driver result/busy state: adapter operation_returned is
not proof of physical NOR success. The initial evidence-kernel V1 incorrectly
cleared uncertainty there. V1 passed48 unit cases, but is superseded and not
accepted for recovery admission. V1 archive/setup failure and all48 XML/isolation/
cleanup receipts remain retained under build/returned-stock-resume-hera.

The repaired kernel retains a union of every attempted unverified write span,
clearing each page only after actual successful matching FD05 response hash.
Unverified earlier program pages remain recoverable after later program returns;
verified pages cannot vary in the new dual dump. Added tests cover returned erase,
partial/full blank readback, two/all returned programs and partial/full sector
readback. Execution remains unconditionally closed. No old returned source or
marker changed. The initial architecture's single-final-mutation assumption is
superseded by this source-backed readback rule. The V2 focused16 gate completed as recorded below; independent final runtime review is pending.


## V2 exact focused runtime receipt

[verified: offline model] All 55 exact unique planned nodes passed in 16 Hera
chunks (seven chunks of 4 and nine of 3), with zero failures, errors or skips.
Runtime was 3.29 seconds. Collection plus 16 test containers used the pinned
image sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d,
2 CPUs, 2 GiB memory and swap, no network, no devices and nonprivileged mode.
All 17 exited zero, had no OOM and were removed. Structured label lookup has
exit zero, empty container_ids and empty stderr. No private fixture or hardware
was used. Cheap prefix fixtures check actual pinned framing/replay functions;
they do not constitute a genuine stopped-restore admission factory.

Source cef2d0ea48c2ceb9c4441a7b9042aae05643f3db01f217787339cace31575277;
tests 9cc26b9b89d63fa3f6a3c1af2380b07324a6a25c36b2969bb4079580e549db6b.
Both py_compile checks passed. All 1676 archived files were hash checked, and
current source/test plus frozen afeefe/f583 pins matched the sealed archive.

Local receipts: build/returned-stock-resume-hera/attempt-v2.
Hera receipts: /home/claude/mvave-fm1/returned-stock-resume-20261011/attempt-v2.
Archive 38c40cf5a39a7bab508a7bdacecbd216b83889effc51376db0d0e11f79bbf08d;
snapshot a47a55ab528b535a82e417b4a51909c6ccb59f5742daec3a1cd73c0011abbe05;
aggregate 966569c43c6c271a297c2c412fb00a800fc4a99446d48105a4c6917d3c312866;
plan 40cbbc6c9dd965a3046d82b375f1e191f665e4fdcb4eef8d86f72a23bc8e950b;
coverage-check 068e52d1a2499947a943e4250bee11b9828411a4c5d0fed94563d2ace26e3ad7;
structured removal lookup af0fefe02a204af739ead493a0016514b2c5c70d703f4aba1427bb633462da0c.

Startup-resolution independently accepted the exact closed evidence-only kernel
and all 55 V2 cases: report e0401d94ce98f7d34a2b8dfd20eb8b793946cbb34966bf674ea6770c036346b8,
own checker f8cb5b5aa6fa43b5bbf55b1fc33a9ad648d8a73aa1ea0dceafe82e1440ffaeb5.
This checked all 1676 archive pins, exact XML coverage, isolation, removal and
the fresh empty container lookup. Genuine stopped-lineage/current journal,
owned capture and retained-loader/new-ROM acquisition remain required. V1 remains retained
as superseded evidence, including its initial harness directory setup failure.

Branch feature/2026-10-11@installable-firmware. Last parent-confirmed pushed and
remote-verified checkpoint is 20284ce7ed0543038c5861e935f345e7b4257a2c. These
three new kernel/test/note paths await root checkpoint. Old accepted sources and
all consumed markers remain unchanged. No hardware, reset, boot, display or
physical recovery claim follows. Next work is exact stopped-lineage/current
journal admission plus a distinct partial-NOR acquisition envelope; production
execution remains closed until those gates are separately implemented/reviewed.
