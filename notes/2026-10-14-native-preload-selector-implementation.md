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

## Limits and next gate
1. Get a fresh successful target link with at least two projects and required production modules/effects. One project only proves default bypass; four projects fail XIP; the separately reported two-project baseline was already slightly over budget before chooser code.
2. Measure incremental XIP/RAM against a one-project baseline with identical source/catalogue/toolchain/flags, resolve the `.bss`/LOAD diagnostic and pass package/layout audits.
3. Physical boot selection needs the coordinator's separate authorized validation; none was performed here.

## Provenance
- Assigned source base: `635dc019e3164fb84b330d590036dbfe2e44440a`.
- Worktree: `/home/claude/.local/share/codex-worktrees/native-preload-selector-implementation`.
- Branch: `codex/2026-10-14-native-preload-selector-implementation`.
- Profile producer source commit: `e435edadad48641e9e08c0023b71b80b5692cd44`; this is link-attempt evidence only, not target admission.
