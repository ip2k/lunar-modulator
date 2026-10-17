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
