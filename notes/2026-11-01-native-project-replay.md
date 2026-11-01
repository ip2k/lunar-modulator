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
