# Shapes voice-cap allocation option - 2026-10-14

## Finding

[verified, compile-time] `engines/src/mi_shapes.cc:132-138` defines `FM1_SHAPES_VOICES`, default 12 and bounded 1-12. Each `Voice` contains a MacroOscillator, 24-sample PCM buffer, envelope/gate/age state, note offsets and glide state (`:165-177`). pi32v2 compile-only size probes give a linear `sizeof(Instance) = 1,608 + cap * 17,108`:

| Cap | Payload |
| ---: | ---: |
| 12 (default) | 206,904 B |
| 8 | 138,472 B |
| 7 | 121,364 B |

These are target compiler type-layout results, not target execution. The catalogue compiler and application probe accept `--shapes-voices` (default 12), but `tools/native/build_demo_image.py` currently hard-codes 12, so the controller cannot select a lower cap.

[verified, allocator-only] Satellite Hearts routes both Shapes tracks to one Shapes unit. Its ordered request payloads are `{10,240 Comet, 5,072 Drawbar, Shapes, 5,072 Drawbar, 49,888 Hall, 11,952 Limit}`. I compiled and executed the unmodified production `firmware/native/instance_pool.c` and TLSF source in pinned WASM32 against a 216,064-byte pool. Assertions verified 32-bit pointers and `size_t`, TLSF alignment 4, minimum block 12, maximum `1<<30`, control size 3,188, pool overhead 8, allocation overhead 4; then exercised `lunar_instance_pool_can_fit` in order:

- 7 voices / 121,364 B: fits the production allocator trial sequence.
- 8 voices / 138,472 B: does not fit.

Temporary probe SHA-256: `b1395da55727251ce946eec26a4bb1faeccdc26fea1d2ec13c4ac7e9d160989d`. Image: `emscripten/emsdk@sha256:e077d54e2b8970575ebc4f185ac1de0b95c05f2b266134d4ba27449af7aebf65`; network disabled, 1 CPU, 1 GiB memory, 2 GiB memory+swap, `docker-batch.slice`, label `codex.task=shapes-voice-cap`. This is allocator arithmetic and ordered reservation execution only. No pi32v2 constructors, module startup, firmware ABI, audio render, or hardware ran; this is not an FM-1 fit or playable-song proof.

Prior nominal modeled charges (round payload plus 16 B/request, excluding TLSF and other runtime allocations) put Satellite Hearts at 289,232 B with 12 voices (73,168 B over pool). Seven voices lower this estimate to 203,696 B, leaving 12,368 B gross. The executable check validates this exact ordered trial vector only, assuming an otherwise empty pool.

## Candidate and musical limit

A future option is a profile-scoped `shapes_voices=7` for Satellite Hearts, only once request schema records that cap and compiled catalogue/profile is bound to it. Do not silently change the default. Before accepting it, count simultaneous routed notes and run the entire 108.8-second arrangement with seven voices, checking note-off/release and owner listening. When all voices are active, `Allocate()` prefers the oldest released voice, otherwise the oldest gated voice (`engines/src/mi_shapes.cc:403-419`). The lower cap can cut release tails or steal held notes; both routed tracks share the cap.

Packet Bloom Showcase has no Shapes instance, so the cap has no effect. Its requests are `{5,972 Crater, 4,240 Phase Bend, 71,392 Macro Heavy, 78,608 Sophie, 49,888 Hall, 11,952 Limit}`; production allocator preflight rejects this sequence at 216,064 B. Nominal charge is 222,160 B, 6,096 B over the arena. Removing/reducing effects changes the authored mix; no content-neutral supported optimization was established. Preserve the chooser disposition.

## Limits and next step

- No production source, builder, catalogue or music changed.
- No native cap-7 full-song test or owner listening; no musical/content/release acceptance.
- No target allocator function, constructors, startup or hardware execution.
- WASM32 geometry assertions match expected source-level TLSF constants, not proof of target ABI/runtime equivalence.
- Next: if selected, add request-scoped cap through the builder while binding it to catalogue/profile; then run target allocation/startup, full-song native SAVE/reload/playback, and owner musical acceptance. Keep cap 12 and Packet Bloom refusal pending those gates.

Source hashes at base `635dc019e3164fb84b330d590036dbfe2e44440a`:
- `engines/src/mi_shapes.cc`: `0e9cf3dc3a654a63342582e61a6d70c630e0ec1cab5b3cfedac9fc927ad0b86a`
- `firmware/native/instance_pool.c`: `6e1871ae8f75c6cb6aca6a7d209e6cca6459d7e899e0576e3b2769d95b037084`
- `firmware/third_party/tlsf/tlsf.c`: `2a0f8cfc9cfe6114ccdc6cf22339059440b16f1149b5107bead4ae4c3a0d50e2`
- `tools/native/build_demo_image.py`: `1b5f72daf0bdc7406a0c6040839a77d293fea9580774765b8a062d6f7b1ab9f7`
- `tools/native/compile_catalogue.py`: `763ac9746b5f2f8198cba915b5ea6f137338ae024196c1fcdadbbd2bad94fc2b`
