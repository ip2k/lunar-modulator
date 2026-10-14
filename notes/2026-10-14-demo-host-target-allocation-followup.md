# Cold-start allocation refusals: host sites and target fit limits

This follow-up records exact refusal sites in the current host startup harness and compares them with retained target-compiler sizing. It does not change project contents, arena capacity, release admission, or chooser labels. No device, USB, MIDI, flash, power, or reboot operation occurred.

## Confirmed host refusal sites

`tests/native/demo_app_startup.c` now records the request size, allocation-attempt number, and pool live payload bytes at the failed call. The test asserts the request rather than assuming that `largest_allocation_request` is the failed request. At the exact-base source projects below, all failures are a single pool refusal (`report_code=5`) and startup rolls the candidate back to zero active units and zero live allocations.

| Project | Host pool before failed request | Failed request | Host payload-only shortfall | Request owner |
|---|---:|---:|---:|---|
| Event Horizon | 155,884 / 192,000 B | 49,888 B | 13,772 B | Hall master effect |
| Neon Transit | 155,948 / 192,000 B | 49,888 B | 13,836 B | Hall master effect |
| Afterglow Relay Showcase | 155,948 / 192,000 B | 49,888 B | 13,836 B | Hall master effect |
| Packet Bloom Showcase | 161,168 / 192,000 B | 49,888 B | 19,056 B | Hall master effect |
| Satellite Hearts | 15,328 / 192,000 B | 207,728 B | 31,056 B | Shapes sound engine |

“Payload-only shortfall” is `live payload + requested payload - pool capacity`; it excludes TLSF block overhead and fragmentation, so it is a lower bound on the extra capacity required in that host run. The refusal is observed; that arithmetic is explanatory, not a recommended arena change.

The module mapping follows the canonical reservation loop in `firmware/native/project_engines.c` (sound units 0–3, inserts 4–11, masters 12–13) and the fixture contents. The startup harness makes two earlier temporary pool calls for sequence and DX7 scratch, so the reported global attempt numbers are not engine indices. In the four Hall failures, the failed request is the Hall master effect after the sound and enabled insert reservations. Satellite Hearts fails on its third sound allocation, Shapes, after Comet and Drawbar.

Largest request and failed request are different for four projects: the host's 65,744-byte Echo is the largest request in Event Horizon, Neon Transit, and Afterglow Relay Showcase; Packet Bloom Showcase's largest request is 79,344 bytes. Neither is the call that failed. Satellite Hearts' Shapes request is both its largest and failed request.

## What target sizing supports

The target arena evidence currently retained in `notes/2026-10-14-demo-target-allocation.md` and `notes/2026-10-14-demo-target-allocation/remaining-unit-sizes.txt` is compile-time layout plus source-formula arithmetic at 44,118 Hz, not an executed target allocator. The retained full-song target link configuration is 216,064 B, but the candidate remains `installable=false`, `hardware_candidate=false`, `hardware_tested=false`, and `startup_project.runtime_verified=false`.

- **Afterglow Relay Showcase:** modeled target reservations total 192,208 B, leaving 23,856 B gross. That is a plausible fit, not runtime proof; TLSF effects, other clients, and constructor/startup behavior remain untested.
- **Packet Bloom Showcase:** modeled reservations total 222,160 B, 6,096 B over target capacity. Its Hall allocation is an observed host refusal; the target static model has no gross-fit margin even before runtime overhead. Keep its current unverified allocation disposition.
- **Satellite Hearts:** modeled reservations total 289,232 B. The cumulative sum crosses target capacity at Shapes (222,272 B, 6,208 B over before later units/effects). Its observed host request also exceeds the host pool on its own. No supported safe instance optimization is demonstrated by these facts.
- **Event Horizon and Neon Transit:** both fixtures have the same 4 sound engines, Filter plus Crush/Drive inserts, Echo insert, Hall, and Limit. Their host failures are Hall requests. The retained target evidence shows Macro at 19,872 B versus the 32,736 B x86-64 host object; two Macro instances reduce nominal payload by 25,728 B, while the configured target pool is 24,064 B larger than the 192,000 B host test pool. That makes Neon Transit a plausible target fit, but target TLSF/runtime has not been executed. Event Horizon substitutes Crush for Drive; the Crush target layout is not in the retained target-size receipt, so its exact margin remains unknown. Neither is admitted on this evidence.
- **Event Horizon Showcase:** separately passes the host cold-start harness (87,968 B retained pool payload at completion, six active units); this does not resolve the other projects or prove target startup.

The target-size note's static estimates include +16 bytes per allocation request but do not model exact TLSF overhead/fragmentation. Host `pool_live_bytes` is payload, not free-block topology. Do not raise arena limits or edit compositions from this evidence alone.

## Verification and next bounded step

Ran `tests/test_native_demo_app_startup.py` in the pinned `lunar-recovery-pytest` container on Hera (`--network none`, `docker-batch.slice`, 4 CPUs, 4 GiB memory/swap). Result: **8 passed**. This host harness builds 55 production modules and exercises native `lunar_project_start`; its fixed 192,000 B pool and 64-bit instance layouts are not the FM-1 target runtime.

Next, if the owner wants these earlier demos enabled, run a bounded allocator/startup test using the actual pi32v2 build configuration on target or an independently validated target-runtime emulator. Preserve the existing 216,064 B configuration and require explicit owner musical acceptance separately from memory/startup results. Do not present the static fit model as acceptance.
