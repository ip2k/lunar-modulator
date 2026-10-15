# Generic diagnostic RehearsalSG adapter (2026-10-14)

This change adds an offline adapter between the reviewed `generic_diagnostic_flash.Policy` and the existing `expanded_sg.RehearsalSG` constructor. It does not create a device opener or CLI: the caller must explicitly inject `transport_factory(prepared, direction_policy, log)`. No factory was invoked against a real transport during these checks.

At bind time the adapter verifies the exact pinned policy, SG, ROM-read, bound-diagnostic and flash-transaction source bytes. The resulting prepared shim rechecks policy files, read evidence and those dependency bytes each time the existing RehearsalSG path calls `prepared.check()`. The direction shim delegates plan bytes, baseline, target, changed sectors and journal checks to the original policy; it does not derive a second transaction. Install is tied to the policy's original read binding. Restore requires the policy's exact fresh-read schema and same stable USB port while allowing the new USB/SG endpoint to be checked by the existing generic policy. The generic `DiagnosticSession` remains responsible for the initial full-image restore reread and mismatch refusal.

The adapter supplies an exclusive mode-0600 JSONL log in a caller-provided owner-only directory. Each record is fsynced. A wrapper closes the transport and log together, including failed binding; it does not retry an exchange. Existing RehearsalSG retains its command allowlist, CDB validation, live mapping check, no-retry latch and durable mutation-intent checks.

Focused Hera command:
`/home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -q tests/test_generic_diagnostic_sg_adapter.py tests/test_generic_diagnostic_flash.py tests/test_expanded_sg.py`
Result: 14 passed. `py_compile` passed for the adapter and its tests. Tests use injected fakes for mapping and close behavior; they do not instantiate RehearsalSG against a device, exercise physical USB/SG, or establish physical/recovery/installability acceptance. SAVE and every hardware-admission flag remain false in the existing policy.

The project semantic servers selected the Mac primary checkout rather than this Hera worker, so this bounded worker used direct source inspection and executable host tests instead of claiming Hera semantic-index coverage. Parent review is still needed before integration.