# Browser export to trusted project-plus-SET preparation

This check follows the exact saved browser export through the real trusted selection/preparation tools. It confirms that the browser request can produce a parent project plus its companion SET in the expected order, and that the backend refuses to prepare the SET if its parent is absent or is not the startup project.

## Inputs and checks

- Source base: `660a9ce3c105d99dd19d19fe1a736e8942b413d8`; browser changes from `e273bd8b7db3a0dc759ace95b37a4db73211ba2c` are included.
- Browser export: `/tmp/lunar-browser-set-preloads/out/installer-request.json`, raw SHA-256 `ef4ce3b330162abe9d4487c5b81bd170defa2c30cf0f00bca21f143f62da55f0`.
- Request selects project `replacement-showcase-candidate-event-horizon`, companion `replacement-showcase-event-horizon-companion-set`, startup index 0.
- A fresh `fm1-state` tool was built from the current source; binary SHA-256 `17f377d9966aac0efab705e6a10b900cb8d47dfebdbea8650bf00793b10bceb2`.
- Added `tests/test_browser_set_backend_interop.py`: exact raw request pin, actual `prepare_selection` and prepared-profile validation, selected-content ordering and identities, and refusal cases for a different parent or startup. The SET dependency scan remains false in the receipt; this is recorded rather than treated as a complete cross-content dependency proof.
- Hera bounded-container command: `python3 -m pytest -q -p no:cacheprovider --basetemp=/tmp/lunar-pytest-final tests/test_browser_set_backend_interop.py`, using the pinned `lunar-preload-tests:20261014` image, pytest mounted read-only, network disabled, and the request/state-tool mounted read-only. Result: 3 passed, exit 0.

## Bounded image-controller exercise

The same exact request also passed through `tools/native/build_demo_image.py` using the current Shapes-8 catalogue and pinned pi32v2 toolchain. The current-source freshness checks accepted the catalogue manifests. This was an offline link/package-controller exercise only.

- Image receipt: `/home/claude/mvave-fm1/set-backend-interop-20261014/build/result/image.json`, SHA-256 `c255d155e87056eeebc49bec43126f3b0e9892115f6953ccaca020026014409d`.
- Receipt reports app size 844,352 bytes against the D7000-reserved app budget of 860,644 bytes: 16,292 bytes remaining.
- Receipt app SHA-256: `7407d52a9cba1414210b6f378ae40d38f63d61b23c9b9fe4394cd93e66101915`. The app binary itself was not retained in this result directory; this is the hash/size recorded by the controller receipt.
- ELF: `.../build/result/link/lunar-app-probe.elf`, SHA-256 `68fec89dba3e46128f06a77b4d9a745433c2c592bf6260f719270e02d5996b1c`; link verification JSON SHA-256 `7b06290870c9e2b12e64d07ceb6dd553275ce830fe7e5485e83a914c5038d9b6`.
- The image receipt contains the project then companion SET, with packed content totaling 6,232 bytes: project 4,345 bytes (SHA-256 `b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163`) and SET 1,887 bytes (SHA-256 `7c850fcf8fda9ea513c8d1f14a414f638c8c1cc931156f7b000c757e7cfd0625`). Prepared profile SHA-256 is `af37827fa09a5925864bfebe01d800f8b37ffcda8ce4f42bf533ea9e774c4f30`; prepared source SHA-256 is `b8758874da7292a87dd25c76593d1052f7f711ae0e2c0813686137610245c7ca`.
- The build selected 54 production modules: 13 engines, 23 audio effects, 2 MIDI effects, and 16 modulation modules. Plate is omitted. Shapes-8, indexed TFT and compressed RAM wavetables were used; runtime is song-diagnostic at 120 seconds. The build used an implicit FM-1_990 application identity because the browser request did not choose an explicit identity.
- The receipt keeps `installable`, `hardware_admitted`, `hardware_tested`, `native_playback_verified`, and `full_song_default_accepted` false. SAVE is linked but flash I/O is unbound and the service is disarmed; storage admission and runtime verification remain false. Embedded SET sequence semantics are unverified.

## Limits and next dependency

This establishes browser request → trusted backend selection/preparation → bounded image-controller/link receipt. It does not establish that the current project-startup image offers a user-accessible way to select or activate its embedded companion SET. The source has a SET startup path behind `LUNAR_STARTUP_SET_INDEX`, but the current builder requires the parent project as startup; defining both startup selectors is not established as safe. The next dependency is a native user-facing companion-SET access path with tested activation and resource/precondition behavior, followed by its own target and hardware acceptance gates. No device or USB/MIDI/flash/power operations were run.
