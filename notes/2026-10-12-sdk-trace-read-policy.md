# Exact SDK trace read policy

The new `tools/fm1_sdk_trace_read.py` is an injected-only successor for the
accepted private trace candidate. It does not modify the old stage probe, SG
adapter, backup, restore, reset or installation gates. The six firmware/build/
trace-test sources accepted at `41fc898d` remain frozen. No hardware operation
is performed by this task.

Actual candidate pins are app `76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44`,
ELF `e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035`,
build manifest `b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e`,
nonce `6b5482dbb66b5f45ed73e2f26c4a4657` [verified]. The native ELF has one
global 64-byte trace object at `0x01c02880` and one local 4-byte stage object
at `0x01c03418`, aligned 16/4, inside writable allocated ordinary `.ram0_bss`
[verified]. The parser checks actual bytes, symbol geometry, section and
nonoverlap before deriving commands. A manifest assertion alone is insufficient.

The fixed loader upload occupies `0x01c02000..0x01c07e00` and overwrites both
records [verified]. The only proposed exchange sequence is original-ROM INQUIRY
36 bytes, FD07 trace64, FD07 stage4, then the same two FD07 reads once more.
The four CDBs are `fd0701c028800040ffffffffffffffff` and
`fd0701c034180004ffffffffffffffff`, each repeated once, with empty OUT payloads.
There is no request argument for an arbitrary range, no loader, NOR or reset
operation, no retry and no hardware opener. Root explicitly chose repeated
coherence over a weaker two-transfer capture.

FD07 address/length encoding and WL82 transfer-local MengLi handling are facts
reported by Andrey Grigoryev (kagaimiq), MIT `jl-uboot-tool` at
`adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a`, `jltech/uboot.py`,
`jltech/cipher.py`, `jltech/crc.py`, `data/chips.yaml` and
`docs/usb-loader-v2.md` [reported]. This independent implementation uses Python
CRC rather than importing that executable source. The earlier physical old-stage
32-byte read in `notes/2026-10-11-diagnostic-first-ram-read.md` verifies the
old-range request ABI [verified]; acceptance of the two new ranges remains
pending physical evidence. The original ROM handler has not been dumped or
disassembled. RAM retention, ROM USB initialization effects, and the reported
in-place cipher's mutation/restoration are unverified. IN-only host requests
do not establish device-side mutation-free execution.

The decoder requires exact lengths, magic/schema, pinned 128-bit nonce,
complement, nonzero even sequence and source-derived phase/sequence/mailbox
relationships. Both decoded trace/stage pairs must be identical. The reset
reason must remain `ffffffff` and is reported unavailable. Initialized caches
must remain zero; later caches must fit the worker's possible success/error
paths, including an invalid clock snapshot following clock-guard failure and
the bounded time-wait failure. Zero heartbeat alone is not forbidden: an
earlier probe can already consume the 20-second threshold before the wait's
first increment. Returned phase 6/7 can coexist with stage 6 because the stage
store follows publication; this is marked `stage_update_pending`. The nonce
identifies an image, not a unique boot or authenticity.

Successful decoding reports conditional coherent publication progress only.
It does not infer a P33 deadlock, CPU cause, reset success, display observation,
physical recovery, ROM handler proof, retention or native parallel-packet operand
semantics. Independent native review accepts the existing compiler packet with
the old-register interpretation explicitly inferred, not verified.

The offline snapshot verifier checks exact candidate pins, a chronological fresh
quiet initial-ROM assertion, original USB port/bus, changed ROM enumeration and
complete changed SG/sysfs/FD identities. Before injected I/O the runner creates
and fsyncs a consumed marker, plan, campaign and every submit intent. It rechecks
source/evidence, lineage, live time and full binding on both sides of every
exchange, checks all SG completion fields and publishes a result only after
successful close and repeat coherence. Any failure consumes the attempt and
leaves no result. Python callers are trusted, not sandboxed.

