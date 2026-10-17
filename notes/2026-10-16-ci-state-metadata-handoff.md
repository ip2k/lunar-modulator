# CI metadata example refresh, 2026-10-16

The metadata example at the assigned base (`2e59c5b5`) still carried
`meta_id` `53ec1875`, while the current default-build C export reports
`64c1b688`. The example was regenerated from `fm1-render --meta` using the
existing `tests.state_meta.subset` and `tests.state_canon.dumps` helpers; no
hash was edited independently. The regenerated subset differs from the old
fixture only in the Shapes `ram` field (`207728` to `207736`) and its
`meta_id`. The schema defines that id as CRC-32 of the full export without
`made` and `meta_id`, so the 8-byte RAM metadata change explains the new id.

Validation used the existing host `fm1-render` at
`/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware/engines/build/fm1-render`.
Its `--build-info` reports the default configuration: GPL enabled, all 40
engines, 2 MIDI effects and all 16 modulation kinds. The binary's source
inputs were compared with the assigned source base; no engine source or
metadata exporter inputs differed. No heavy Mac build or hardware operation
was run.

Checks:

- `pytest -q tests/test_state_schema.py -k 'schemas_are_valid_and_named_for_their_place or example_validates_and_is_canonical or schemas_refuse_what_they_should or numbers_are_written_as_the_layout_says or every_q14_amount_has_one_shortest_decimal'`: 15 passed.
- A focused invocation of the same exporter/subset/canonical comparison as
  `test_the_metadata_example_is_the_builds`, plus the repository's metadata
  schema validator: passed (`meta_id=64c1b688`, Shapes `ram=207736`).
- `git diff --check`: passed.

The renderer-dependent pytest case itself was not run through the repository
fixture because its fixture invokes `make -C engines`; the bounded direct
check exercised the exact fixture comparison using the verified existing
renderer instead. This change does not alter schema compatibility gates,
hardware acceptance, or release status. Parent review and current CI remain
the next validation steps.
