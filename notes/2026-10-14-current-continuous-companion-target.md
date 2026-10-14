# Continuous FM-1_500 target link with Event Horizon and companion SET

Date: 2026-10-14  
Source branch: `codex/2026-10-14-current-continuous-target`  
Source base: `dab9daae8f0d40d663b835ddb5f4dc241c914ba8`

## Result

A fresh pi32v2 target build linked a continuous-mode FM-1_500 application using the current approved Event Horizon Showcase project and its companion SET. The link uses the named `expanded-d7000` layout, 8 Shapes voices, the indexed TFT, compressed Plaits and Braids wavetable resources, the project loader and companion SET loader, and the 165,376-byte instance pool.

The linked application is 845,768 bytes (SHA-256 `d7216f6c62c42266c1886e4b57f6ed33de8afcffec7be226e724fbadfe137d3b`). The D7000 profile reserves an 860,644-byte application extent, leaving 14,876 bytes of link-time slack. The ELF is 978,276 bytes (SHA-256 `465f5ce940a2185c3777d76fe1f9be4a0e6b2421961fdbe437d52fb92e0b29e3`). The verification receipt SHA-256 is `eda0496ed12e70970c9ce9232aab0acf15a944fc1e54a1b5c7364421c1f4aabf`; the artifact receipt is `bbe67fc4d769f2e207f5cdbc805919c700ca687f5f8a6e430fc5bf5dc04f5596`.

The build selected 54 catalogue entries: 13 sound engines, 23 audio effects, 2 MIDI effects, and 16 modulation modules. The Plate effect is absent; the build excludes the test-only sine engine. The embedded project and SET total 6,284 bytes: project 4,395 bytes (SHA-256 `1d2fe09f7e37a657852a372468bdc6cc0f47661b28d5d5cbcf632a3530a95e28`) and SET 1,889 bytes (SHA-256 `f4bea6aa654be10e4cd1d0c54c87ade21f10cd6420eeb09d4e63f8bd9a67a1c3`). Request SHA-256 is `a089835b668a07d711ee13a2a4bd58aa96f483925aaf2f47767fa2be6e0e9a07`; prepared profile SHA-256 is `ab86df38ea150da9e770e39400f407ea3e4ebee482019517bccdcd510e6c2a74`.

The verification receipt records explicit application identity `FM-1_500`, recovery identity `FM-1_000`, continuous runtime mode, and `-DLUNAR_RETURN_TO_ROM_SECONDS=0`; `return_to_rom_seconds` is null. Runtime playback has not been tested. The linked modules and assets establish a link configuration only, not musical behavior or successful boot.

The build used source `dab9daae8f0d40d663b835ddb5f4dc241c914ba8`, JieLi pi32v2 toolchain `jieli-linux-toolchains-20250324.1`, and the bounded `lunar-jieli-check:bookworm` container image (digest `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`). The 16 catalogue shards completed without compiler failures. The final link command and receipts are retained under `/home/claude/mvave-fm1/current-continuous-target-20261014/` on Hera; its `link-build/link/run-link.sh` configuration includes both `--link-project-loader` and `--link-set-loader`.

The SDK-free linked-image key audit passed with zero failures and zero pending checks; the artifact receipt records no SDK archives and a passed SDK-free audit. Link layout validation passed. SAVE service code is linked, but storage admission, flash-I/O bounds, service arming, and runtime verification are all false. Hardware candidate, hardware tested, and installable are all false. No firmware package was emitted by this direct application-link path.

## NOR closure follow-up

The closure-analysis helper originally linked only the project loader, omitting the SET loader even when the trusted prepared profile contained a SET. `tools/native/verify_nor_writer_closure.py` now derives `--link-set-loader` from the prepared profile's content kinds, and refuses malformed rows or a SET-only profile. The companion profile was relinked through the analysis-only closure path.

The analysis-only output is `/home/claude/mvave-fm1/current-continuous-target-20261014/nor-closure-rerun/run2`. Its evidence input manifest SHA-256 is `b122323dee858b943caf84f6311a9222c112286a5a10dfaab32915c78a196ead`; linked ELF SHA-256 is `0accf5c876090143ef7b3e1879731ba342cb7e5cd89b42c1a7460a3c826f6400`; linked map SHA-256 is `0b43950b3b3d09e7b306de9c9bb9fc899e3f90ed7f623f21baf98300dd3e14363`; RAM-closure audit SHA-256 is `fea7c63fa3ae9ff2a15cc2a79e1e23aa0599cde32cd34ec9af4f4c19683e310a`. The analysis-only audit reports passed static writer checks and linked-wrapper checks, but marks static data closure, control-flow closure, runtime pointer residency, and watchdog feeding in RAM as unproven. Its separate analysis link uses the closure tool's diagnostic configuration; do not treat that ELF as the continuous build ELF or as a release artifact. No package was emitted.

The closure build computes hypothetical SAVE extents only. SAVE remains disarmed and no flash, device, or runtime behavior was exercised. Static writer analysis is not NOR safety or hardware acceptance.

## Reproducibility and remaining dependency

The target link command is retained in `link-build/link/run-link.sh`; its inputs and artifacts remain private on Hera. The analysis-only closure invocation/result are retained under `nor-closure-rerun/run2`. The helper regression is `tests/test_native_nor_writer_closure.py`; all 19 focused tests passed with Hera Python's `unittest discover`, and `git diff --check` passed.

This run did not produce `image.json`, a `build_tuple.json`, or a build-provenance sidecar. It therefore supplies exact application/link/runtime-identity evidence but is not yet admissible to the trusted FWSC packager. The next dependency is a trusted continuous build-tuple capture and strictly validated continuous policy in the package composition path. Keep the diagnostic song policy distinct; do not infer an implicit timeout or synthesize `return_to_rom_seconds` from this receipt.
