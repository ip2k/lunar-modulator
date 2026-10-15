# Generic D7000 RehearsalSG adapter review (2026-10-14)

Reviewed adapter commit fd3c62e1cc33d6a770a684a674c1cfa2e200a7f4 and its three owned files read-only. The adapter preserves the policy as the transaction authority: it accepts only factory-created Policy instances, revalidates exact pinned source bytes, verifies the paired-read bundle, constructs a direction shim from verified USB/SG/read data, and delegates final binding plus restore's first complete-image reread to the existing DiagnosticSession. The RehearsalSG constructor can consume the supplied prepared shim and direction policy; its exact live mapping, wire allowlist, mutation journal gates, command latch, and close-on-error remain in force. The transport factory is injected; this adapter adds no opener or CLI.

Install read binding is compared field-for-field against the policy's original read binding before the factory is called. Restore accepts only the exact fresh-read field set, verifies that bundle, requires the same stable USB path/bus/VID/PID, then uses the new verified SG mapping and lets Policy.bind recheck the stable device and full-image hash before mutation. New read evidence and all adapter/dependency source bytes are retained in _Prepared.check(); log creation is exclusive, mode 0600 in an owner-only directory, each JSONL record is fsynced, and the transport/log lifetime is coupled.

Focused verification on the exact checkpoint:

- `/home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -q tests/test_generic_diagnostic_sg_adapter.py tests/test_generic_diagnostic_flash.py tests/test_expanded_sg.py` — 14 passed.
- `python3 -m py_compile tools/native/generic_diagnostic_sg_adapter.py tests/test_generic_diagnostic_sg_adapter.py` — passed.
- Checkout remained clean.

Tests cover install shim binding/log close, wrong-port rejection before factory invocation, changed source-pin rejection before factory invocation, and policy-binding failure cleanup, plus the existing policy and SG suites.

No code blocker found in this bounded review. Coverage limit: adapter tests use injected fake transports and a stubbed read verifier; they do not instantiate RehearsalSG against a physical SG device or prove USB identity, command completion, flash behavior, recovery, or installability. Full offline prepare() evidence elsewhere used an explicitly simulated verify_read_bundle; that is not live-read evidence. No device or hardware commands were run. Hardware/admission flags remain false.
