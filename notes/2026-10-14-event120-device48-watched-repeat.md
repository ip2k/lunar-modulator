# Fresh device48 Event Horizon watched repeat

[verified] Root source `8f8f7531a1f889f0c89146b7167977913f21c9e3` integrated the independently tested device48 read/boot adapters. The owner requested another watched attempt. Evidence remains private on bench01 under `/home/claude/fm1-device48-event120-repeat-20261014` (0700); no device binaries were added to Git.

[verified] The fresh read completed all 8,757 allowlisted commands, with zero flash or reset operations. Both 1,048,576-byte dumps matched `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. Read manifest SHA-256: `0655abf5c2b5abb3bd5af073a04858353e43137c97dbb1ecb746e43d0f31e1f7`; transcript: `979b25ca1722af05259c2d0f59ee298b8b280e341b25b6671a060037df67d480`.

[verified] A fresh passive same-connection USB/SG snapshot retained bus1/device48, path1-1, 4c4a:8057 and the matching SG inode identities. Its SHA-256 is `4e2be6f020b6bfc4f3b88659a7d14eca9efcb93b909cd9448e2160c2561abb1a`. Boot preflight passed with zero hardware operations. Campaign SHA-256: `cfc4e806b9ec537f0ad498312ae4a46f92b19ef1636f9dcec53771258f610911`.

[verified] At Unix time 1792017843.4294136 the coordinator submitted exactly one `fc0c00000001ffffffffffffffffffff` request. Completion had host=7, residual=16, info=1 and raised the reviewed ambiguous-result error. No retry occurred. Passive enumeration immediately afterward showed native USB 1209:0001, bus1/device49. This establishes native USB appearance, not complete application acceptance or independent recovery. The consumed campaign must never be reused.

[reported] Owner screen, PLAY/song audio, keys, encoders, glitches and footer observations are pending through a fresh question sent after this request. Earlier missed observations are not acceptance. SAVE remains disarmed; hung/corrupt-app recovery, migration/rollback and browser release gates remain open.
