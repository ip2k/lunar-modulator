# Full-app retained NOR writer closure (analysis only)

Date: 2026-10-14  
Source base: `454046b40e9e2869d061585c0aa71e0b86e915f3`  
Branch: `codex/2026-10-14-nor-real-writer-closure`

## Result

A fresh pi32v2 link of the actual generated application retained the production `fl_erase4k_ram` and `fl_prog_ram` functions by adding an unreachable analysis-only root in a private copied-source overlay. The completed ELF and full disassembly provide stronger evidence than the earlier synthetic object link: on this exact profile, the writer entry paths contain no out-of-line calls while XIP is off. The only call in `.ram_text` is the compatibility `fl_jedec_ram` wrapper calling the other RAM function `fl_jedec_checked_ram`; neither is an erase/program entry path.

This does **not** establish safe SAVE operation. The SAVE service is linked but remains explicitly unadmitted, unbound, unarmed, runtime-unverified and hardware-untested. The writer does not feed the watchdog and keeps interrupts disabled across flash operations; that conflicts with the SAVE service's stated I/O contract. Do not arm or bind it on this evidence.

## Reproduction and inputs

The tracked verifier is `tools/native/verify_nor_writer_closure.py`. It checks exact source anchors before creating its analysis overlay; its target builder changes are applied only to that copied overlay. It does not call the analysis root, emit `app.bin`, emit a regular verification receipt, run packaging or alter the checkout.

- Exact source: `454046b40e9e2869d061585c0aa71e0b86e915f3`.
- Toolchain: JieLi SDK V1.2.13 pinned toolchain `jieli-linux-toolchains-20250324.1`, clang 4.0.1, target pi32v2.
- Container: `lunar-jieli-check:bookworm`, image ID `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.
- Limits: 4 CPUs, 8 GiB memory and swap, 256 PIDs, network disabled, `docker-batch.slice`; source, catalogue, toolchain and headers read-only.
- Catalogue: 16 target-built shards. Prepared Event Horizon profile SHA-256 `bfe627dc60ca5552dfd2f749611105989f7fcfb3c8637840225b377c38ac6972`.
- Build: song-diagnostic, stack watermark, expanded-d7000 profile, project loader and save service linked, startup index 0, Shapes 8, indexed TFT and compressed wavetables.
- Hypothetical, **not admitted**, discontiguous ranges: VM `[0xD9000,0xE5000)` and USR `[0xEA000,0xF6000)`, 48 KiB each. They avoid the BTIF boundary and VM/USR gap, and the settings/globals and key_mac sectors. The existing contiguous project store has no binding to these ranges; no production storage geometry was changed.

Run `python3 tests/test_native_nor_writer_closure.py` and then execute the command recorded in `analysis-inputs.json` (the checked-in verifier rejects a preexisting output directory).

## Artifacts

Private, non-repository output: `/home/claude/mvave-fm1/nor-real-writer-closure-analysis-20261014/run7/build`.

- ELF: `linked/lunar-app-probe.elf`, SHA-256 `7ac7928466e803fd3f0c4b3084d60c24921908f1e098642f2711fc264f0b35bf`.
- Map: `linked/lunar-app-probe.map`, SHA-256 `4ab8519b4b753a987ae225478b1f889dd411cb13c6c01770d0067e6cffbb0ad1`.
- Full target disassembly: `linked/full-disassembly.txt`, SHA-256 `8172e4d901ebc1f560b9ccd52009ce25a9553bc53f4007602da9b7e13514e958`.
- RAM disassembly: `linked/ram-text.txt`, SHA-256 `b0cbc75a9b0f3a0535d43804f67cf0c7f4139436320de90d53cf40b9dd927c58`.
- Final-ELF relocation dump: `linked/linked-relocations.txt`, SHA-256 `151e4a521a2d27dce291316b9e527a4f5ff3a7a58d791e1a4d524ed0c63b611d`. The static linked ELF has no remaining relocation records.
- Machine-readable call audit: `linked/ram-closure-audit.json`; writer-entry calls are empty. One RAM-to-RAM call is recorded from `fl_jedec_ram` to `fl_jedec_checked_ram`.
- Analysis-only builder patch: `builder-overlay.diff`, SHA-256 `91b6494d16cfe4e109eb54a0ef09879e3f2251158ba467ff807c2830992dbf2a`.
- Generated platform delta: `platform-analysis.diff`, SHA-256 `4724ca24a91a3d6fa23bb41f9d6fa4d8515a186dd230e624e5c63af2086b0218`.
- `analysis-inputs.json` records profile/source hashes, build flags, sections and SAVE flags. `linked/analysis-only.json` explicitly says installable=false, hardware_tested=false and release_accepted=false.

## What the final link establishes

The linked ELF has `.text` at `0x02000120` (size `0xCE074`), `.ram_text` at `0x1C00000` (size `0xD60`), `.data` 112 bytes, `.bss` `0x4BE0`, `.pool` `0x66AA0`, and `.noinit` 24 bytes. No `.rodata` section is present.

RAM writer symbols are contiguous in `.ram_text`: `fl_erase4k_ram` at `0x1C00000` (0x3EA bytes), `fl_jedec_checked_ram` at `0x1C003EA` (0x180), `fl_jedec_ram` at `0x1C0056A` (0x16), `fl_prog_ram` at `0x1C00580` (0x43C), `fl_read_ram` at `0x1C009BC` (0x1DE), and `fl_status_checked_ram` at `0x1C00B9A` (0x1C6). The RAM code's SFR references are immediate addresses for cache, SFC, SPI0, pin mux/GPIO and TIMER4. It also consumes caller-supplied RAM pointers for buffers/status/timing. No out-of-line flash-resident helper or constant-pool section was observed in the final writer RAM paths.

The full disassembly shows the ordinary XIP wrappers `fl_erase4k` and `fl_write` entering IRQ-save, using a far function pointer to the RAM helper, and restoring ICFG only after that helper returns. The analysis-only force-retain function references those wrappers to keep them in the final link, but is not reached from startup.

## Blocking integration contract

`firmware/native/project_save_service.h` says the storage I/O must “service watchdog and safely permit unrelated interrupts itself.” The current Dinghy writer instead requires interrupts disabled before entering RAM code, and the wrapper restores the saved ICFG only after RAM code returns. The actual quiesce callback only pauses audio briefly; it re-enables global IRQs before SAVE begins. No admitted I/O adapter reconciles these requirements. In addition, `fl_wait_ready` can wait indefinitely if WIP never clears or status polling never succeeds; WDT feeding and bounded recovery while XIP is unavailable are not proven here. This is a concrete integration blocker, not just missing hardware testing.

## Limits and next dependency

This is a static final-link/call-closure inspection for one analysis profile. It does not prove runtime instruction fetch behavior, flash electrical timing, exact external ROM/cache semantics, worst-case interrupt/audio effects, watchdog operation, or data-pointer residency for arbitrary callers. Absence of static ELF relocations does not prove the CPU never executes from XIP during controller busy time. No emulator or physical device was used.

Next, a separate reviewed design must reconcile the SAVE callback contract with the IRQ-off flash critical section, and provide an approved watchdog/recovery strategy. Only after that should an analysis-only runtime harness or hardware review be considered. The installer/API, physical writer binding, and storage admission remain unchanged and disabled.
