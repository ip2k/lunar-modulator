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

## Reproducible allocation vectors (2026-10-14 follow-up)

`tests/native_allocator_vectors_wasm.c` and `tools/native/check_allocator_vectors_wasm.sh` preserve the earlier allocator-only experiment as a repeatable test against the unmodified production `firmware/native/instance_pool.c` and `firmware/third_party/tlsf/tlsf.c`. The runner checks the exact installed Emscripten image ID, disables network, and caps the compile and run containers at 1 CPU, 1 GiB RAM, 2 GiB RAM+swap under `docker-batch.slice`. The test asserts WASM32 pointer/`size_t` width and TLSF's alignment 4, minimum 12, maximum `1<<30`, control 3,188, pool overhead 8, and allocation overhead 4 before exercising actual preflight. It passes on the pinned Hera image.

The pool is 216,064 bytes, matching the audited production layout. Canonical order comes from `lunar_project_units_plan`: sound slots first, inserts by sound and insert slot, then master effects by slot. The exact payloads below are from the pi32v2 compiler size probe using `tools/jieli/sizes.cc`, `tools/jieli/sizes_felucca.c`, and `tools/jieli/analyze.py` semantics (not guessed host `sizeof`):

- `replacement-showcase-candidate-event-horizon` (the current Sixop/Trio/Acid Bass candidate): Drums 7,648; Sixop 11,224; Trio 4,240; Acid Bass 1,248; Hall 49,888; Limit 11,952. Total requested payload: 86,200 bytes. The ordered WASM32 production-pool preflight fits.
- `neon-transit`: Drums 7,648; Macro 19,872; Macro 19,872; DX7 16,188; Filter 656; Drive 240; Echo 65,744; Hall 49,888; Limit 11,952. Total requested payload: 192,060 bytes. The ordered preflight fits.
- `afterglow-relay-showcase`: the same engine/effect IDs and request order as Neon Transit; this candidate's current project JSON therefore has the same vector and fits. This check does not assert the projects' music is equivalent.

The target compiler emitted Sixop `sizeof(Instance)=11,224`, Acid Bass `sizeof(Instance)=1,244` (project allocator payload rounds this engine size to 16-byte alignment, yielding 1,248), Felucca shim `sizeof(Instance)=2,476`, and Trio world size 1,752. Probe source hashes: `tools/jieli/sizes.cc` `4d1ae20ec26cf7dc6d6122a42f59c86f0606c0c1f2577655c8e644b0fecb95e4`; `tools/jieli/sizes_felucca.c` `0150ea5d562c69c18b26fa76d8ffc68aa6364f07086f45a6b346a03e99a45d09`; `engines/src/mi_sixop.cc`, `engines/src/acid_bass.cc`, `engines/src/felucca_shim.cc`, and `engines/src/felucca_bridge.c` were read from this checkout and compiled with the same target and pinned compiler. The existing sizing rule gives Trio `round16(2476)+round16(1752)=4,240`. These are compile-time target layouts only. The size probe used the installed JieLi compiler at `/home/claude/mvave-fm1/sdk-v1213/toolchain/current/common/bin/clang` (SHA-256 `42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`) with target `pi32v2 -mcpu=r3 -mfprev1`; the SDK source headers were mounted read-only. The Emscripten run then exercised those numeric vectors under WASM32, not the pi32v2 allocator binary.

Do not call `sum(round16(payload)+16 per request)` the TLSF allocation charge. `lunar_instance_pool_alloc` requests `payload + 16-byte owner header` through `tlsf_memalign(16, ...)`; TLSF uses its own header, alignment-gap and split/coalesce rules, while its control structure and pool overhead are part of the supplied arena. The previous nominal figures are a rough request-size estimate only, and cannot prove fit or remaining headroom. The recorded pass means that the exact ordered calls to the production allocator fit an otherwise empty 216,064-byte pool under asserted WASM32/TLSF geometry. It does not execute target constructors, project startup, the full link's RAM use, audio, save/reload, or hardware; no project is admitted or marked musically accepted.

The old macro/DX7 Event Horizon arrangement is a separate legacy project and is not represented by the replacement-showcase Event Horizon vector. Its Crush payload is not included in this vector/test. `replacement-showcase-candidate-event-horizon` is the new full-song candidate but remains pending native full-song and owner listening gates.
