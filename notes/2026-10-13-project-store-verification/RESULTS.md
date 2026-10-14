# Project transaction core, 2026-10-13

[verified] A geometry-independent two-slot native project store accepts streaming
writes into an inactive slot. Sector erases, page-bounded programs, full payload
CRC, mandatory caller format-validation, metadata readback, payload recheck and
commit-last publication are implemented. Startup scan checks metadata and payload
CRC and rejects ambiguous generations. The previous active slot is not erased.
Transport failures latch the transaction; no automatic retries.

[verified] 30 C tests pass in 30 Hera containers under ASan/UBSan, including a
maximum-size 98,304-byte payload, 25 selected transport-failure positions across
scan/erase/payload/readback/commit, validation refusal, bounds/error latch,
repeated commit refusal, invalid geometry, and corrupted-latest fallback. Every
case checks previous-slot byte preservation. All logs/exits/noOOM/source hashes
checked. Target wrapper compiles with pinned pi32v2/r3/-mfprev1/Oz freestanding
C99 Wall/Wextra/Werror; object private, digest in target-compile.json.

Initial campaign failed a misleading-indentation warning. Second campaign passed
29/30; its invalid-geometry case incorrectly expected a scan using the rejected
geometry to succeed. Final campaign explicitly tests that refusal, reconstructs
a read-only context with valid geometry, and passes all30.

Limits: these are selected whole-callback failure positions, not exhaustive
byte-level torn-write/power-loss simulation. The format validator is a test stub;
real Lunar reader integration and serializer-to-store end-to-end tests remain.
Equal-generation and wrap cases need additional coverage. No physical allocation,
flash permission, application linkage, settings migration or hardware acceptance.
Two full-size slots need 200KiB; available protected space after the current
13-engine app cannot hold them. Release capacity/layout is unresolved; this code
does not silently reduce the release project capacity or enable any NOR writes.
