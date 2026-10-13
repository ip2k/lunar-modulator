# V8 diagnostic display retry, 2026-10-12

[verified, owner observation] The owner saw white, red, green and blue horizontal bands after the independently admitted repeat RUN_APP request. This is the first positive physical display acceptance for the installed V8 diagnostic. It is not full Lunar, audio or web-install acceptance.

The owner confirmed the FM1 had remained powered continuously. Passive USB and SG topology remained bus 1, device 13, port 1-1 before the attempt. The genuine completed returned dual-target backup verifier accepted the retained two matching 1 MiB dumps and original installation lineage. No NOR operation or loader upload was performed for this retry.

`tools/fm1_sdk_trace_repeat_boot.py` is a separate one-use adapter around the pinned fixed-loader FC0C arg1 mechanics. It requires the exact completed returned backup, explicit continuous-power/no-later-device-command attestations, immutable source/evidence, unchanged SG binding, and a new private receipt. Its consumed marker precedes SG access. It never retries an ambiguous command. The attestations require actual session evidence; USB device number alone cannot establish continuous power.

[verified] 60 syscall/refusal tests passed in 16 parallel Hera containers, all exited zero with no OOM. An initial run lacked a staged dependency and failed collection; the corrected run passed. Real evidence-only preparation initially stopped on missing staged source files, then passed after copying the original reviewed firmware/source dependencies. No device commands were issued during these failures. Both semantic tools select the primary checkout, where these branch-only Python files do not exist; their bounded queries failed, so source inspection was used without changing the shared project.

[verified] At Pi time 1791860791.8018296, the durable log recorded one `fc0c00000001ffffffffffffffffffff` submission intent. The SG ioctl returned; the subsequent topology check found the device gone and recorded `reset_stopped_ambiguous`. This is preserved as ambiguity, not rewritten into a successful transport receipt. The owner subsequently reported the expected bands. No second request was sent.

Private Pi source/campaign: `/home/claude/fm1-repeat-boot-v1-20261012-source`; adapter SHA256 `74497d2fa5a697a8472ea4d8fcabd7b99ad01daffa96dde062a89357213bd5fc`; campaign SHA256 `e97feaca16efca80733b61696157998f4479d3663696fce0aaeffac2ad9043fd`.
Receipt: `/home/claude/fm1-sdk-trace-entry-20261012-v8/stock-backup-001/returned-target-backup-001/repeat-boot-001`.
Hera verification: `/home/claude/mvave-fm1/repeat-boot-16-v2-20261012/verification.json`.

The original unused stock-restore packet is now stale following this boot and must not be executed. Fresh returned-loader admission/bindings and backups are required for later flash operations. Preserve the running image and recovery evidence while continuing the SDK-free native Lunar integration.

[verified] After the display run, passive USB enumeration showed mask ROM `4c4a:8057`, bus 1 device 14, port 1-1. This does not establish a new RAM-loader admission. Packetry capture was stopped through computer use and saved privately as `build/repeat-boot-16-v2-20261012/cynthion-v8-repeat-display-pass.pcapng`, SHA256 `8a29500050b808bae08968ce034a435bf13038ccde56a32d6ac8e3997879f94f` (947,527 packets; 4,985 transactions). No target-power toggle was used.
