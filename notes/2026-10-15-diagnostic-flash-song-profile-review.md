# Diagnostic flash admission for a telemetry-only project + SET build

This began as a bounded source review for the proposed Event Horizon Showcase
plus its companion SET. The original review below describes the pre-change
policy. The implementation status at the end records the narrow policy
extension; no device was accessed.

## Admission findings

- [verified] The generic diagnostic policy currently admits only the older
  content-free Trio pulse profile. In
  `tools/native/generic_diagnostic_flash.py`, `_check_build()` requires the
  exact enabled `LUNAR_DIAGNOSTIC_TRIO_PULSE=1` record with its note/timing at
  lines 184–188. That rejects telemetry-only output, whose pulse record is
  disabled even though diagnostic telemetry is enabled.
- [verified] The same function requires `embedded_content.asset_count == 0`,
  `packed_content_bytes == 0`, and `assets == []` at lines 201–203. A project
  and companion SET cannot pass that check. `prepare()` then seals the
  content-free assumption again in its scope string and receipt at lines
  287–290 and 334–336 (`project_ids: []`, `startup_project_id: None`,
  `content_free: True`, pulse copied from the verification record).
- [verified] The independent stock reconstruction, exact frozen build and
  source/toolchain/catalogue/profile pins, complete paired live read, sector
  transition, directory-last ordering, and disarmed SAVE checks are separate
  checks in `_check_build()`/`prepare()`. A content-capable extension should
  keep those checks intact. In particular, retain all 13 sound IDs, D7000
  layout and empty flash-write-range evidence, exact app/ELF/disassembly pins,
  explicit FM-1_500/recovery FM-1_000 identity, stock/current image binding,
  and all hardware/installability/storage-admission flags false.
- [inferred] The narrow policy change is a second, explicit content-bearing
  diagnostic profile, rather than relaxing the existing pulse profile. For
  this profile require the externally pinned prepared-profile digest; exactly
  the selected Event Horizon project plus its exact parent-matched SET in the
  embedded-content receipt; startup project index/identity matching that
  project; companion-set selection enabled and matching that same parent;
  both loaders linked; `song-diagnostic`; telemetry enabled; pulse explicitly
  disabled; and no other content assets. Derive IDs, indices, byte counts and
  hashes from the pinned profile/build receipts and cross-check them against
  `startup_project`, `companion_set_selection`, and `embedded_content` in
  `verification.json`. Do not accept caller-provided IDs that disagree with
  those receipts. Keep the existing content-free branch exact.
- [inferred] The prepared profile/builder currently resolves asset indices and
  checks SET parentage (`tools/native/build_application_probe.py` lines
  353–388), and its report records embedded content (677–683), companion-set
  selection (703–711) and startup project (712–718). These are suitable
  cross-check inputs; admission must still validate their exact structure and
  bytes rather than treating the booleans `runtime_verified: false` or
  `activated: false` as runtime success.

## Startup result and telemetry

- [verified] `lunar_content_start_set()` returns 1 on successful checked
  activation and 0 on failure, while its `fm1_state_report_t` carries a
  separate detailed code (`firmware/native/content_set.c` lines 70–83 and
  86–107). `lunar_project_start_with_set()` similarly returns the combined
  project-plus-SET startup result through `project_start_impl()`
  (`firmware/native/project_boot.c` lines 103–124 and 132–138).
- [verified] The current `app_probe.c` has three relevant paths. Standalone
  SET startup stores both `startup_set_result` and `startup_set_report` at
  lines 282–289, but the telemetry frame serializes only
  `initial_engine_result` (`app_probe.c` lines 233–239). That field is assigned
  the Trio selection enum in the non-project branch at line 328, so a
  standalone SET build would not report its SET result. The standalone SET
  path also does not take the project path's explicit failure-to-ROM branch.
- [verified] The proposed project-plus-companion-SET build takes the project
  branch: it calls `lunar_project_start_with_set()` at lines 297–308, stores
  its boolean return in `startup_project_result`, returns to ROM on failure
  at lines 316–322, and assigns that result to `initial_engine_result` at
  lines 323–325. Thus successful telemetry from this path reports combined
  startup success as `1`; the existing detailed `startup_project_report`
  (including the SET load report) is not included in the schema-1 frame.
- [inferred] For this exact EH+SET target, the result is adequate as a
  combined startup-success indicator, but the name `initial_engine_result`
  is ambiguous across Trio and project startup modes. Keep the schema stable
  for the immediate build and document the mode-specific meaning in the
  receipt/note. A follow-up should either add a separately versioned startup
  status/report field or explicitly encode distinct startup modes; it should
  not claim that the frame includes the detailed SET report. Do not change the
  standalone SET path to a success claim without routing failure through the
  same recovery behavior and adding a test.

## Checks and limits

[verified] Reviewed the current source and tests directly. Rarefaction was
configured to the stale `/Users/likwid/Developer/mvave-fm1-firmware` root and
could not orient this worktree; Serena symbol navigation succeeded for the
reviewed files. That read-only review did not admit a build, prove audio
playback, or authorize a flash.

## Implementation status

- [verified] Added a separate Event Horizon + companion SET diagnostic input
  kind in `tools/native/generic_diagnostic_flash.py`. It keeps the existing
  content-free Trio pulse input strict and requires that pulse to be explicitly
  disabled for the song profile.
- [verified] The new path cross-binds the exact prepared profile bytes, the
  adjacent `selection.json` digest, ordered project/SET assets and hashes,
  parent project identity, startup indices, linked project/SET loader receipts,
  telemetry receipt, and the one-shot PLAY receipt. PLAY must be explicitly
  enabled with `LUNAR_DIAGNOSTIC_SONG_PLAY=1`, start at 2000 ms, run once, and
  remain untested on hardware. Output flags continue to report hardware and
  installability as false.
- [verified] Compared the policy assumptions with the actual prepared
  profile/selection at
  `/home/claude/mvave-fm1/song-telemetry-current-profile-20261015/selection/`.
  It has the exact EH project and parented companion SET, project startup index
  0, packed-content total 6232 bytes, and false hardware/installability flags.
  The prepared profile hash is
  `fd68a478ea594ab9c3a7f34a604e23f99614e707bb9840b8a91947b07e547738`.
  The policy also requires the final builder's exact PLAY receipt including
  its compile-definition field. The referenced directory contains prepared
  profile inputs, not a final linked build receipt; this check is schema
  compatibility only.
- [verified] Focused tests passed with the repo runner:
  `uv run --with pytest --python .venv/bin/python -- python -m pytest -q -o addopts= tests/test_generic_song_diagnostic_policy.py tests/test_generic_diagnostic_flash.py`
  (22 passed after adding the compile-definition tamper case). `py_compile`
  and `git diff --check` passed.
- [inferred] This validates policy/schema rejection and acceptance behavior
  using synthetic build receipts plus inspection of the real prepared profile.
  It does not prove a complete real `_check_build` admission, target playback,
  erase/program readiness, hardware recovery, or release acceptance. Parent
  review and the exact current frozen-build receipt remain required.
