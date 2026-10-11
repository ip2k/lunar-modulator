# FM-1 ROM-to-application return using the minimal RAM reset stub

2026-10-11; owner's FM-1_092 on bench01. **Normal USB and a fresh FM-1_092
identity reply returned without an owner power cycle** [verified hardware
outcome]. This is one successful observation of the fixed RAM-only route.
It does not establish a bare-UBOOT reset opcode or recovery from a broken app.

## Concrete attempt

The owner asked whether UBOOT could reboot the device to unblock bench work.
The [full loader audit](2026-10-11-loader-run-app-reset.md) found FC0C core
reset, but retained-RAM parsing during loader startup can change NOR status.
That loader-reset guard remains simulation-only. Instead, the independently
authored [14-byte reset stub](2026-10-11-rom-core-reset-stub.md) omits loader
initialization, stack use, helpers and recovery-mailbox writes.

[verified source/artifact] Exact image SHA256:
`b137c15cc0b82d0d056246f08ad2292f754216b9f70bd83a1caec4e35978cee5`.
Entry is 0x01C02000. The source disables local interrupts, sets bit4 of
`JL_POWER->CON` at 0x10000, synchronizes and loops. Its source, linker, native
listing and encrypted upload were checked before hardware access. The fixed
guard is committed at `b397ca90864aac504f3e120cddff959e53d32e7e`.

[verified review and Hera mocks] The separately reviewed private adapter was
frozen at SHA256
`4ddecc450dcdac07ffd38d64d30c10b4a23460a4f94271a99cc06ee48ecb78d9`.
All 48 isolated adapter mock checks passed; the 170 combined guard checks also
passed. Adapter main and actual Linux I/O were not exercised by those mocks.
Root independently checked the final source and its passive-enumeration fix,
all ten staged regular files, six imported-module pins and historical entry
receipt. Files were staged under root-owned 0700
`/home/claude/fm1-core-reset-20261011/`; inputs/receipts were 0600.

[verified bench preflight] Before the single attempt, cached sysfs attributes
still matched direct port3-2, bus3/device21, VID/PID `4c4a:8057`. The adapter
discovered the matching SG character device, checked fd/sysfs identities and
fresh binding immediately before every command, checked cooperative ownership
with fuser/flock, and started passive usbmon capture before SG access. These
checks do not provide kernel exclusivity or cryptographic unit attestation.

Only the following three requests were submitted, once each, with durable
intent before the syscall and no retry:

| Request | Exact CDB | Transfer |
| --- | --- | --- |
| INQUIRY | `120000002400` | 36 bytes in |
| RAM upload | `fb0601c02000020000a794ffffffffff` | 512 encrypted bytes out: 14-byte stub plus 498 zero bytes |
| RAM jump | `fb0801c020000001ffffffffffffffff` | entry 0x01C02000, argument1; 16-byte reply requested |

No LoaderV2, FC0C, flash erase/program, eFuse, soft key or mailbox-clear request
was part of this attempt. The historical normal-to-ROM entry receipt was
checked separately; it was not represented as a new identity query.

## Observed result

[verified receipts] INQUIRY and upload completed with status/host/driver/resid
all zero. INQUIRY returned `WL82` / `UBOOT1.00`. Jump submission at Unix time
1791755134.902881 lost the connection: SG host7, info1, residual16. The adapter
closed/latch-stopped with status2 and no retry; it did not mistake a missing
reply for a completed transport transaction.

Cached sysfs observations showed port3-2 absent by +0.105 seconds and returned
at +1.518 seconds as bus3/device22, `4c4a:c755`, the normal MIDI/audio USB
interface. Observation continued for a bounded 15 seconds, with explicit
snapshot completeness and non-atomicity. After the reset adapter and capture
had closed, a separate existing read-only identity query on the uniquely
mapped `/dev/snd/midiC2D0` received the exact known FM-1_092 reply. Its decoded
checksum remains false, as in the previously recorded owner-unit checksum
bug; only that exact previously captured frame was accepted. No soft key was
sent by this confirmation query. Normal USB and a responsive FM-1_092 app
are confirmed; display/audio function was not inspected.

[verified capture; bounded completeness] The saved usbmon window contains
exactly three BOT command wrappers: the three requests above. It contains no
additional kernel storage CDB and no observed flash/eFuse command. Subsequent
USB hub/control/audio enumeration is visible. Capture liveness and persisted
output do not prove a lossless capture. Its text format shows only the first
32 bytes of the 512-byte upload; the durable host pin establishes the intended
whole buffer, not an independently captured whole-payload proof. No flash
reread was made, so unchanged flash-array/status hashes are not claimed.

[inferred causal mechanism] The return is consistent with the stub's core
reset request, and unlike the earlier 700-byte probe it returned the installed
app. There is no independent instruction-execution or reset-domain witness.
Warm core reset, retained recovery-marker state and ROM fallback are not
fully characterized. This is a useful observed exit from this UBOOT session,
not an unconditional reset/recovery guarantee.

## Saved evidence and next use

The private remote directory remains at the fixed bench path above. Root
copied the complete staged files and receipts to ignored
`build/core-reset-bench/physical/`. No vendor or firmware binary is committed.
An independent file-only review corroborated the three captured command
envelopes, sampled return time and decoded identity, retaining the transport,
capture and checksum limits above. Its saved report SHA256 is
`209afbc31cfde42fc36e4c5709c3731a26c182aae2b9bdb29bd9005e4c529f95`.

| Evidence | SHA256 |
| --- | --- |
| Bench snapshot tar | `6e595d47e8c852352993d53bfea64ca355100a7b935592755162c6ada4ddc783` |
| events.jsonl | `c73b44c13c14ebbf18d2f94ed1c94f5f931dcbaa20ae5888b215b0f9564adbac` |
| commands.jsonl | `059b3f7eb7667e1ea7634afd7c0e56cb235478207f7a3602cfafa05cc6c6a36b` |
| usbmon.txt | `eaabc429afcdea979abb575831e3cc5aa70cfc2d4bb07b28de90a83436bb3b2f` |
| identity.jsonl | `f5aa6fb0aca54f582e05b9978e58aa3428f129aefdda7c8d601462787868a71c` |

The consumed adapter cannot be rerun: its receipt already exists and its fixed
device21 binding no longer matches. A future attempt requires a newly reviewed
concrete session binding and fresh private receipt; do not edit pins or retry
an ambiguous jump. A real owner power cycle remains the fallback. This result
unblocks bench access, while diagnostic-image boot/display/recovery acceptance,
USB_KEY-on-hardware and full broken-app restoration remain outstanding.
