# Cynthion empty-target recovery-key timing control

[verified: source, artifact hashes and independent source review]
This is a disconnected control experiment, not another FM1 key attempt.
The owner was asked to unplug both TARGET ports, leaving CONTROL to Mac only.
Do not load until that confirmation arrives. The FM1 must remain disconnected
throughout the run. No flash, FM1 key, power or reboot command is involved.

## Reason

Attempt7 stopped after832 packets (about0.4s), reporting a candidate ACK,
then500ms WAIT_DP timeout with SE0 and no SOF. The timestamp of the owner's
switch movement is unknown. The candidate may be an FM1 clamp or a receiver/
waveform artefact; it is not proven ROM acknowledgment. Do not automatically
resume keying after a possible ACK or generate blind calibration pulses.

With both TARGET ports empty, a candidate ACK would demonstrate a false-positive
risk without an FM1. Absence of a candidate only narrows this unloaded condition;
it does not prove the connected case's candidate genuine or establish recovery.

## Pinned existing image

Directory: scratch/cynthion-usb-key-20261016/debug-readback-control-power/.
Source62ca873fb1c54975902376cdc7d557674c06d0e8. Root compared current top.py,
gateware.py and gateware/ulpi_safe_phy.py byte-for-byte with that source.

| Artifact | SHA-256 |
| --- | --- |
| cynthion_usb_key.bit | b3b2037bf2e7e743c0d8ade268a22c5e8f9ef3859426bf7f10e3951c56c56a2e |
| cynthion_usb_key.json | c804c8419b4f46f25f812f1da4abd5f5a4e11fd7e1a88938aba623a852071378 |
| cynthion_usb_key.lpf | 7779409006f61ba755ff3ebf07e16ec64d75c2abe2674da2c23a077821d4e0c3 |
| cynthion_usb_key.tim | 25a2c1b57d5a7749d5af5b22d9956e3723b2ce69e5fa03fb061a2834df6a5179 |

All four hashes rechecked by root. Retained routed timing meets60/120MHz:
66.68/212.77MHz. Retained netlist power constants CONTROL1,C0,AUX0,discharge0.
Previously reviewed operation image stays SAFE until USER.5ms debounce,
1us ARMED, four1ms self-tests then KEY. There is no10s software arming timeout.
Packetlimit30000 bounds the key train to about14.4s; WAIT_DP is500ms; SOF is
separately bounded. Terminal DONE/FAULT releases both GPIO outputs. A floating
empty bus might enter SOF; there is no attached target in this control.

## Steps and limits

1. Owner confirms both TARGET ports empty, CONTROL to Mac; FM1 disconnected.
2. Coordinator volatile-loads the pinned existing image, then reads layout6
   identity/status and verifies SAFE, PHY ready/no fault and both OEs off.
3. Owner presses/releases USER once with both TARGET ports still empty.
4. Coordinator captures terminal receipt, packet count, event ring and PHY
   diagnostic. Verify DONE/FAULT and both OEs off; do not infer ROM success.
5. Review result before preparing any connected experiment. Do not reconnect
   FM1 or host to TARGET ports while the result/state is unknown.

Read-only capture helper retained privately:
scratch/cynthion-empty-target-control-20261017/read_status.py,
SHA9cf9a39c59c22a3beb305beef0e533c2765bb56e08c1582a6951602e22d1961c.
It checks LUNR/layout6 before reading the known register map and labels sweeps
non-atomic. It compares state/GPIO/terminal/ring markers after the sweep. No
register write or arm API is used. Python syntax check passed. Semantic MCPs
selected the primary checkout, not integration; no shared retarget performed.
Source review therefore used explicit integration files and git object bytes.

Status: PREPARED; no load or USER attempt performed for this control yet.

## Volatile load and disarmed readback — 2026-10-18

[verified: owner] Both TARGET ports empty, CONTROL remains connected to Mac;
USER not pressed. Root loaded the pinned174763B bitstream via `cynthion run
--bitstream`; exit0, upload complete. Bitstream SHA recheckedb3b2037b…c56c56a2e.
Read-only capture at07:11:41–49UTC: LUNR/layout6, status0x4410, SAFE(0),
PHYready/no fault, bothGPIOOEs0, terminalreceipt0. State/GPIO/terminal/ring
markers unchanged across the non-atomic sweep. Saved
`scratch/cynthion-empty-target-control-20261017/disarmed-status.json` and
`volatile-load.log`. Owner requested one USER press with targets still empty;
awaiting confirmation. No FM1 commands or writes.

The owner's replacement AGENTS instructions on2026-10-18 reinstate the strict
FM1 dump-and-byte-identical-restore precondition and identity/passive-only
traffic before that gate. This disconnected Cynthion control does not touch
the FM1. Before any future connected active experiment, resolve that gate
against actual evidence/current explicit authorization; do not rely on the
older relaxed AGENTS wording alone. No AGENTS/CLAUDE overwrite performed.

## Unloaded control completed — 2026-10-18 07:12 UTC

[verified: owner USER press plus stable terminal register sweep] Both TARGET
ports remained empty. At07:12:39–48UTC root read LUNR/layout6, status0x47d8,
FAULT8, GPIO0 (both OEs off), all four self-tests passed (maskF, observedC6,
events01010101). Terminal receipt0x843 decodes packet-limit reason1, origin
GAP4, terminalFAULT8. Completed30000 packets, WAIT_DP0us, SOF0us. No candidate
ACK was latched. PHY timeout diagnostic was not requested (allzero). Event
ring frozen with32 entries; state/GPIO/terminal/ring stable across sweep.

Raw capture `scratch/cynthion-empty-target-control-20261017/post-user-status.json`,
SHA `5cebe5db1f60c4725706c64c7b009f7cbdd8f6a0f6ffe4047d51d7439926626d`.
Comparison retained at `scratch/cynthion-empty-target-control-20261017/attempt7-comparison.json`.
The final ring has10 KEY events with both outputs high/enabled and PHY SE1,
versus attempt7's4 such SE1 events and8 K events under the same GPIO snapshot.
These are event-on-change records from the final32 entries, not uniform
sampling or analog voltage measurements. The comparison does not establish
when the FM1 switch moved or prove a ROM-generated clamp.

[verified] The same image does not reproduce the early candidate under this
unloaded control. [inferred] The connected target/cable/loading or state
changes the observation; a valid ROM ACK remains unproven. Do not call packet
limit a recovery success. No automatic key restart or blind SOF is justified.

Current: Cynthion terminalFAULT/high-Z, both TARGET ports empty, CONTROL to Mac.
Keep FM1 disconnected pending the next reviewed test. No FM1 traffic occurred.
