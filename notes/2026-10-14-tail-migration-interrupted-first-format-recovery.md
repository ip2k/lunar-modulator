# Interrupted first-format recovery design for storage48 — 2026-10-14

Offline design only. No device, USB, MIDI, flash, power, reset, package, or admission operation was performed.

## Recommendation

[inferred from verified map and scan evidence] Keep the 43,130-byte supported-state bound and two full-capacity journal slots. The most direct way to address the eight archived trailer-page hazards is a ROM-held first-format transaction: preserve the exact pre-migration bytes off-device, establish a device-specific USB_KEY-at-power-on route before destructive work, and do not let the target execute SPL until all changed slot sectors have completed erase/readback and all 24 mapped record pages are verified 0xFF. If interruption occurs, re-enter ROM before any normal boot, then resume formatting or restore the exact saved sectors and verify the full pre-migration digest.

This is operator-mediated recovery, not an autonomous cold-boot guarantee. USB_KEY has not been physically proven on this owner's target; ROM multi-sector rollback, semantic VM/USR migration, and physical erase interruption behavior are also unproven. The sequence below is a concrete design for closing those dependencies, not permission to bypass existing review/admission.

## Evidence and capacity decision

[verified: prior offline archived-image analysis] `notes/2026-10-14-tail-migration-archived40-inventory.md` reports two equal archived device40 full-flash reads, SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. Eight final pages in the proposed 24-sector map are non-FF: `0xEA000`, `0xEB000`, `0xEC000`, `0xED000`, `0xEE000`, `0xEF000`, `0xF0000`, and `0xF1000`. None currently matches the modeled SPL outer-record or retained cleanup-record predicate. This archive is not a fresh current-target baseline or admission.

[verified: retained SPL scan analysis] `notes/2026-10-14-spl-record-scan-proof.md` records a conditional scan at each 4 KiB boundary-minus-256 candidate from `0x01F00` through `0xFEF00` for the 1 MiB profile. Felucca cleanup checks candidate offsets `0x93F00` through `0xFBF00` and may erase the containing sector when its broader predicate matches. Current non-matching bytes do not characterize partially erased bytes. The prior worker rechecked its byte-level listing; this task did not rerun the vendor disassembler or device.

[verified: layout arithmetic] The candidate VM+USR envelope has 34 sectors; excluding the live OTA staging range `[0xE0000,0xE5000)` leaves 29. Two full-capacity slots need 24 physical sectors, 12 per slot, so the current map has five spare sectors. Replacing all eight known dirty trailer pages with spare sectors is impossible within this envelope; at least three hazards remain even if every spare is suitable. Extending beyond these named ranges requires new ownership and boot-path evidence.

[verified: capacity arithmetic] Reserving the final 256-byte page of each physical sector packs 3,840 bytes/sector. Twelve sectors give 46,080 packed bytes. The store exposes eleven 4 KiB logical blocks (45,056 bytes), leaving 45,024 payload bytes after the 32-byte journal header: 1,894 bytes above the 43,130-byte collector bound. Thus the two-slot full-capacity design remains viable without lowering the bound.

## Interruption and recovery model

[inferred: conservative model; erase behavior is not physically characterized] Treat an interrupted sector erase as any mixture of old and erased bytes, including a transient candidate window that satisfies either retained record predicate. Do not assume prefix-only or predicate-monotonic erase progress. While held in mask ROM, SPL and cleanup are not running. After a power interruption, the recovery path is to enter ROM again with USB_KEY before normal flash boot. If ROM entry cannot be obtained, this design has no demonstrated safe continuation.

| State | Recovery action | Limit |
|---|---|---|
| Baseline/export verified, ROM entered, formatting not started | Begin only the exact reviewed sector list; erase and read back one full sector before moving on | No autonomous protection if the device is powered normally instead of re-entering ROM |
| Erase/program interrupted or readback differs | Return to ROM; read actual state; repeat erase or restore the sector from the baseline and verify | USB_KEY and ROM writer behavior after interruption are not proven on this target |
| Any slot sector incomplete or candidate page non-FF | Stay in ROM and resume or restore; do not execute SPL | No claim about SPL behavior for arbitrary transient bytes |
| All slots formatted and read back; outside extents/protected components match; export/import checked | Only then allow ordinary boot and application checks | Still no physical cold-boot, SAVE, stock-loader or owner acceptance from this offline design |
| Rollback selected | Restore all changed sectors from the exact pre-migration snapshot in ROM; compare complete 1 MiB readback to its digest | Prior bounded single-sector restoration does not prove a 24-sector/full-image restore |

The physical ROM route is independent of the app soft key, which may be unavailable when needed. Project sources report USB_KEY-at-power-on on other FM-1s; the project dongle has build/simulation evidence but has not been tried on this target. A fresh same-target recovery witness is therefore required before relying on it.

