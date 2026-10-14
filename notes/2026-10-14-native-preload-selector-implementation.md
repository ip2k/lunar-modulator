# Native cold-boot preload selector implementation checkpoint

## Scope and outcome
Implemented a polled cold-boot chooser for immutable embedded project assets in the generated native platform. It filters SET assets, begins at the configured default project, rotates with the SELECT encoder, opens on a debounced SELECT press, and returns the default after eight seconds. A one-project image bypasses the chooser. Existing recovery-mode and recovery-key branches remain before the hook. It executes before audio initialization and app startup; there is no hot-switch path or second live app instance.

This is source/host-tested only. The exact four-project candidate does **not** pass target XIP linking and is not installable, release-ready, or target accepted. No device, USB, MIDI, flash, power, or reboot operation was performed.

## Changed files
- `firmware/native/preload_selector.h`: bounded project-index state machine (max 64 assets; validates default; cycles; confirm/default timeout).
- `firmware/native/preload_selector_platform.h`: target polling/UI adapter, watchdog feed, SELECT encoder, debounced SELECT press, eight-second TIMER4 elapsed timeout.
- `firmware/native/content_catalogue.h`: trusted generated title pointer in each descriptor.
- `firmware/native/app_probe.c`: mutable generated-probe startup index used by existing project-start call.
- `tools/native/embed_image_content.py`: printable bounded labels from admitted source basenames, never filesystem paths.
- `tools/native/build_application_probe.py`: stage hook only for profiles with more than one project; after recovery checks and before audio initialization.
- `tests/test_native_preload_selector.py`, `tests/test_native_content_embedding.py`: state-machine/platform-hook and descriptor/title coverage.

## Timing and input evidence
`firmware/third_party/dinghy/src/platform.c` calls `fm1_time_init()` at `fm1_cstart()` entry. Bootguard and `recovery_key()` checks run before LCD/input/audio initialization. The generated hook runs after `fm1_input_init()` and before `fm1_audio_init()`. HAL polled `fm1_input_scan()` advances a matrix frame; `fm1_input_edges()` returns debounced button edges; `fm1_enc_take(ENC_SELECT)` returns detents. Time uses TIMER4 `fm1_ticks()`, not an IRQ-dependent clock; unsigned elapsed subtraction handles wrap over eight seconds. The chooser feeds `fm1_wdt_feed()`. TIMER5 startup and IRQ enable remain in their current order.

The chooser adds up to eight seconds to a multi-project boot; single-project images bypass it. Song-diagnostic duration starts later with app playback/timer startup, so chooser time is not counted as playback.

## Checks and target result
On Hera:
```sh
PYTHONPATH=/home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/lib/python3.12/site-packages \
FM1_STATE_TOOL=/home/claude/.local/share/codex-worktrees/lunar-demo-packed-validation/out/demo-packed-validation-v1/fm1-state-build/fm1-state \
FM1_NATIVE_TOOLCHAIN=/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1 \
python3 -m pytest -q tests/test_native_preload_selector.py tests/test_native_content_embedding.py
```
Result: **43 passed**.

A bounded pi32v2 build ran in `docker-batch.slice` with 4 CPUs, 8 GiB RAM, and 10 GiB total memory+swap, image digest `sha256:7e32dd6d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`. The recorded command did not set an explicit Docker network mode, so this is not described as network-isolated. Input was production-only 55-module `production-prepared-combined` (four projects, packed aggregate 38,176 bytes, profile SHA-256 `fd7153f2806e3f3ef215662d5e66b3153504e623f34365d180476cf6c497101a`). Flags included song-diagnostic, project loader, startup index 0, indexed TFT, compressed and flash Plaits wavetables, Shapes 12 voices. Objects compiled; link failed: `.text` exceeded XIP by **299,360 bytes**, and linker reported `.bss` could not be allocated in LOAD segment 2. No successful verification receipt or app image was produced. Log: `/home/claude/mvave-fm1/preload-selector-multiproject-link-20261014/link/link.log`; map is beside it. Failure does not isolate chooser contribution from profile changes. One-project retained builds do not prove multi-project fit. Coordinator separately reported an un-reproduced two-project baseline overflow of 1,248 bytes before chooser code.

