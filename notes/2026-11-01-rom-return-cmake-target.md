# Return-r01 CMake target selection — 2026-11-01

The first separately allocated offline Pico build from `446fa00c9154c5f468e0669c3706ea011339c47c` stopped during CMake configure, before any firmware compilation. The retained build log reports `if` receiving `TARGET STREQUAL fm1_transporter_return_r01` and rejecting those arguments. The function parameter was named `TARGET`; CMake parsed its bare spelling as the `if(TARGET <name>)` predicate.

Patch `0003-fixed-return-r01-rom-mode.patch` now compares the expanded and quoted function argument: `if("${TARGET}" STREQUAL "fm1_transporter_return_r01")`. No other patch hunk, firmware source, wire grammar, default build script, host driver, SDK pin, or recovery path changed.

The test materializes the exact pinned upstream CMake file at `a7fb5e8ac692c528f8ed29e325911a3f4b8111d6`, applies the actual patch's CMake hunk, extracts the resulting selector from `fm1t_add_firmware`, and executes it with `cmake -P`. Before correction, all three cases failed with the same parser error as the actual build. After correction, the strict return-r01 target selects `return_r01_proto.c` and its strict log stub, while both default targets select `transporter_proto.c` and `log.c`.

This is source and host CMake interpreter proof only. A later frozen-source, separately allocated Pico configure/compile/link remains required; no second target build, Docker container, download, UF2, device traffic, or hardware qualification occurred in this correction lane.
