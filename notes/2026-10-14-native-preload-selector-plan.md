# Native preload selection: design and safety boundary

Date: 2026-10-14  
Source base: 635dc019e3164fb84b330d590036dbfe2e44440a  
Scope: design-only review; no production code or hardware actions.

## Decision

Implement the first native selector as a **cold-boot chooser** that runs before fm1_audio_init and before fm1_app_init. It chooses one immutable, already embedded project asset by catalogue index, then starts exactly one app through the existing cold-start path. Keep the current compiled startup index as the default/timeout choice. Do not add an in-app hot switch or claim rollback to a running project yet.

This supports choosing among the projects embedded in that firmware image. It does not add project persistence or change which project survives a power cycle. With native SAVE currently disarmed and no physical storage ownership admitted, a selection is a boot-time choice only.

## Evidence in this source tree

- firmware/native/app_probe.c:175-211 initializes the app and external instance pool, binds storage, and starts the one asset selected by LUNAR_STARTUP_PROJECT_INDEX. The selected asset must have kind FM1_STATE_PROJECT. The startup failure branch stops audio, detaches USB, waits, clears the boot guard, and enters UBOOT; it does not attempt a second project on a partially mutated app.
- firmware/native/project_start.h documents that lunar_project_start is cold-start-only, before input/render, and is not a live transactional replacement API. Restore failures after mutation require discarding the cold app.
- firmware/native/project_boot.c:65-139 enforces an unrendered app (frames == 0), empty audio units, an empty instance pool, and a valid pool/storage binding. It preflights project units, allocates temporary sequence and DX7 scratch, stages and applies engines, adopts units, restores MIDI/scalars/modulation/view. A later failure can occur after app or pool mutation.
- firmware/native/project_engines.c:13-23 releases candidate-owned units and their pool allocations, but only while that candidate still owns them. After adoption, ownership has moved to the app. There is no general app destroy/reset routine for the native external arena in this path.
- firmware/native/instance_pool.c:13-29 initializes TLSF and accounting. Reinitializing this allocator over live units would invalidate ownership/accounting; it is not a safe cleanup operation.
- tools/native/build_application_probe.py:391-400,434-441 adds and roots project_units.c, project_mod.c, project_seq.c, project_engines.c, project_start.c, and project_boot.c for the dedicated native loader. It does not link sim/web/src/fm1_app_state.c as the project replacement route.
- The generic fm1_app_state_load in sim/web/src/fm1_app_state.c:1415-1445,1786-1890 does preflight, then resets the same fm1_app_t in place and reapplies a project. However, this file is absent from the native link roots, and declares g_w[480 * 1024] at line 25 plus other large static buffers (g_json, g_bin, g_set, g_seq_scratch). Its pass-1/pass-2 behavior is not evidence of native arena cleanup or ISR safety. It is not a justified shortcut for this target.
- firmware/third_party/dinghy/src/platform.c:305-340 initializes input and LCD, then calls fm1_audio_init before enabling IRQs and entering app_main. Startup recovery already scans input for 50 ms and draws a recovery UI before normal audio initialization (firmware/third_party/dinghy/src/recovery.c). This demonstrates an audio-off input/display window that a bounded chooser could use, but not a finished selector implementation.
- fm1_audio_stop only clears the ALNK control bit (platform.c call sites at lines 268 and 290; confirm the implementation before coding). The ALNK interrupt path writes DMA buffers and calls app rendering. A register-bit clear alone is not proof that an in-flight callback/ISR has drained or that queued USB/MIDI events and held notes are safe for destroying a live app.
- fm1_app_all_notes_off exists and releases active notes, but does not establish IRQ/DMA quiescence or free every external arena allocation. The MIDI input handler also has a bounded event queue/poll path in firmware/native/app_probe.c; live switching would need to account for events arriving during teardown.
- firmware/native/content_catalogue.h represents embedded assets as immutable const byte ranges. tools/native/embed_image_content.py emits a catalogue of selected assets and bytes. A chooser can hold a validated numeric index and a pointer into XIP; it need not copy project data or hold two applications in RAM.

## Proposed boot chooser contract

1. Run after the platform has initialized LCD and input, and before fm1_audio_init, timer/IRQ enable, or app_main app construction. Prefer a platform hook returning a bounded catalogue index over moving app initialization into UI code.
2. Offer only catalogue entries with kind FM1_STATE_PROJECT; never include set assets. Validate selected index, asset pointer/size, and a bounded entry count before returning it.
3. Start from the existing LUNAR_STARTUP_PROJECT_INDEX as the default/timeout selection. Keep that default when the chooser is disabled, input is absent, or the wait expires. Do not persist the choice to flash.
4. Do not allocate project-sized buffers, instantiate engines, or initialize another app in the chooser. Draw labels from generated safe metadata or a fixed bounded name table; ensure it cannot dereference malformed data.
5. Invoke lunar_project_start exactly once, before the first render/input dispatch. If it fails, preserve the existing recovery-to-UBOOT behavior. Do not retry on the same partially mutated app or reinitialize TLSF over allocations.
6. Keep save-service admission, bank allocation, catalogue membership, and source content independent from the selector. A selection does not authorize new persistent storage use.

## Unsaved changes and rollback

A cold-boot chooser runs before a project exists in RAM, so there are no in-session edits to discard. Once a project is running, changing to another project remains unsupported. If a later design requires in-app switching, it must first define a user confirmation/dirty-state rule and a safe transaction boundary. Current storage admission does not establish durable rollback; the old project cannot be promised restorable from flash.

The existing project loader can partially mutate the app after constructor/adoption stages. A failed selection therefore cannot safely fall back to another candidate in the same app/pool. Current platform recovery is the honest failure route. If a future implementation wants an automatic default fallback, it must prove whole-app and allocator teardown/reinitialization or perform a controlled full reboot with a bounded no-loop policy, then rebuild from a known default. That is not included in this design.

A live switch would additionally require a reviewed HAL protocol to stop new event admission, release notes, disable and drain audio DMA/IRQ callbacks, quiesce USB/UAC and timers, release every adopted engine and app-owned allocation, reset sequencing/modulation/MIDI state, recreate the allocator, and only then build the next project. No existing function inspected here provides that end-to-end guarantee.

## Resource and acceptance limits

- The chooser itself should need only a small bounded UI/index state and XIP references; no second project image or app pool.
- The assigned linked candidate has roughly 6.5 KiB of XIP headroom (latest assigned app 862,272 B against 868,836 B; verify the matching build receipt before implementation). Keep the UI and strings within this exact linked budget and preserve all 13 engines, effects, voices, and boot guards.
- App instance pool is a separate RAM constraint (216,064 B in the current assigned receipt). The chooser must not assume extra heap or enlarge this pool.
- Source-level/platform logic is not native hardware validation. Any later implementation needs exact-source native link/package checks and owner-reviewed watched hardware startup/playback acceptance; this note authorizes neither installation nor device interaction.

## Next step

Ask the coordinator to review this boundary before implementation. If approved, make a small platform-level pre-audio selection hook with a deterministic timeout/default and only then wire its returned index into the existing single cold project-start call. First inspect the exact current fm1_audio_stop implementation and bootguard/recovery contracts, and build a tiny UI/resource budget against the assigned current link receipt. Keep hot-switch work as a separate design and acceptance gate.
