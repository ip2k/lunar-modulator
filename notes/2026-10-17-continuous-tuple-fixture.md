# Continuous tuple test fixture correction — 2026-10-17

The integrated continuous tuple-capture suite had one failure because its
`inputs('continuous')` helper supplied MIDI and current storage values but
omitted the canonical continuous instrumentation and optimization policy.
The production checker correctly rejected this stale fixture at
`diagnostic_telemetry`.

The fixture now merges `continuous_link_configuration()` when constructing a
continuous receipt. This keeps expected policy sourced from the same fixed
helper consumed by `checked_continuous_configuration`; no production checker
or admission behavior changed. Continuous tests still assert that receipts
are not installable or hardware-admitted.

Validation on base `6ac3808ea2ccbf0a4cb6e26558b7d9c3983b634d`:

```text
/tmp/lunar-installer-service-test-venv/bin/python -B -m pytest -q -p no:cacheprovider -o addopts='' tests/test_native_demo_image_controller.py tests/test_native_continuous_tuple_capture.py
108 passed, 1 skipped
```

Before the fixture update, the tuple-capture regression failed with
`Private continuous instrumentation/policy mismatch: diagnostic_telemetry`.
The focused suites are local test evidence only; no target build, hardware
operation, installability, or physical acceptance was exercised.
