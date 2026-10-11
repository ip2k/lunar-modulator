# Fixed-loader physical full backups, 2026-10-11

[verified: bench01 execution and private copied receipts] The owner's FM-1
returned its exact known `FM-1_092` identity frame, entered ROM after one vetted
soft key, accepted the reviewed fixed RAM loader, and produced two matching
1,048,576-byte flash dumps. Both match the October 7 baseline byte for byte.
No flash erase/program command was issued. Lunar has not booted on the device;
installation, restoration, display and broken-application recovery remain open.

## Frozen source and concrete entry

Source checkpoint `5a4e3e32d9eb45849ecd728a2e275d92697df294` was pushed and
compared with the origin feature branch before device traffic. The fixed reader
passed 80 focused tests in 16 Hera containers; its independent review and the
fixed loader's native review are recorded in the adjacent notes.

The private entry wrapper was independently accepted at SHA-256
`907b5fb0459f17a1c40b0259602a668e06408c6511e044b8bda4e115415e33b4`.
It durably recorded an exclusive entry intent, bounded passive text usbmon to
1,800 seconds, verified its own capture process group and open endpoint FD,
then invoked the pinned identity/soft-key tool once with isolated Python
startup. Device entry returned exit 0; no retry occurred.

At Unix time `1791762353.5106442`, the FM-1 was at USB `3-2`, bus 3, device 22,
`4c4a:c755`. Its identity reply hash was
`7679e7be907c6cc32b3c1f27c48cc8ce6daa865852e8021e2207cdeae223217d`.
The exact known checksum defect was accepted only for that frame. The one soft
key was `f0 22 24 35 7d f7`; usbmon recorded its 8-byte MIDI packet
`04 f0 22 24 07 35 7d f7`. ROM appeared on the same port as device 23,
`4c4a:8057`, after 0.747 seconds.

Entry log SHA-256:
`f704d7893b134acdf0c4aed78757f81c83d0463ffcf59b17cce3ea42c85654dc`.
Campaign SHA-256:
`79000ac37e0f312d6edf30e810acd09ce551c51c061fcf48aede212d86f61a6e`.
The fixed campaign parent on bench01 is
`/home/claude/fm1-fixed-backups-20261011` (0700); its one-use entry marker
remains. Do not reuse this entry or remove the marker.

## Physical backup result

Reader SHA-256:
`79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb`.
Candidate encrypted loader SHA-256:
`fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c`.
Profile SHA-256:
`3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe`.
The same-port SG node was `/dev/sg0`; the private manifest records the actual
USB, SG class, device and character-FD identities, checked before/after each
syscall. Advisory flock does not establish kernel exclusivity.

The adapter exited 0. Its 17,516 JSONL events contain one prepared event,
8,757 ordered intent/completion pairs, then one completed event at
`1791762397.036248`; no stop event occurs. Every completion has zero status,
masked/message/host/driver status, residue, info and sense length. Full dumps
were independently rehashed after completion and after copying off bench01.

Both dump hashes:
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Manifest hash:
`1ab5e38943648080d9fde9fa86197607aa7a0e01c19da62cd20f24e8f11280cf`.
Command log hash:
`e626e30e6ea58d3ee6c01aa199af1b678c75615439429ec54dcd8f905525628e`.

Text usbmon capture hash:
`4d5bf9375e957ef17f89966a74645e96ee528041271b641f35ed880a5ca2b331`.
Its 8,756 vendor CBWs match every recorded vendor CDB, direction and transfer
length in order: FB06 47, FB08 1, FC14 1, FC0A 515, FD05 8,192. Kernel SCSI
INQUIRY, TEST UNIT READY and REQUEST SENSE traffic is separately excluded from
that comparison. Each of the 47 captured upload prefixes matches its pinned
loader block. Text usbmon retains only 32 payload bytes; full upload wire
hashes were not independently established. Only the verified owned capture
process was stopped, after backup completion.

Private evidence is retained on bench01 and copied to
`build/fixed-backup-physical/`; archive SHA-256:
`20b91b294dd66442af83374ec3cc3eb8cf641033b59ed91b9ce63b079e9aaaea`.
Neither dumps, vendor loader, reference binaries nor bus capture are in Git.

## Current state and next gate

The fixed loader remains active at USB `3-2` device 23. No reset, flash erase,
program, eFuse command or firmware boot was attempted in this campaign. A
separate reviewed active-loader FC0C argument-1 reset is being prepared so
normal boot can be requested without the owner's physical power cycle.

The fixed-loader selector/default-mode patch has native evidence for bypassing
the identified quad NOR status writes. The inherited external initializer at
`0x01e00428` and entry-supplied operations remain unresolved. Matching flash
contents do not prove NOR status or all peripheral state remained unchanged.
This experiment establishes successful full-flash reads, not universal loader
safety or a verified recovery path from a corrupted application.

Next: bind the exact private SDK app/ELF and fresh backups to the distinct SDK
transaction policy; independently review/test its physical SG adapter; verify
installation/readback and baseline restoration before the diagnostic boot
trial. Preserve stock SPL, OTA/cfg, partition descriptors and unrelated bytes.
