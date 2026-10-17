# Captured-source wavetable regeneration — 2026-10-17

Tuple capture receives a detached, clean Git snapshot as its `root`, while
the capture service itself runs from another checkout. Importing
`prepare_wavetables` in the service process therefore selected the wrong
source tree and rejected valid Trio/Macro builds.

Capture now hashes the clean source manifest before running generated-input
verification and requires it to match the invocation's commit and post-build
tree digest. It then starts an isolated `python -I -B` subprocess, prepends
only the captured tree's `tools/native`, verifies the loaded
`prepare_wavetables.py`, `evaluate_wavetables.py`, and `evaluate_wavetables.ROOT`
all resolve to that tree, and runs the generator there. The existing selected
namespace, generated-file inventory, metadata, and byte-for-byte comparisons
remain in force. The post-capture source-manifest check still detects changes
during verification.

The regression builds a separate clean temporary Git checkout, makes the
service generator fail if called in-process, and confirms captured-root
generation succeeds. After modifying the captured asset, the pinned manifest
gate rejects it as dirty. Existing Trio-only, Plaits-only, Braids-only, and
combined namespace cases and tamper/missing/extraneous-resource checks remain
covered.

Validation:

```text
/tmp/lunar-installer-service-test-venv/bin/python -B -m pytest -q -p no:cacheprovider -o addopts='' tests/test_native_continuous_tuple_capture.py tests/test_native_demo_image_controller.py
109 passed, 1 skipped
git diff --check
```

These are local capture and fixture tests only. No target build, device
operation, package admission, installability, or physical acceptance was
performed.