## Concrete sequence

1. **Freeze the actual target.** Obtain two fresh, complete, matching 1 MiB reads tied to current installed identity/mode; hash and retain privately. Do not substitute archived device40 or require current firmware to be stock FM-1_092. Pin current SPL, OTA, cfg, key/protected ranges, and every proposed slot sector. Reconstruct the exact pre-migration image and verify its full digest.
2. **Preserve old state.** Save original VM/USR and every touched sector in two durable private copies with hashes. Before calling this a migration, decode the version-matched format or create a lossless conversion checked against all supported old data. A raw archive allows byte restoration but does not prove new-firmware semantic availability.
3. **Recheck ranges and scans.** Keep the live OTA range `[0xE0000,0xE5000)` and record at `0xE4F00` untouched. Prove no write/erase reaches SPL, OTA, cfg, key data or unassigned ranges. Enumerate every relevant SPL/cleanup candidate from the exact pinned scan against the fresh baseline; the eight-page archived summary is insufficient.
4. **Prove the recovery path before erasing.** Coordinator-owned physical review should establish USB_KEY-at-power-on into mask ROM on this same target and test the exact reviewed read/erase/program/readback recovery path in a bounded scratch sector. The earlier `0xD8000` program/read/restore proves that specific sector/test only. Use existing physical review/admission for the proposed ranges and image; this note creates no new owner-approval gate.
5. **Hold ROM throughout first format.** Start from fresh ROM enumeration and the reviewed RAM loader. Erase one exact slot sector at a time; read back its full 4 KiB and log before/after hashes durably off-device. Never jump to SPL, normal reboot, or OTA while any slot sector is incomplete. On interruption or lost acknowledgement, use USB_KEY at power-on to re-enter ROM before inspecting, retrying, or restoring. Do not blind-retry a timeout.
6. **Check the post-format invariant.** Read every slot sector; verify map/capacity; confirm all 24 candidate pages are 0xFF; compare every byte outside exact slot extents against the frozen baseline. Verify SPL/OTA/cfg hashes and OTA staging/record are unchanged. Keep SAVE disarmed until independent ownership, RAM-closure, watchdog, NOR and migration checks are complete.
7. **Choose forward completion or rollback in ROM.** Forward completion needs lossless state import, a valid initial journal generation, and exact readback. Rollback restores original bytes for every changed sector and verifies the complete-device digest. On interruption, re-enter ROM and resume from observed readback, never assumed command completion.
8. **Permit ordinary boot only after verification.** Then capture identity, boot selection and app startup independently. This still does not prove proprietary OTA acceptance, full-song behavior, or release readiness.

## Why clean-sector-only relocation does not immediately solve it

[inferred from verified map arithmetic; not a claim that any sector is available] Within the same VM/USR-minus-OTA envelope, the five spare sectors cannot replace all eight dirty trailer pages while retaining 24 sectors and the full payload in both generations. A wider search may find additional erased candidate pages, but erased bytes alone do not establish stock allocator ownership. Protected or unnamed sectors require separate exact ownership and scan evidence. A one-slot or compressed-only fallback changes journal recovery or the supported-state bound and is not equivalent.

The ROM-held process addresses the transition risk by keeping SPL away from intermediate states while recovery remains available and is used before every restart. An interruption becomes an operator recovery event, not a boot-safe state. If the requirement is autonomous cold boot after any interruption, this design is insufficient; next work must find 24 clean, semantically releasable sectors or redesign the record/boot interaction while retaining capacity and rollback.

## Evidence still needed

- [verified: present] The offline planner refuses archived non-FF tails and emits no erase sequence. The test-only 256-tail mapper covers already-formatted slots with 43,130-byte host fault injection; it does not model first format or physical power loss.
- [reported: recovery notes] USB_KEY-at-power-on reports exist for other FM-1s. The project dongle remains untried on this target.
- [unresolved] Fresh current-target pair and provenance; raw plus semantic VM/USR export; full candidate inventory; same-target USB_KEY witness; range-specific interruption/recovery; multi-sector rollback; physical format readback; post-format boot and owner acceptance.
- [verified: scope] This note creates no new prohibition. Expanded-layout authorization already exists; the coordinator should assess the exact sector list and existing recovery authorization against it, clarifying only if that scope does not cover the proposed operation.

## References

- `notes/2026-10-14-tail-migration-archived40-inventory.md`
- `notes/2026-10-14-tail-migration-first-format-plan.md`
- `notes/2026-10-14-spl-record-scan-proof.md`
- `notes/2026-10-14-spl-record-window-mapper.md`
- `notes/2026-10-14-storage48-migration-plan.md`
- `notes/2026-10-14-tail-page-io-adapter.md`
- `notes/2026-10-07-fm1-softkey-bench.md`
- `docs/10-usb-key-dongle.md`, `docs/17-recovery.md`

