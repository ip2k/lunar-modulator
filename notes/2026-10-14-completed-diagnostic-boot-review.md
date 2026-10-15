# Completed diagnostic boot adapter review — 2026-10-14

Reviewed sibling adapter commit `0588e8bde59396c3cdfff80e1bb33ae9a516582d` (`tools/native/generic_diagnostic_boot.py`, `tests/test_generic_diagnostic_boot.py`) against its actual imported interfaces and fixed source dependencies. The original `7c9ec525` draft had runtime mismatches (policy wrapper field, binding return type, reset helper module argument, SG header type, durable-log closed state, and snapshot clock sampling). All six are corrected in `0588e8b`:

- `DiagnosticSession._policy._policy` identifies the factory policy; `_capture_binding()` is consumed as a dict.
- The adapter passes the imported `event120_reset` module to `event120_generic_boot.session_class`, carries the already-bound SG `header_type`, and verifies `DurableLog.fd is None` after the wrapped transport closes.
- It samples wall time after `snapshot_provider()` writes its observation, avoiding rejection of a just-created snapshot as future-dated.
- Tests now instantiate the real `DiagnosticSession`, `_LoggedTransport`/`DurableLog`, generic boot session class, and completion-first reset implementation; only `Policy.check_files`, transaction `session.run()`, and OS SG open/flock/ioctl are faked.

The adapter review is clear for this offline boundary. It owns the single install `session.run()`, verifies the completed journal/result and closed transcript, replays the exact allowed SG operations and final 1 MiB target readback, requires a post-completion ≤120-second same USB/SG passive snapshot, writes/fsyncs a one-use marker before constructing the reset session, and issues one FC0C argument-1 request through the already bound connection. There is no ROM loader upload. Its result keeps reset/core-reset/boot observations false; a successful request is not proof of USB re-enumeration, app start, audio, or recovery.

Focused verification on Hera at exact source commit `0588e8bde59396c3cdfff80e1bb33ae9a516582d`:

```text
PYTHONPATH=tools:tools/native /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_generic_diagnostic_boot.py
5 passed
```

`git diff --check HEAD^ HEAD` passed. No USB, MIDI, flash, power, or reboot commands were issued. The test does not run a genuine completed flash transaction: `session.run()` and `Policy.check_files()` are stubbed, while the actual interface classes and reset path are exercised with a fake SG endpoint/ioctl. No physical installation or boot acceptance is implied.

## Private orchestrator integration finding

Read-only inspection of `scratch/trio55-cycle/run-cycle.py` and `capture-stimuli.py` found a remaining sequencing hazard outside the reviewed adapter. The launcher starts valid WAV capture before boot, as required, but `start_capture()` currently writes `boot-about-to-submit.json` before the adapter takes its post-install snapshot, persists the boot campaign, opens the existing SG session, and submits FC0C. The helper begins a 15-second stimulus epoch as soon as it sees that marker. If any later preflight step fails, it may send physical MIDI while the device remains in its loader. Use a distinct durable completion/submit gate for stimuli; keep WAV recording pre-boot. The adapter callback currently precedes snapshot/preflight, so the marker must not be interpreted as proof the reset was sent or completed.

The earlier capture reliability findings were corrected in the current private script copies: helper checks `arecord` liveness and RIFF/WAVE growth, records a ready PID, cleans up the recorder in `finally`, and limits USB MIDI discovery to a unique Lunar ALSA card whose sysfs ancestry matches physical USB `1-1`; launcher terminates its helper process group if startup readiness fails. These private scripts were inspected only and not executed.
