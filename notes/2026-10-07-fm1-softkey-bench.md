# FM-1 soft-key / bench01 experiment (2026-10-07)

## Owner decision and scope

The owner explicitly asked to remove the blanket "one rule" restriction,
explore the soft-key UBOOT path over bench01 USB, and pursue dump/restore
without waiting weeks for the dev board. Follow-up: "I'm pretty sure we can
get to dump and restore using the soft key uboot mode — let's see."

This supersedes the 2026-10-05 draft's requirement to rehearse on the dev kit
and its requirement for separate approval of every recovery-entry step.
It authorizes a staged experiment, not arbitrary erases or key burning.
First observe soft-key entry; then audit and use a pinned RAM-only download
loader to take two private 1 MiB backups; assess restore with exact ranges
and image review. No eFuse writes. Retain stock package safeguards. A failed
Lunar app may not process a soft key: an independent boot-entry path remains
important before relying on that app as its own recovery mechanism.

## Current bench observations

[verified] bench01.local is reachable as `claude`, Raspberry Pi OS aarch64.
The FM-1 is directly on root bus 3 port 2, USB `4c4a:c755`, full speed,
ALSA `/dev/snd/midiC2D0`. The other device is a high-speed USB analyzer on
port 1; no downstream USB hub is present.

[verified] Fresh identity reply on this session decodes to `FM-1_092`:
`f0 00 32 45 58 01 00 00 23 4d 5a 44 79 05 26 0e 19 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 20 06 f7`.
Checksum fails in our decoder. The initial probe refused the soft key.
[reported] Baud Girl documents an identity checksum defect in pre-94 builds:
https://baudgirl.com/work/FM-1+VA/manual (version history, 94). The probe
exception accepts only the exact full captured reply, for expected 092,
and only with `--accept-known-092-checksum-bug`; no general checksum bypass.

The static 092 soft-key handler is byte-identical to V15 and writes a RAM
mailbox then resets, without a flash write on that traced path [verified:
notes/2026-10-05-softkey-efuse.md]. Hardware behavior remains to be observed.

## Probe tool and tests

`tools/fm1_softkey_probe.py` uses Linux ALSA raw MIDI and Python stdlib. The
only allowed output messages are identity and `F0 22 24 35 7D F7`. The latter
is opt-in, sent once, after a fresh identity matches; no automated retry.
It rejects unvetted firmware versions, downstream hubs and incorrect VID/PID.
It logs before each send and watches for `4c4a:8057`. A passive usbmon capture
must establish actual USB-MIDI packet framing; one ALSA write is not itself
proof of one USB transfer. This tool cannot upload a loader or erase/program
flash. Six tests pass for exact checksum exception, malformed/truncated
replies, rejection of upgrade/arbitrary messages, partial-write/no-retry,
identity timeout and unvetted-version rejection [verified].

## Next firmware milestone

[inferred] A few-day milestone should be a small bootable hardware proof
(audio plus one Lunar engine, controls and a recovery entry), not a claim
that the complete simulator/editor is now firmware. Lunar currently has no
linked hardware application. Felucca supplies a working GPL bare-metal
platform reference; reusing its GPL implementation makes that prototype GPL
regardless of the engine switch. Using independently permissive drivers for
both GPL/permissive variants takes longer. Build/link, resource fit, packaging
and bench validation are still necessary; no delivery date is promised.

## Handoff

Branch `feature/2026-10-07@fm1-softkey-probe`, based on `origin/main` at
`64209e3`. Initial checkpoint contains policy, probe and tests. Private
captures/backup images belong under ignored scratch or private bench storage,
never Git. Record probe results here before proceeding to loader/dump work.
The advanced-editor branch and PR #99 remain separate, awaiting owner listening
feedback. Confirm backup by comparing this branch's HEAD and origin ref.

## Soft-key result on this unit

[verified, bench session] `7D` succeeded once at 2026-10-07 21:43 Pacific.
The passive usbmon capture contains one 8-byte EP4 OUT transfer:
`04 f0 22 24 07 35 7d f7`. Normal `4c4a:c755` (bus 3 device 10)
changed to `4c4a:8057`, product `WL80UBOOT1.00` (device 11), in 0.745 s.
SCSI sysfs reports `WL82` / `UBOOT1.00`; endpoints are OUT 0x01 / IN 0x81,
64-byte packets, USB mass-storage bulk-only. Loading the existing Linux `sg`
module exposed `/dev/sg0`; no persistent host configuration was changed.
The host's USB storage driver also sends normal INQUIRY / TEST UNIT READY /
REQUEST SENSE traffic; these are visible in the capture.

The capture and entry JSONL are retained privately under the main checkout's
ignored `scratch/fm1-bench-20261007/` and `/tmp/` on bench01. No flash dump or
restore has yet occurred at this checkpoint. Device remains in UBOOT.

## Bounded dump tool

`tools/fm1_uboot_read.py` uses stdlib Linux SG_IO with a hard phase allowlist:
ROM INQUIRY, FB06 within `[0x01C02000,0x01C07E00)`, FB08 only to 0x01C02000
with argument 1; loader FC14, FC0A and FD05 only. No flash write/erase or key
operations exist. Loader is jl-uboot-tool `adb3f188`'s 24,064-byte WL82 blob,
SHA-256 `d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376`,
the blob audited in the desk investigation. No config block is uploaded.
Unused CDB bytes are FF; reads use the reported WL82 256-byte buffer limit.
The tool checks flash type 3 / JEDEC 0x856014, takes two 1 MiB dumps with
keepalives and insists on identical hashes. CLI requires the successful
092 entry log and checks the same USB path/enumeration. Twelve tests pass
across probe and dump tools, including rejection of every opcode outside
the allowlist, loader range/config overflow, altered blob, unsafe jump,
flash-read bounds and online-device configuration [verified].
