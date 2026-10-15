# Permissive diagnostic and postmix headers — 2026-10-15

The native app's overall GPL-3.0-only distribution and these headers' MIT
licenses are compatible and describe different copyright scopes. The root
`LICENSE` governs the combined application, which contains GPL components;
`LICENSE-MIT` preserves the author's MIT grant for first-party reusable
components. Using MIT-licensed code in a GPL application does not convert that
source file to GPL. The headers remain under MIT; a combined firmware that
links GPL runtime/engine components remains GPL-3.0-only and must satisfy its
source and notice obligations.

Two first-party headers were incorrectly tagged GPL, which made the MIT/BSD
engine-profile dependency check reject them even when selected GPL engines are
excluded:

- `engines/include/engine_render_profile.h` was introduced by first-party
  commit `6b8576bde3fed1fa6af065f6ade19167586525bd` as a new 40-line header.
  It defines two engine IDs, opt-in timing macros and declarations for callback
  functions. It contains no copied GPL code. With profiling disabled, the
  macros compile away; with profiling enabled, the application may provide
  the timing callbacks, but the header's API declarations/macros remain
  independently authored MIT code.
- `sim/web/src/fm1_postmix.h` was introduced by first-party commit
  `7dabaec1f91eb1649ce2853835ab260e6d229ded`, extracted from
  `fm1_app_render` in `sim/web/src/fm1_app.c`, whose header already stated
  “MIT licence, like the rest of this repository.” Its scope-wrap helper,
  scope/peak tracking and gain pass are first-party app logic. Later commits
  `c0644560`, `faf5147d` and `0e02422f` refined this same helper (including the
  builtin fabs path); they did not import third-party code.

Both files now declare `SPDX-License-Identifier: MIT`.
Existing `tests/test_gpl_switch.py::test_the_mit_build_compiles_no_gpl_file`
remains the integration check: it follows every dependency of the switch-off
build and rejects GPL-marked files. No license scan was weakened, and no
Plaits/Mutable provenance or license marker was changed.
