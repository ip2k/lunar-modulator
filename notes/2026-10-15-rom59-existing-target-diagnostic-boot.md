# ROM59 existing-target diagnostic boot path — 2026-10-15

This note identifies the existing no-write boot path for the private diagnostic
target `222164721a323bce80a3fd3a0444588c93ef734e577940ddb80b7432402d1ab6`.
It is source/test review only. No ROM read, USB command, reset, flash operation,
or device access was performed here.

## Finding

[verified] `tools/native/event120_generic_boot.py` already provides the bounded
fresh-ROM-read → single-reset flow. It is independent of
`generic_diagnostic_flash.py` and does not require an install transaction.
Use this existing path; do not fabricate an install journal or route through
`generic_diagnostic_boot.run_completed()`.

[verified] `verify_read_bundle()` requires the exact generic ROM read schema,
the pinned reader adapter/source/loader/profile/inventory, 8,757 transcript
commands, two complete identical 1 MiB dumps, and an externally supplied
`expected_current_flash_sha256`. It verifies that both dump hashes equal that
expected SHA and that `flash_operations == 0`, `reset_operations == 0`, and
`install_history_proven == false` (`tools/native/event120_generic_boot.py`,
`verify_read_bundle`). For the candidate, the caller should supply the exact
candidate SHA above as the expected current flash SHA; this proves only that
the freshly read image bytes match the candidate.

[verified] The boot campaign binds the completed read manifest, command log,
read campaign, expected current image SHA, exact ROM USB binding, and a second
passive snapshot taken after read completion. `prepare()` requires the second
snapshot to be fresh, same USB/SG mapping, same physical USB port and the
explicit expected devnum; it also checks the running SG mapping and rejects an
already consumed marker. The read marker and reset marker are distinct.

[verified] `run()` writes a durable one-use marker and sends exactly one
`FC0C` argument-1 reset request through the existing completion-first reset
session. The log marks `flash_operations: 0`, `upload_operations: 0`,
`install_history_proven: false`, `boot_observed: false`, and `retry: false`.
An ambiguous completion is terminal; it must not be retried. The return value
does not prove reset causation, application boot, audible output, or recovery.

## Exact preparation inputs

The read adapter must first produce its normal private evidence bundle:

- `read-campaign.json` and its externally recorded SHA-256;
- `read/manifest.json` and SHA-256;
- `read/commands.jsonl` and SHA-256;
- `dumpA.bin` and `dumpB.bin`, both exactly 1 MiB and matching the candidate
  SHA; and
- the fresh passive ROM snapshot and one-use read marker produced by that
  adapter.

After the read has completed, obtain the generic boot adapter's passive
same-connection snapshot and create a schema-1 campaign with exactly these
fields: `schema`, `kind`, `adapter_sha256`, `read_manifest_path`,
`read_manifest_sha256`, `read_commands_sha256`, `read_campaign_sha256`,
`snapshot_path`, `snapshot_sha256`, `snapshot_observed_at`, `usb_binding`,
`sg_binding`, `active_session_state`, `receipt_path`, and
`expected_current_flash_sha256`. Set `kind` to
`fm1-event120-generic-rom-boot`, `active_session_state` to
`same-rom-connection-after-matching-read`, and use one exact current ROM
devnum for both read verification and CLI `--expected-devnum`. The campaign
and read evidence must share their private evidence root; `receipt_path` must
be a new path directly under that root. The campaign digest is an external
CLI pin, not a value copied from a prior ROM session.

Run the existing adapter's no-operation check first:

```sh
python3 tools/native/event120_generic_boot.py \
  --campaign /absolute/private/path/boot-campaign.json \
  --campaign-sha256 <sha256-of-exact-campaign-bytes> \
  --expected-devnum <fresh-current-devnum> --preflight
```

Only after independent review of that exact prepared bundle should the
coordinator consider invoking the same command without `--preflight`. The
preflight reports `hardware_operations: 0`; it does not consume the reset
marker. A live invocation is a separate one-shot physical operation and remains
outside this review.

## Checks and limits

[verified] `tests/test_event120_generic_boot.py` includes a synthetic complete
read transcript/bundle test, campaign-to-read binding, SG substitution refusal,
exact one-ioctl FC0C success, and ambiguous-status no-retry refusal. These are
mock-only tests, not proof of ROM59 live evidence or successful boot.

[inferred] The remaining immediate dependency is coordinator-side creation and
review of a fresh ROM59 read bundle whose two full-image hashes equal the
candidate SHA, followed by a fresh passive same-connection snapshot and exact
campaign pin. If ROM59 bytes differ from the candidate, this path correctly
refuses; the install path is then a different operation requiring its own
fresh installation admission.


## Completed capture and ROM61 return

[verified] The detached capture completed normally: arecord and telemetry
exited0; the110-second usbmon timeout exited124 as expected. All100 telemetry
frames were valid, covering uptime1006–100963ms. The initial84 underruns never
increased during those samples; render maximum27768ticks (1157us), draw
maximum154548ticks (6439.5us), minimum sampled user/system stack margins
15064/7724bytes. USB messages, UART bytes, accepted note-ons and rejected
messages remained0. Physical1-1 subsequently enumerated as4c4a:8057 device61,
without another reset request or owner power cycle. The consumed ROM59
campaign must not be retried.

[verified] The filtered exact-device bulk-OUT usbmon file is empty; stderr
is empty. It does not prove absence of all bus traffic, physical capture
completeness, or firmware receipt. The helper logged successful aseqsend
exits for six scheduled notes. A later passive full-bus sample checked the
text field spacing only; it did not cover those earlier stimuli.

[verified] Private bench WAV SHA256:
`78a1f3b9ebee3e3577384654c386e396d921afa579d85a866bc2adb4ab2bc8b6`.
Coordinator private copied telemetry JSONL:
`e356ddf636581021617cccb16a96f6924cd754f4ef3a4be55fc79b771ef87246`;
helper log:
`92e6bd8b1ca8b8fba7d2ff9e13a8f7891816a707d8a1e66e169665dc551cc69a`.
No waveform/listening acceptance is claimed for this run.

[inferred] Host-side ALSA subscription is the next discriminating hypothesis.
Upstream aseqsend1.2.14 addresses events directly without connecting a port;
the Linux raw-MIDI sequencer bridge opens its hardware output in the port-use
callback. Software Midi Through loopback does not establish that this hardware
output was opened. Actual bench kernel is6.18.34+rpt-rpi-2712; upstream-source
inspection is not proof of its exact compiled behavior. Prepare a bounded,
explicitly subscribed mido output, verify host OUT callbacks alongside device
counters, then assess analogue response before changing firmware receive code.

SAVE remains disarmed; full-song, independent recovery, storage ownership,
installer and release acceptance remain open.
