# Bounded project SAVE transaction bridge — 2026-10-14

[verified] Thirty cases in thirty concurrent Hera containers pass ASan/UBSan
and compile the bridge harness with pinned pi32v2 clang and warnings as errors.
All thirty logs, container exits, OOM flags and fourteen source hashes checked.
Private complete logs: `build/native-project-save-20261014/v4/`.

[verified] The bridge leases indexed pixels, constructs the compact binary
writer, serializes a complete record source without flash I/O as preflight,
then erases the inactive slot and serializes again. A streaming CRC covers all
emitted offsets, lengths and bytes; the two complete streams must agree before
full read-only file validation and outer commit-last programming. The callback
source must stay stable across both passes. CRC is not cryptographic identity.

[verified] Geometry/admission/stopflag refusal leaves the framebuffer and flash
unchanged. Collector refusal or false success without END performs zero flash
I/O. Once a lease is granted, every return invalidates pixels and releases it;
the harness redraws after both success and failure. Callback tests reject a
short header and writes after a completed header.

[verified] Nine binary fixture types round-trip through real codec and modeled
NOR; changed FIRSTORBIT projects recover correctly. 3,006 injected NOR
callback failures cover refusal, half-applied and fully-applied operations.
FIRSTORBIT requires 1002 modeled operations. Reboot scanning retains
an intact previous slot and selects a fully validated committed file. Outer CRC
agreement with malformed inner magic falls back to the older valid file.

[verified] Mutation between preflight and writing is refused before outer
commit, and recovery loads the previous project. Initial v2 showed that comparing
only headers misses same-length parameter changes; complete-stream CRC fixed
that defect in v3, with boundary/refusal additions verified in v4. v1 launcher
was prepared but not run. v2 failed and v3 passed logs are retained privately.

[verified] This is a record-source/codec/store bridge, not a live application
SAVE implementation. The harness source reads actual fixture records; the native
application collector, audio pause/resume, UI scheduling and physical flash HAL
are not wired here. No hardware command occurred. No physical storage ownership,
full firmware RAM/flash fit, settings migration or physical rollback is proved.
Maximum-capacity storage, all13 acceptance and web/release gates remain open.
