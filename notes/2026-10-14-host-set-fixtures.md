# Host fixtures after native companion SET support

The native project sequence fixture lists compile/link sources directly instead of using the firmware build graph. After project_seq.c gained the checked companion-SET loader call, those explicit fixtures needed firmware/native/content_set.c. The application fixtures also need that source in their object lists. This repair is test-only; production source and firmware behavior are unchanged.

The app arena fixture now compiles and links content_set.c for both embedded and external arena profiles. The uncompressed demo startup fixture includes it in its native object list. The two sequence-only probes (test_native_demo_sequences.py and the adapted scene-label probe) include content_set.c, the sim/web/src headers it depends on, and compile functions/data into separate sections. They use the repository's native_host_link_flags() so unused app activation paths are garbage-collected at link time while the exercised sequence path remains linked. The full sanitizer flag bundle was not suitable for this Hera host: its linker lacks libasan.so.8; the target-specific help needed here was only section collection.

Validation on Hera (/home/claude/worktrees/host-set-fixtures, branch codex/2026-10-14-host-set-fixtures):
- /home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -xq tests/test_app_arenas.py completed successfully (all parametrized arena/startup cases reached 100%).
- /home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -xq tests/test_native_demo_sequences.py tests/test_native_demo_scene_label_adaptation.py completed successfully (8 cases reached 100%).
- /home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -q tests/test_native_demo_app_startup.py -k "not compressed" completed successfully (8 uncompressed startup cases reached 100%). Compressed startup selectors were left to the sibling owner.
- git diff --check passed.

The initial arena reproduction failed at link with undefined reference to lunar_content_load_set_checked, confirming the missing translation unit. A first edit had the object name without its corresponding source path; the corrected paired lists pass. One experimental sequence-test link using native_host_flags() failed because Hera lacks the ASan runtime library; replacing it with native_host_link_flags() passes and keeps the fixture's intent.

Limits: these are host-side fixture/build checks only. They do not establish target ABI, physical device behavior, or any installability/admission result. The sibling's compressed startup/content embedding run was separate and is not included here.
