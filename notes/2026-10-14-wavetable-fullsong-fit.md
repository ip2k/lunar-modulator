# Lossless wavetable compression full-song fit experiment — 2026-10-14

## Result

[verified target-link measurement] On source base `dbf008c7c88b87c54434e595a9e7617605bf4138`, the existing private `--compressed-wavetables` application-probe path linked the prepared Event Horizon Showcase profile (108.8 seconds; profile SHA256 `b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46`) with all 13 engines, all 55 modules, startup index 0, indexed TFT, stack watermark, linked project loader, and linked but disarmed SAVE service.

The all-table build reported app size 844,284 bytes (SHA256 `8d613f0599e1e8b14b0da336eae5d3e81f8777ece6ab79f8f9d0da2fa9ba6083`) and ELF SHA256 `255d56b43ccf8f1bfd3fa6ecea3770e377f9067a4065f67fe605071628a19d2b`. The comparable uncompressed-Plaits / compressed-Braids build was 862,296 bytes (app SHA256 `b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956`). The measured net reduction is 18,012 bytes. Against the D7000 candidate's 860,644-byte app budget, this leaves 16,360 bytes. The link was performed with the expanded-D9000 layout (reported budget 868,836 bytes); D7000 fit here is an arithmetic comparison, not a D7000 package admission or device test.

The image retained all configured features and passed the build's linked key/security audit and linker/layout checks. SAVE remained linked, storage-admission false, flash-I/O-bound false, disarmed, runtime-unverified and hardware-unverified. `installable=false`; no hardware operation or listening occurred.


[experiment environment] Hera container image `lunar-jieli-check:bookworm` resolved to `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`; toolchain symlink was `sdk-v1213/toolchain/current` -> `jieli-linux-toolchains-20250324.1`. The container was CPU/memory limited, network-disabled, and mounted the exact source, catalogue, prepared profile, toolchain and output paths read-only except output.

## Compression representation and tradeoff

The pinned generator `tools/native/prepare_wavetables.py` uses raw DEFLATE level 9 over modular-delta encoded bytes and the repository's pinned `tinf` decoder. Its exact content receipts for this run were:

| Table | Original bytes | Packed bytes | Raw SHA256 | Packed SHA256 |
|---|---:|---:|---|---|
| Plaits `wav_integrated_waves` | 50,688 | 32,513 | `bd1d04177e240247de3224ef8e6f52afd907d8ae1a9971e0ce4ba68258e7ecea` | `2cbdd706ef8cd7b97e705b139eab7a328ff4cb03257326faf34c396ac5b21255` |
| Braids `wt_waves` | 33,024 | 24,159 | `c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634` | `d05f3f0b852719327983c82418a1b6b9e4c2414430078267653a77feb2ed1952` |

The generator records the raw-table FNV32, packed bytes and generated translation-unit SHA in `wave_tables.json`. Prior evaluation at `notes/2026-10-12-native-engine-link.md` used the pinned C decoder to round-trip all bytes for sixteen block/level profiles with output canaries and insufficient-capacity checks. The current target-link receipt is consistent with that same retained table input and generator. This task did not add a new decoder implementation or modify production source.

Both tables remain directly addressed by existing engine consumers. The probe therefore expands Plaits' 50,688-byte table into RAM and keeps direct immutable-style table access; it does not introduce block caching into render code. Compared with the preceding full-song probe, `instance_pool_bytes` drops from 216,064 to 165,376 bytes, exactly the additional Plaits table reservation. Braids was already expanded under the preceding compressed-Braids probe. The Plaits raw table is not a second temporary copy: the generated resource object writes the table into `.pool.wavetable`.

The probe's `app_main` calls `lunar_wave_tables_init()` before `fm1_app_init()`; failure enters the probe's bootguard rejection path. This is a one-time startup path, outside the audio render callback. No pi32v2 execution measured decode duration, peak stack, constructor/allocation success, or deadline. Prior source evaluation notes tinf's stack use can exceed 1 KiB. The full-song target constructor path has not been executed, so the reduced 165,376-byte instance capacity remains the key unresolved constraint.

## Interpretation and next check

This is a measured flash-fit candidate: the current all-feature diagnostic application probe saves more than the D7000 shortfall without feature removal, with exact table-content identities and fail-closed decoder wiring. It is not evidence that the current project arrangement or every engine combination fits the smaller pool. The next bounded offline check can extend the existing host cold-start harness in `tests/test_native_demo_app_startup.py` / `tests/native/demo_app_startup.c`: generate/compile the existing mutable table sources, link the pinned `tinf` decoder, call `lunar_wave_tables_init()` before `fm1_app_init()`, and run the exact packed `event-horizon-showcase` project with a 165,376-byte aligned instance arena. Record every request, failed attempt, live/peak bytes and allocator overhead; also run near-capacity/rejected showcase fixtures and all engine/effect worst-request vectors. The current harness runs all 55 modules and has a full replacement-showcase cold-start test but hardcodes a 192,000-byte arena and does not decode tables. This extension would be host allocator/runtime evidence only; it must not be presented as pi32v2 execution or audio timing. Before enabling this in an installable image, also measure target startup time and stack on a supported target. Preserve the owner-listening and physical acceptance gates; neither follows from a linker fit.

Evidence is private on Hera at `/home/claude/mvave-fm1/native-resource-compression-fit-20261014/out/current-compressed-indexed-try3/` and `.../out/current-both-compressed/` (ELF, map, section listing, `verification.json`, generated table receipts). The exact command used `tools/native/build_application_probe.py` with:
`--runtime-mode song-diagnostic --stack-watermark --flash-layout expanded-d9000 --link-project-loader --link-project-save-service --startup-project-index 0 --indexed-tft --compressed-wavetables`.
