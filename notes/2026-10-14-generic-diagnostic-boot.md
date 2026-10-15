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
than install completion, and match the bound loader connection. The adapter
writes a mode-0700 receipt directory, fsyncs the campaign and a mode-0600
one-use marker, and only then invokes the pinned
`event120_generic_boot.session_class(CompletionFirstReset)`. That reviewed
class rediscovers the same USB/SG mapping and opens the existing loader’s SG
node for one FC0C argument-1 request. It never uploads a ROM loader or retries.
The result deliberately leaves `boot_observed` false; a completed reset request
and later native USB enumeration remain separate observations.

The reset session is the existing `event120_generic_boot.session_class`
returned subclass of `CompletionFirstReset`. Its constructor takes
`(prepared, log_callable)`. Prepared exposes `check()`, `campaign` with the
USB binding, `bridge`, `expected_mapping` canonical bytes, and campaign/source
fields. The log callable accepts `event, **fields` and fsyncs JSONL rows. The
adapter derives the bridge/mapping from the already-bound install
`RehearsalSG` preparation and pins the exact helper source hashes; callers do
not provide an arbitrary reset CDB or uploader.

Focused tests use injected fakes only; there was no USB, MIDI, flash, power, or
reboot access. They check the single-reset ordering and consumed marker,
rejection of a mismatched completion hash, rejection of a bad last readback
page, and refusal of an old snapshot. The positive test is orchestration-level:
it does not establish physical SG_IO behavior, USB detach, native enumeration,
application boot, or audible output. Hardware/installability claims stay false.
