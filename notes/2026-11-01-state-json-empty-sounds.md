# Project JSON requires Sound 1

Personal, non-commercial Lunar work. Scope: SS3 from the sequencer/state audit;
base `951ca6eb053c7fde82cd17baed949fd43528dab0`. This is a bounded codec fix,
not a whole-repository audit or an aggregate native RAM acceptance result.

## Contract and cause

[verified] `engines/state/schema/project.schema.json` requires `sounds`, defines
four canonical slots, and says Sound 1 is never empty. The state-files format
note (`notes/2026-10-06-state-files.md`, sections 3 and 7) likewise says Sound 1
is never empty/null. Both JSON readers already refuse an explicit null in slot
1, and both JSON writers refuse a project without Sound 1.

[verified] At the base, `{"lunar":"1.0","kind":"project","sounds":[]}`
passed both readers because their per-item validation never ran. The C reader
emitted END with zero UNIT records; either writer then refused `BAD: Sound 1
is never empty`. A fresh HEAD/END-only project also fails the writers, as
intended. Fresh application initialization does not choose an engine; the
separate default-chain operation does. The codec must not invent that choice.

The C reader now checks a closing sounds array, and the Python reader checks
the list before iterating. Empty project `sounds` is `BAD` before END. The
existing writer guards, format version, APIs and memory layouts stay unchanged.

## Compatibility boundary

[verified] This deliberately rejects previously accepted **invalid** empty
project arrays. It preserves accepted one-, two- and three-slot shorthand:
Sound 1 must exist, and canonical rewriting fills omitted trailing slots with
null. Explicit nulls in slots 2–4 and four populated sounds still roundtrip.
Unknown engine names and numeric parameter UID fallback survive canonical
rewriting. Empty effect chains/settings remain valid. The C maps-only setter's
separate envelope still accepts missing or empty `sounds`; it is not a project
load and still requires its browser metadata. Python has no maps-only reader.

## Verification

[verified] Before the fix, the focused normal probe passed 36 cases and failed
only the three empty-sounds feed sizes (1, 7 and 256 bytes): independent reader
success and END, followed by writer failure. After the fix, 82 focused cases
pass across optimized normal and AddressSanitizer/UndefinedBehaviorSanitizer
builds. Valid cases actually read, write, read and rewrite, requiring byte
stability and C/Python canonical parity. Negative cases check refusal code and
absence of END. They also cover missing sounds, null Sound 1, missing engine,
wrong sounds type, too many sounds, truncated JSON and empty input. Fresh
HEAD/END writer refusal and the maps-only exception are explicit regressions.

Seventeen existing schema validity/example/refusal cases also pass: **99 passed
in 7.05 s** on this Mac. Run with the project's existing Python environment:

```sh
python -m pytest -o addopts= -q tests/test_state_json_roundtrip.py \
  tests/test_state_schema.py::test_schemas_are_valid_and_named_for_their_place \
  tests/test_state_schema.py::test_example_validates_and_is_canonical \
  tests/test_state_schema.py::test_the_schemas_refuse_what_they_should \
  --basetemp=scratch/state-json-empty-pytest
```

The probe compiles only the tokenizer, number conversion, state names, JSON
reader/writer and test driver; it uses an empty registry and unknown IDs to
avoid DSP/renderer builds. Each compile/probe has a wall-clock timeout. Probe
buffers and writer storage belong to the test, with allocation freed on exit.
No hardware, renderer, full codec fuzz suite, WASM/native firmware build, CI or
listening checks were run. No application, event, sequencer or pipeline source
was changed.

[verified] Rarefaction status/orient/scope and Serena initial instructions,
current config and symbol lookup were checked. Both servers select the main
absolute checkout, not this external worktree. Shared Serena selection was
left untouched; their bounded main-checkout results were compared with exact
base source, then pinned worktree files were inspected directly. This does not
establish a complete index or device ABI coverage.

## Lifecycle and next dependency

The isolated worktree is `~/.codex/worktrees/lunar-state-json-empty-20261101`,
branch `fix/2026-11-01@state-json-empty-sounds`. Evidence belongs in its ignored
`scratch/state-json-empty/`; generated probes, sanitizer symbols and pytest
temporary outputs are removed after recording results. Retain this worktree
until coordinator integration, then remove it through `git worktree remove`.
The coordinator must review/cherry-pick the returned SHA and run the combined
release checks; this lane does not resolve the separate RAM fixture blocker.
