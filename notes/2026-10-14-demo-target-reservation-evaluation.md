# Offline target reservation bounds for selectable demos

This note evaluates the project instance pool at source base `257e4cb204be2ab16da6be0c27bf3e92d1084a52`. It uses exact pi32v2 compile-time sizes and production allocator source; no target program or device was run. Results constrain memory selection only. They do not establish constructor success, musical acceptance, installability, or release admission.

## Arena and reservation path

The linked production configuration reserves a fixed 216,064-byte instance arena. `lunar_instance_pool_init` gives the same buffer to TLSF; the target compiler probe in `notes/2026-10-14-demo-target-allocation/size_tlsf.c` reports a 3,188-byte TLSF control structure, 4-byte allocation header overhead, and 8-byte pool sentinel overhead. Thus the initial free block has 212,868 bytes of block size (about 212,864 bytes of free payload). Each instance request goes through `lunar_instance_pool_alloc`: a 16-byte owner/size/magic wrapper is prepended, then `tlsf_memalign(..., 16, payload + 16)` is called. The pool therefore has unavoidable fixed and per-allocation costs before any alignment prefix or fragmentation.

The reservation loop in `firmware/native/project_engines.c` reserves all selected units before constructors, in compact plan index order: sounds 0–3, insert slots 4–11, master effects 12–13, then MIDI effects 14–17. A MIDI effect is only planned when its serialized selection is on. These demo fixtures have bypassed arp records, so no MIDI-engine instance is included. The project base-mod rack is a separate 8 KiB arena and is not included in these instance-pool totals.

## Target compiler evidence

The target compiler was JieLi pi32v2 clang 4.0.1 with the production target and include configuration. New constant-emission probes are retained beside this note:

- `size_crush.cc`: target `sizeof(Instance)=172`, alignment 4, `InstanceSize(0)=176`; emitted target ELF32-pi32v2 object SHA-256 `5bfad08d8c885aa6881e2cc8d8a0a41a948ce24507e8b0bc5c45b79c4767a063`.
- `size_warble.cc`: target `sizeof(Instance)=16,464`, `InstanceSize(0)=16,464`; object SHA-256 `a6ee14207461bbf88dbbd725426900136b3e855c94959a768a38185f14379b9f`.
- `size_tlsf.c`: control size 3,188; block header 16; allocation-header overhead 4; minimum block size 12; base alignment 4; pool overhead 8; object SHA-256 `aedfcdd3849af7198974e543e547216440928893149e1c21ef20c31c9b60de6d`.

The prior target-size receipt `remaining-unit-sizes.txt` contains source/layout evidence for the remaining selected engines and effects: Drums 7,648; Macro 19,872; DX7 16,188; Filter 656; Drive 240; Echo 65,744; Shapes 206,904; Comet 10,240; Drawbar 5,072; Crater 5,984 rounded instance size; Macro Heavy 71,392; Sophie 78,608; Phase Bend 4,240; Hall 49,888; Limit 11,952. Hall and Limit sizes are transparent source-formula evaluations using target `sizeof` values at 44,118 Hz, not executed target layout functions. Their existing caveats remain.

## Reservation bounds

The table gives payload sum, then a lower bound on total pool use: each requested payload plus the 16-byte adapter wrapper, rounded to TLSF's 4-byte size granularity, plus 4 bytes of TLSF allocated-block overhead per request and 3,196 bytes of TLSF control/sentinel overhead. The listed sizes are already 4-byte aligned. This bound excludes any leading alignment fragments, free-block remainder loss, fragmentation, temporary/runtime consumers, and constructor-side allocations.

| Selection | Ordered native engine/effect instances | Count | Payload bytes | Minimum total pool charge | Static result |
|---|---|---:|---:|---:|---|
| Event Horizon | Drums, Macro ×2, DX7, Filter, Crush, Echo, Hall, Limit | 9 | 191,996 | 195,372 | Candidate; 20,692 B lower-bound margin |
| Neon Transit | Drums, Macro ×2, DX7, Filter, Drive, Echo, Hall, Limit | 9 | 192,060 | 195,436 | Candidate; 20,628 B lower-bound margin |
| Afterglow Relay Showcase | Drums, Macro ×2, DX7, Filter, Drive, Echo, Hall, Limit | 9 | 192,060 | 195,436 | Candidate; 20,628 B lower-bound margin |
| Packet Bloom Showcase | Crater, Phase Bend, Macro Heavy, Sophie, Hall, Limit | 6 | 222,064 | 225,380 | Definite reject; 9,316 B over even the lower bound |
| Satellite Hearts | Comet, Drawbar ×2, Shapes, Hall, Limit | 6 | 289,128 | 292,444 | Definite reject; 76,380 B over even the lower bound |

The candidate order follows the production plan, not project JSON display order: Event Horizon reserves sound0 Drums, sound1 Macro plus Filter and Crush, sound2 Macro, sound3 DX7 plus Echo, then Hall and Limit. Satellite Hearts reaches Shapes after Comet and the first Drawbar; it cannot fit even if subsequent units are omitted because its minimum whole-pool bound already exceeds capacity. Packet Bloom's selected units likewise exceed the whole pool before TLSF alignment effects. These two are safe memory-based exclusions under the unchanged 216,064-byte pool.

The three candidate rows have meaningful static margin after the fixed overhead, but there is no target allocator run to establish that exact ordered `memalign` sequence succeeds. Keep them marked allocation-pending. The earlier native startup harness refused at Hall in its 192,000-byte 64-bit host pool; that outcome does not override these target sizes or prove a target fit.

For comparison only, the legacy `afterglow-relay.lunar` and `packet-bloom.lunar` assets select Warble instead of Echo. With target Warble 16,464 and the same other units, their payload is 142,780 bytes and the corresponding lower-bound charge is 146,156 bytes (nine units). This is also only a candidate bound, not a target execution result.

## Optimization and next step

No supported safe instance-memory optimization is demonstrated here. Shapes is 206,904 bytes, but Satellite Hearts' total is dominated by the engine's selected instance and remains far beyond the arena; reducing it enough would require a substantive implementation change and independent audio/reference validation. Echo's target instance is 65,744 bytes and is not the cause of the earlier host refusal; its state layout is engine-owned and any compaction needs a concrete ownership/lifetime audit. Do not cut delay lines, voice counts, or alter projects to force a fit from static arithmetic.

Next implementation step: add a small offline reservation verifier that links the exact target `instance_pool.c`/TLSF and production engine-size table, feeds the ordered size vectors into `lunar_instance_pool_can_fit`, and runs only on a validated pi32v2 emulator or target execution environment. Until such an execution path is available, chooser policy may reject Packet Bloom Showcase and Satellite Hearts by hard lower-bound overflow, while keeping Event Horizon, Neon Transit, and Afterglow Relay Showcase explicitly pending allocation/startup verification. Musical owner acceptance and release admission remain separate gates.

