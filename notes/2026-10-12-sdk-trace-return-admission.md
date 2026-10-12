# Distinct owned trace-read admission

Before implementation: consumed receipts cannot be passed back through the reader
preparer, which requires an absent marker and fresh snapshot. Recovery needs an
evidence-only factory that reconstructs original lineage without an opener or
timestamp refresh. Existing closed V2, wrapper/child and old receipts stay frozen.

New source `tools/fm1_sdk_trace_return_admission.py` contains this separate replay
path. BOOT_SHA, READER_SHA, NATIVE_SHA and WIRE_SHA remain literal None; the first
factory step rejects any pending pin before evidence reads or imports.
Canonical boot prepare_read_lineage supplies the exact registered original
CompletedInstall, with optional preserved original install journal. No run,
reader.prepare, native.prepare_campaign or SG constructor is called.

The proposed schema1 kind is fm1-exact-owned-sdk-trace-returned-state. Fields are
adapter_sha256, boot_lineage_path/sha256, native_campaign_path/sha256 and
owned_capture_path/sha256. The native input snapshot must be the boot lineage's
original ROM snapshot path. Exact ELF/app/manifest derive the five operations,
published plan/seal and consumed marker. Historical wrapper-attempt and logged
read admission must be within the original snapshot's 120 seconds; proof.check
rechecks immutable files/registered lineage/policies/absence, never freshness.

The owned wrapper and child must differ from the frozen tracked templates only
by the exact top-level None-to-literal assignments. All packet members, ten
owned lifecycle files, terminal capture and source bytes freeze. Completion
publication and native+USBmon replay use separately pinned pure kernels.
Incomplete logged reads require actual plan/seal; consumed pretransport missing
or empty logs require owned nonzero exit, zero native/USB requests, no response
files/result/pending; any missing plan/seal remains frozen absent.

The returned proof has its own exact-instance WeakSet and retains original
policy inputs, stock manifest, install campaign/journal pins, terminal time and
original snapshot raw hash. It grants no loader/NOR authority. Future backup
uses a separate fresh current witness and full matching target dumps.

After implementation: AST parsing and existing frozen dependency hash checks
passed. Focused tests cover closure before reads/imports, exact real template
derivatives, positive/negative evidence drift, private/direct bounded files and
copied proof rejection. Registered-check tests manufacture membership solely
to exercise check mechanics; they are not a genuine factory acceptance.
Heavy tests ran on Hera in 30 source-read-only, no-device/no-network chunks.
Canonical boot/read/native literal acceptance and genuine composed file replay
remain required before any successor activation. No hardware traffic occurred.

Worktree /Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware;
branch feature/2026-10-11@installable-firmware. Parent owns commits/push/hardware.
Current last parent-confirmed pushed checkpoint 4c9120efcfb57bf6391ca0b9e8b83a8d4c7f7842.
Source/check artifacts and handoff are build/sdk-trace-return-admission-hera.
Shared semantic backends still select the primary checkout; no retarget/restart.
File and AST inspection supplies bounded Python coverage, not native ABI proof.


[verified: isolated Hera mechanics gate] V1 finished with 45 unique planned nodes
passing exactly once across 30 nonempty chunks (15 chunks of two and 15 of one),
plus one separately retained template-derivative smoke. No failures, errors or
skips occurred. The source archive has 1,750 regular pinned files at source
HEAD `9cd2523e588e7a2f8e2a7c2ca66c33d52dc5e8e7`; this is an archive boundary,
not a claim that this lane verified a remote push. The frozen source is
`bd58664db651978c419fa5be36743b785eb0893cd4879385ea10e1860448cec0` and tests
`f0dad1024f5f8bf7ff93fd774a699b72f76f8f0db6ccefd009f92a54c31edaf5`.

The 32 retained collection/smoke/shard inspections have exit 0, no OOM,
network none, no devices, nonprivileged containers, two CPUs, 2 GiB memory and
4 GiB combined memory/swap, with source and jobs read-only. All named removal
receipts and a fresh structured exact-label lookup show no remaining containers.
The image is
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.

Exact retained artifacts under `build/sdk-trace-return-admission-hera/`:

- `source-v1.tar.gz`: `a530a6d880211d0b8835ffee6445ec29506a0b857ba65178c7ae145a648e4de1`
- `snapshot-v1.json`: `1c3ecea5185549e70e11f6468845bdc356f4a2a2c0055688f47dcd2163bf8f2e`
- `run-v1.py`: `6e9c33d3fe5074a63bf2e9a00122f864e6782d468a1c3f8f482457f04b199fe2`
- `plan-v1.json`: `8b2cc0e8082011f3a0cff26ef202a09c4fcd3576077371ced3f9cf42f4d29948`
- `aggregate-v1.json`: `f715ccb5fbcca659f5467de51fc520504379c55c4fe162d475c1fbfa149d448b`
- `cleanup-v1.json`: `047ee117e725b108b69a62721b8d6aa3a941a436213ba3fedf6c3785560c5524`
- `author-check-v1.json`: `36dbc829fe95ec204111e6b0b5c958e85f6668e3c12947c441596fa86ad11760`

[verified: scope] These tests establish closure and bounded file/AST/registry
mechanics. The genuine admission factory was not exercised; four production
pins remain None and no returned proof or opener authority was granted. Root's
pending boot/read composition present in the archive is outside this gate.
Independent source/runtime review and then exact canonical boot/reader/native
pins plus genuine composed evidence replay are the next dependencies. No
hardware traffic, source commit or push was performed by this lane.
