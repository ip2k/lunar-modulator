# Independent SPL rescue-record audit — 2026-10-14

## Result

[verified] The retained 1 MiB stock FM1_092 capture pair contains no SPL-recognized trailer record at any slot the pinned stock SPL scans. The offline expanded candidate likewise contains no record in either its raw physical representation or the canonical decrypted SFC app view. Consequently, the candidate does not preserve an independent SPL trailer-record rescue path from stock. This is a byte-coverage result for the captured images, not proof about every FM-1 unit or every ROM/USB recovery path.

The phrase “stock OTA” needs care here: preserved stock OTA/configuration bytes are not equivalent to a valid on-flash SPL trailer record. The SPL trailer lookup is a distinct conditional recovery mechanism. No complete candidate record was found, so there is no referenced loader pointer to classify as being inside or outside protected unchanged ranges.

## Inputs and provenance

[verified] The historical read-only stock capture is at
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1/`.
Both `stockA.bin` and `stockB.bin` are 1,048,576 bytes and have SHA-256
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
The capture manifest describes two matching read-only dumps; it does not claim
physical recovery verification or current-device freshness. Private identity
and config content are intentionally omitted.

[verified] The expanded candidate is the previously constructed offline raw
image at
`/home/claude/.local/share/codex-private/event120-expanded-candidate-20261014/candidate/target.bin`;
size 1,048,576 bytes, SHA-256
`0eaa6bd5501c64bb6f1e76c5e089dcd543816de35434d5cf4ed1170ba01df8c7`.
Its candidate note says installable=false and all hardware/physical admission
gates false. This audit neither changes that status nor authorizes a write.

The slot arithmetic and record acceptance checks below are from the byte-level
review of the pinned SPL at
[`2026-10-14-stock-spl-update-record-byte-review.md`](2026-10-14-stock-spl-update-record-byte-review.md),
which disassembled and byte-compared the exact pinned 14,384-byte SPL using the
vendor JieLi objdump. That earlier review is the control-flow authority; the
current task only scanned retained image bytes.

## Reproducible scan definition

[verified] For 1 MiB capacity and a 4 KiB SPL stride, the exact slot offsets are
`boundary - 0x100` for boundaries `0xFF000` down through `0x2000`, inclusive.
Ascending notation is `0x1F00, 0x2F00, …, 0xFEF00`, step `0x1000`: **255
slots**. (This count follows the full address interval; a prior informal
160-slot count is incorrect.) At each 80-byte record candidate the SPL first
requires LE16(+6) == `0x5441`, CRC16/XMODEM over bytes +2..+79 equal to LE16(+0),
and a nonzero LE16(+2). It then follows the 32-bit pointer at +72 and validates
the referenced 32-byte inner header CRC over +2..+31 and its nonzero length
field at +8. CRCs provide integrity checks, not authentication.

The audit tested all 255 offsets in raw bytes. It also formed the canonical
logical SFC view by decoding the app span relative to `APP_BASE = 0x4000`,
using the repository's `tools/jieli/inspect_fwsc.py` decoder, then retested
slots falling within the encrypted app span. In the stock image that span is
`[0x4000, 0xAE000)` (170 candidate slots); in the expanded image it is
`[0x4000, 0xD9000)` (213 slots). Slots outside each span were still checked in
raw physical bytes. The pinned scan covers app, data, and reserved extents
because it derives bounds from detected flash capacity; there is no partition
ownership exclusion in the scan.

## Results

| Image/view | Slot candidates checked | SPL tag `0x5441` found | Full valid records | Referenced loaders |
|---|---:|---:|---:|---:|
| stockA raw | 255 | 0 | 0 | 0 |
| stockB raw | 255 | 0 | 0 | 0 |
| stockA canonical SFC app view | 170 | 0 | 0 | 0 |
| stockB canonical SFC app view | 170 | 0 | 0 | 0 |
| expanded candidate raw | 255 | 0 | 0 | 0 |
| expanded candidate canonical SFC app view | 213 | 0 | 0 | 0 |

Every tested candidate was rejected at the first signature check. Thus outer
CRC, pointer bounds, inner CRC and payload-length checks were not reached for
any candidate. No raw record bytes, loader contents, or private config values
are reproduced here.

[verified] The expanded candidate's raw protected prefix `[0, 0x4000)` and
suffix `[0xD9000, 0x100000)` compare byte-for-byte equal to stockA. This
includes the preserved top stock boot/config area and preserved suffix banks,
but does not create an SPL record: the complete scan found none in either
image. Preserving these ranges is not evidence that they contain an
independent rescue record.

## Consequence for rollback design

A software-only transaction must treat “ordinary application invalid and no
valid SPL trailer record” as a reachable failure state for this retained
baseline/candidate pair. It cannot assume that unchanged stock OTA files or
protected banks provide the SPL with a fallback loader. The earlier disassembly
shows the trailer lookup is conditional and distinct from ordinary-app
selection; this audit does not prove the exact terminal behavior after every
possible damaged-header/update context and does not invalidate separate
physical USB_KEY / mask-ROM recovery routes.

Before a restart-safe update is considered, its design needs a separately
proven independent bootstrap/recovery mechanism, exact sector ownership and
preservation evidence, and a rollback path validated across interrupted-write
cut points. Do not erase, relocate, or repurpose VM/BTIF/USR or any scanned
sector-tail address based on this finding. The broad SPL scan is not an
allocation policy.

## Limits

No device or hardware interface was accessed. The raw captures are historical
and are not fresh measurements. The scan validates byte representations
against the already reviewed SPL signature/CRC/pointer contract; no SPL was
executed. SFC decoding uses the repository's canonical transform; both raw and
decoded views were checked to avoid depending on whether the SPL's internal
flash-read mode exposes a given app span in encrypted or logical form. The
result only establishes that these exact images contain no valid record at
any candidate offset. No USB, MIDI, flash, power, reboot, package installation,
or runtime operation occurred.
