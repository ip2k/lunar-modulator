# Exact SDK trace Linux transport successor

Parent authorized implementation in parallel with reader review, with all
activation pins closed [verified]. No hardware action was performed. Existing
SG, backup, reset, install, frozen reader and firmware source stays unchanged.
Root owns commits, pushes and device operations. Branch is
`feature/2026-10-11@installable-firmware`; preceding root checkpoint
`abc8135a48ea02e4228b83858481f6c0add7a1a0` was pushed and remote verified
[reported: parent]. New SG source/tests are ready for the next root checkpoint.

New `tools/fm1_sdk_trace_sg.py` is a distinct minimal transport. It reuses only
the reviewed MIT mapping function from `fm1_fixed_loader_backup.py`
(`79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb`)
and SGHeader framing from `fm1_uboot_read.py`
(`28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57`).
Their factories are never called and neither command inventory is changed.
The actual ELF parser source `tools/jieli/audit_link.py` is also frozen to
`673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252`.
It is executed into a private module; the exact-byte private reader receives
only its `Elf` through its own isolated builtins import dictionary. The shared
canonical `jieli.audit_link` cache is never replaced. Parser actual bytes are
positive Prepared evidence checked before opening and at every intent. A
foreign canonical cached parser cannot affect this composition [verified: model].
Credit: kagaimiq's jl-uboot-tool (adb3f188, MIT, Andrey Grigoryev), through the
reviewed existing primitives. No command-line opener is provided.

`prepare_campaign(envelope_path, canonical_boot_lineage)` is device-free and
currently rejects before any evidence read because `READ_POLICY_SHA = None`.
It must remain closed until independent reader, boot and transport acceptance.
An exact envelope has schema 1, kind `fm1-exact-native-sdk-trace-read`, this
adapter's source hash, `inputs` with exact `elf_path`, `app_path`,
`manifest_path`, `snapshot_path`, and a private new `receipt_path`. It privately
executes exact hash-checked source bytes of the reader, mapping and SGHeader,
retaining the reader's own instance registry. Preparation additionally requires
the reader's accepted canonical boot pin. The registered boot-lineage object is
passed separately; JSON assertions do not manufacture execution authority.

`run_campaign(prepared)` delegates to the private reader. A runner-only,
one-use permit allows opening after the reader writes its exclusive consumed
marker, plan, campaign and `read_prepared` journal. Every ioctl follows both a
durable reader `submit_intent` and a durable native intent [verified: models].
The native receipt `native.jsonl` is exclusive, mode 0600, fsynced with its
parent directory. It records opening, ioctl intent, binding failure, actual
syscall exception/errno, and descriptor close failure. The reader journal
records returned completion status/sense/residual/length/hash before rejection.
SG failure evidence is preserved without producing a coherent result or issuing
another command [verified: models].

One direct character descriptor is opened with O_RDWR/O_NOFOLLOW/O_CLOEXEC/
O_NONBLOCK and held with nonblocking exclusive flock. Full USB/sysfs/SG mapping
and fstat identity are checked after opening and before each fixed SG_IO 0x2285
request. Only INQUIRY36 and the exact two native FD07 requests repeated once are
admitted: trace `01c02880`/64 bytes and stage `01c03418`/4 bytes. Each has empty
OUT, IN direction -3, bounded command/data/32-byte sense buffers, zero flags,
3000ms timeout and a ten-second monotonic session bound. Operations increment
before validation and failure is sticky; there is no reset, upload, NOR command,
retry or reopening. Close attempts both descriptor and journal; close failure
remains sticky and precludes a result. Advisory flock cannot exclude unrelated
tools. Owner-enforced quiet state remains a dependency.

New tests explicitly manufacture private model authority; no real boot-lineage
factory or hardware opener was accepted. All device syscalls were mocked. The
Final 41 cases passed in 30 isolated Hera chunks on the exact pinned image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
[verified]. Each retained inspection shows network none, no devices, no
privilege, 2 CPUs/2 GiB, no OOM, and source/jobs/native mounts read-only. The
collect container plus 30 test inspections were independently replayed;
planned unique cases and all JUnit counts match, with zero failures/errors/skips.
A fresh query for `lan.session=sdk-trace-sg-test-20261012` found no remaining
containers. Tests cover exact pointer/header framing, full mapping and FD
identity, flock/open/ioctl/close failure, status fields, short/invalid residual,
sense length, changed repeat, no nonfixed commands, consumed replay, copied or
foreign authority, source drift between native intent and ioctl, timeout,
raw descriptor cleanup after fdopen failure, and closed activation, private exact parser selection with a foreign canonical
cache, and rejection of broader parser import forms. V1 passed 38 cases;
then dependency review required pinning the ELF parser. V2 retained a single
negative-import failure because Python supplies `fromlist=None` for a plain
import. A direct exact-tuple comparison now rejects that form with ValueError;
V3 passed all 41 cases. All three snapshots and receipts are preserved. The
changed SG source justified subsequent runs; previous frozen suites were not run.

