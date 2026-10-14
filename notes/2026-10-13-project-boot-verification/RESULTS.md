# Native PROJECT startup composition verification

[verified] Composed cold startup validates the complete PROJECT and engine plan,
stages/adopts a SET if present, reclaims sequence and DX7 scratch before engine
allocation, adopts audio engines, reconstructs inline MIDI effects, then restores
scalars, final-storage modulation with its seed, and saved VIEW. Ownership and
sample-rate mismatches refuse before restoration. Later failures require
returning to recovery or discarding the cold app; this is not live replacement.

[verified] Host v2 passed 168 cases in 30 Hera ASAN/UBSAN chunks: 30 composed
startup cases, 32 modulation, 30 cold adoption, 30 DX7, 30 scalar and 16 arena
cases. Composition tests cover nine screen modes (including Session/Song UI),
finite nonzero synthesized audio, single retained sound allocation, and refusal
without app mutation for live frames, CRC, truncation, report alias, occupied
pool and mismatched rate. Composition fixtures have one Trio sound, one mod
module, no SET, DX7 bank or effects; individual adapters retain their separate
coverage. Integrated mixed-project playback remains unproven.

[verified] Host v1 passed 24 chunks; six failed only because sequencer-screen
keys edit instead of playing live notes. The corrected fixture verifies the
saved view first and then uses the shared note-input API. Production behavior
and audio assertions were not weakened. Failed logs remain private.

[verified] Thirty native retained-entry links and thirty boot-hook links passed
SDK-free audits, ELF symbol and embedded asset-byte checks. The latter includes
22 profiles with PROJECT startup selected, text/binary input, and optional Plate.
A startup failure stops audio, detaches USB and returns to ROM before rendering.
The 20-second diagnostic recovery remains. Target linkage is not execution.

[verified] An all-thirteen/twelve-voice-Shapes link with composed entries retained
produced 843564 application bytes, leaving 25272 of the approved 868836-byte
budget. It has no selected startup PROJECT; includes existing diagnostic effect
fixtures. It is an audited private probe, not a release or hardware admission.

[verified] Every campaign log and terminal exit/OOM state was inspected; owned
containers were removed. Tested immutable source hashes match worktree files.
Receipts and reproduction scripts accompany this report. Full logs/binaries
remain private under build/project-boot-v1/. No device command was issued.

Serena and Rarefaction remain on the primary checkout, absent these native files.
Both located shared fm1_app_show there; worktree source and Hera compiler are the
native authority. Fallback clangd indexes cannot prove pi32v2 ABI or absence of
callers. Shared server selections were preserved for other sessions.

Remaining: mixed-project composition/playback; target stack/RAM/timing; final
production image and settings migration; physical install/recovery/rollback;
web builder and installation; exact-head review/CI/integration. Goal active.
