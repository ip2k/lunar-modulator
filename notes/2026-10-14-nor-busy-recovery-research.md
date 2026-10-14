# Puya 85 60 14 identity and NOR-busy recovery evidence

Date: 2026-10-14. Offline manufacturer-source review on exact base
`3807f3de8d0e1d1ef9b659678a1b15607835bc5c`, branch
`codex/2026-10-14-nor-busy-recovery-research`. No firmware source or admission
policy was changed.

## Decision

[verified] JEDEC RDID `85 60 14` identifies an 8-Mbit Puya SPI NOR density/type,
not a unique orderable suffix. Puya datasheets explicitly assign the same tuple
to P25Q80H, P25Q80SH, P25Q80U, P25Q80L, P25Q80SL and P25Q80SLE. This list is
only the variants confirmed in manufacturer documents reviewed here, not a
claim that it exhausts Puya history. Their operating-voltage ranges differ:
H/SH are 2.3–3.6 V, U is 1.65–3.6 V, and L/SL/SLE are 1.65–2.0 V. The FM-1's
ROM-reported ID alone therefore cannot establish the fitted suffix, reset
feature set, or applicable timing table. Do not select a less-conservative
watchdog or reset policy from this ID.

[verified] Reset is not a safe escape from an in-progress operation in the
reviewed documents. H and U document the 66h/99h software-reset sequence and
warn that reset during program/erase disables the operation and data under
processing could be damaged or lost. SH documents RESET#; driving it low during
program/erase terminates the operation and data could be lost. H's parameter
table reports its hardware RESET# pin as unsupported. Thus even the flash's
own reset mechanisms are not a recovery primitive during WIP. This does not
prove what the FM-1's MCU watchdog toggles: no evidence reviewed shows that the
watchdog toggles an external NOR reset pin or removes NOR power.

[verified] Puya's power-transition protection language is narrower than a
rollback guarantee. SH says the state machine initializes to standby on power
up and lists POR/command validation/WREN protections against accidental write
cycles. That text does not promise old-or-new contents after loss of power
mid-program/erase, nor does it state that a bootloader can safely fetch XIP
while an interrupted operation remains busy. Power-up initialization cannot
be used as evidence that bytes being processed were preserved.

## Watchdog assessment for current firmware

The existing task notes and pinned SDK evidence show an 8-second reset-mode
watchdog, normally fed from the main loop through XIP code. The destructive NOR
path disables XIP and polls status from RAM. Its safe return condition is a
completed status transaction positively reporting WIP clear; when transport
or WIP remains unknown it cannot return to XIP. The normal-loop feed is not
available in that interval.

No safe bounded watchdog policy is established by these datasheets. Not feeding
allows the MCU watchdog to reset while NOR readiness may be unknown. Feeding
only while busy can keep the CPU trapped indefinitely if status stays busy or
unreadable, and the existing feed path is not a verified RAM-resident closure.
A nominal/max erase timing row is not a recovery guarantee: the exact part is
unknown, the datasheets' timing notes describe characterization, and neither
document guarantees interrupted-state recovery. Do not add a busy-loop feed,
watchdog disable, forced reset, finite timeout returning to XIP, or a claim that
the SPL can recover from a watchdog reset during WIP.

## Minimum next evidence and implementation gate

1. Resolve the fitted suffix and actual NOR VCC from a controlled BOM/package
   marking or manufacturer-supported identifier. The retained board evidence
   does not provide either.
2. Obtain primary evidence for that exact part covering power loss and MCU
   reset while each relevant Page Program/Sector Erase is active, including
   post-reset command/read behavior and affected-data guarantees. The present
   reset sections warn of possible damage/loss; POR text only addresses
   accidental commands.
3. Determine from authoritative JieLi documentation and board schematic whether
   the 8-second MCU watchdog reset affects the external NOR RESET# or supply,
   then trace the SPL's first NOR accesses against the documented busy behavior.
4. Until those facts and a recovery design are reviewed, leave native SAVE
   disabled. Preserve the current rule that ordinary return/XIP restoration
   requires positive-ready status. A host test or normal successful operation
   cannot establish watchdog/power-loss recovery.

If no manufacturer guarantee exists, any electrical characterization must be a
separately designed, owner-authorized sacrificial-part experiment; this task did
not authorize or perform it. Do not test by interrupting the owner's flash.

## Primary sources and cross-checks

- Puya [P25Q80H datasheet V1.7](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80H_Datasheet_V1.7.pdf): RDID table, software reset section, parameter table (H hardware RESET# unsupported).
- Puya [P25Q80SH datasheet V1.5](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80SH_Datasheet_V1.5.pdf): RDID table, RESET# behavior, and data-protection/power-up language.
- Puya [P25Q80U datasheet V1.8](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80U_Datasheet_V1.8.pdf): RDID table, 1.65–3.6 V range and reset-during-WIP warning.
- Puya [P25Q80L datasheet V1.7](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80L_Datasheet_V1.7.pdf), [P25Q80SL datasheet V1.5](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SL_Datasheet_V1.5.pdf), and [P25Q80SLE datasheet V1.0](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SLE_Datasheet_V1.0.pdf): reviewed RDID tables also print `85 60 14`.
- Puya [P25Q80SH product page](https://www.puyasemi.com/en/h_series653/3173.html), [P25Q80H product page](https://www.puyasemi.com/en/h_series653/3172.html), [P25Q80L product page](https://www.puyasemi.com/en/l_series483/3141.html), and [official downloads catalog](https://www.puyasemi.com/en/download.html) for family voltage ranges and current datasheet revisions.
- Existing project audits: `notes/2026-10-14-nor-part-interrupt-evidence.md`, `notes/2026-10-14-native-nor-wdt-strategy.md`, `notes/2026-10-14-nor-program-semantics.md`; pinned SDK and writer references are recorded there.

No device command, USB/MIDI/flash/power/reset operation, target measurement, or
SAVE enablement occurred. This establishes manufacturer-documented identities
and warnings only; exact fitted part, MCU watchdog-to-NOR electrical coupling,
and physical recovery remain unknown.
