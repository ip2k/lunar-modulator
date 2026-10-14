# Fresh device48 Event Horizon watched repeat

[verified] Root source `8f8f7531a1f889f0c89146b7167977913f21c9e3` integrated the independently tested device48 read/boot adapters. The owner requested another watched attempt. Evidence remains private on bench01 under `/home/claude/fm1-device48-event120-repeat-20261014` (0700); no device binaries were added to Git.

[verified] The fresh read completed all 8,757 allowlisted commands, with zero flash or reset operations. Both 1,048,576-byte dumps matched `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. Read manifest SHA-256: `0655abf5c2b5abb3bd5af073a04858353e43137c97dbb1ecb746e43d0f31e1f7`; transcript: `979b25ca1722af05259c2d0f59ee298b8b280e341b25b6671a060037df67d480`.

[verified] A fresh passive same-connection USB/SG snapshot retained bus1/device48, path1-1, 4c4a:8057 and the matching SG inode identities. Its SHA-256 is `4e2be6f020b6bfc4f3b88659a7d14eca9efcb93b909cd9448e2160c2561abb1a`. Boot preflight passed with zero hardware operations. Campaign SHA-256: `cfc4e806b9ec537f0ad498312ae4a46f92b19ef1636f9dcec53771258f610911`.

[verified] At Unix time 1792017843.4294136 the coordinator submitted exactly one `fc0c00000001ffffffffffffffffffff` request. Completion had host=7, residual=16, info=1 and raised the reviewed ambiguous-result error. No retry occurred. Passive enumeration immediately afterward showed native USB 1209:0001, bus1/device49. This establishes native USB appearance, not complete application acceptance or independent recovery. The consumed campaign must never be reused.

[reported] Owner watched this attempt and rejected playback: “It sounds like it can't keep up with the processing power required to play the song back properly and the VU meteer is super laggy. It sounds awful and sounds like it's lagging super hard.” This is a failed audio/performance acceptance gate. CPU exhaustion is a hypothesis, not a measured cause. A follow-up asks whether onset preceded PLAY; no screen/control/footer values were separately confirmed.

[verified] At 22:46:10 UTC passive enumeration showed ROM 4c4a:8057 bus1/device50; the diagnostic returned without a coordinator power-cycle command. Timed return is not independent recovery from a hung or corrupted app. Device48 read and boot campaigns are consumed; new hardware action requires fresh admission for device50.

[inferred] Current app source collects render/draw maxima internally but does not expose those counters in the diagnostic footer; audio_queue also counts underruns. The 64-frame block at approximately 44,118 Hz has about 1.45 ms of audio time, with eight blocks buffering about 11.6 ms. Offline investigation is assigned before choosing a minimal instrumented hardware follow-up. No replacement firmware was flashed. SAVE remains disarmed; hung/corrupt-app recovery, migration/rollback and browser release gates remain open.
