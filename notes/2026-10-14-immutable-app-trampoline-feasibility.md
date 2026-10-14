# Immutable first-sector trampoline: offline feasibility review

Date: 2026-10-14. Design-only review against tracked source, retained SPL disassembly notes, and existing image measurements. No code/package/layout change or device/USB/MIDI/flash/power/reset operation occurred.

## Decision

**Plausible for subsequent updates, not currently implemented or admitted.** A fixed XIP entry in [0x4000,0x5000) could validate the mutable application before branching into it and choose a separately persisted recovery loader on failure. This directly addresses the observed SPL behavior: its valid 32-byte app-area header is sufficient for ordinary XIP selection, and that success path bypasses trailer rescue scanning. The SPL does not validate the whole XIP payload before jump. See notes/2026-10-14-spl-header-rescue-audit.md and notes/2026-10-11-stock-spl-final-contract.md.

This can only protect later writes which preserve the entire first sector and independent rescue storage. It does not make the initial conversion safe. Fresh identity, paired backups, reviewed initial image/recovery plan, and watched physical acceptance remain a separate bootstrap gate. This review establishes neither NOR atomicity nor storage ownership and authorizes no layout/write.

## Source-grounded path

[verified in SPL disassembly review] Entry XIP 0x02000120 maps to raw 0x4120. The app-area header starts at 0x4000. SPL checks the top directory and selected 32-byte app-area header, then normal success bypasses the rescue-record loop. A body rewrite can thus leave a valid old header selecting partially rewritten code.

[verified in tracked source] Dinghy crt0.S starts with the required `goto +4; rts`, saves incoming state, disables interrupts, sets user/supervisor stacks, then calls fm1_cstart. app.ld maps .text/.rodata to XIP 0x02000120. platform.c initializes .bss, .pool, .data, and .ram_text during C startup. A validator must execute before fm1_cstart and must not depend on mutable application data, pools, runtime services, or initialized libraries. Its pre-C ABI, stack, watchdog behavior, and flash-read path are not target-verified.

Only 3,808 bytes exist from entry 0x4120 to 0x4fff. The app-area descriptor occupies the same first sector and current tools/jieli/expanded_flash_profile.py regenerates it using app size/CRC. No current builder/updater promises [0x4000,0x5000) immutability. A future fixed profile must freeze the descriptor/extent and preserve every byte of that sector across body revisions.

## Conditional protocol sketch

1. After an independently accepted bootstrap, leave [0x4000,0x5000) byte-identical. The fixed entry validates a versioned manifest and complete declared body before branching to normal entry. Missing, malformed, oversized, out-of-range, or mismatched state fails closed.
2. Place a bounded independent recovery image and redundant metadata in an extent proven owned. Verify record, compressed/raw lengths and checksums before copying to safe RAM and entering it; do not rely on mutable app startup or libraries.
3. The updater never touches first sector or recovery bytes. Write only declared body, read back and validate it, then publish new metadata. During body updates, the old digest should fail, selecting recovery. Metadata torn-write outcomes must be designed/tested as old-valid, new-valid, or invalid. Redundant records do not establish physical atomicity.
4. Keep recovery until a later image has passed cold startup/readiness gates. Header validity alone is not a cleanup condition.

Manifest records need generation, format/version, bounded fixed extents, declared length and digest; choose the newest fully valid record and fail closed on ambiguous/equal-generation disagreement. Cover every mutable executable/constant/data-init byte, excluding only manifest space. CRC detects accidental errors but is not authentication; signatures/keys are a separate threat-model decision.

0xD8F00 is only a candidate SPL scan record if it and its referenced payload match the exact SPL format. A private trampoline manifest is a distinct format. Existing Dinghy staging at 0xE0000/record 0xE4F00 is another layout and cannot be presumed reusable.

## Geometry

Proposed tail [0xD7000,0xD9000) is 8,192 bytes; VM begins at 0xD9000. Existing compressed Dinghy/Felucca package is measured 6,954 bytes and its SPL record 80 bytes. Arithmetic leaves 1,158 bytes around the record, but does not validate this custom loader/manifest format, ownership, or linker bounds. Its measured runtime .text is 8,232 bytes and .bss 11,216 bytes; these are RAM costs, not staged-byte count.

Current full-song app plus preserved metadata ends at 0xD7674. Tail start D7000 overlaps tool/config records by 1,652 bytes. Correct app budget with this tail is 860,644 bytes; current image is 862,296 bytes and misses by 1,652 bytes before trampoline/manifest/alignment/growth. This supersedes earlier optimistic geometry in notes/2026-10-14-rescue-tail-fit-measurement.md. A fresh feature-equivalent profile must prove fit; “16 KiB headroom” does not apply to this exact image.

Two compact records might fit in the arithmetic gap around the existing package, but no range is allocated and current OTA erases all five stage sectors. A writer must preserve metadata separately from rescue code or use a new measured layout. Any overlap with app, config, stock VM/BTIF/USR, or OTA stage is refusal.

## Existing implementations

The repository includes the pinned zlib-licensed `firmware/third_party/tinf` decoder (upstream commit `57ffa1f1d5e3dde19011b2127bd26d01689b694b`), used for bounded wavetable startup decompression. It is not an app verifier or decoder for the measured LZ4-block Dinghy package, and supplies no manifest or rollback protocol. No reusable first-sector validator or redundant manifest implementation was found in the scoped source. Reuse existing formats/code only after matching the target bounds; no new codec is justified by this note.

MCUboot is a useful maintained comparison: it validates before execution and persists trailer/swap progress to resume interrupted swaps. It is not drop-in here because bootloader layout, storage geometry, and hardware minimum write-size are unestablished. Its docs explicitly treat minimum write size as a flash property. References: [MCUboot design](https://docs.mcuboot.com/design.html), [imgtool sizing](https://docs.mcuboot.com/imgtool.html).

## Gates before any implementation/admission

- Verify exact SPL accepts a frozen descriptor without requiring changing body CRC/length; build two body revisions and byte-compare first sector.
- pi32v2-link a fixed-entry section below raw 0x5000; inspect map/instructions; prove startup ABI, stack, IRQ/watchdog and bounded streaming digest before C runtime. Do not buffer the whole app.
- Define versioned, overflow-safe manifest and digest coverage with golden/malformed/torn-copy tests. Do not claim authenticity absent signature/key proof.
- Rebuild recovery for its final extent; prove decompression bounds, RAM .text/.bss/stack, entry ABI, independent USB update loop, and readback. Keep a separate route for damaged trampoline/rescue as a bootstrap/hardware requirement.
- Verify every writer preserves boot and rescue bytes, updates only bounded body, verifies before metadata publication, and refuses overlaps. Cutpoint tests must evaluate boot-choice predicates after each sector and record write interruption.
- Fresh target image/link receipt must fit the intended feature selection with tail plus preserved tool/config and growth margin. Current full-song receipt is over budget.
- Initial installation and watched physical cold-boot/interruption acceptance remain independent.

## Conclusion and next dependency

The design could avoid poisoning a stock app header on future updates if immutable entry execution, full-body verification, independent recovery, fixed metadata, and all writer boundaries are proved. Current code does not implement it; the first-sector descriptor is regenerated, the exact full-song image misses the tail budget, and loader format/ownership/target ABI are unresolved. Keep it as a design candidate, not a recovery guarantee.

Next: obtain a feature-preserving production profile which fits with a bounded tail, then do a target-ABI/linker spike for a fixed verifier without image admission. In parallel define concrete manifest/recovery extents which do not rely on SPL rescue while ordinary headers pass. Initial migration remains a separate physical gate.
