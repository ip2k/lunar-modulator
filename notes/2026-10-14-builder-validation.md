# Native builder catalogue boundary validation — 2026-10-14

The selectable builder's module resolver consumes `print-modules` output from
the canonical Make catalogue. The prior parser accepted repeated catalogue
IDs, arbitrary kinds and malformed object paths, skipped every row beginning
with `list`, and did not verify that the backend selected the IDs requested by
the caller. That could let inconsistent catalogue metadata flow into builder
profiles and exported receipts.

`tools/native/module_selection.py` now requires the single expected terminal
row (`list custom` for literal selections or `list all` for `all`), unique
well-formed module IDs, known module kinds, literal `0`/`1` selection flags,
and relative `.o` object paths without parent traversal. For literal requests,
the selected set must exactly match the requested IDs. The `all` selection
still takes its selected set from the canonical catalogue output.

Five focused hostile-backend tests were added in
`tests/test_native_module_selection.py`, covering duplicate rows, an unknown
kind, a parent-traversing object path, a wrong trailer and a backend-selected
set that differs from the request. The full selection test file passed locally:
`/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/pytest -q
tests/test_native_module_selection.py` — 37 passed. Running system `python3`
first failed because that interpreter has no pytest; the repository venv run is
the passing result. The live Make catalogue's normal literal and `all` output
is also covered by the existing tests.

This validates metadata returned by the local Make catalogue; it does not
authenticate a compromised source tree or build service. It is not a linked
image, installable artifact, firmware-admission receipt, release image,
all-thirteen fit result, semantic validation of song/set dependencies, or
hardware/OTA/recovery acceptance. No device or hardware command was run. The
timed builder remains diagnostic, and the web UI/build service and release gates
remain open. Serena and Rarefaction were checked, but both selected the primary
checkout; the shared selection was left unchanged and Rarefaction could not
orient this worktree path.
