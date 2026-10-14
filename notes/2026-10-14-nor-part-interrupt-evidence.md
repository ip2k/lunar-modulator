# NOR part timing and pi32v2 interrupt evidence

Date: 2026-10-14
Task branch: codex/2026-10-14-nor-part-interrupt-evidence
Base: b0db316372ca65e92b20a097480e2a8f81c1d995

## Findings

The retained flash identity is JEDEC 85 60 14. That code is not sufficient to select a part-specific erase-time contract: Puya publishes P25Q80H and P25Q80SH documents with that same ID. The currently available device evidence does not include a legible package marking, BOM/order code, or other evidence that distinguishes H from SH. Do not choose the faster timing profile from the JEDEC bytes alone.

The two official datasheets specify different maximum erase intervals at Ta=-40 to +85 C:

- P25Q80H datasheet V1.7: page program 3 ms max; page, sector, and block erase 20 ms max; chip erase 20 ms max in the AC table. The timing footnote says guaranteed by characterization, not 100% production tested.
- P25Q80SH datasheet V1.5: page program 3 ms max; page/sector/block erase 30 ms max; chip erase 180 ms max. Its timing footnote likewise says characterization, not 100% production tested.

The Puya SH product listing advertises -40 to +105 C, while its cited datasheet AC table is specified at -40 to +85 C. The H product listing also advertises a broader range than the H datasheet timing table. Treat the datasheet table conditions as the supported timing envelope; do not silently extend the datasheet guarantee based on the listing.

Both datasheets warn that issuing software reset during program or erase disables the operation and can damage or lose data being processed. This is evidence against a reset-as-recovery shortcut, not evidence that a CPU watchdog reset behaves identically or that the part will be safe after any reset. No watchdog/reset experiment is authorized here.

The pinned SDK asm/irq.h implements local_irq_save(flags) by reading icfg, clearing bit 8 in the saved value, and writing it back; local_irq_restore(flags) writes the saved ICFG value. The current Dinghy-derived flash header follows this source pattern. This proves the software macro contract used by this SDK revision. It does not establish the pi32v2 ISA semantics of ICFG, nesting behavior, interrupt priority behavior, memory barriers, or whether an arbitrary direct ICFG write is architecturally equivalent. No authoritative public pi32v2 architecture/register manual establishing those details was located in this bounded review.

The pinned SDK defines WDT_8S as 0x0D and documents wdt_reset_enable() as enabling a direct system reset. The current flash routine's fl_wait_ready() loops in RAM until a valid status transaction observes WIP clear; after status transport failure or persistent WIP it does not return to XIP. Its nominal max_us is a lateness diagnostic, not an escape bound. This avoids knowingly returning to XIP while readiness is unknown, but the armed 8-second watchdog may reset the system during that indefinite wait. Neither the part datasheets nor the pinned SDK source proves that such a reset during active/unknown NOR operation reaches a safe recovery path. The watchdog interaction remains an admission blocker.

## Minimum implementation candidate

1. Keep the SAVE writer disabled. Do not use JEDEC 85 60 14 by itself to pick H versus SH timing, and do not use software reset or watchdog reset as a recovery primitive.
2. Resolve the actual ordered part from a documented board BOM or readable package top marking, then bind a reviewed manufacturer timing document and operating range to that identity. If identity cannot be resolved, retain the more conservative characterized timing values only as diagnostics; this does not resolve stuck-WIP or authorize XIP restoration.
3. Preserve the positive-ready rule: normal return/XIP restoration only after a valid status read positively reports WIP clear. A finite timeout that returns into XIP on unknown readiness is not a safe timeout policy.
4. Before enabling the path, obtain a vendor-supported pi32v2 ICFG/interrupt-state contract or an equivalent authoritative SDK/ISA reference; verify the compiled save/restore sequence and required calling-context constraints for the real target. Host modeling cannot establish these CPU semantics.
5. Resolve watchdog behavior while the flash call graph is RAM-resident and NOR status is unknown. Require vendor evidence or a separately reviewed, target-verified terminal/recovery design before claiming safety. Do not add unconditional watchdog feed/disable/reset behavior.

## Sources and limits

- Puya P25Q80H datasheet V1.7 (official PDF): https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80H_Datasheet_V1.7.pdf
- Puya P25Q80SH datasheet V1.5 (official PDF): https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80SH_Datasheet_V1.5.pdf
- Puya P25Q80SH product page: https://www.puyasemi.com/en/h_series653/3173.html
- Pinned SDK source: /home/claude/mvave-fm1/sdk-v1213/source-sdk/include_lib/driver/cpu/wl82/asm/irq.h and asm/wdt.h.
- Project code inspected: firmware/third_party/dinghy/hal/fm1_flash.h.

This is source and retained-identity research only. No device command, flash operation, timing measurement, reset test, writer enablement, or admission decision was made. The part suffix, pi32v2 architectural IRQ semantics, and watchdog behavior during NOR busy remain unverified.



## Rendered AC table cross-check

I rendered the official PDF page 11 images and read Table 5-4 directly; this confirms the units and column positions rather than relying on flattened PDF text.

| Part / source page | Operation | Min | Typ | Max | Unit |
|---|---|---:|---:|---:|---|
| P25Q80H V1.7, page 11 of 70 | Page program (256 B) | blank | 2 | 3 | ms |
| P25Q80H V1.7, page 11 of 70 | Page erase | blank | 8 | 20 | ms |
| P25Q80H V1.7, page 11 of 70 | Sector erase | blank | 8 | 20 | ms |
| P25Q80H V1.7, page 11 of 70 | 32 KiB block erase | blank | 8 | 20 | ms |
| P25Q80H V1.7, page 11 of 70 | 64 KiB block erase | blank | 8 | 20 | ms |
| P25Q80H V1.7, page 11 of 70 | Chip erase | blank | 8 | 20 | ms |
| P25Q80SH V1.5, page 11 of 101 | Page program (256 B) | blank | 1.5 | 3 | ms |
| P25Q80SH V1.5, page 11 of 101 | Page erase | blank | 16 | 30 | ms |
| P25Q80SH V1.5, page 11 of 101 | Sector erase | blank | 16 | 30 | ms |
| P25Q80SH V1.5, page 11 of 101 | 32 KiB block erase | blank | 16 | 30 | ms |
| P25Q80SH V1.5, page 11 of 101 | 64 KiB block erase | blank | 16 | 30 | ms |
| P25Q80SH V1.5, page 11 of 101 | Chip erase | blank | 80 | 180 | ms |

The H and SH tables really do print these chip-erase figures in milliseconds. This is a transcription of the datasheet, not an independent plausibility claim or a measured erase time. The operative maximum erase entries are the Max column; the values in the Typ column are typical values at 25 C per each table's note. The table heading specifies Ta=-40 C to +85 C. Page renders were generated from the official PDFs linked above with pdftoppm and inspected at full resolution.

