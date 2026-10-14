# Native demo preload export (2026-10-14)

`tools/native/export_image_catalogue.py` now emits four selectable project
records for the restored original examples. It reads and hashes the exact
materialized `.lunar` file in the current exporter checkout; it does not read
Git history or another worktree at build time. IDs are stable
`legacy-example-<slug>` values. The default profile still has `content: []`.

| ID | BPM / bars / scenes | Nominal arrangement estimate | Source SHA-256 |
| --- | --- | ---: | --- |
| `legacy-example-afterglow-relay` | 92 / 76 / 8 | 198.260870 s | `56098c13c658450c4013f91583cf04dafa6062b30c1c240446401a4201741a62` |
| `legacy-example-event-horizon` | 144 / 116 / 8 | 193.333333 s | `5b92ad3d8e6448855b9cde032a935437331620819becbb206212f32845414897` |
| `legacy-example-packet-bloom` | 112 / 88 / 8 | 188.571429 s | `7d755fd777f1b0534c2518717e4bded475872db57f9596fe410d75606765e349` |
| `legacy-example-neon-transit` | 120 / 104 / 8 | 208.000000 s | `e19152d0747d6d2a69cc61eaabeed6d083f89fbecdfa7e1d85ba7f9911f6e251` |

Each duration is explicitly a metadata estimate computed as bars × four beats
per bar × 60 / BPM. It is not a listening, arrangement-length, or native
playback finding. The projects remain `legacy-example`, `default_candidate: false`,
and are described as not approved showcases/defaults. Project master effects
and all other module dependencies are intentionally not inferred here:
`dependency_validation.status` remains
`pending-packed-backend-validation`, `dependency_scan_complete` is false, and
no module IDs are declared validated. The packed backend and exact link receipt
must establish those dependencies.

Each `source_path` is relative to the exporter repository root, for example
`engines/state/examples/afterglow-relay.lunar`. It is a catalogue locator, not
a profile `content` path. `prepare_image_profile.py` resolves content against
the directory containing the selected profile and refuses paths escaping that
profile directory. A profile producer must hash-check the selected repository
source, copy those exact bytes into its own profile staging directory (for
example `projects/legacy-example-afterglow-relay.lunar`), and place only that
staged relative path in `profile.content`. This keeps repository paths such as
`../../engines/...` out of untrusted or externally supplied profile data.

The export now carries `full_song_default.required: true` and
`full_song_default.status: "pending"`, with blockers for owner musical approval,
packed content/dependency validation, and native full-song playback plus
save/reload. This makes the still-empty production default explicit and
noncompliant until its separately authorized acceptance gates pass; this task
does not select a default.

## Verification and limits

Parent verification using the primary repository `.venv/bin/python` passed
all 34 catalogue, candidate-inventory and canonical/web asset checks:
`tests/test_native_image_catalogue.py`,
`tests/test_native_demo_preload_catalogue.py`, and
`tests/test_sim_files.py::test_the_page_examples_are_the_state_examples_and_mit`.
This resolves the worker-local pytest availability limit below.

The normal `python3 -m pytest tests/test_native_image_catalogue.py -q` command
could not start because the system Python has no pytest. An offline `uv run`
attempt also confirmed pytest is absent from the local cache, so no dependency
was fetched. The exporter itself ran successfully using the real Make metadata
resolver and emitted groups of 13 engines, 24 effects, 2 MIDI effects, and 16
modulation modules. A direct Python verification checked all four exact file
hashes, titles, stable IDs, manifest-derived timing fields, empty default
content, pending release metadata, and unvalidated dependencies. No image,
native link, device, or physical playback was tested.

Rarefaction status resolves `tools/native` under the active primary checkout,
not this worktree. Serena also reports the primary checkout as active. Neither
shared semantic selection was redirected; the changed Python source and known
test caller were inspected directly.

Next: root should review this catalogue shape with the preparing/build worker,
which must copy selected bytes into safe per-profile staging and then use the
packed-image decoder and exact embed/link receipts. Do not set the full-song
default until an owner-approved composition has passed those gates and native
playback/save/reload acceptance.
