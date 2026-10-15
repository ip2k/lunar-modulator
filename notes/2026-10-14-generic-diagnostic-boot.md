# Completed diagnostic reset adapter — 2026-10-14

This offline change adds `tools/native/generic_diagnostic_boot.py`. It provides
`run_completed(policy, session, *, evidence_root, install_log_path,
snapshot_provider, after_install=None, now=None)` and no command-line/device
opener. It owns the install session’s single `run()` call so its returned
`verified_sha256`, completed journal, bound closed SG log, and final 1 MiB
readback cannot be substituted by caller-provided objects. The log replay
requires successful non-retried commands and a final page-by-page readback of
the exact policy target. Erase/program transcript rows must match the policy’s
allowed sectors and target page bytes/CRC.

After the transaction completes, `after_install(result)` can start asynchronous
audio capture. `snapshot_provider()` then returns `(snapshot_path,
raw_sha256)`. The snapshot JSON has exactly `schema`, `kind`, `observed_at`,
`usb_binding`, and `sg_binding`; it must be fresh (at most 120 seconds), later
than install completion, and match the bound loader connection. Freshness time
is sampled after the provider returns. The adapter writes a mode-0700 receipt
directory, fsyncs the campaign and a mode-0600 one-use marker, and only then
invokes the pinned `event120_generic_boot.session_class(event120_reset_module)`.
That reviewed class rediscovers the same USB/SG mapping and opens the existing
loader’s SG node for one FC0C argument-1 request. It never uploads a ROM loader
or retries. The result deliberately leaves `boot_observed` false; a completed
reset request and later native USB enumeration remain separate observations.

The reset adapter now uses the actual interfaces from `generic_diagnostic_flash`,
`generic_diagnostic_sg_adapter`, and `event120_generic_boot`: its direction
wrapper exposes the underlying policy as `_policy`, `_capture_binding()`
returns a mapping, closed `DurableLog` instances expose `fd is None`, and the
reset session requires the actual module containing `CompletionFirstReset`.
The prepared reset object carries `header_type` from the existing RehearsalSG
preparation. Tests instantiate a real `flash.Policy`/`DiagnosticSession`, a real
`DurableLog`, and the pinned generic boot/reset classes; only SG discovery,
file descriptor operations on the fake endpoint, and ioctl are replaced. The
large synthetic transcript skips fsync latency in the test fixture; this is not
a durability test.

Focused tests: `PYTHONPATH=tools:tools/native pytest -q
tests/test_generic_diagnostic_boot.py` (5 passed). `py_compile` and
git diff checks pass. There was no USB, MIDI, flash, power, or reboot access.
The positive test validates orchestration against mocked syscalls; it does not
establish physical SG_IO behavior, USB detach, native enumeration, application
boot, or audible output. Hardware/installability claims stay false.
