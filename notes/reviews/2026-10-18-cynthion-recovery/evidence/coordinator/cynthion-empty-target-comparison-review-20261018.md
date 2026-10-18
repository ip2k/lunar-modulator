# Empty-target USB_KEY control: comparison and gated next step

Read-only comparison of the owner-operated disconnected control result with attempt 7. No hardware, USB, key, power, flash, or firmware operation was performed by this reviewer.

## Evidence pins

- Worktree HEAD: `1f12ad5b8d6a865268af94179a3442183a680602` at review time; this checkout also had coordinator-owned edits in `HANDOFF.md` and `notes/2026-10-17-cynthion-empty-target-timing-control.md`. I did not modify them.
- Empty-target post-USER capture: `scratch/cynthion-empty-target-control-20261017/post-user-status.json`, SHA-256 `5cebe5db1f60c4725706c64c7b009f7cbdd8f6a0f6ffe4047d51d7439926626d`.
- Empty-target disarmed capture: `scratch/cynthion-empty-target-control-20261017/disarmed-status.json`, SHA-256 `44411b8b0bf45265ab861165e364c5c07beb11dcb748dd99d2e8dfef881131f9`.
- Attempt-7 terminal capture: `scratch/cynthion-usb-key-20261016/debug-readback-control-power/owner-attempt-7-status.json`, SHA-256 `a7840f19f447966955ce763b8faa558842446fd567dc2ea7599455650d64021d`; review detail is in `scratch/cynthion-usb-key-20261016/attempt7-waveform-review/HANDOFF.md`.
- Operation image receipt: `scratch/cynthion-usb-key-20261016/debug-readback-control-power/build-receipt.json`, SHA-256 `2428eea737e17cd5f4c0c90ffba493d70bc4b108ee27cae1bb7f3eb47e858d52`. Coordinator verified the exact existing bitstream and source/netlist/LPF/timing pins; I relied on that check.
- Source hashes: `tools/cynthion_usb_key/top.py` `02f8436d59ce9cd571bd467685d40f36d7c628b6f5aad79bd964e3ddbd2f1d26`; `tools/cynthion_usb_key/gateware.py` `5f0e9309cdcd77a8cf7b623ee7f1c71e4b4f2dad8402c8836926494539aaedda`.

## What the disconnected result establishes

With both TARGET connectors empty and CONTROL connected to the Mac, the disarmed snapshot was SAFE with both GPIO output-enables off. After the owner's single USER press, the same pinned image completed its self-test and drove the bounded key train. It ended after 30,000 packets in FAULT due to packet-limit reached from GAP (`register 0x0c = 0x843`); ACK was not latched, WAIT_DP and SOF progress were zero, and GPIO OEs were zero at terminal. The ring froze and status/GPIO/terminal/ring markers stayed stable over the read sweep. The event evidence shows line-state changes during driven symbols and SE0 in released gaps, but no 100-us active-key SE0 candidate. `receiver_live` was set; the terminal ACK-progress value was 1 (live, no latched ACK, zero ACK ticks).

Attempt 7 differs: it reached the candidate-ACK transition at packet 832, then waited 500 ms for J, timed out in WAIT_DP, and recorded SE0 with SOF=0. Its event ring showed the candidate while keying was active, with a K observation under the driven GPIO snapshot near the end. Thus the empty test rules out the narrow hypothesis that this build's key waveform plus the unloaded receiver alone reproduces attempt 7's candidate-ACK transition. The earlier candidate depended on something present in the connected setup—FM-1-side line loading, power state, wiring/contact, or a genuine target response are still alternatives. The comparison does not identify which one. The missing post-ACK J transition means attempt 7 still did not demonstrate a completed ROM-entry sequence.

## Next step and authorization boundary

The Oct 18 owner replacement instructions, as relayed by the coordinator, reinstate a strict fresh-dump and byte-identical-restore gate, allowing only identity/passive checks before that gate. No connected active FM-1 key experiment is currently authorized. Do not attach the FM-1 or repeat keying based on this control result. First have the coordinator resolve the exact current gate and permissible path to satisfy it. If the gate permits it, the next evidence sequence is: fresh passive device identity/state; a fresh paired full-flash read with exact-match verification and preserved private backups; then the required byte-identical full-image restore and verification under an owner-reviewed transaction/recovery plan. Only after that gate is actually satisfied and active experimentation is explicitly authorized should one bounded, timestamped connected key trial be considered. Capture the same event ring and independent connector-side power/state evidence so a target-side clamp can be distinguished from the required post-key J/pull-up. No blind retry or post-ACK SOF change follows from these observations.

If no approved route can acquire the required fresh dumps without first violating the strict precondition, stop and ask the owner to resolve that policy deadlock; historical backups or this disconnected control do not satisfy the new gate.

## Limits

This comparison is based on two non-atomic JTAG register sweeps and retained event-ring snapshots, not an oscilloscope capture or direct connector voltage measurement. It establishes an absent candidate in the unloaded CONTROL-only run and a candidate in the prior connected attempt, not FM-1 ROM behavior or current device condition. No tests or physical actions were run by this reviewer.
