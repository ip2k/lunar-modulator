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
## Follow-up: dependency-root correction

Independent review found that the reset adapter is under tools/native, while its fixed reset modules live under tools/ and tools/native/. prepare() now passes the declared ROOT (tools/) to _target_modules() and freezes fm1_fixed_target_reset.py, fm1_fixed_loader_reset.py, and native/event120_reset.py from that same root. This aligns dynamic source loading and frozen evidence with the actual repository layout and the existing SHA pins.

A positive prepare() test uses the real adapter/module files and their pinned hashes, with a temporary private evidence root. It reaches successful preparation without opening /dev; a second test changes the live discovered SG mapping and confirms rejection before any /dev open. The preparation check binds the discovered mapping to the passive snapshot. The session re-discovers it before opening the descriptor, then validates the opened descriptor identity and rechecks binding before the one reset request. These checks reduce mapping races but are not atomic with kernel topology changes and do not establish physical behavior.

Updated focused command on Hera:

    /home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q tests/test_event120_repeat40_boot.py tests/test_event120_repeat40_read.py

Result: 12 passed. Offline test evidence only; no hardware was accessed and no USB, MIDI, flash, reset, or reboot command was issued.

The offline adapter pins and validates source, campaign, manifest, transcript, and mapping inputs during preparation and before opening the SG node. It does not hash the full read evidence before every one of the 8,757 read commands; that repeated work would exceed the operation deadline. The coordinator must stage these inputs in a root-owned mode-0700 evidence directory and keep them immutable for the attempt. This operational control is not a filesystem immutability guarantee; concurrent privileged mutation remains outside the adapteréÝyø§yÙs proof.

Semantic-tool limitation: Serena and Rarefaction were checked, but both reported the Mac primary checkout rather than this Hera worktree. They were not retargeted because their selection is shared; this change was navigated and tested with direct source inspection.
