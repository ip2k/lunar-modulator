# Stock SPL update-record scan: byte-level bounds and semantics

2026-10-14. Offline, read-only follow-up for the recorded FM-1_092 geometry.
No device, USB, MIDI, flash, package-install, or runtime operation occurred.
No vendor binary or raw disassembly is committed. [verified] means exact
artifact/disassembly control-flow inspection, not target execution.

## Pinned inputs and method

[verified] The retained Hera capture
/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1
identifies a 1,048,576-byte flash image; its manifest says it was a read-only
flash capture and not a physical-recovery verification. stockA.bin and
stockB.bin are both SHA-256
96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4.
The reference top/uboot.boot is 14,384 bytes and SHA-256
730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef, matching
the repository package-guard pin. The reference package jlfw.yaml names
that exact file as the uncompressed SPL. The capture's full identity and USB
binding are intentionally omitted.

[verified] In a bounded lunar-jieli-check:bookworm container (image
sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc,
docker-batch.slice, 4 CPU, 4 GiB memory/swap, task label
codex.task=lunar-stock-spl-record-byte-review), the installed JieLi vendor
clang assembled a temporary .incbin wrapper and vendor objdump -D
decoded its .fw section. Vendor objcopy -j .fw -O binary produced 14,384
bytes that compare byte-for-byte with the pinned SPL. The input package and
toolchain were mounted read-only; temporary wrapper/object/listing/decoded
bytes remain under /tmp/lunar-spl-record-byte-review on Hera only.

Offsets below are SPL-file offsets. The 16-byte SPL bank header is included,
matching the earlier SPL notes. Decoding instructions is not a claim that all
decoded addresses are reachable or executable.

## Exact trailing-record scan

[verified] The scan is conditional. With a selected ordinary app, the check
at 0x2e08 sees r13 == 0 and jumps to 0x2f78, bypassing the trailing
flash-record loop. The loop at 0x2e0c..0x2e74 runs when that ordinary-app
selection did not succeed. This is consistent with the earlier final-path
trace; it does not prove behavior for every inherited RAM/update context.

[verified] For the scan, helper 0x141e called with selector 103 writes the
flash-capacity field ([0x01c06460+52]) into [sp+232] (0x2e0c..0x2e14,
helper 0x1436..0x143e). The capacity field is populated by the earlier
flash-geometry setup (0x0f54..0x0f72); for this 1 MiB profile its value is
0x100000. The loop initializes its stride to 0x1000 at 0x2e24; a
geometry-derived conditional can substitute the encoded sector size
(0x2e18..0x2e2c). The loop therefore uses a runtime sector stride, not a
hard-coded partition range.

[verified] With the 4 KiB stride, the candidate arithmetic is:

- 0x2e30: first boundary r7 = flash_capacity - 0x1000.
- 0x2e3c..0x2e44: candidate record address is r7 - 0x100; the SPL reads
  80 bytes into its RAM buffer.
- 0x2e4a / 0x2e58: a nonmatching signature or CRC returns to the loop
  decrement at 0x2e34, reducing r7 by 0x1000.
- 0x2e36: stop when the decremented boundary is <= 0x1000.

For a 1 MiB capacity and 4 KiB stride, the exact candidate offsets are
0x1f00, 0x2f00, ... 0xfef00 (descending in the SPL; ascending notation here).
The first is the tail of the second 4 KiB sector; the last is the tail of the
sector immediately below the final 4 KiB sector. The scan does not examine
capacity - 0x100 in the final sector. More generally, it examines
boundary - 0x100 for boundaries from capacity - stride down through
2 * stride, inclusive, in stride steps. This arithmetic is the SPL's
lookup behavior, not permission to reserve or write any such location.

[verified] Each candidate read is exactly 80 bytes. It is accepted as a
record only if the 16-bit value at +6 equals 0x5441, the CRC helper at
0x58 applied to bytes +2..+79 (78 bytes) equals the 16-bit value at +0,
and the 16-bit word at +2 is nonzero (0x2e3c..0x2e72). This review does
not assign a higher-level meaning to the nonzero word. Upon acceptance, the
SPL takes a 32-bit pointer at +72 through helper 0x1448; it then reads a
32-byte inner header and validates its CRC at 0x2e98..0x2eb6 before using
the loader path described in
the final SPL contract (notes/2026-10-11-stock-spl-final-contract.md). CRC is
integrity checking, not authentication.

## Consequences for staging and recovery design

[verified] The SPL does not confine this lookup to a documented spare/user
partition: the upper bound comes from detected flash capacity and the loop
continues down to the second sector. Thus a record-like 80-byte sequence at a
sector-tail candidate can be considered during the failed-app selection
path, even if a higher-level design intended that area for some other use.
A proposed staging address must be assessed against the exact stock map and
bytes; an erased sector alone is not evidence of safe ownership.

[verified] An ordinary valid app selection bypasses this flash search, so a
persistent trailer record is not a general way to inject a second-stage
loader while leaving the ordinary app selected. The separate inherited RAM
mailbox path and its pointer/header checks remain distinct from this scan.

[reported/inferred] Dinghy/Felucca's example 0xE0000..0xE4FFF stage with
record at 0xE4F00 fits the same sector-tail convention, but the FM-1_092
ownership review places 0xD9000..0xE9000 in the VM region. The exact SPL
scan does not make that location available for Lunar. No safe persisted
RAM-loader location or restart guarantee has been established for the
expanded-d9000 geometry. A RAM-only updater also cannot recover from power
loss after overwriting the app unless a separate stock-owned persistent
recovery mechanism is independently proven.

## Validation limits and next step

The direct evidence is the exact pinned SPL and fresh vendor disassembly with
full byte comparison. No update record was written, no flash sector was
changed, and no boot/scan was observed on hardware. The transaction's
successful resume behavior, mailbox initialization across cold/warm reset,
physical backup restorability, and a safe stock-owned staging extent remain
unproven.

Next, any persisted-loader design must name exact 4 KiB sectors, show their
ownership and contents from the matching captured baseline, prove how normal
boot reaches the record path, and demonstrate a power-loss recovery route that
preserves the pinned stock SPL/OTA/configuration contract. Without that, keep
this transport as offline design only; do not treat the SPL's broad scan as
an available installer slot.
