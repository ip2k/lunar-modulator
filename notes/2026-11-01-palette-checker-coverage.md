# Palette checker coverage, 2026-11-01

Base: `951ca6eb053c7fde82cd17baed949fd43528dab0`. This fixes a checker false acceptance found in the read-only audit of `b831724fcf413720aaa036dac742a382cdfaa93c`; it does not change the screen header, CSS, palette values, status colours, or generated Wasm.

`tests/test_sim_palette.py` now invokes the actual `palette.check()` entrypoint with in-memory changes to the pinned header. Before the checker fix, removing `RP_TEXT` returned no failures, and a defined `C_SELECT` alias through `C_PALETTE_SELECTION` was rejected. The checker also accepted `C_SELECT LUNAR_IRIS` even though that symbol was undefined. These cases were confirmed before implementation. The fixed checker requires shared screen tokens, resolves valid `C_*` aliases to their terminal palette token, and rejects missing, cyclic, or undefined aliases, including non-role `C_*` colour aliases.

Verification: `tests/test_sim_palette.py` 21 passed using the project venv; `python3 -B sim/web/tools/palette.py` reports “every rule holds”; `git diff --check` passed. No browser, audio, heavy build, generated Wasm, or device operation was part of this focused change. The separate Wasm source-drift gate is tracked by the coordinator.

Lifecycle: tests ran without bytecode or pytest cache writes in this worktree. Remove this isolated worktree after the branch is integrated and backed up; retain this note as the small durable provenance record.
