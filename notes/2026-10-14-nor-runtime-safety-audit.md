# NOR runtime safety audit: stack, RAM closure, watchdog

Date: 2026-10-14  
Source base: \`3c38eaf0534d31363b786e62815cee9a7dfc17da\`  
Scope: source and retained pi32v2 artifact inspection; no admission or hardware action.

## Current writer caller context

\`firmware/third_party/dinghy/crt0.S:_start\` records incoming state, disables interrupts, and assigns \`sp = _ustack_top\` (\`0x01C7A000\`) and \`ssp = _sstack_top\` (\`0x01C7C000\`) before calling \`fm1_cstart\`. The latter initializes the firmware and calls \`app_main\` directly. Main-loop routes reach \`fl_write\` through \`app_main -> settings_save -> fl_write\` and \`platform_poll -> ota_session -> ota_prog -> fl_write\`; neither is an ISR callsite. \`fl_write\` uses \`sp\`, reserves 260 bytes, stages each up-to-256-byte page at \`sp+0\` before the RAM call, and passes its duration output at \`sp+256\`. Linker stack regions are SRAM: user \`0x01C74100..0x01C7A000\`, system \`0x01C7A100..0x01C7C000\`.

This supports SRAM-backed arguments for the current main-loop routes, statically. It is not runtime stack sampling or margin proof. \`firmware/native/project_save.h:lunar_project_save_write\` delegates to abstract \`lunar_project_io\`; no current call binds project SAVE to \`fl_write\`. A future storage callback must re-establish its own caller context and stack margin.

## RAM code and error behavior

The retained link is from source \`76fdd1b9483064e657ba0262f296b0b24ab15cd4\`; its \`fm1_flash.h\` hash matches this checkout exactly: \`49fd8420c40231605d4d76e4772f2f7423d476896bc47bbf61d87fc2818150de\`. ELF SHA \`f5afed6d3433ee30645debcc898c2acf5adebe43d94027a27c04ddd625a30589\`; full disassembly SHA \`ac17e8202aec153e39a45b207bd945d6d24c99108d6b9bfa1b35960cd915e60f\`; RAM disassembly SHA \`e2c769cb654cb102d4061314848e2ba623963b45f98c20d04d20bd4d5926b537\`; audit JSON SHA \`bf5d82dab63844df734241d7175280aecfaed0a555d8a5a37707c86b3906d6ab\`.

The generated \`fl_prog_ram\` is at \`0x01C00580\`, 1084 bytes. Erase/program entry paths contain no out-of-line calls in the retained disassembly; they use stack locals and immediate SFR access. \`fl_write\` disables global interrupts just before the indirect RAM call and restores saved ICFG after return. \`fl_wait_ready\` does not return until a completed status transaction sees WIP clear. If ready eventually appears after a status transport error, it returns \`-5\`; if the nominal threshold was exceeded, \`-4\`; a command error remains an error even if ready later appears. None bypasses the readiness check.

The closure report intentionally leaves static-data closure, whole control-flow closure, runtime pointer residency, watchdog-in-RAM and runtime-XIP-off proof false. Local page staging/direct-branch inspection is bounded evidence, not a complete RAM closure or runtime proof.

## Watchdog boundary

\`fm1_cstart\` arms reset-mode WDT with \`fm1_wdt_arm(0x0D)\`; pinned SDK comments call that eight seconds. \`fm1_wdt_feed\` is XIP \`.text\` at \`0x0204EC64\` and is not called in the RAM erase/program wait. Nominal ready thresholds are 500 ms erase and 10 ms program, but they only report lateness: persistent WIP or status-read failure causes an unbounded loop. The code intentionally does not restore XIP without positive ready evidence.

Thus transient status failures that later recover have a fail-closed software result. There is no demonstrated safe contract for persistent WIP/status failure: the RAM loop cannot return while the armed eight-second watchdog may reset during NOR busy. No retained evidence establishes safe restart for this exact part/board. Relocating only the WDT feed is insufficient; its P33 transaction helpers, literals, stack and timing path would also need RAM closure, while continual feeding could mask permanent busy. Do not disable WDT or rely on reset without evidence.

## Next step and limits

Keep native SAVE unbound/disarmed. Resolve exact-part reset/timing behavior through authoritative device evidence or a coordinator-owned staged experiment with backups and recovery readiness before choosing a WDT policy. Any later SAVE adapter should require main/quiesced context and SRAM-resident source, then rebuild and audit the actual bound caller.

Inspected source chains, stack assignments, retained ELF and vendor disassembly; no rebuild was needed because \`fm1_flash.h\` bytes match. No target execution, watchdog reset, status fault, flash operation or storage admission occurred. Serena still selected the Mac authoritative checkout and was not retargeted; Rarefaction also selected \`/Users/likwid/Developer/mvave-fm1-firmware\`, with fallback C flags and no compile database. Hera direct source/artifact inspection was used; semantic coverage for this isolated checkout was unavailable.