**Required next dependency:** no accepted exact trace target boot successor
exists yet. `BOOT_POLICY_SHA=None` deliberately closes the real `prepare`
factory. A separately reviewed `fm1_sdk_trace_boot.py` must provide a registered
lineage object and `require_read_lineage`, `check`, `read_binding` and
`read_receipt_parent`, validating actual new install/directory-last/consumed
receipts and the one exact reset transmission. Its source pin and registry
integration must be reviewed before opening the factory. The current pure
snapshot verifier does not convert caller assertions into boot/install proof.
No old reset receipt or old image policy can substitute for this dependency.

New model tests explicitly manufacture private registry entries for injected
transport tests only. Such tests do not claim a real boot factory was accepted.
First Hera V1 run collected 107 new cases; native-dependent cases exposed an
incorrect initial parser assumption that the stage symbol was global. Direct
ELF inspection shows trace binding 1/global and stage binding 0/local after LTO.
The parser now requires those exact distinct bindings. Failed V1 receipts remain
under `build/sdk-trace-read-hera/evidence-v1`; no firmware changed. Hera final
receipts, source/archive pins and independent review will be appended after the
focused run. Parent owns commits/pushes and integration.

Final reader snapshot is `f4dc8706b0db9844c3b0913fe39ea3b502dfe1e89af5e4ec75ada11ae84df018`,
test snapshot `2f8983fe677112b7433279a8317d6f917b3f0ed31560593772698e70f8147ad3`.
The new V2 cases passed 107/107 across 16 Hera chunks. Independent review then
found missing actual failure-completion receipts and raw descriptor cleanup on
`fdopen` failure. V3 logs every structured completion before post-I/O binding
or completion rejection, preserving status, bounded sense prefix, actual sense/
response lengths and response hash. Both wrapper-creation failure paths close
the raw descriptor. Additional cases cover those faults, sense bytes and cached/
foreign/unrecorded boot-module rejection. Canonical boot imports must export
`IMPORTED_SOURCE_SHA256` matching the accepted source pin; this preserves the
boot module's exact-instance registry while rejecting a cached older source.
The real factory remains closed until the separately accepted boot policy pin.

V3 passed **113 unique cases in 16 chunks**, with zero failures, errors or skips
[verified]. Only this new test snapshot was run after the review fixes; earlier
already-passing firmware/backup/restore tests were not rerun. Hera was
`claude@192.168.1.48`, pinned image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
network none, 2 CPU/2 GiB, no privilege/devices, source/jobs/native read-only.
Independent retained inspection/JUnit replay checked all 17 container receipts
(collect + 16 chunks) for each V1/V2/V3 run, with no OOM; fresh label-filtered
cleanup found zero containers [verified]. V1 failed receipts remain intact and
are explicitly excluded from passing acceptance.

Ignored artifact directory is `build/sdk-trace-read-hera/`; Hera copy is
`/home/claude/mvave-fm1/sdk-trace-read-20261012/`. Important retained pins:

| Artifact | SHA-256 |
| --- | --- |
| source-v3.tar.gz | `6373fd9131ad6ea4dac2fdee5a9bfacf24a845ea5fef221de5a20510032328f5` |
| plan-v3.json | `bec635a1ac35114e2ab77233c9075a96283a48d4e8755a5df3de44bcc5052eec` |
| aggregate-v3.json | `e352d9c9631651a57910adfdf17b7f168ebd04a7b5e39be10b887a5798e605a9` |
| inspection-check.json | `ecb57079ed0b61982d647332208777e6698ee37d1837e483686ffe4f4cabebb7` |
| actual-native-plan.json | `7cbb4021ca1bcf4018576070670eb22b1253d430c251cb8ff763a070f89ca2ca` |
| cleanup.json | `5c9a4c2f97d1eafef605e8eaa3acbd8135a3cd290c83035d15f13d9c6b92766a` |
| evidence-index.json (273 files) | `3b54e08d34905e0aa1079e3c8d300138255d0598fe9d80fb84c9d2796cad9022` |

Actual native ELF derivation produced the exact five operations above [verified].
No real transport, boot lineage factory, ROM retention or new-range device
acceptance was exercised. Parent owns integration, commit/push and any later
hardware opener and physical acceptance. Independent reader review is pending.
