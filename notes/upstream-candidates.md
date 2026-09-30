# Upstream candidates

A running list of fixes or findings that would help other projects, kept so
they are not lost. Nothing here has been posted. Anything headed upstream
follows the `oss-contributions` house rules: draft only, and the owner posts.

| Found | Project | What | State |
| --- | --- | --- | --- |
| 2026-09-29 | AL-255/FM-1-RE | `parse_handshake_identity` rejects units running Baud Girl's FM-1+VA, whose ID block keeps V15's checksum byte, so rollback with `fm1_ota.py` fails (found by reading, not running). Also relevant: the same-version gate, the flash-head rewrite, loader resume | issue drafted in `scratch/drafts/2026-09-29-issue-al255.md`, unsent |
| 2026-09-30 | pichenettes/eurorack (Plaits) | `WavetableEngine::Init` allocates 64 wave pointers but `LoadUserData` writes 256. It is harmless on the module because all engines share one arena, but it corrupts memory in any port that gives engines separate arenas (polyphonic ports). A one-line fix: allocate `kNumBanks * kNumWavesPerBank` | found in stage A (`engines/third_party/mutable/UPSTREAM.md`); worth checking whether CTAG, VCV or Daisy ports already patch it before drafting anything |
| 2026-09-30 | pichenettes/eurorack (Plaits) | `LPCSpeechSynthController` reads `phonemes_[15]`, one past the 15-entry table, whenever a trigger in LPC phoneme mode picks the last consonant: `PlayFrame(frames, 14, false)` still fetches `frames[15]` as the blend partner, at weight 0. It happens at ordinary HARMONICS positions (about 0.17–0.44). A one-line fix: when `interpolate` is false, `LPCSpeechSynth::PlayFrame` passes the same frame twice | found by ASan in stage A2 (`engines/plaits-heavy.md`, quirk 2); same check of other ports first |
| 2026-09-30 | pichenettes/eurorack (Plaits) | Smaller sanitizer findings, each harmless on the module: `fm::NormalizeVelocity(1.0)` reads `lut_cube_root[17]` (one past), reached at full LEVEL; `fm::Pow2Fast` left-shifts a negative int (UB before C++20); `String::ProcessInternal` computes `1.0f / f0` with `f0 = 0` on the first trigger after a reset; `SixOpEngine`'s `temp_buffer_` is too small for 24-sample calls (Plaits only makes 12-sample ones) | found in stage A2 (`engines/plaits-heavy.md`, quirks 3, 4, 5 and 12); could be one small PR if upstream still takes them |
