# Edit text parser and formatter safety

Personal Lunar Modulator work; scoped to app-core audit A4/A5 at baseline
`b831724fcf413720aaa036dac742a382cdfaa93c`. No device operations. [verified]

## Changes and compatibility

- `fm1_edit_parse_text` rejects nonfinite index values and values at or above
  the exclusive float boundary 2^32 before conversion. `float(UINT32_MAX)`
  would round up to that boundary, so it is not a safe inclusive limit.
  Finite negative values retain the UINT32_MAX sentinel; nonnegative finite
  fractions retain truncation toward zero. Negative infinity is now rejected
  rather than becoming the sentinel. Non-index float record behavior is
  unchanged. [verified]
- `fm1_edit_rec_text` derives a role only for unpacked records; verbs no
  longer read an unwritten record. Formatter protocol strings are unchanged.
  [verified]

## Directed verification

`tests/test_edit_text_safety.py` compiles the actual translation unit with
Clang `-fsanitize=undefined,float-cast-overflow -fno-sanitize-recover=all`,
using function/data dead stripping to avoid linking the engine bank. The
minimal module header disables FM6 only for this isolated link. Command:

```sh
/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -m pytest -q tests/test_edit_text_safety.py
```

At baseline: 7 failed / 9 passed. NaN/NaN-case variant, positive infinity,
1e30, 4294967296 and 4294967295 reproduced float-cast-overflow at original
line 1077 (the final decimal rounds to 2^32 as float). Negative infinity
failed the new rejection expectation; its old sentinel path did not perform
an invalid conversion. After the fix: all 16 passed. [verified]

Coverage includes the highest representable float below 2^32 (4294967040),
zero/negative zero, finite positive/negative fractions and large finite
negatives. Formatter coverage checks CURRENT, VIEW, SWAP, MOVE, LOADED,
invalid type/role and every supported record type at zero, truncated and
full output capacities. Valid records/verbs survive pack-unpack byte comparison;
a golden PARAM vector fixes layout/padding. These valid formatter checks also
passed at baseline. [verified]

Apple Clang 21.0.0 on arm64-apple-darwin27.0.0 rejects `-fsanitize=memory`;
MemorySanitizer was not run. A5 is a source-level fix with directed formatter
regressions, not an MSan reproduction. Small before/after/sanitizer logs remain
in ignored `scratch/edit-parser-safety/`; temporary sources/executables are
removed in the test fixture and baseline probe. [verified]

## Tool and acceptance limits

Rarefaction status/orient/scope and Serena initial instructions/config plus
bounded `find_symbol` were checked on their shared primary checkout
`/Users/likwid/Developer/mvave-fm1-firmware`. Shared activation was not changed.
Serena found the parser's matching source range. Rarefaction found the parser
signature/body/callees and the formatter's dump caller, but missed the known
`fm1_edit_check.c` parser caller. Its fallback C flags have no root compile
database. Neither tool selected this external isolated worktree; authoritative
editing and verification therefore used exact baseline/worktree files and
bounded source searches. No complete semantic index or target ABI claim.
[verified]

No engine, PCM or event-order code changed. Full existing native `--edit-check`
(including dump/application roundtrips) and the Wasm edit test remain integration
checks for the coordinator. This changes hashed source `fm1_edit.c`: a full
WASM batch rebuild is required before integration/release acceptance. No PR or
merge performed by this lane. [verified]

Branch: `fix/2026-11-01@edit-parser-safety`. Worktree:
`/Users/likwid/.codex/worktrees/lunar-edit-parser-20261101`. Coordinator should
review/cherry-pick the pushed commit, run the integration checks above, and
remove this worktree after integration. Built-in Data volume had 1122 GiB free
at start, above the 500 GiB floor. [verified]
