# Semantic tool validation, 2026-10-09

Lunar Modulator is the owner's personal MIT project [verified: `AGENTS.md`].
This evaluation used source navigation only; it did not access hardware.
Work branch: `chore/2026-10-09@semantic-tools-config`, based on
`origin/main` at `0a033d4eeca12103dbdbddbd9124fc078196c936` [verified].
The isolated checkout is
`/Users/likwid/.codex/worktrees/semantic-tools-config/mvave-fm1-firmware`.
The foreground editor checkout and other agents' files were not edited.

## What was tested

Results below are observed tool responses compared with actual source
[verified]. Successful startup alone was not counted as successful navigation.
Rarefaction reports an **on-open** index; these checks establish representative
coverage, not a complete whole-repository graph.

| Connection and language | Practical result | Limit |
| --- | --- | --- |
| Live Rarefaction, primary checkout, JavaScript | `orient` on `sim/web/www/editor/editor.js:31:10` returned `pref`, its body, and `startEditor` calls at lines 69/85/86. | Inferred JS project without a jsconfig; initial project membership was broad. |
| Live Serena, primary checkout | Initial instructions/current config showed only `cpp`; requesting symbols in the existing editor JS file failed with `ValueError: Explicitly requested symbols ... while path is ignored`. | This was an unsupported language in the active configuration, not proof the file was absent. |
| Serena, explicit absolute isolated checkout | Activation with session ID `a698b7f0`, followed by symbol queries, found JS `pref`, Python `check_package`, and C `fm1_state_bin_read`. | Session ID is not project-state isolation; see below. |
| Fresh private Rarefaction, JS | New config selected the `sim/web` root; `orient` found `pref`, direct `startEditor`, and the depth-two `setLayout` caller through the dynamic `startEditor` call in `www/app.js`. Source membership was 35 files. | A depth-two caller is indirect, not a direct call to `pref`. Paths passed to the tool remain workspace-relative, even when the profile root is nested. |
| Fresh private Rarefaction, Python | `check_package` found `main`, cross-file `stage`, and helper callees `_sha256`, `_forbidden`, `record`. | `tests/test_package_guard.py:57` uses dynamically loaded `PG.check_package`; no test edge was returned. This is missing coverage, not missing tests. |
| Fresh private Serena, same absolute checkout | Current config was ready; JS body/references matched source, Python and C symbols resolved. Bounded C diagnostics at lines 1179–1184 returned `{}`. | Empty diagnostics for six lines say nothing about the complete translation unit or target validity. |
| Live Rarefaction, C | `fm1_state_bin_read` resolved with its signature and helper callees; the six-node result was truncated. | Zero callers were returned despite known callers in `engines/host/render_state.cc:184`, `seq_tool.c:340/350`, `state_tool.c:343/672`, and `sim/web/src/fm1_app_state.c:1710/1805/1811`. No compilation database was present. |
| Fresh private Rarefaction, WAT fixture | `status` found `wat_server`; `orient scale` returned `$scale`, its body and `$render` calling it at line 8. | Disposable source fixture, not Lunar's binary module. |
| Fresh private Serena launcher, WAT fixture | `find_symbol` with substring matching returned `module 0/$scale`; references with `$scale` found `module 0/$render`; diagnostics returned `{}`. | Exact `scale` returned `[]`; preserve the returned WAT name path or use substring matching. |

The fresh checks used independent stdio clients, closed afterward. Their
scratch driver/results are in this checkout's ignored `build/` directory
(`semantic-tools-smoke.mjs`, `semantic-tools-final.jsonl`) [verified].
The WAT fixture was copied from
`/Users/likwid/Developer/rarefaction-lsp-mcp/fixtures/SampleWasm/engine.wat`
to a disposable canonical absolute temporary directory and removed afterward.
The final matrix returned no tool errors; the first attempts deliberately
exposed path/name conventions: a path relative only to the TS profile root was
rejected as outside the selected project, and exact WAT `scale` missed `$scale`.

Tools used in the attached session: `mcp__rarefaction__status`,
`mcp__rarefaction__orient`, `mcp__serena__initial_instructions`,
`mcp__serena__get_current_config`, `mcp__serena__activate_project`,
`mcp__serena__find_symbol`, `mcp__serena__find_referencing_symbols`, and
`mcp__serena__get_diagnostics_for_file` [verified]. Private clients called the
same server tools through the installed MCP SDK. No semantic edit tool was
needed for these small config/document changes.

## Configuration changes and applying them

- `.serena/project.yml` enables `cpp`, `typescript` (JS included), and `python`,
  retains gitignore filtering, and excludes research/scratch/generated output.
  No WAT language is enabled here because Lunar has no `.wat` source [verified].
- `sim/web/jsconfig.json` includes browser source and Node test scripts with
  ESNext modules and JS navigation enabled. It leaves `checkJs` disabled; this
  change does not establish that the editor is type-correct [verified].
- `.rarefaction.json` scopes the TypeScript profile to `sim/web`; it does not
  change the C or Python target or choose a machine-specific interpreter.
- `pyrightconfig.json` selects first-party Python roots and excludes ignored
  research/build output. Its final roots include assets, dongle, engines, sim,
  tools and tests. No portable configuration claims to provision dependencies.
- `.gitignore` shares only `.serena/project.yml`, keeping caches/memories out.
  A pre-existing local `.git/info/exclude` ignores all `.serena`; force-add was
  required to checkpoint the shared config [verified].