The adapter's local storage is a 64-byte kind filter plus a 67-byte selector struct (131 bytes excluding call frames). Target stack watermark/resource acceptance is not established. No scratch build outputs were added to Git.

## Follow-up: exact two-project link and receipt binding

The earlier statements above that a successful multi-project link was still needed are superseded by a fresh matched target build on the two-project branch. With the selector present, the exact two-project image linked at 868,116 / 868,836 app-budget bytes (720 bytes free). The same request/profile linked without the selector at 867,564 bytes (1,272 bytes free), so the observed selector/link delta is 552 bytes. A fresh one-project image linked at 859,780 bytes (9,056 bytes free) and now records the chooser hook as absent. These are target link/package measurements only; the 720-byte margin is small and does not demonstrate runtime RAM, stack watermark, boot timing, or physical acceptance.

The API receipt now binds the runtime_hook_linked boolean to the number of selected projects: false for one project (chooser bypass), true for multiple projects. The target builder propagates the verified startup hook bit into image.json; controller tests verify both states and reject a receipt that says a multi-project image omitted the hook. The private service contract intentionally refuses older version-1 receipts missing this field; jobs are ephemeral and outputs are rebuilt by the pinned worker, so it does not reinterpret stale receipts as valid.

A broader focused run of installer service, native image controller, selector, and content embedding tests passed with the project state tool and pinned native toolchain environment. One parameterized test is skipped by its existing condition. The first test attempt without FM1_STATE_TOOL failed collection/execution for embedding cases; the successful rerun supplied both FM1_STATE_TOOL and FM1_NATIVE_TOOLCHAIN.

Fresh target receipts and build logs are retained privately on Hera under /home/claude/mvave-fm1/native-preload-selector-two-project-20261014/receipt-fix/. No binary or private scratch output is committed. Two-project configuration uses the matched all-13-engine/production-module selection except Plate, exactly as its baseline; this does not claim the all-55-module set fits with two projects. The single-project build uses the same no-Plate production selection.

## Limits, matched-link evidence, and next gate
The earlier numbered gate asking for a successful two-project link is superseded by the fresh matched results below. The four-project candidate's XIP failure remains a separate fact; it does not negate the successful two-project link. The older all-55 full-song target result is also separate because it used different profile/build flags and is not a matched chooser comparison.

A fresh bounded Hera build from the exact final source passed link/package verification for both one- and two-project requests, each with 54 of 55 production modules selected (Plate omitted). The two-project case is the matched chooser case: legacy Packet Bloom followed by Event Horizon, startup index 1. It linked at 868,116 / 868,836 bytes (720 free), with runtime_hook_linked=true. Its matched one-project Event Horizon request linked at 859,780 / 868,836 bytes (9,056 free), startup index 0, with runtime_hook_linked=false. The measured two-project-minus-one-project delta is 8,336 bytes overall; this is not an isolated chooser cost because project content and startup configuration differ. An earlier no-chooser two-project baseline at source a2463d83abcaba939884972a24932f1e6af6cb8f linked at 867,564 bytes (1,272 free); the observed image-size delta for adding the chooser to that corresponding request is 552 bytes. That baseline image SHA-256 is 7ee7e719b8b77e150fc507e8887de5b47842c7fa8da36216ed3e8ca6864a594a.