Frozen new source SHA256:

- `tools/fm1_sdk_trace_sg.py`: `2b7872d7cb375a8e8dcc62245de9eba42c197890e7ab96774593ec6e457b136a`
- `tests/test_sdk_trace_sg.py`: `67c101c5c8b94d22a99393ccb0957106ded8aa1643e57e75a4ef4019563a9f0f`

Frozen reader source remains
`f4dc8706b0db9844c3b0913fe39ea3b502dfe1e89af5e4ec75ada11ae84df018`
and reader test source remains
`2f8983fe677112b7433279a8317d6f917b3f0ed31560593772698e70f8147ad3`.
Its 113 prior cases were not rerun; the SG snapshot contains them only to reuse
fixtures. No already-passing firmware, backup, reset or install suites were
rerun. Native ELF/app/manifest were mounted read-only.

Ignored evidence directory: `build/sdk-trace-sg-hera/`; Hera copy:
`/home/claude/mvave-fm1/sdk-trace-sg-20261012/`.

- source archive: `d91b8bc5a5806dff1d7127ab19e3eb71acbd36b2344375f195e22eade5f8436f`
- source snapshot: `58e71a1ca3f598e66cb0a3e67b1cdc9fae157e001cc36e1d535e2cc3706dcb12`
- 30-chunk plan: `4003bd711557cf70acc2628a248601ad87b89e4fd48217aac93ccb6633ad16a5`
- aggregate: `d8d0f8cae62edfabfb5dc65563f4a7391ff526ddadba1cf21242ecc80b460c9d`
- independent inspection replay: `16683f319550584b49fe84cfb9bac6caf3ffda9e1ba959b511b9a08680e3b9db`
- fresh cleanup: `e6c95448c30dad7d3faab468e1ee3fd57648646b6a722acd16edeed1267049bf`
- index of 483 evidence files: `44b237f2ce6d373db9bc6b7a06893908e7c9b4cf92ad9ae0169f19ebad5b19df`

Independent SG source review is requested and pending. Independent reader V3
review is accepted only in offline/injected scope (report b436f454); exact
install/reset completion and actual reset-wire lineage review also precede
activation. Only root may activate accepted literals and open the device under
that lineage. Successful models do not prove ROM RAM retention, FD07 handler
semantics for the new ranges, actual device mutation freedom, native parallel
packet operand semantics, display observation, recovery cause or physical
recovery. Four reads must occur in original ROM before any loader upload because
the fixed loader overwrites both ordinary-BSS objects. Complete/stopped read
receipt validation for a later fresh returned-ROM backup is owned by the
installation subtask; it must not reinterpret old receipts or reuse this reader's
consumed campaign.

Independent closed/offline review accepted the frozen `2b7872d7cb375a8e8dcc62245de9eba42c197890e7ab96774593ec6e457b136a` implementation and `67c101c5c8b94d22a99393ccb0957106ded8aa1643e57e75a4ef4019563a9f0f` tests [verified: `build/sdk-trace-sg-hera/independent-review.md`, SHA `a8589cfa8eaf559d00756bbd98ede6c516233789bb8ba4e8c93dd7437450e9d9`]. The supplemental exact-label cleanup receipt (`cleanup-exact-label-final.json`, SHA `6bdbb3cf6ac547e4f50f45468de5d62535762f71e87a297a95a414eae9e35629`) records `docker ps -aq --filter label=lan.session=sdk-trace-sg-test-20261012`, start `1791796110.5921547`, end `1791796110.6101186`, exit 0 and empty stdout, stderr and container IDs. This was a read-only list; no tests or daemon mutations were repeated. Genuine boot/native composition, literal successor review, concrete deployment and physical reads remain pending. Reader and native activation pins remain `None`.
