# Event120 device-42 repeat read and boot adapter

Date: 2026-10-14
Branch: codex/2026-10-14-event120-device42-repeat

[verified] Added device-42-specific copies of the Event120 dual-ROM-read and repeat-boot adapters, with matching focused offline tests. Device 42 is the USB enumeration binding (VID:PID 4c4a:8057, bus 1, path 1-1); it is not a firmware version. Both adapters bind the same expected full-flash digest 145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657, the existing reviewed 8,757-operation command inventory digest f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017, and the retained source pins for the fixed loader, reader, reset target, and completion modules.

[verified] The read adapter requires a fresh passive snapshot no older than 120 seconds, exact USB/SG mapping, dual complete 1 MiB dumps matching the fixed digest, and a private mode-0700 receipt root. Its consumed marker is bound to this exact enumeration; flash operations, resets, boot, and recovery claims remain false. The boot adapter requires a fresh same-connection snapshot, verified read bundle and unchanged no-later-command transcript, the exact 42 binding, and the single existing FC0C request. It reports request completion only; processor reset, app boot, install history, and physical recovery remain unproven.

[verified] Focused checks ran in pinned lunar-preload-tests:20261014 (image SHA256 1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313), bounded to 2 CPUs, 3 GiB memory/swap, 256 pids, network disabled, and docker-batch.slice, with pytest dependencies mounted read-only. Command: /usr/bin/python3 -m pytest -p no:cacheprovider -q tests/test_event120_device42_repeat_boot.py tests/test_event120_device42_repeat_read.py; result: 13 passed.

[verified] These were offline unit/contract tests. No read, reset, USB, MIDI, flash, power, or reboot command ran in this task. The root coordinator has separately reported a passive lsusb observation of bus 1 device 42 and the presence of a Pico2W; this note does not independently verify those observations or authorize a read.

Next step: coordinator reviews the exact campaign and evidence paths, performs fresh passive enumeration/snapshot capture, and decides whether to invoke the bounded read and repeat-boot adapters. The repeat boot is diagnostic only and does not install firmware.
