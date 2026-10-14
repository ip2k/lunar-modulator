# Native audio pause verification — 2026-10-14

[verified] Source inspection of Dinghy `fm1_audio_stop` shows that it clears
ALNK CON0 bit 11, without masking IRQ 11. `audio_pause.h` now provides an
explicit main-loop pause token: preserve ALNK's interrupt field and DMA-run
bit, mask ALNK, stop DMA; on release clear both 256-frame stereo DMA halves,
discard queued pre-SAVE blocks, preserve cumulative underruns, restore only
ALNK's saved interrupt field and running state. Both calls require global
interrupts disabled by the caller. No global interrupt state is changed here.

[verified] Hera campaign v4 passed the pinned pi32v2 target compile and thirty
concurrent ASan/UBSan register-model shards, 2,000 randomized cases each.
All 32 process exits and thirty exact success logs were inspected; twenty
source hashes match the current worktree. Tests cover missing arguments,
incorrect DMA size, re-entry, inactive release, DMA canaries, all saved IRQ
enable/priority combinations, running/stopped DMA, unrelated IRQ-field changes,
queue reset with underrun retention, and subsequent queue playback.
Compiler SHA256: `42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`.
Reproduction driver: `tests/native/verify_audio_pause.py`; public receipt:
`verification.json`. Complete private logs/objects are under
`build/native-audio-pause-20261014/`. No vendor binaries are committed.

[verified] Initial target harness v1 lacked the IRQ HAL's required application
fault handler; v2 supplied it but failed `-Werror` for the included, unused HAL
startup functions. V3 suppresses that specific unused-function warning and
passed. Its receipt included macOS `._` archive sidecars as source headers;
local collection rejected those absent paths. V4 excludes dot-prefixed paths
and was rerun successfully with source hashes verified. Prior logs are retained.
Initial Podman image lookup failed; the established image is in Docker's store.

[verified] The actual USB `uac_packet` repeats its last sample on ring starvation.
Stopping ALNK alone therefore does not establish silent USB audio during SAVE.
The scheduler must set the UAC stream unprimed (`uac.go = 0`) while its producer
is paused, clear stale stream state under a short interrupt exclusion, then let
`uac_render_start` prime from silence on restart. TIMER5 must otherwise remain
available between flash operations for USB/input/watchdog service. Display DMA
reads the separate strip canvas; synchronize it before leasing TFT pixels and
redraw invalidated pixels before sending strips again.

[inferred] Restoring ALNK's DMA-run bit should resume its existing configuration.
This has not been observed on FM1 hardware. Pending-half behavior, audible
restart, codec behavior and USB-stream restart need physical acceptance before
enabling SAVE. Host register tests do not model DMA, bus timing or interrupt
delivery. Target compilation does not prove execution or a full-image link.
The helper is not yet wired into `app_probe.c` or retained by its default link.
It does not admit physical storage, silence USB or synchronize display DMA.

[verified] Serena resolved this worktree's `fm1_audio_stop` body by absolute
path, matching source inspection. Rarefaction's primary-checkout fallback did
not find that symbol within its bounded search; no native ABI/call-graph claim
is based on that failure. No shared project selection was changed.

Next: integrate audio/UAC/display quiescence into actual SAVE event handling,
with refusal before pausing when storage is not admitted; retained full-image
link and stack/IRQ audit; resolve two-slot capacity and ownership/migration;
watched all-thirteen boot and physical rollback; browser installer/builder and
release gates. No FM1 commands were sent in this campaign.
