# Physical preparation-stop trace preservation, v2

[verified: actual retained receipts] One distinct bounded reader completed on
the owner's powered FM-1, USB bus1/device10, in UBOOT. All five replies are
saved privately: INQUIRY, trace, stage, trace, stage. No loader upload, reset,
NOR command or retry was sent by this reader. The original v1 expired packet
was not reused. V2's consumed marker must not be deleted or replayed.

The actual campaign is a91fe230df0c00418ac269cd46285d83026eb42290e5568d21466e3b81ed7dac;
the preparation-stop envelope is 9abc4264bbb20a7392495ea8aa63919e03e2ccb3d89e06dc169b9c75c2324a3d.
The reader ran at1791847034.1318064–1791847034.5883102; its owned capture
stopped at1791847034.6706986. Native logs contain five ioctl intents and all
replies agree with the outer journal. Both trace reads and both stage reads
match. USBmon independently has four expected FD07 requests, five standard
commands and50 bulk records, without terminal transfer ambiguity. Its
captured prefixes do not prove the full RAM payload or process origin.

[verified: decoded retained bytes; attribution conditional] The record has
phase5 (`final-start-intent`), stage6, sequence10, elapsed20,000ms, heartbeat1976,
mailbox_verified1 and panel_result0. Reported clocks are360MHz system/60MHz LSB;
startup reason is unavailable. These values do not establish a fresh boot,
visible display, retention, reset cause, or physical recovery. The reported
system clock is a concrete item to investigate against intended clock setup.

[verified: live UI and saved file] Packetry was controlled through Computer
Use, stopped and saved without toggling Target Power. The saved Cynthion file
is1,228,552 bytes with SHA256
dad6373338d77f4522ff5954b235aacc3118484c6bbfbe5ea95ad18445f90b2d.
Offline framing checks find34,056 enhanced packet blocks; Packetry displayed
34,058 packets. The difference is retained without attributing a cause.
The capture began in ROM mode without enumeration and displayed Unknown.

Private bytes remain under
`build/preparation-stop-trace-physical-v2-20261012/`; the original Pi paths are
`/home/claude/fm1-stop-trace-capture-v2-20261012/run/` and
`/home/claude/fm1-sdk-trace-entry-20261012-v7/stock-backup-001/physical-distinct-preparation-stop-trace-v2/`.
No vendor image, device backup, RAM reply or pcapng is committed. The saved
source preparer and offline replay are in this note directory. The replay
summary is `physical-v2-replay.json`.

[verified: source/model scope] The new pure capture receipt kernel accepts the
original stop-capture schema. Sixteen distinct cases passed in16 concurrent
Hera containers, including semantic corruption after resealing hashes. All
containers were inspected, exited0 and removed; none remains. Exact source
and receipt hashes are in `capture-receipt-verification.json`. Actual physical
receipt, capture lifecycle and wire replay pass independently. This kernel
does not grant loader/recovery authority. A canonical post-read recovery
factory remains required before the overlapping loader upload.

Rarefaction and Serena currently select the primary checkout; the bounded
queries could not find these worktree-only Python files. No shared project
retarget or semantic edit was made; source inspection used the actual worktree.

Next: compose the genuine stop proof with frozen read/capture/source/marker
evidence, verify the explicit recovery successor, then fresh dual backup,
stock restore and the next physical diagnostic boot/display acceptance.
Preserve the current device state and all consumed markers. No owner power
cycle is required for these preparation steps. The overall goal is active.
