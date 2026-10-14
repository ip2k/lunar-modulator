# Native continuous-mode and stack-watermark size comparison - 2026-10-14

## Result

[verified] A matched target link confirms that continuous mode plus removing the stack watermark does **not** recover the 1,652 bytes needed for the proposed D7000 app tail. The bounded builder baseline is 862,296 bytes; the continuous no-watermark link is 861,836 bytes. It is 460 bytes smaller than baseline, but still 1,192 bytes larger than the D7000 app budget of 860,644 bytes.

The project required no feature cuts for this A/B: all 13 sound engines, all 55 catalogue modules, the 4,345-byte Event Horizon Showcase packed project at startup index 0, the project loader, and the real SAVE service link were held constant. SAVE remained disarmed, without storage admission or a flash binding. Both direct-probe variants report installable and hardware admission/testing false. They are not builder outputs and continuous mode is deliberately refused by the public-facing builder gate.

| Probe profile | Stack watermark | Runtime return | App bytes | Delta vs guarded-builder baseline | D7000 budget margin |
|---|---:|---:|---:|---:|---:|
| Song diagnostic baseline | yes | 120 seconds | 862,296 | 0 | -1,652 |
| Continuous | yes | none | 862,360 | +64 | -1,716 |
| Continuous | no | none | 861,836 | -460 | -1,192 |

The song-diagnostic baseline app SHA-256 is identical to the independently produced guarded builder artifact: `b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956`. This is the control for the comparison. On the continuous profile the watermark instrumentation costs 524 bytes (862,360 - 861,836). Changing the bounded 120-second return to continuous while retaining the watermark adds 64 bytes, rather than shrinking the image. Removing both options therefore yields a 460-byte net saving against the current guarded-builder image, not the 1,652 bytes required.

The proposed D7000 threshold is a planning budget only: `0xD7000 - 0x4120 - 384 - 2940 = 860,644`. The actual link used the existing expanded-D9000 linker profile, whose budget is 868,836 bytes. The D7000 threshold comparison above is arithmetic against the measured output, not a D7000 link or a package-layout verification.

## Method and evidence

Source and code base: Hera isolated branch `codex/2026-10-14-release-size-measurement`, exact HEAD `dbf008c7c88b87c54434e595a9e7617605bf4138`, clean source tree. Target probe source SHA-256: `e539a75f4f6f67a2af39d03c701fc32231de15cd375c7adc7236449b907f6f94`; runtime policy source SHA-256: `24398cda9a68886d9557256f428ca2ee3e47e57ec1483672c8adaedf08fd598c`.

All three variants were linked by the exact-commit `tools/native/build_application_probe.py` against:
- Prepared profile `b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46`, selecting all 55 modules and `replacement-showcase-candidate-event-horizon` at startup index 0. Packed payload SHA-256: `b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163`; source SHA-256: `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f`.
- All-thirteen `-Oz`/LTO catalogue `/home/claude/mvave-fm1/all13-fullsong-link-comparison-v1/catalogue-z`; the probe checked source manifests, every object hash, and shard reports before linking.
- Pinned JieLi compiler bundle `jieli-linux-toolchains-20250324.1` (the existing `sdk-v1213/toolchain/current` link).
- Identical arguments: expanded-D9000 link layout; indexed TFT; compressed Braids wavetable with Plaits wave bank in flash; 12 Shapes voices; `--link-project-loader`, `--link-project-save-service`, `--startup-project-index 0`; all thirteen engines, effects and other modules selected. The only varied inputs were `--runtime-mode` (song-diagnostic or continuous) and `--stack-watermark`.

The builder baseline was reproduced exactly in the direct probe before comparing the other two profiles. The target-compiler layout and key/eFuse audits passed in all three probe reports; the artifact receipts keep `installable=false` and `hardware_admitted=false`. All three app hashes, ELF hashes, verification JSON hashes and artifact JSON hashes are retained with their exact measurements below.

