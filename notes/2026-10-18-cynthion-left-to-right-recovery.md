# Corrected FM1 power-on direction recovery-key test

[reported: owner checked other videos, 2026-10-18] RIGHT is ON; LEFT is OFF.
Previous RIGHT-to-LEFT trials ended OFF. This corrects the previously unknown
switch orientation; it does not establish the owner's processor supply voltage.

[verified: direct owner instruction] Owner requested: “Prepare another test
going LEFT to RIGHT and tell me when you’re ready.” Scope is one bounded
recovery-key test with corrected power direction and passive enumeration,
not flash, restore, loader upload or arbitrary vendor commands. This named
request follows the replacement AGENTS strict gate; preserve the dump/restore
precondition for any later writes rather than interpreting this test as a
blanket exception. No firmware erase/program operation is authorized here.

## Prepared image and preconditions

Same previously reviewed operation image, not a changed key waveform:
`scratch/cynthion-usb-key-20261016/debug-readback-control-power/cynthion_usb_key.bit`,
SHA-256 `b3b2037bf2e7e743c0d8ade268a22c5e8f9ef3859426bf7f10e3951c56c56a2e`.
Root rechecked its hash. Both TARGET ports were last explicitly confirmed empty
and no reconnection occurred in the conversation before this reload. CONTROL
remains connected to Mac. Root volatile reload completed exit0. New logs and
readbacks reside in `scratch/cynthion-left-to-right-recovery-20261018/`.

The preceding unloaded control completed30000 packets with no candidate ACK,
WAIT_DP0 and SOF0, then released outputs at the packet limit. The connected
attempt7 instead stopped at832 packets and timed out waiting for J. Neither
proved ROM entry. Powering OFF after a possible response could explain the
missing J; this remains a hypothesis until the corrected-direction test.

## Staged physical procedure

1. Root verifies freshly loaded SAFE, PHY ready/no fault and both OEs off.
2. Keep CONTROL to Mac, TARGET C empty. Set FM1 switch LEFT/OFF and connect
   FM1 to TARGET A using the verified data cable. Do not press USER. Confirm
   connection so root can verify still disarmed before any keying.
3. Only after that check, owner presses/releases USER once and immediately
   moves FM1 LEFT/OFF to RIGHT/ON. Leave it RIGHT/ON and report done.
4. Root reads the terminal receipt and frozen event history, verifies released
   GPIO outputs, and distinguishes candidate ACK, J, SOF and terminal outcomes.
5. Root requests TARGET C to bench01 only after both OEs are confirmed off,
   then checks application/OTA/mask-ROM enumeration. No loader/flash command.

No automatic retries, KEY restart after ambiguous ACK, blind SOF modification,
or inference of recovery from a timer or charging indicator. No physical step
is assumed complete from elapsed time. Keep a blank screen distinct from USB
bootloader evidence; successful recovery requires actual identity/enumeration.

[verified: read-only sweep 2026-10-18T07:20:57.984508+00:00 to 2026-10-18T07:21:06.183619+00:00]
LUNR/layout6 status `0x4410`, SAFE0, PHY ready/no fault, both OEs0,
terminal0; state/GPIO/terminal/ring unchanged across sweep. Ready for the
connection-only step with FM1 LEFT/OFF and TARGET C empty; USER not yet.

## FM1 connected while OFF; SAFE verified

[verified: owner] FM1 connected to TARGET A, switchLEFT/OFF, TARGET C empty,
noUSERpress. At07:22:21–28UTC, LUNR/layout6 status0x4410/SAFE before and
after read-only sweep; PHYready/no fault, GPIO0/OEs0, terminalreceipt0.
Event ring changed during the sweep (expected live capture); do not call the
whole sweep atomic/stable. Safety status, GPIO and terminal markers matched.
Raw `scratch/cynthion-left-to-right-recovery-20261018/connected-left-disarmed-status.json`.
Owner now requested USER once then immediateLEFT/OFF→RIGHT/ON, leaveRIGHT;
TARGET C remains empty until terminal outputs are confirmed released.
