# Software reset observation and fresh stock backup

The owner connected Cynthion CONTROL to the Mac, TARGET C to bench01 and
TARGET A to the FM-1. Computer Use returned no native apps and reported a
locked Mac despite the owner's unlocked Mac and enabled locked-use setting.
No Packetry clicks or capture export are claimed. Bench01 usbmon supplied
the retained USB capture. [verified: tool response and owner wiring report]

## Consumed RAM-only reset

At 1791815571 the separately reviewed adapter submitted exactly INQUIRY,
one 512-byte FB06 upload at 0x01c02000 and one FB08 jump to that address.
INQUIRY/upload completed cleanly; jump returned host7/info1/residual16 and
the CLI stopped with exit1. Its consumed marker remains and it was not
retried. No NOR command ran. A separate command-free passive observation
at 1791815602.3909593 saw normal USB 4c4a:c755, bus1/device5, same port1-1
and MIDI C2D0. This establishes normal enumeration after the attempt, not
a clean final reset-command completion. [verified: retained receipts]

The independent reset receipt audit is retained under
`build/expired-entry-core-reset-v1/root-stage-v1/`, report SHA256 fc0c0240,
check04bcc402. The 1,553-byte capture ended before normal enumeration;
the separate passive observation must not be presented as captured wire.

## Fresh entry V3.1 and two full backups

The fresh once-only orchestrator queried identity at 1791816117.2943022,
decoded FM-1_092 with the documented checksum failure, sent exactly one
F0 22 24 35 7D F7 key, and observed UBOOT at 1791816118.041899 on the same
port, bus1/device6. Its passive bounded wait found SG0 before any loader
command. Entry, preparation and backup exited0; backup ran
1791816119.1963236–1791816138.8851843. Owned capture stayed live across
backup and was stopped/waited with leader and reader absent. [verified]

Exactly 8,757 SG intents/completions match the reviewed fixed-loader
inventory, with zero completion errors: 47 RAM upload chunks, one RAM jump,
8,192 flash pages and the fixed inquiry/buffer/online checks. No erase or
flash-program opcode appears. Both 1,048,576-byte dumps are byte-identical
and match stock SHA256
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
[verified: retained complete dumps and command log]

Independent wire review matched all 8,757 logged operations in order, with
expected transfer size/direction and successful CSW. The capture also has
41 unlogged host SCSI commands: 19 TEST UNIT READY, 20 REQUEST SENSE,
one INQUIRY and one PREVENT/ALLOW. Their originating process is unknown;
`kernel_exclusivity=false` accurately records the limitation. Capture
payload truncation prevents independent reconstruction of the full dumps
from wire bytes. Physical recovery remains false in the manifest. [verified]

The sealed 25-regular-file receipt archive is
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/fresh-entry-v3.1/actual-entry-backup-receipt.tar`,
SHA256 `bf41339569cab9facf54a0009ec37fc2527cd4b6677adb95e1caf1c4bc963678`.
Independent review51237df5/checkf5b33e99 passed all26 bounded checks.
These ignored private artifacts retain original files without publishing
vendor binaries or private dumps.

## Next gate

The installer's 120-second interval from backup completion expired before
the resumed verification. No install transaction, packet or device write
was prepared or run from these backups. Never refresh the original
timestamps or retry a consumed attempt. Prepare the complete sequence
before the next fresh entry: canonical stock baseline reset, new identity
and entry, two full stock backups, exact diagnostic installation, boot,
five original RAM reads before any later loader upload, admitted dual
backup and full stock restoration. All canonical freshness, source,
connection, protected-sector, consumption and owned-capture checks remain.
Display, physical interrupted-write recovery and goal acceptance are open.
