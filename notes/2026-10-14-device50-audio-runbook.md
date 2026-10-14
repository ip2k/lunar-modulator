# Device 50 Event120 audio runbook (coordinator review)

Date: 2026-10-14
Scope: runbook only, derived from the checked device-50 adapters and retained
K6 capture procedure. This note is not authorization to perform the sequence.
The Mac coordinator exclusively owns bench/device operations.

## Current evidence and preconditions

The offline adapters are on `codex/2026-10-14-event120-device50-offline`
at `acbda8b84fdd2e1ace04f50f29b199a0836c63ff`. The read adapter is
`tools/fm1_event120_device50_rom_backup.py` (SHA-256
`65f76ce56cffac284c16a2a003067b1db40456f9d57d580bbfb4d61ed8943c87`);
the boot adapter is `tools/native/event120_device50_repeat_boot.py`
(SHA-256 `4fdb13c6c69370b2ad3a6397f648370dbe24b88599ff471ecc3e404d54baa589`).
Read adapter hash before execution; any source change invalidates these pins.

The coordinator reports a fresh device-50 read campaign at
`/home/claude/fm1-device50-audio-20261014/read-campaign.json`, raw SHA-256
`ee708999caa9fddec689893aa15db57736f3ce577bfeb043f9cdd35ee780884a`,
and says the 8,757-command dual read has started. Treat this as coordinator
reported live state, not independently checked here. Continue only after the
coordinator confirms success and verifies its manifest, transcript, both
1 MiB dumps, and identical target SHA
`145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657).
A completed backup proves current flash bytes match that digest; it does not
prove installation history, successful firmware boot, audio quality, or
recovery.

Before any reset attempt, the coordinator must capture a *new* passive snapshot
on the still-connected ROM enumeration after the read completes. It must retain
USB binding exactly
`{"path":"1-1","busnum":"1","devnum":"50","vid":"4c4a","pid":"8057"}`
and the exact live SG mapping from `discover_sg`: `node`, `class`,
`device`, `usb`, `node_identity`, `class_identity`, `device_identity`,
and `usb_identity`. The mapping is compared canonically at preflight and
again before opening/using SG. Do not copy device 48 values. Do not infer a
connection from a repeated devnum; use the fresh observed USB/SG identities.
Both snapshots use schema 1 and finite Unix `observed_at` seconds. The read
snapshot kind is `fm1-passive-device50-rom`; the later boot snapshot kind is
`fm1-passive-device50-boot-same-connection`. Each snapshot also contains
`usb_binding` and `sg_binding`, with no extra keys. The boot snapshot must
be fresh (within 120 seconds), later than completed read, and exactly match
the read manifest SG mapping.

## Read campaign contract

The read campaign is a direct mode-0700 evidence-root member named
`read-campaign.json`; its snapshot, campaign, and read receipt share that
root. Its exact schema-1 keys are:

```json
{
  "schema": 1,
  "kind": "fm1-device50-event120-repeat-rom-read",
  "adapter_sha256": "65f76ce56cffac284c16a2a003067b1db40456f9d57d580bbfb4d61ed8943c87",
  "snapshot_path": "<absolute path in this private evidence root>",
  "snapshot_sha256": "<raw SHA-256 of snapshot.json>",
  "loader_path": "<absolute pinned fixed-loader file>",
  "profile_path": "<absolute pinned loader profile>",
  "profile_source_path": "<absolute pinned profile source>",
  "usb_binding": {
    "path": "1-1",
    "busnum": "1",
    "devnum": "50",
    "vid": "4c4a",
    "pid": "8057"
  },
  "receipt_path": "<new absolute read-receipt directory in this root>"
}
```

The actual loader/profile paths are fixed campaign inputs already staged by the
coordinator. Do not substitute guessed paths or regenerate the campaign after
the run starts. Read preflight is non-invasive; the normal run is the dual
read and consumes an enumeration-specific marker. Once run has started, any
failure is terminal for that campaign. Do not retry it or reuse its marker.

Review command, from the exact checked-out source tree:

```sh
python3 tools/fm1_event120_device50_rom_backup.py --campaign /home/claude/fm1-device50-audio-20261014/read-campaign.json --preflight
python3 tools/fm1_event120_device50_rom_backup.py --campaign /home/claude/fm1-device50-audio-20261014/read-campaign.json
```

The second line is shown for coordinator review only; it performs the real
8,757-command read and was not run by this task. Do not proceed unless the
result manifest and replay checks accept both full dumps, zero write/erase/
reset operations, and the expected current-image hash.

## Boot campaign contract and sequence

After successful read verification, make the fresh boot snapshot and freeze its
raw hash, timestamp, and SG mapping. The boot campaign is a direct member of
the same private evidence root as `read-campaign.json` and its read receipt.
It has exactly these keys:

```json
{
  "schema": 1,
  "kind": "fm1-device50-event120-repeat-boot",
  "adapter_sha256": "4fdb13c6c69370b2ad3a6397f648370dbe24b88599ff471ecc3e404d54baa589",
  "read_manifest_path": "<absolute path to completed read manifest>",
  "read_manifest_sha256": "<raw SHA-256 of read manifest>",
  "read_commands_sha256": "<raw SHA-256 of completed read commands.jsonl>",
  "snapshot_path": "<absolute path to fresh boot snapshot.json>",
  "snapshot_sha256": "<raw SHA-256 of boot snapshot>",
  "snapshot_observed_at": 0,
  "usb_binding": {
    "path": "1-1",
    "busnum": "1",
    "devnum": "50",
    "vid": "4c4a",
    "pid": "8057"
  },
  "sg_binding": {
    "node": "<observed /dev/sgN>",
    "class": "<resolved /sys/class/scsi_generic/sgN path>",
    "device": "<resolved SCSI device path>",
    "usb": "<resolved /sys USB device path>",
    "node_identity": [0, 0, 0],
    "class_identity": [0, 0, 0],
    "device_identity": [0, 0, 0],
    "usb_identity": [0, 0, 0]
  },
  "active_session_state": "same-device50-rom-connection-after-matching-read-no-later-commands",
  "no_later_commands_attested": true,
  "receipt_path": "<new absolute boot-receipt directory in the same root>"
}
```

Replace every placeholder from the retained completed read and fresh passive
snapshot. `snapshot_observed_at` is the exact numeric timestamp from that
snapshot, not zero. The coordinator's `no_later_commands_attested` statement
must be true only after confirming no intervening commands. Run `--preflight`
and review its zero-operation result before capture. If identity, receipt,
source pin, freshness, chronology, or preflight differs, stop and do not invoke
the normal adapter.

First perform the no-operation preflight and require success:

```sh
python3 tools/native/event120_device50_repeat_boot.py --campaign /home/claude/fm1-device50-audio-20261014/boot-campaign.json --preflight
```

The analogue capture procedure is grounded in
`notes/2026-10-14-komplete-audio-capture.md`: K6/device 0, six interleaved
S32_LE channels, 48 kHz; preserve the original six-channel WAV and log. The FM-1
is connected to K6 inputs 3/4, zero-based channels 2/3. Start capture before
the one reset request so it includes startup:

```sh
umask 077
arecord -D hw:CARD=K6,DEV=0 -f S32_LE -r 48000 -c 6 -d 150 -t wav /home/claude/fm1-device50-audio-20261014/event120-device50.wav 2>/home/claude/fm1-device50-audio-20261014/arecord.stderr &
ARECORD_PID=$!
date -u +%Y-%m-%dT%H:%M:%S.%N%z
```

Run boot preflight first, with no recording or device command. Only if it passes
while the same ROM connection remains present, start capture; then issue exactly
one normal adapter invocation:

```sh
date -u +%Y-%m-%dT%H:%M:%S.%N%z
python3 tools/native/event120_device50_repeat_boot.py --campaign /home/claude/fm1-device50-audio-20261014/boot-campaign.json
```

The reset request is the adapter's fixed FC0C argument-1 command; do not hand
craft another CDB. Immediately treat any thrown/ambiguous completion as
consumed. Never rerun the campaign, issue another reset, or use the prior
read snapshot to retry. Save stdout/stderr and the receipt transcript.

If the coordinator observes the native MIDI port after the request, record
that as enumeration only and bind the observed port for the short audition.
Keep the capture running. Use one bounded note-on followed by its matching
note-off (standard channel-1 note 60, velocity 80: `90 3C 50`, then
`80 3C 00`), with UTC timestamps in the operator log. Do not send PLAY,
transport-start, program-change, or additional notes in this run. Stop after
the note-off; do not infer song playback from the audition. The MIDI port name
and detection command are live coordinator observations and must not be
invented in this template. If no native port appears, do not send MIDI. Track
USB return passively; an appearance of ROM 4c4a:8057 is a separate observation,
not proof that the app booted or that recovery works. A 150-second recording
may end before a delayed return; if so, stop it cleanly and preserve the exact
end reason/time rather than extending or repeating the boot.

## Failure and evidence handling

- A failed read, changed USB/SG identity, mismatched dump, stale snapshot,
  nonzero/ambiguous SG completion, recorder overrun, MIDI-port ambiguity, or
  missing note-off ends the attempt. Preserve evidence and errors; no automatic
  retry or alternate command.
- For a started read/boot campaign, preserve its marker and evidence root as
  consumed. Do not delete or rename markers to make it reusable.
- On recorder completion, wait for the bounded process to exit; if still active,
  terminate only that recorder process and record its exit/status. Do not stop
  unrelated audio services or touch USB ownership.
- Keep WAV, raw dumps, logs, manifests, snapshots, markers and campaign data
  private under the coordinator's mode-0700 evidence root; do not commit or
  publish them.
- Report separately: dual-read hash match; reset ioctl status/completion;
  native USB enumeration; MIDI-note response; owner listening/performance;
  passive return. None implies another.
- Preserve the existing reset adapter's false `boot_observed`,
  `physical_recovery_verified`, and `install_history_proven` fields unless a
  new independently reviewed evidence path establishes them.

The current private device-48 evidence directory is not present in this Hera
worktree. This runbook therefore depends on the coordinator supplying the
device-50 private read manifest, its raw transcript/hash and dumps, then
creating the fresh boot snapshot/campaign after successful read. No bench,
USB, SG, MIDI, reset, flash, power, or reboot command was issued while writing
this note.
