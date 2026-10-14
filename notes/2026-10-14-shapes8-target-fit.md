# Shapes-8 target compile and full-song candidate link

Date: 2026-10-14. Source/base: `359a46e6b17b3b6eed3242a2b2256bf0b1d8c3e9`. Branch: `codex/2026-10-14-shapes8-target-fit`.

## Result

Before this run, the compressed startup work was a host sanitizer fixture: it exercised production startup and showed Event Horizon Showcase plus individual engines fitting a 165,376-byte host pool with Shapes capped at 8, but did not establish pi32v2 compiler catalogue or linked image fit.

This run freshly compiled all 13 engines and 55 modules in 16/16 shards, then linked the full-song replacement candidate with the target toolchain. It establishes target compile/link viability for this exact profile and content. It does not execute target code.

## Inputs and target catalogue

- Target image: `lunar-jieli-check:bookworm`, sha `0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`; toolchain `jieli-linux-toolchains-20250324.1`.
- Flags: Shapes 8, indexed TFT, shared resampler, `-Oz`, LTO; 167 objects from a common 536-entry source manifest. Catalogue was compiled, not firmware-linked.
- Configuration SHA-256 `ee3918b43648d0b092a8ef0fa6f1948bd270f64c1919962d5b2759c6a9678375`; input configuration SHA-256 `1ecea71a69fcc88a4ed7bf290ac60ec92eb351ee0c3cc0a1808ade179540bcaf`.
- Prepared selection: `replacement-showcase-candidate-event-horizon`, startup index 0; prepared-profile SHA `09e083de657a66d0bee17c2f65d8771d270de9e710ce7e7f896bb83016ce8702`; request SHA `0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a`.
- Project source SHA `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f`; packed data 5,100 bytes, SHA `ecb00a5363695e3275891bcb1fa0ab44d9b23d7108c1b9ddac35230d81f24a32`. Dependency scan found acid-bass, arp, chance, drums, env, hall, lfo, limit, sixop, trio; image contains the full catalogue.

## Link receipt

The target app probe used song-diagnostic mode, expanded-D9000 layout, stack watermark, SAVE and loader linked, startup index 0, Shapes 8, indexed TFT and compressed Plaits/Braids tables (not flash-hosted Plaits).

- app.bin 845,036 bytes; SHA-256 `5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573`.
- ELF SHA-256 `db9d800022a4e73e672b049ee1aa350a01858a4baad58ef50eebe732e6d03134`.
- Link/layout and key/security audit passed (zero failures, zero pending); source freshness passed. Configured instance pool: 165,376 bytes. This receipt does not measure target allocation/peak.
- App is 23,800 bytes under expanded-D9000 probe budget 868,836. Arithmetic comparison against D7000 budget 860,644 leaves 15,608 bytes; the actual link used expanded-D9000, so this does not prove D7000 packaging/admission.
- Startup metadata index is 0, but the optional runtime chooser hook is absent for this one-project link; startup runtime and stack margin remain unverified. Loader is linked but not activated/runtime-verified. SAVE is linked but storage admission, bounded flash I/O, and arming remain false.
- Artifact and prepared-selection receipts explicitly state `installable=false`; hardware tested/admitted/candidate false; sequence semantics and native playback false; no flash write range or OTA cleanup admitted.

## Checks and limits

Six focused files passed: `test_native_demo_selection.py`, `test_native_demo_image_controller.py`, `test_native_image_profile_integrity.py`, `test_native_stack_watermark.py`, `test_native_ram_layout.py`, and `test_native_demo_app_startup.py`: 117 passed, 13 skipped (130 collected). The last includes ASan/UBSan cold start and decoded table byte equality from the host fixture, Event Horizon at voice caps 12/8, Satellite Hearts rejection at both caps, and single-engine cases. It is not target runtime or audio proof.

The test command used pinned `lunar-preload-tests:20261014` sha `1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313` (Python 3.12.3 and libasan), with the read-only Hera venv `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014` (pytest 9.1.1; host Python 3.12.15) mounted in. Network disabled, 4 CPU, 6 GiB memory/equal swap, `docker-batch.slice`, task label `codex.task=shapes8-target-fit`; `FM1_STATE_TOOL` pointed to ignored `engines/build/fm1-state`. Container itself has no pytest. An initial run without FM1_STATE_TOOL failed 18 tests for the missing environment variable; corrected run passed. A host-only compressed startup attempt failed because host `/usr/lib64/libasan.so.8.0.0` is absent.

This proves no physical ABI execution, audio timing, sustained playback, eight-voice musical quality, SAVE runtime behavior, owner listening or release admission. Shapes-8 remains an experimental profile. Complete Satellite Hearts remains rejected in the pool fixture: at Shapes 8 the later 5,072-byte request fails with 154,352 live; cleanup returns pool live bytes to zero.

Generated catalogue, app, ELF/map/disassembly and receipts remain private and untracked under `/home/claude/mvave-fm1/shapes8-target-fit-20261014/`; no source/default changed. Next: coordinator review/integration, then exact-source release-path rebuild and owner-controlled hardware/audio/listening before admission.
