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
The fixture now uses existing cold-test teardown for sound zero; v4 is running
on Hera in thirty containers. Full campaign success remains unproven.

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
