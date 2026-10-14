# Native companion SET selection and startup

This branch adds an explicit pre-audio choice for an embedded companion SET while keeping Event Horizon Showcase as the default startup project. The builder derives each SET's parent index from the trusted prepared-selection receipt, embeds that index in the native catalogue, and rejects a SET whose parent does not match the prepared startup project. A project chooser runs first when the image contains multiple projects; the SET chooser then lists only SETs bound to the selected project. Confirm loads the SET through the cold-start staging path. Timeout preserves the selected project's own sequence.

The platform selector is injected only for project-startup images containing multiple projects or at least one companion SET. Both selector polls run before `fm1_audio_init`, scan debounced encoder/button input, feed the watchdog, and use an 8-second timeout. The existing single-project/no-SET image path remains unchanged. This supports explicit selection during cold boot; it does not add hot switching or standalone SET startup.

Companion startup stages the SET into one temporary sequence allocation sized from the initialized app's actual sequence limits, validates its route and parameter locks against the selected parent project's engine plan, activates it into the app sequence, then frees staging before engine allocations. Existing ownership and no-live-pool preconditions remain in force.

Validation on Hera:
- Focused native selection, companion receipt, and project sequence suite: 43 passed, 2 skipped because the generic test image has no JieLi pi32v2 toolchain.
- Selector/receipt tests after the added chooser-order regression: 11 passed.
- Browser-export request interoperability against the committed fixture, using a freshly built `fm1-state` binary and no browser-export environment override: 3 passed (preparation acceptance plus wrong-parent/startup refusals).
- `git diff --check`: passed.

Limits: these are host/parser/sequence tests and a request-to-profile interop check. No target link was run in this task because the assigned Hera checkout had no installed pi32v2 compiler, and no physical device or audio/listening acceptance was performed. The generated selector ordering is covered by a source-level regression; physical control feel, timeout timing on device, and companion audio behavior still require later target and owner acceptance. Device/installability/recovery admission remains false.


## Follow-up: standalone SET compatibility and target link

The initial branch implementation regressed two supported builder cases: a standalone `--startup-set-index` image without a startup project, and generic `embed_image_content` callers that embed SET content without companion-parent metadata. Commit `756950d7bb5aa8863d9565d8218cb2227f19edd5` restores both paths. Unbound SET catalogue content is permitted by the generic embedder and explicit standalone SET startup; project-startup companion mode still requires the trusted selection receipt to identify the SET's parent project. Passing both startup modes remains a refusal. Native SET selection now checks the selected index against the catalogue count before dereferencing it.

Focused regression command on Hera used the current committed tree and a fresh `fm1-state` binary:

```text
python3 -m pytest -q -ra -p no:cacheprovider --basetemp=/tmp/lunar-pytest \
  tests/test_companion_selection.py tests/test_native_content_embedding.py \
  tests/test_native_preload_selector.py tests/test_native_project_sequences.py
82 passed, 18 skipped (target-only compiler checks; FM1_NATIVE_TOOLCHAIN absent in pytest image)
```

An exact-commit offline pi32v2 link then succeeded with project startup index 0 and companion SET index 1. Inputs were the prepared selection in `/home/claude/mvave-fm1/set-backend-interop-20261014/build/result/selection`: selection receipt SHA-256 `1cf0a0b897005e4ff0925d63a345c8d5db59a3b59368c6e7dfcd34308994db95`, prepared profile SHA-256 `af37827fa09a5925864bfebe01d800f8b37ffcda8ce4f42bf533ea9e774c4f30`. It includes two packed assets (project 4,345 B; SET 1,887 B), with the SET parent bound to the startup project. The request selects 54 catalogue IDs, including all 13 production engines; Plate is not selected. The production test-only `test-sine` module is excluded. The builder reported catalogue source freshness verified.

The bounded command used source commit `756950d7bb5aa8863d9565d8218cb2227f19edd5`, `lunar-jieli-check:bookworm` image `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`, and toolchain `/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1` (`clang` SHA-256 `42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`). It ran offline under `docker-batch.slice` with 4 CPUs, 8 GiB memory/swap, pids 512, read-only inputs, and no network. Flags were `--runtime-mode song-diagnostic --stack-watermark --flash-layout expanded-d7000 --link-set-loader --link-project-loader --startup-project-index 0 --shapes-voices 8 --indexed-tft --compressed-wavetables --flash-plaits-wavetables` plus the exact prepared-profile digest above.

Target receipt `/home/claude/mvave-fm1/native-companion-set-target-20261014/output/linked/verification.json` (SHA-256 `ad5484345120647d08482b3c37640f1a4b77c6f0eb345ee8affc5aed024be347`) reports app size 848,160 B against the 860,644 B expanded-D7000 link budget (12,484 B remaining), ELF SHA-256 `43f3b3d1f41de8e834acdeaa0376df234e6d097c05b5dbb40efd2a1e49c5f697`, and app SHA-256 `b8394eee2c5b8ccfa916fdce060de0b039a0fc4e4195f87d142f7c9768accc3f`. It links the project and SET loaders, companion selector, indexed TFT, compressed wavetable path, and 216,064-byte instance pool. The chooser receipt says selection is before audio init and timeout preserves the project's sequence. Runtime activation, sequence semantics, stack margin and hardware behavior remain unverified. `hardware_candidate`, `hardware_tested`, and `installable` are false; flash write range is empty and OTA cleanup is false. This target link is compile/link and static-audit evidence only, not physical, perceptual, package, or installation acceptance.