The exact matched receipts are retained privately under /home/claude/mvave-fm1/native-preload-selector-two-project-20261014/receipt-visibility-v1/. The source archive used for the fresh pair is 44,052,480 bytes, SHA-256 f8a83b1d4d4b3e0f48c8fb6253701f03d43d338c1924751a385523d670f6451a. The one-project request SHA is 99fa8f7a08b1757fb2e1f35026a159444993b59f4333cf4881d0c4604782e2c3; image receipt SHA 1264f842289685780999d1deec000022baa668312fbb911161a41088d470ee7f; verification SHA 5b006baee99c8846c13d9ea1948e0df6692288a2e4382ae42882fe9fd973264b; artifact-receipt SHA 71a2a3c70159aa376ce2b71d61995dbfd6a5f06153af44223a45602addbea53a; app SHA 3db418833a96244ad2add016cad53f69a5026092cdf93337ea0d869b9b94b30f; log SHA 267aac34d7d9af4e486f92d4de6b71c1c396edc102e2c6ca0e68b317d5aca81a.

The two-project request SHA is b52d9e846f67abe4dd187754e25f558543d7c8dcd8bd9a79c791ce5d5077a561; image receipt SHA 935a9b3f0f475b6c31e7a166c3a6061b76c1f05f05ff7deb80bd1d323bcb9808; verification SHA 599213a76eb07cca3d5769b27b20f909e5cbc81de4ab431b25ff7cb5b4ba9770; artifact-receipt SHA 77f3386c8c2bd760b405d05176340e304a9e63a681df6ab5693761a7f787ba8d; app SHA 5d94894282caf8eb769991e8d5535a2b14deae1fe7fd01617083b937f126031a; log SHA 751283635157222dbb824f209306e548954a1c67922adb5e171afb319a750eac. Both receipts report installable=false, hardware_admitted=false, hardware_tested=false, native_ram_verified=false, native_playback_verified=false, and full_song_default_accepted=false. These are private diagnostic links, not release or device acceptance.

The all-55-module single-Event-Horizon target result documented in notes/2026-10-14-song-diagnostic-runtime.md is 862,272 / 868,836 bytes (6,564 free) under its own continuous/full-song flags and profile. It is not the same configuration as these no-Plate 54-module diagnostic comparisons and must not be used as their baseline. The four-project link failure also remains unchanged and is not resolved by these two-project receipts.

Focused Hera tests were rerun with the project state tool and pinned native toolchain configured: **113 passed, 1 skipped** across tests/test_installer_service.py, tests/test_native_demo_image_controller.py, tests/test_native_preload_selector.py, and tests/test_native_content_embedding.py (114 collected). The skip is tests/test_installer_service.py:272, which requires LUNAR_RETAINED_BUILD to exercise an optional retained real build. The prior initial attempt without FM1_STATE_TOOL was an environment failure; the successful run supplied both FM1_STATE_TOOL and FM1_NATIVE_TOOLCHAIN.

Remaining gates are target RAM/stack-watermark and startup timing, native cold-boot/playback validation, full-song SAVE/reload and physical storage ownership/migration/rollback, watched device acceptance, web install/recovery, owner listening/default acceptance, and project review/CI/release. The chooser is currently an intermediate source/build capability only. No USB, MIDI, flash, power, reboot or other device operation was performed.

## Provenance
- Original assigned source base: 635dc019e3164fb84b330d590036dbfe2e44440a (historical task base, not the base of the final receipt run).
- Implementation branch/worktree: codex/2026-10-14-native-preload-selector-implementation in /home/claude/.local/share/codex-worktrees/native-preload-selector-implementation (historical implementation checkout).
- Final receipt source checkout: /home/claude/.local/share/codex-worktrees/native-preload-selector-two-project, branch codex/2026-10-14-native-preload-selector-two-project, source commit 6a968e69f5ccb13ad2c47ed89cab09425f3f2278.
- Coordinator integration/GitHub-backed SHA reported by parent: aca4d8104b6b45ac0acb272fa36b373009b72669.
- Final source archive SHA-256: f8a83b1d4d4b3e0f48c8fb6253701f03d43d338c1924751a385523d670f6451a.
- The pinned build image digest is sha256:7e32dd6d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d; builds were bounded under docker-batch.slice with network disabled, 4 CPUs, 8 GiB memory plus 10 GiB memory+swap, 512 pids, read-only root/source/toolchain mounts, and no-new-privileges.
