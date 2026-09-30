# Upstream candidates

A running list of fixes or findings that would help other projects, kept so
they are not lost. Nothing here has been posted. Anything headed upstream
follows the `oss-contributions` house rules: draft only, and the owner posts.

| Found | Project | What | State |
| --- | --- | --- | --- |
| 2026-09-29 | AL-255/FM-1-RE | `parse_handshake_identity` rejects units running Baud Girl's FM-1+VA, whose ID block keeps V15's checksum byte, so rollback with `fm1_ota.py` fails (found by reading, not running). Also relevant: the same-version gate, the flash-head rewrite, loader resume | issue drafted in `scratch/drafts/2026-09-29-issue-al255.md`, unsent |
| 2026-09-30 | pichenettes/eurorack (Plaits) | `WavetableEngine::Init` allocates 64 wave pointers but `LoadUserData` writes 256. It is harmless on the module because all engines share one arena, but it corrupts memory in any port that gives engines separate arenas (polyphonic ports). A one-line fix: allocate `kNumBanks * kNumWavesPerBank` | found in stage A (`engines/third_party/mutable/UPSTREAM.md`); worth checking whether CTAG, VCV or Daisy ports already patch it before drafting anything |
