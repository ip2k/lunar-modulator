# First-publication recovery options for stock VM/USR migration

Offline source and retained-byte analysis only. No device, USB, MIDI, flash,
power, reboot, or package operation was performed. This note does not authorize
storage reassignment or SAVE enablement.

## Finding

No currently evidenced on-device method provides crash-safe first publication
of the captured stock VM/USR archive. A host-held copy can preserve the old
bytes and support an operator-mediated restore **if** an independent ROM entry
and write/readback recovery route is available after interruption. That route
has not been shown to recover this migration on this exact target, and the
archive decoder/restore path is not target-tested. Thus external escrow is a
necessary safety net, not an autonomous rollback mechanism.

The archive does fit arithmetically in the nominal five-sector remainder:
18,673 bytes serialized against 20,480 bytes, leaving 1,807 bytes for this
specific captured image. But the remainder `[0xF7000,0xFC000)` contains 7,690
non-`0xFF` bytes. It is part of stock USR, and the ledger leaves ownership
unresolved even for sectors that are all `0xFF`. Writing the archive there
would overwrite source bytes it is supposed to preserve; a partial archive
write can leave neither a complete on-device archive nor the untouched old
bank contents.

## Candidate routes and interruption behavior

| Route | What it can protect | First-publication cutpoint | Assessment from current evidence |
|---|---|---|---|
| **Private host escrow** | Two matching full-flash reads and the verified compressed VM/USR archive remain off-device. An external archive SHA-256 anchors the encoded bytes. | A cut during any flash mutation leaves the host copy intact, but the FM-1 may not boot into a path that can read or restore it. | Only credible source of an independent copy today. Could support a human-operated ROM recovery sequence after same-target entry and writer recovery are proven. Does not itself make the first write crash-safe. |
| **Five-sector USR remainder `[0xF7000,0xFC000)`** | Nominal capacity exceeds the measured archive by 1,807 bytes. | Its first 4 KiB sector erase destroys bytes in the very USR extent being archived. A cut while emitting archive data can leave an incomplete archive; the remaining sectors are not proven free scratch. | Refuse as a first-publication destination. The 7,690 non-`0xFF` count is evidence of occupied bytes, not a complete semantic inventory. |
| **Existing OTA staging `[0xE0000,0xE5000)`** | Same nominal 20 KiB size. | Current Dinghy OTA code erases the five sectors before staging, stores its 112-byte `UPDATA_PARM` at `0xE4F00`, and erases the staging window on failure/boot cleanup. This range is also inside stock VM. | Not durable independent escrow. Reusing it would conflict with the live update path, its record, SPL scan, and stock VM data. `LUNAR_OTA_RAMONLY` removes the persistent record and explicitly loses resume safety on power loss. |
| **D7000-to-D9000 staging proposal** | 8 KiB geometric interval sometimes discussed as application-tail/stage space. | It cannot contain the 18,673-byte serialized archive; even a partial staging write has no proven recovery consumer. | Too small and not established as durable or available. Do not infer availability from the app link profile. |
| **Sectorwise in-flash relocation** | Could preserve a source sector only after its full bytes are copied to a distinct verified destination. | The first destination erase/write needs a known-safe scratch sector. No such sector is established: the five nominal spare sectors are USR data or unresolved, and an all-`0xFF` sector is not proof of ownership. Moving the first sector into another unknown sector merely transfers the destructive cutpoint. | No admissible ordering without a separately proven staging extent or external recovery route. RAM cannot bridge power loss. |

The map's 24-sector SAVE layout leaves five sectors arithmetically outside its
slots and the OTA stage, but this is not five free sectors. The ownership
ledger reports each sector's bytes and overlaps while keeping logical ownership
unresolved and `erase_safe=false`. The archive compresses only the recorded
VM+USR bytes; it does not explain their records or make a migration
semantically reversible.

## Failure sequence for a possible operator-mediated route

This is a reasoning checklist, not an executable procedure or approval.

1. **Capture baseline.** If either full read is incomplete, the two reads
   differ, or identity/provenance cannot be bound, stop before mutation. The
   current archived pair is historical FM-1_092 evidence, not a fresh baseline
   for whatever image is currently installed.