These configs **work on fresh private connections** [verified]. The attached
Rarefaction still has the primary checkout as its startup root; it cannot be
retargeted outside that workspace via `project`. Start a new connection/session
in the desired checkout after pulling these settings. Serena activation is
explicitly absolute; reselect the correct checkout and verify configuration
before relying on queries. No other live session or MCP server was restarted.
Source synchronization exists in Rarefaction's `src/session.ts` and profiles
report on-open freshness [verified: source inspection]; saved-edit freshness
was not independently exercised in this matrix.

## Embedded and Wasm boundaries

C/C++ navigation is **partial** [verified]. The existing live C scan counted
9,264 source files, including ignored research/vendor trees; no root compilation
database existed. Accurate cross-file coverage needs compilation commands for
the selected build, generated headers (including `fm1_gpl_mods.h`), include paths,
GPL build switch, language standard and target/sysroot [inferred from the build
files and failed caller coverage]. Host, Emscripten and device analysis databases
must remain distinct. Do not commit machine-specific compile commands or vendor
binaries. `make -n` is not entirely read-only here: `engines/Makefile` has
parse-time shell generation of the GPL header [verified: source inspection].

Upstream clangd does not implement JieLi pi32v2 [verified: the existing helper
explicitly rejects JieLi processing without `--analysis-target`].
`/Users/likwid/Developer/rarefaction-lsp-mcp/tools/prepare_clangd.py` can remap
captured paths and strip custom ISA flags only with an explicit approximate
analysis target. A 32-bit substitute such as `i386-unknown-none-elf` is a parsing
approximation, **not** evidence of device ABI, inline assembly or code generation.
The helper was inspected, not executed for Lunar. Actual device compiler/link
checks remain separate gates; none ran in this task.

Lunar's Wasm is built from C/C++ (`sim/web/mk/sim.mk`, `WASM_EXPORTS` and standalone
Emscripten link flags) and instantiated by `sim/web/www/fm1-wasm.mjs`; worklet and
parity tests call its exported functions dynamically [verified]. No generated
Emscripten JS runtime bridges this standalone module. Inspect `fm1_web.c`, export
list, wrapper, `worklet.js` and `test/parity.mjs` separately: neither MCP infers
cross-language export/runtime-dispatch edges [verified: Rarefaction tool
contract; inferred Serena graph boundary]. The Lunar binary was not disassembled;
`wasm-tools`/`wasm2wat` were absent from PATH [verified]. WAT backend success on a
fixture must not be reported as validation of `fm1.wasm` or its C build target.

## Tool improvement candidates

No upstream source was changed or posted. Candidate investigations [inferred]:

1. Rarefaction source membership should honor configurable exclusions/gitignore
   so firmware research/vendor trees do not dominate scans. `src/fs.ts` currently
   excludes dot directories and common output directories but not `reference/`
   or `scratch/`; `.rarefaction.json`'s strict schema lacks exclusion settings
   [verified]. Narrowing one C root would lose relevant callers in other roots.
2. Embedded profiles should surface the selected compilation database, target,
   sysroot and generated-header readiness, and make incomplete caller coverage
   harder to mistake for dead code. Today's warning is useful, but the observed
   graph still omitted known C callers [verified]. Do not automatically apply a
   host substitute to Emscripten or label it device validation.
3. Serena project activation is agent-global in the installed
   `2.0.0.dev0` implementation: `ActivateProjectTool.apply` invokes
   `self.agent.activate_project_from_path_or_name(project)`; `session_id` is
   used for the activation message, not project lookup [verified:
   `.../site-packages/serena/tools/config_tools.py:44–53`]. Use independent
   connections for concurrent worktrees unless the runtime proves isolation.
   An explicit per-session project parameter/state would be a useful upstream
   improvement. The installed code alone does not prove Codex shares one server
   between these agents.

## Account-wide guidance saved

At the owner's explicit request, the existing joint-workflow sections were
extended in `/Users/likwid/.codex/AGENTS.md` and
`/Users/likwid/.claude/CLAUDE.md`, with this identical text [verified]:

> At the start of every new Codex or Claude session on a new or existing codebase,
> check Rarefaction status, read Serena's initial instructions/current config, and
> verify both tools select the actual absolute checkout/worktree for this session.

> Perform a small practical evaluation before relying on either tool: compare a
> bounded Rarefaction orient result and Serena symbol/reference or diagnostic query
> with representative source and a known caller or test in each relevant language.
> Check index freshness, interpreter/build target, generated headers/bindings and
> FFI/runtime dispatch separately; evaluate WAT only when present, or use the
> original source language and actual Wasm build target. Empty results are not
> proof of no callers. Record tested successes, failures and coverage limits in
> project notes; repair configuration when justified and report reload/restart
> requirements. Select projects by absolute path and verify per-connection/session
> selection during concurrent work; a session ID alone does not prove isolation.
> Do not change another active session's shared project or restart its server.

One new owner-authorized memory update was saved at
`/Users/likwid/.codex/memories/extensions/ad_hoc/notes/2026-10-09-semantic-tools-session-evaluation.md`.
No existing memory file was edited. These account files are regular files outside
Git [verified]; their local saves are not a verified off-machine backup. The exact
new policy is backed up with this repository note once this branch is pushed.
Already-loaded instructions in other live sessions are not retroactively updated.
