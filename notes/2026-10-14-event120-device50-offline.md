# Device 50 Event120 repeat-read and boot adapters

Date: 2026-10-14
Base: coordinator-audio-capture-20261014, `68c7a51d7edf5dff54da9bd87d57d856ba9c0b16`
Branch: `codex/2026-10-14-event120-device50-offline`

This offline-only task adds separate read and boot adapters for the newly enumerated device 50, following the reviewed device 48 transaction contract. It does not run either adapter against hardware.

The read adapter is `tools/fm1_event120_device50_rom_backup.py`. It binds USB path `1-1`, bus `1`, devnum `50`, VID:PID `4c4a:8057`; requires a fresh passive snapshot with matching sysfs SG mapping; pins the same fixed loader, profile, source files, 8,757-command inventory, and installed-flash digest as the device48 proof; and requires two complete 1 MiB reads with the expected SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. It records no flash or reset operations, keeps install/recovery claims false, and consumes an enumeration-specific `.event12050-rom-<identity>.consumed` marker.

The boot adapter is `tools/native/event120_device50_repeat_boot.py`. It verifies a completed device50 read bundle, the exact reader-adapter raw SHA-256 `65f76ce56cffac284c16a2a003067b1db40456f9d57d580bbfb4d61ed8943c87`, source and inventory pins, two matching dumps, transcript/replay, fresh boot-stage snapshot, and unchanged USB/SG mapping before an opener can be reached. The campaign kind, boot snapshot kind, active-session label, markers, module namespace, and log event names use device50. It sends at most one existing reviewed FC0C argument-1 reset through the completion-first adapter; ambiguous/incomplete completion remains latched and is not retried. It does not claim that enumeration or command acknowledgement proves the firmware booted.

The preserved source chain is:
- `fm1_fixed_loader_backup.py`: `79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb`
- `fm1_returned_rom_backup.py`: `afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be`
- `fm1_uboot_read.py`: `28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57`
- fixed command inventory: `f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017`
- fixed loader payload: `fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c`
- target/current flash digest: `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`

Validation on Hera: `pytest -q tests/test_event120_device50_repeat_read.py tests/test_event120_device50_repeat_boot.py` passed 27 tests. `py_compile` for the two adapters and tests passed; `git diff --check` passed. Tests cover exact device50 binding, device48/other-devnum snapshot refusal, full dual-read accept/refuse cases, enumeration-bound one-use markers, source-pinned tool loading, pre-open refusal, same-connection mapping, one-shot reset and ambiguous no-retry behavior.

Limits: this is host-side contract coverage only. No live USB/SG enumeration, read, reset, flash, power, or reboot command was issued. Device50 remains unproven against the installed digest until the coordinator independently captures fresh passive state and runs the staged campaign. A successful SG reset reply would still not establish boot or audio acceptance.

Semantic-tool coverage: Serena and Rarefaction were queried, but both selected the Mac primary checkout (`/Users/likwid/Developer/mvave-fm1-firmware`), not this Hera worktree. The shared Serena project was not retargeted; source inspection and tests were done directly on the assigned Hera checkout instead.
