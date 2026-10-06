# Read-only soft-key test plan for the owner's FM-1 (DRAFT for owner review, 2026-10-05)

**Status: draft. Nothing in this plan may be done until the owner has read it and decided the questions at the end.** It amends CLAUDE.md's one rule for a single read-only session, and only if the owner says so. The findings behind it are in [notes/2026-10-05-softkey-efuse.md](2026-10-05-softkey-efuse.md).

READ-ONLY TEST PLAN for the owner's unit (FM-1_092). Every step needs the owner's decision first (see the questions at the end).

A. Preconditions
1. Owner decision: amend the one rule for this one session to allow:
   - the soft key;
   - ROM FB06 into RAM only, at 0x01C02000-0x01C07DFF;
   - FB08 to 0x01C02000 with arg 0x0001;
   - loader FC14, FC0A and FD05 only.
   Record this in notes/.
2. Host tool: our own, reviewed, stdlib-only tool (e.g. tools/fm1_uboot_read.py). Not fm1t.py.
   - It sends only commands on a whitelist, and checks every argument (addresses, lengths, 0xFF padding).
   - It refuses FB00/01/02/04/42, FD07, FC0C/0D/12/16/40-48/83/84/9D/A0/A1, and any standard SCSI write, format or mode select.
   - It refuses to send the soft key unless the identity read in the same run is FM-1_092 and a confirm flag is given.
   - It has unit tests against a simulated UBOOT, like the dongle co-simulation.
   - Preferred host: Linux (aeon, a Pi or a live USB), using SG_IO on /dev/sgN, with the soft key sent by ALSA rawmidi as one write() call while nothing else holds the port (trap 5).
   - Alternative: an RP2040 running a reviewed read-only build of FM-1-transporter's firmware (writes and RAM-run compiled out).
   - Avoid macOS direct: the kernel driver claims the disk, Finder may offer 'Initialize', and detaching the driver needs root.
3. Rehearse the whole session first on the AC79 dev kit when it arrives (same chip). Do this before touching the FM-1.
4. On hand, with SHA-256 checked:
   - FM-1_092.fwsc (ed8415f3…) and stock V15 FM-1.fwsc (db1642b2…);
   - M-UPGRADE and Baud Girl's installer;
   - the USB_KEY dongle built and self-tested.
5. Battery ≥80 %; FM-1 plugged straight into a root port (no hub); usbmon / Wireshark capture running (passive, allowed).

B. Session 1
1. Power on and wait 15 s on the home screen. Stop playback; no edits, no saves.
2. Read the identity with tools/fm1_identify.py: expect FM-1_092. Save the reply.
3. Send the soft key once: F0 22 24 35 7D F7. In the capture, confirm a single 8-byte OUT transfer `04 F0 22 24 07 35 7D F7`.
   - If nothing happens within 3 s, it was probably packed differently. Do not resend more than once, and never send 7F.
4. Watch enumeration: C755 disappears (~20 ms), then 4C4A:8057 'WL80UBOOT1.00' appears (~1 s). Record descriptors and INQUIRY (WL82 / UBOOT1.00 / 1.00).
5. Upload the loader: FB06 × 47 blocks (raw, already-ciphered wl82loader.bin with its pinned SHA-256), then FB08 to 0x01C02000 with arg 0x0001.
6. FC14, then FC0A: expect type 3 and ID 0x856014. Keep FC0A as a keepalive at ≤1 s intervals.
7. FD05 over 0x000000-0x0FFFFF → dumpA.bin. Immediately again → dumpB.bin.
8. Check SHA-256(dumpA) == SHA-256(dumpB). Write a manifest with the hashes, timings and command log.
9. Send nothing more. Switch the FM-1 off, wait 5 s, switch it on.
10. Read the identity: expect FM-1_092. Check the screen and the GLOBE settings.

C. Session 2 (optional, on a later day)
1. Repeat B to get dumpC.
2. dumpC must equal dumpA over [0, 0xD9000) (code and PRCT) and over BTIF/USR/key_mac. VM [0xD9000, 0xE9000) may differ if 092 saved settings.
3. Compare [0, 0xAE000) with the 092 .fwsc flash entry with only the UFW layer removed. Do not compare with decrypted.bin, which is chip-key-deciphered. Investigate any mismatch before going further.
4. Store the dumps privately; never commit or publish them.

D. If it does not come back
- No UBOOT and the screen is frozen or the app runs without USB (expected after a warm reset): power-cycle, then identity. Nothing was written.
- UBOOT appears but the upload or jump fails: power-cycle.
- After a power cycle the FM-1 shows as 4D4A:4155 'ota-FM-1': resume with the 092 or V15 package through Baud Girl's installer or M-UPGRADE.
- Blank after a power cycle (not expected): power-cycle again. If 8057 appears by itself, stop and read only. Otherwise use the USB_KEY dongle (docs/10 §6) to reach UBOOT and dump.
- Any restore waits until the gate is met (rule 1).
- Settings lost: re-set them; presets live in USR.

E. Never send
- F0 22 24 35 7F F7.
- syscmd 33-36 or 48; 5A AA A5 frames.
- More than one soft key per boot.
- Any loader opcode outside the whitelist: FB00/01/02/04/42, FB06 outside the loader range, FB08 to any other address, FD07, FC0C/0D/0F-13/16/40-48/83/84/9D/A0/A1.
- Any config block after the loader, or CDB bytes 6-7 = '_' '0' in FC0A.
- Standard SCSI WRITE/FORMAT. Never click Initialize.
- Never unplug the cable mid-session.

F. Dongle-less restore (only after the gate is otherwise satisfied, with USB_KEY proven on this unit first)
Requirements:
- a running 7D-capable app;
- verified dumps of this unit;
- an extended whitelist adding FB01 (4 KiB sector erase) and FB04, all in one session;
- write only sectors that differ, never [0, 0x4000) and never key_mac;
- write VM, BTIF and USR only from this unit's own dump;
- read back every sector, write the directory sector last, then do a final full read;
- a full battery and no hub.
Writes use the raw dump bytes (chip-key form). Prove it first by rewriting one unused sector with its own bytes, as the transporter did on V15. Candidate: [0xAE000, 0xD9000) if the dump shows it unused.
Risk: an interrupted app-sector write removes the soft key, which is why USB_KEY must be proven first.

Questions for the owner:
(a) Do you allow the soft key and the RAM loader upload and run under the one rule, for read-only dumps?
(b) Which host: Linux SG_IO tool, or an RP2040 read-only transporter build?
(c) Rehearse on the AC79 dev kit before the FM-1?
(d) Is losing VM settings to a mid-save reset acceptable?
(e) Should I draft the doc corrections (the base address 0x02000120; AL-255's 0xFFC0xxxx targets are RAM; the soft key exists in stock since V13) for CLAUDE.md, docs/01/03/07/10?
(f) Should I write the read-only tool and its simulator tests on a branch?
