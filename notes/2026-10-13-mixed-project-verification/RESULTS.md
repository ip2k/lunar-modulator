# Mixed PROJECT verification checkpoint

[verified] The first combined PROJECT campaign failed in its MIDI-slot test
access; the corrected v2 campaign found a production DX7 descriptor-identity
bug. Application-specific DX7 descriptors supply saved patch names, so direct
catalogue-pointer comparison incorrectly refused correct installed DX7 units.
The native modulation preflight now recognizes only the exact application DX7
wrapper with a matching, in-range DX7 catalogue index. Copied descriptors and
mismatched indices remain refused.

[verified] All thirty v3 sanitizer shards passed startup, voice-bank bytes,
modulation seed, scalar/effect state, SET round-trip, explicit sequence playback
with finite nonzero audio, and three non-mutating descriptor/index refusals.
They failed afterward at fixture teardown: normal selection forbids removing
sound zero. Each shard's separate existing composition test passed. All v3
containers exited without OOM and were removed. Their logs remain private in
build/mixed-project-v3/; terminal states are in receipts/host-v3-containers.json.
The fixture now uses existing cold-test teardown for sound zero; v4 completed
on Hera in thirty containers: all sixty tests passed. Every quiet pytest log
and terminal exit/no-OOM receipt was inspected; source hashes match the immutable
remote snapshot. The earlier log-check script expected a pytest summary suppressed
by quiet mode; the corrected log check confirms the actual two-success output.

[verified] All-thirteen production link v2, with twelve-voice Shapes and the
embedded FIRST ORBIT project selected for startup, passed SDK-free/eFuse audits
and exact embedded-byte verification. It excludes diagnostic modules. Receipts
are in receipts/all13-v2-*.json. This is link evidence only: runtime, stack
margin, physical installation/recovery and web-installable release remain
unverified. No device command was issued.

Both semantic tools select the primary checkout; dx7_give navigation matched
its source, but native worktree additions are absent there and fallback clangd
cannot prove pi32v2 ABI. Shared selections were preserved; worktree source and
Hera compilation are authoritative for this fix.

Goal remains active. Next inspect all v4 terminal logs/states and tested source
hashes, then verify production-profile startup and target resources/timing.
Settings migration, physical rollback, web builder/install and required
exact-head review/CI/integration remain unfinished.

## Production-content verification correction

[verified] Production host v1 refused a parameter before allocation. Read-only
record diagnostics in v2 identify arp retired Swing UID 7. Both containers exited
1 without OOM and were removed; receipts are production-v1/v2-container.json.
The all13-v2 driver mistakenly chose tests/fixtures/state/1.0/first-orbit.lunar,
a frozen compatibility fixture, rather than engines/state/examples/first-orbit.lunar.
The current example has Macro bass, no retired arp Swing, new drum Choke/Kit Decay,
time/glide parameters, envelope Delay and set key. The compatibility fixture was
not modified and its refusal remains evidence; native retired-UID compatibility
is not verified. Earlier references to production FIRST ORBIT runtime failure
must be read with this distinction. Host v2 includes project_boot.h, correcting
a missing prototype in v1's acceptance probe.

The driver now selects the actual production example. All13-v3 link is running
on Hera using immutable mixed-project-production-source-v3. After its audits and
packed-byte check pass, production-v3 will test that same prepared content.
All13-v1/v2 retain their earlier legacy-fixture scope; they are not production
content acceptance. No hardware command issued. Semantic tools still select the
primary checkout, bounded state_kind bodies agree with source, but native worktree
additions and device ABI remain outside their verified coverage.
