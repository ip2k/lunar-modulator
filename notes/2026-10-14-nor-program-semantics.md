# NOR page-program semantics and CRC-poison admission

2026-10-14. Offline source/datasheet audit on exact base
`97e073c08875a80c840510af9e4a1bec1d844fc3`, branch
`codex/2026-10-14-nor-program-semantics`. No device interface was opened and
no USB, MIDI, flash, power, reset, or reboot action was run. This note does not
change firmware source or grant flash-range ownership.

## Decision

[verified] The proposed CRC-poison protocol must **not** be admitted as a
power-loss-safe transaction on current evidence. The XOR model proves only that
an ideal raw one-bit alteration of the captured header CRC can flip its
validation result while leaving the remaining header bytes unchanged. It does
not show that the FM-1 flash accepts or guarantees such an atomic physical
operation. The audited retained-loader write path accepts aligned 256-byte
pages, not a one-bit programming primitive. Puya's matching-family datasheets
explicitly describe data in the interrupted program/reset region as potentially
damaged or lost; they do not guarantee the requested old-or-new one-bit outcome,
page collateral behavior, or unchanged bytes after supply collapse. Requiring
readback can detect an invalid/partial result after power remains available; it
cannot establish a result if the unit loses power during the operation.

[verified] This is a proof gap, not proof that a particular chip will corrupt
other bytes in every interruption. Treat the proposed poison-and-rescue order as
unproven until exact fitted-part evidence and a separately authorized physical
characterization establish the needed behavior and rollback invariants. Do not
use an intentional power interruption as a test outside a reviewed, owner-led
bench plan.

## Part identity and manufacturer sources

[reported: retained captures and prior source notes] Two existing evidence
streams record ROM-reported JEDEC bytes `85 60 14` and 1 MiB geometry:
`notes/2026-10-07-fm1-softkey-bench.md` and
`notes/2026-10-05-community-repos.md`. They do not identify the die marking,
exact Puya suffix/revision, package, or in-package SiP assembly.

[verified: manufacturer datasheets] Puya's [P25Q80H datasheet V1.7](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80H_Datasheet_V1.7.pdf) gives the RDID tuple `85 60 14` in its ID Definitions table, and the [P25Q80SH datasheet V1.5](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SH_Datasheet_V1.5.pdf) gives the same tuple. Therefore this ID and 1 MiB capacity are consistent with more than one manufacturer part; they are not enough to assert that the installed flash is the H or SH variant. A chip marking, controlled BOM/assembly record, or uniquely identifying manufacturer read-only property is still needed before applying suffix-specific guarantees.

[verified: manufacturer behavior caveat] The P25Q80H V1.7 software-reset section (§10.40; manufacturer PDF page 53) says that if reset is executed during program/erase, the operation is disabled and the data under processing “could be damaged or lost.” The P25Q80SH V1.5 status-register description (manufacturer PDF page 30) defines EP_FAIL as set when program/erase failed or was interrupted by reset; this is an error indication, not a guarantee of data integrity. The manufacturer document describes software reset, not a formal supply-collapse envelope. Neither source promises atomic mutation of one CRC bit or that all other bits/bytes remain stable when power is interrupted. Their program-time table values are typical/characterization figures, not atomicity guarantees.

The datasheets describe Page Program (`02h`) as programming the selected page with up to 256 input bytes. This defines the operation and normal geometry; it does not promise that a power cut during internal programming leaves either the exact old page or exact requested new page. A 1-byte data payload, if accepted by a part, would still invoke a Page Program operation and would not by itself establish one-bit or neighboring-byte atomicity.

## Reviewed transport/loader boundary

[verified: retained native listing audit] `notes/2026-10-11-fixed-loader-nor-write-review.md` records the pinned vendor-object-disassembly trace. Its exact fixed-loader FB04 path takes CDB address and length but the reviewed admitted request is exactly 256 bytes at a 256-byte-aligned address. It feeds the complete page to the NOR driver's opcode `02h` primitive. The driver transfer length is caller-supplied, but the fixed-loader handler is the relevant reviewed external path; this evidence is not permission to expose arbitrary shorter writes. The fixed path has no application partition policy, and the handler ignores the lower write result. Host-side durable intent and verified readback are necessary for ordinary completion evidence, but still cannot promise power-loss atomicity.

The companion note names/hash-pins the original encrypted/decoded and fixed encrypted/decoded loader artifacts, fixed profile, vendor listing, and objdump; see its “Exact inputs and tooling” table. It found the internal NOR driver unchanged between original and fixed candidate, but that source trace is transport and command behavior, not silicon interruption characterization. The historical 2026-10-07 matched dumps and bounded write/restore were completed operations; they do not test a torn page-program event.

## Required gates before any CRC-poison design can be considered

1. Establish the exact fitted device/suffix and relevant revision using non-destructive evidence (package/BOM/assembly provenance, or a manufacturer-supported unique identifier that actually distinguishes the parts). Do not derive it from JEDEC `85 60 14` alone.
2. Obtain manufacturer confirmation/specification covering minimum operation granularity, interrupted Page Program under loss of VCC, possible page/array collateral, and startup/recovery behavior for that exact part and operating envelope. “NOR bits only clear” and ordinary successful programming are insufficient.
3. If the manufacturer leaves torn-program semantics unspecified, the owner/coordinator must authorize a separately designed physical characterization; measure only on a sacrificial compatible part with controlled supply-cut points and complete pre/post array reads. This is not authorized by this offline task and must not be done on the owner's FM-1 as an incidental experiment.
4. Independently prove the SPL fallback route and preservation invariant across each permitted cut point, including the old application header no longer passing SPL validation before app payload mutation, a valid rescue record plus complete referenced loader, and recovery through the actual boot chain. The software model's idealized one-bit premise is not a substitute.

Until these gates close, leave the currently reviewed stock boot components and protected bank contents unchanged and do not claim the raw CRC bit poison is a safe atomic primitive.

## Sources and scope limits

- Puya, [P25Q80H V1.7 datasheet](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80H_Datasheet_V1.7.pdf), RDID ID Definitions and §10.40 software reset.
- Puya, [P25Q80SH V1.5 datasheet](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SH_Datasheet_V1.5.pdf), RDID ID Definitions, Page Program operation and EP_FAIL status bit.
- Existing source audit: `notes/2026-10-11-fixed-loader-nor-write-review.md`.
- Existing identity/readback evidence: `notes/2026-10-07-fm1-softkey-bench.md`; corroborating reported ID sources: `notes/2026-10-05-community-repos.md`.
- Prior offline SPL control-flow audit and header-CRC model reviews establish only their stated predicates/control-flow and idealized transform. Neither provides physical torn-program evidence.

No datasheet guarantee was inferred from typical timings, status bits, successful normal writes, or JEDEC identity. No physical flash operation was performed or authorized by this audit.
