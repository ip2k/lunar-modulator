# Device 40 Event120 repeat adapter review

Date: 2026-10-14
Worktree: /home/claude/worktrees/event120-repeat40-adapter
Branch: codex/2026-10-14-event120-repeat40-adapter

This offline adapter adds a separate read-then-reset attempt for the current device-40 identity. It does not claim installation history, app boot, processor reset, recovery, nor permission to install firmware.

The read stage is bound to the exact 8,757-operation fixed ROM inventory, fixed loader/tool sources, passive USB/SG mapping, and the expected 1 MiB flash digest 145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657. The two retained dump files must each have the exact length and digest and match one another. Its consumed marker is now derived from canonical USB and SG mapping, rather than the timestamped snapshot hash. Refreshing a snapshot for the same mapping cannot reopen that enumeration.

The reset stage replays the read manifest and full command transcript, re-hashes retained source/evidence, requires a new passive boot snapshot observed at or after read completion, and compares the exact USB/SG mapping before it creates the one-use marker or opens the SG node. The live mapping and opened node identity are checked again before the sole FC0C request. A completed ioctl response reports request completion only; core reset and boot remain false. Ambiguous responses latch failure, close the descriptor, and cannot be retried through the same session or campaign.

Two timing rules are intentional: the original ROM snapshot is checked for freshness at the first read-prepared transcript timestamp (a full dual read may exceed 120 seconds); the boot-stage snapshot must be fresh at reset preparation and no earlier than read completion. This requires a new physical passive observation between stages but does not assert continuity beyond the campaign's explicit operator attestation and same USB/SG mapping.

The helper fm1_event120_rom_backup.py is found at tools/fm1_event120_rom_backup.py, not beside the reset adapter under tools/native. Its exact SHA is checked before it is accepted as retained source evidence. The boot adapter no longer imports or executes that helper at module import. Reset modules are loaded only after their fixed source hashes are checked.

## Focused checks

Command on Hera:

    /home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q tests/test_event120_repeat40_boot.py tests/test_event120_repeat40_read.py

Result: 10 passed. Coverage includes malformed-policy no-open, changed device number, same-enumeration one-use despite changed snapshot timestamps, reset completion without boot claims, and ambiguous-reply no-retry/close. These are offline mocks and do not establish live USB behavior.

The coordinator owns bench01 and must independently review the finalized campaign schema and all evidence before any physical operation. No device commands, hardware access, flash operations, or reboot were performed by this task.
