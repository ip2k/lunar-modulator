# Native PROJECT replay — implementation in progress, 2026-11-01

Phase1 codec3a1c9a31 independently approved and integrated by coordinator.
This dependent slice is incomplete and must not be merged as persistence.
No production UI/storage/hardware binding.

The existing canonical JSON emitter now has separate explicit host backing and
an internal current-PROJECT borrowed-value source. Host collector capacities and
any-order behavior remain; the current-app adapter is still being implemented.
The sequencer gains a streaming sink using the same formatting body; its old
buffer API remains. MIT line-fragment helper provenance is historical
cccd21cc5dc82859ed8a5d84f0a7a40646d07353, with current formatter extensions kept.

[verified, narrow host] Nine existing binary golden inputs rendered through old
and new JSON writers in pretty/compact modes match bytes and full writer reports
under ASan/UBSan. Host writer481688B, small emitter2800B. This does not prove
PROJECT provider parity or native memory/stack fit. Actual current-app rich,
random, failure/cap/ownership tests, reader context, fake transaction and native
closure remain required. No whole-document retention is planned for native.

Private design/active handoff: performance scratch/devkit-20261023/native-save-20261101.
Rarefaction sibling root is rejected; Serena absolute write_doc boundaries agree
with direct source. Shared active roots unchanged. Exact source is authority.

WIP continuation: current-app PROJECT-only adapter now shares collection,
canonical emission and the existing256B-cadence push reader. It holds the busy
lease through preflight/begin/replay/internal identity+semantic checks/commit.
Explicit commit outcomes include indeterminate; no automatic retry. A fixture
now exercises actual current app host-vs-staged bytes/reports. It is not yet run;
reader still uses its old stack temporaries and must move to caller context.

[verified, WIP differential] Exact frozen e267d7cd app-state, JSON writer,
sequence persistence and binary codec translation units were rebuilt alongside
current source on Aeon CPU0–3/max4CPU6GiB. All76 callback/report/byte streams
(PROJECT modes0/1/2/3) match exactly, normal and ASan/UBSan. Current native
staging additionally matches host modes2/3. Host aux7296B, arena65536B.
The reader now offers the same parser with its large inflater and mutually
exclusive BROW/UNIT arrays in queried caller storage (<=16384 compile guard);
old read API remains a wrapper. Neither this narrow corpus nor object sizes
establish inclusive target memory, stack, transaction or runtime admission.

[verified] Expanded exact e267 oracle:244 saves per build, all four modes,
including32 FM6 slots, per-focus randomized drum parameters, reordered/duplicate
parameter descriptors, invalid UTF8/nonfinite-level failures and near reports.
Reader relocation:1633 old-vs-workspace parses per build include truncation,
byte mutations with CRC on/off, sink stops, records, source read order and full
reports; normal+ASan/UBSan passed. Prior387 codec cases/digest remain unchanged.
Fake-only transaction:2x102400-byte slots,183 operations/549 partial-effect fault
cases per build passed; old/new-only independent semantic rescans, source
mutation, reentry, corruption, wrap/equal/half-range ambiguity and uncertain
marker handling. Further known-alias/short-read guards are being verified.
No flash partition, production storage, complete native fit or live save claim.