| Variant | App SHA-256 | ELF SHA-256 | Verification SHA-256 | Artifact receipt SHA-256 |
|---|---|---|---|---|
| Song diagnostic + watermark | `b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956` | `06da15abe6beb88dfe9a0c27af48e2c22716bb15a79825b3d90f72fcd8d02e77` | `9f15f4f99c8fa20fe7cd01d4b51d99938270328187ce63b38e8b6be37277fc4a` | `94af2a919e4370cdc7e4d7236cfac804ebdc96cf936f9e487423f350f247df58` |
| Continuous + watermark | `85c4d83a05d8b8d9a4663f0d7dece0d58b09b6fd1b0075fcf254a08fe4bfc8de` | `ffa86e1a05c8f18d7c932dc6813e01088fdd5fd653329a2c7ea18176ae98cd15` | `f330f8ed906b5fe1f974be5f097b6ba6ba01ece2cc443d2db9dd3e25b4687fa9` | `b04805bb1f3cd82aa08d43df5cd35a13e5f612cc470345b0dff4d8896e7e745b` |
| Continuous, no watermark | `0cd6f0d0652591b92b5855bbef57585b36c1f8c804faedc8f4da3ed9b810f5f0` | `ff4706bc5c1e113177588c42474fdf95b283e57553f9df7e13a77300d07196a5` | `edf32543d5e65d60b912b9cdd9b6dc10129811cf83424564612589e4f2f47040` | `a28de4f6996921936a1531dac17faef907254aaf151494696d711d11c68ae201` |

The private worker ran in `lunar-jieli-check:bookworm`, image SHA-256 `0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`, with `--cgroup-parent=docker-batch.slice`, network disabled, 4 CPUs, 8 GiB memory and equal swap, 512 PID limit, read-only root, and source/catalogue/toolchain/profile mounted read-only. Output files are under `/home/claude/mvave-fm1/release-size-measurement-20261014/`; the build binary/map files are private measurement artifacts and are not committed.

No hardware command was issued. This proves target compilation and link-size deltas only; no runtime initialization, stack-bound adequacy, audio/playback, SAVE, physical capacity, package safety, or release acceptance is established.

## Largest live symbol attribution

The no-watermark continuous ELF has 3,006 retained symbols with nonzero linked sizes. The largest are live linked resources/code, not dead-code savings. Selected leading entries from `tests/native/size_savings_audit.py`:

| Bytes | Kind | Symbol |
|---:|---|---|
| 50,688 | data | `plaits::wav_integrated_waves` |
| 46,999 | data | `x0x_smp_ride` |
| 43,300 | data | `x0x_smp_crash` |
| 24,159 | data | `packed_braids` |
| 20,250 | data | `x0x_smp_hh` |
| 14,230 | code | `apply_op` |
| 11,032 | code | `fm1_app_render` |
| 11,030 | code | `fm1_app_encoder` |
| 10,450 | code | `draw` |
| 9,728 | data | `x0x_pot_exp` |
| 8,192 | data | `fm1_msfa::kSinTab` |
| 8,192 | data | `fm1_msfa::kExp2Tab` |

The link already uses `-Oz -flto`, function/data sections, linker `--gc-sections`, and `NDEBUG`. The 24,159-byte Braids bank is already compressed; the 50,688-byte Plaits bank and drum samples are live engine resources. The default full-song payload is already packed to 4,345 bytes. These data sizes are not evidence of removable overhead.

## Bounded next optimization

The smallest maintainable follow-up is a matched full all-thirteen application A/B of the existing pinned compiler's `-Oz -flto` and `-Os -flto` settings, rebuilding all catalogue objects for each side and keeping the exact same 55-module selection, project payload, SAVE link, and runtime. Do not mix cached optimization-level objects. Record app/map/symbol deltas, then run relevant render/oracle, target link/audit and project SAVE tests before crediting any win. This is the narrowest feature-preserving candidate likely to produce a 1.2 KiB shift without changing resource access semantics.

Further table compression is possible to evaluate, but is a larger change: direct readers of Plaits wave data and whole-array drum sample users would need a compatible decoding/access strategy, with timing and RAM costs measured. Do not count gross compressed bytes without decoder, scratch-memory, and target behavior costs. Removing the watermark itself is not an acceptable shortcut to stack evidence; it saves only 524 bytes in this comparison and does not meet the app-tail budget.