2. **Create and verify escrow.** Compress only matching bytes, enforce the
   exact 20,480-byte encoded cap, and verify the archive against an externally
   pinned archive digest. If encoding, capacity, digest, or private durable
   storage fails, leave flash unchanged. A baseline digest embedded in archive
   metadata is not an authentication root.
3. **Publish a first on-device copy, if a separately owned extent is ever
   established.** Erasing that destination is already destructive if it
   contains any old bytes. Before the archive is complete and read back, an
   interruption makes the on-device archive unusable. The host escrow is then
   the only known copy; recovery requires ROM entry and an audited restore
   path. There is no proven atomic sector/page write assumption to remove this
   cutpoint.
4. **Only after complete archive readback could bank mutation begin.** An
   interrupted VM/USR erase/program leaves changed banks. The stage-last cutpoint
   review proves that a valid app header selects XIP, not that the selected
   stock app remains usable after arbitrary USR damage. The FM-1_092 app's
   VM/USR startup semantics are unresolved, so returning to stock app execution
   is not a recovery proof.
5. **Publish the new application/layout.** A power cut while changing the app
   header/body or its settings banks can leave SPL selecting an unusable app,
   no accepted recovery record, or neither a valid old nor new application
   state. Existing offline cutpoint models intentionally report app readiness
   unknown; they do not establish which branch ROM takes for every partial
   image. A valid completed raw archive does not supply an on-device decoder,
   installer path, or semantic settings importer.
6. **Verify and retain escrow.** Even complete readback does not establish
   normal boot, stock updater operation, or settings compatibility. Keep the
   external baseline and archive until those separate behaviors and rollback
   have been demonstrated. Do not delete the only recoverable copy on the
   strength of a hash match alone.

## Minimum evidence that changes the conclusion

- A fresh, identity-bound pair for the actual currently installed target and a
  complete source-to-output ledger for every byte/sector touched.
- A separately owned scratch/archive extent with capacity and boot-time
  lifetime proven against app bounds, OTA erase/cleanup, SPL trailer scans,
  and every stock bank descriptor; alternatively, a tested operator ROM
  recovery route that can restore the external escrow after interruption.
- Exact-target USB_KEY/ROM entry at the required state, plus a rehearsed
  audited loader read/erase/program/readback path after an unavailable or
  partially written app. Existing entry/read success and prior bounded writes
  do not prove recovery from this transaction.
- A target-side reader for this archive format with bounded memory, exact
  stream consumption, digest checks and failure behavior, followed by an
  interruption test of archive publication itself. The host codec roundtrip
  is not this test.
- Version-matched stock VM/USR startup/allocator semantics, or a verified
  byte-preserving relocation/import contract. Raw restoration can reconstruct
  old bytes but cannot certify stock settings remain meaningful after an
  application changes their layout.

Until those facts exist, the defensible option is to retain VM, BTIF, USR and
the OTA staging window unchanged and keep storage SAVE disarmed. The measured
archive is useful as an off-device preservation artifact for this exact
historical pair; it is not a first-publication protocol.

## Source and evidence references

- `notes/2026-10-15-opaque-stock-archive.md`: A/B hash, extent hashes, 18,673
  byte archive and external archive-digest requirement.
- `notes/2026-10-15-storage-ownership-source-review.md`: exact VM/BTIF/USR
  descriptor geometry, opaque-sector accounting, and unresolved ownership.
- `notes/2026-10-14-storage48-migration-plan.md`: SAVE map, OTA conflict,
  reserved geometry and migration/rollback gates.
- `tools/native/storage_ownership_ledger.py`: hash-bound inventory that marks
  every candidate sector ownership-unresolved and not erase-safe.
- `firmware/third_party/dinghy/src/ota.c`: OTA stage extent, full-window erase,
  persistent record placement and cleanup behavior.
- `notes/2026-10-14-rollback-stage-last-cutpoint-review.md` and
  `tools/native/rollback_cutpoints.py`: valid SPL app-header selection is not
  proof of usable stock app or recovery after partial mutation.
- `notes/2026-10-14-independent-recovery-route.md`: ROM entry/read/write
  recovery gates and the distinction between ROM entry and interrupted-write
  recovery acceptance.

No tests were needed for this note-only analysis. No source, storage profile,
writer, archive bytes, or admission flag was changed.
