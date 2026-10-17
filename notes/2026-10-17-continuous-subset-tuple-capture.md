# Continuous subset build tuple capture

[verified: source review and focused host tests] Tuple capture now derives the
compressed wavetable namespaces from the selected module list that is shared by
the prepared profile, linked build receipt and image receipt. It verifies the
prepared module header digest and re-runs the pinned source-tree wavetable
generator into a temporary directory. The resulting metadata, generated
include, and exactly selected resource source/header files must match the build
output byte for byte. This permits a Trio-only link with no resource banks while
still requiring and checking `wave_tables.json` and `wave_tables.inc`; missing,
changed or unselected bank files fail capture.

For both selected banks, the generated tuple path order remains the previous
all-bank order (`braids.cc`, `plaits.cc`, `braids.h`, `plaits.h` between the
same fixed paths). Tuple schema, field values and canonical serialization are
unchanged. This is build-provenance verification only. It does not establish
firmware admission, installability, physical behavior or SAVE authorization.

## Checks

- Namespace matrix: Trio only, Macro only, Shapes only, and Macro plus Shapes.
- Negative cases: missing selected source, changed selected source, extra bank,
  changed metadata, missing include, changed include, inconsistent module
  receipts, and changed prepared module header.
- Focused matrix/negative suite: 14 passed.
- Full tuple-capture test file excluding a pre-existing continuous receipt
  fixture failure: 30 passed, 1 skipped, 1 deselected.
- The deselected `test_continuous_runtime_is_explicit_and_still_not_an_admission`
  fails identically on base `bd64c60b13b797200d5cdb85c08e6dd58affc541` because
  its fixture's `diagnostic_telemetry` differs from
  `checked_continuous_configuration`; this change does not touch that contract.
- Rarefaction status and Serena instructions were checked. Rarefaction/Serena
  still select `/Users/likwid/Developer/mvave-fm1-firmware` or the separately
  active integration worktree, so they were not retargeted to this checkout;
  source was checked directly. No Insight tool was available.

The next step is root review and integration, followed by a fresh tuple capture
against the retained Aeon Trio-only build. No Aeon build, Hera work, bench,
device command, package creation or installation was performed here.
