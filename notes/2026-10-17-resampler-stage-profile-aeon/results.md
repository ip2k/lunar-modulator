# Aeon schema-7/schema-9 target-build results

Built offline on Aeon from the same exact source commit `36988d0c2ef1b793e5f9d343fac1b9f6c4b7891f` with the pinned Event Horizon profile, selection, target toolchain and image. Pair root: `/home/claude/mvave-fm1/resampler-stage-profile-pair-aeon-20261017-codex/`. Each side's full receipt is in `schema{7-control,9-enabled}/`; linked outputs are under `writable-output/build/`. No hardware command was issued.

This is specifically a profiling-package delta, not a resampler-only comparison: schema 7 uses no diagnostic IRQ or resampler-stage app profile, while schema 9 enables both and the catalogue stage profile. Source/workload/toolchain otherwise match. The schema-9 code folds tracked IRQ-union data into its schema-9 frame and therefore changes the diagnostic packet cadence. Physical profiler overhead has not been measured.

| | schema 7 control | schema 9 enabled | delta |
|---|---:|---:|---:|
| artifact ELF SHA-256 | `aa5a4faaa4af35b0c110119c2b658b3ca875de55417eacd812b282a492cb856f` | `48c028b5f9afcf7bb468be67c7445e48fe2dd2eea6cf4a22111db6351ce9611c` | — |
| app SHA-256 / bytes | `c1dd1270af183f507011314767c610bec4c90ba80a4e3d6b6738fa87e5774e0a` / 856,096 | `9bae424c1e83cf2d50a70c42af4ebf4cb4530de56c7fe4515b202bc3e9709193` / 857,912 | +1,816 B |
| `.text` | `0xCCD10` | `0xCD068` | +856 B |
| `.ram_dsp` | `0x3D54` | `0x4114` | +960 B |
| `.bss` | `0x4FE0` | `0x5110` | +304 B |
| `.pool` | `0x66AB0` | `0x66AB0` | same size; base shifts +`0x130` |

Both `artifact.json` files report `layout_passed=true`, `hot_dsp_ram=true`, and `hardware_admitted=false`, `hardware_tested=false`, `installable=false`. The application budget is 860,644 bytes, so observed app-byte slack is 4,548 B (schema 7) and 2,732 B (schema 9). Both tool/container builds succeeded: all sixteen catalogue shards and the linker exited zero per side; no OOM. Schema-9 stage receipt is 189 bytes / 63 packets / stride 32; timing counters are cumulative raw 24 MHz TIMER4 wall and tracked-IRQ-union ticks, not CPU cycles.

## Codegen and caveats

The exact schema-9 linked disassembly is `schema9-enabled/writable-output/build/artifact/disassembly.txt`; vendor function listings are in `ram-dsp.txt`, and symbol addresses are in `symbols.txt`. `fm1_resampler_pop_ready_` instances are in `.ram_dsp` (`0x01c005c8`, `0x01c00a46`, `0x01c00ede`, `0x01c0132c`, `0x01c01d24`). The resampler kernel and low-pass are also in `.ram_dsp` at `0x01c0395c` (12,292 bytes) and `0x01c04560` (248 bytes). In the profiled binary, `.ram_dsp` code calls `lunar_resampler_profile_stage` at XIP `.text` `0x02003724` and `lunar_resampler_profile_count` at XIP `.text` `0x020036d4`; for example see disassembly lines around 212049 and 212060, and equivalents for the duplicate inlined engine sites. Thus the diagnostic path introduces flash/XIP helper calls from the RAM hot region. This build does not establish whether XIP calls are a practical bottleneck or the profiler's observed instrumentation cost.

The diagnostic additions increase the ready-pop body from `0x36a` bytes to `0x3fa` for the main instance, and the corresponding Drums instance from `0x36a` to `0x3ca`; inspect the exact variant-specific symbols in `symbols.txt` rather than treating these as isolated code size for the full instrumentation. The `ram-call-audit.json` reports `all_callees_in_ram=false` for the selected DSP set in both variants. Stack-watermark instrumentation reports 24,320 user bytes and 7,936 system bytes, but `worst_case_stack_bound=false`, and it is not a runtime high-water measurement here. There is no evidenced stack regression attributable to the profiler; stack safety is simply not proven by these static artifacts.

## Next step

Owner-controlled FM-1 diagnostic run is required to obtain actual schema-9 stage counters and user-perceived lag/distortion correlation. Preserve the current schema-7/schema-9 distinction and explicitly account for profiler perturbation. If the owner requires instrumentation-only attribution, first make a valid same-cadence baseline that satisfies the schema validator; do not compare these two images as a causal estimate of resampler hook overhead. No target performance/sound-quality conclusion follows from fit, disassembly or successful linking.
