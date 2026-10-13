# Physical completed-trace recovery

Personal, non-commercial. Source checkpoint: `93d5f2b83b12468c68a39c65917607819c6d3744`.

[verified: actual Pi receipt] A distinct completed-trace admission uploaded the
reviewed fixed RAM loader and completed two matching 1 MiB NOR reads, 8,757
commands, zero reported errors. Both dumps match the installed diagnostic target
`5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d`.
There was no erase/program/reset/retry in that backup. Existing consumed markers
were preserved; no predecessor authority was replayed.

[verified: reviewed private derivative] Canonical backup and restore dependency
pins remain `None`. Private activation changes exactly their reviewed dependency
literal and verifies that reversing that substitution restores the canonical
source. The backup derivative SHA is
`1be3a3fef0b026b381aa1bd6e3fea5545896a2a181fa0150df108e8e11a66819`;
the restore derivative SHA is
`dee2524fa85bc9936921636ce55ec6a2c2f7aaed0fe334946c871687c6626b9a`.
The reviewed 16 backup/16 restore model chunks remain separate evidence from
these physical operations.

[verified: computer use and file framing] Packetry was controlled through the
computer-use plugin. The dual-backup capture is retained privately as
`build/completed-trace-physical-20261012/cynthion-dual-backup.pcapng`,
48,484,556 bytes, SHA
`3126196a726f7f59da850425974423e3d5782fe0ea58ae3c0ed79352928f1c81`.
Every pcapng block has matching lengths with no truncated tail; 1,276,250
Enhanced Packet Blocks were counted. This is framing verification, not a
claim that all captured USB transactions were decoded or independently replayed.
Target power was not toggled. Packetry's capture is supplemental evidence;
it does not replace the adapter's SG completion and full-image readback checks.

Private Pi root: `/home/claude/fm1-completed-trace-recovery-20261012/run/`.
Actual backup receipt:
`/home/claude/fm1-sdk-trace-entry-20261012-v7/stock-backup-001/physical-completed-trace-backup-001/`.
The private full evidence archive includes vendor bytes and must remain ignored.

[verified: zero-command preflight] Restore campaign SHA
`001a97f2fcb756e0ef11fec049330ae7ba92ef9a9f132bc1782d8472debb44d6`
passed its file-only preflight. Its one-time execution wrapper started under
an owned USBmon capture and a fresh running Cynthion capture. The initial full
diagnostic target read passed before any write. The fixed plan restores 29
application sectors, then directory sector 0x4000 last, with per-sector and
full-image readback. [verified: physical receipt and strict replay] Execution exited zero. All
10,836 SG commands completed successfully, with no reset/retry. The final
full-flash hash matches stock baseline
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
The evidence-only completed-restore verifier passed with 715 frozen evidence
entries and zero USB opens or commands. The restore capture has complete
pcapng framing, 75,917,676 bytes, SHA
`5dc34b6ba27051e851553115010abf4515bcf335166ba3b163629b1aa6dd54ae`.
Structured results are in `physical-verification.json`. No reset has been sent;
retain this completed loader session for separately admitted stock boot.

Physical stock boot, fresh diagnostic boot, visible pixels and recovery after
corruption/interruption remain required acceptance gates. A full stock hash
alone would establish restored bytes, not successful boot or recovery.
