# Native framebuffer project workspace — 2026-10-14

[verified] Thirty cases in thirty concurrent Hera containers pass host
ASan/UBSan and compile the harness under pinned pi32v2 clang with warnings as
errors. All thirty logs, container exits, OOM flags and eleven source hashes
were checked. Private full logs: `build/native-project-workspace-20261014/v2/`.

[verified] The compact writer uses 39,176 host bytes inside 57,600 indexed
pixel bytes. Fixtures exercise four framebuffer alignments, successful binary
round trips and first/third callback refusals. Tests check metadata and outer
canaries, invalid pixels while leased and after release, refusal of missing
stop flags, oversize/empty requests and reentry, and complete redraw recovery.

[verified] Source inspection of `app_probe.c::display_strip` shows panel DMA
reads `cv_px`, populated separately from the indexed framebuffer. The lease
requires main-task exclusive access and affirmative audio/drawing/display-read
stop flags. These are caller assertions, not independently enforced locks.
No engine, sequencer or modulation arena is borrowed.

[verified] Initial v1 failed target compilation because JieLi clang warns on
`{0}` for this structure under `-Werror`; explicit initialization corrected it.
Failed campaign logs are retained in the private v1 directory.

[inferred] Pixel reuse can remove the need for a dedicated writer arena. This
component is not yet wired into native SAVE, and the tests do not prove full
firmware RAM fit, actual scheduling, hardware redraw or flash ownership.
No physical device command was sent. Flash capacity, migration, physical
rollback, full thirteen-engine acceptance and release gates remain open.

[verified] Serena resolved the actual worktree display function by absolute
path. Rarefaction resolved the primary checkout TFT declaration and draw
callers with fallback flags; it did not validate this worktree's native target.
Neither semantic index verifies pi32v2 ABI or hardware behavior.
