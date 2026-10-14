# Device-44 Event120 read and one-boot adapters

Date: 2026-10-14
Branch: `codex/2026-10-14-device44-event120-repeat`
Base: `845bfd5df92a43ca3f765419a49622c9293612f4`

[verified] Added device-44-specific read and one-boot adapters based on the reviewed device-42 flow. The enumeration binding is USB path `1-1`, bus 1, device 44, VID:PID `4c4a:8057`. This is a USB enumeration number, not a firmware identity. The adapter still requires the same exact current full-flash SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`, the pinned fixed loader/profile/source, and the existing 8,757-operation read inventory SHA-256 `f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017`. Shared source pins were not changed.

[verified] Read campaign schema remains version 1 with exact keys: `schema`, `kind`, `adapter_sha256`, `snapshot_path`, `snapshot_sha256`, `loader_path`, `profile_path`, `profile_source_path`, `usb_binding`, and `receipt_path`. It requires a fresh passive device-44 snapshot, exact USB and SG mapping, dual complete 1 MiB reads matching the pinned SHA, and a new receipt under a private mode-0700 evidence directory. A one-use marker is tied to the device-44 enumeration and SG binding. The read path reports zero flash and reset operations.

[verified] The one-boot campaign remains bound to the completed read receipt, its manifest and command transcript hashes, the same fresh device-44 USB/SG snapshot, and an explicit no-later-commands attestation. The reset request remains a single existing FC0C operation with no retry. Its result describes request completion only; `boot_observed`, installation history, physical recovery, and flash-write claims remain false. A consumed read authorization cannot be reused.

[verified] Focused tests cover exact device-44 bindings and current-image hash, refusal of snapshots for other device numbers (including device 42), read completeness/hash failure and enumeration-bound consumed marker, boot request at-most-once behavior, malformed campaign refusal before SG open, changed live mapping refusal, read-source resolution, and refusal of reused boot authorization. Device-42 receipts are not referenced or accepted by these adapters.

[verified] This work is adapter/test preparation only. No USB, MIDI, flash, reset, power, or reboot command ran. No device-44 passive snapshot, read receipt, or boot campaign was generated. The coordinator owns any later physical run and must create fresh evidence for this enumeration; no test boot timing or result is assumed.

[verified] The focused suite passes 18 tests in the pinned `lunar-preload-tests:20261014` image (image ID `sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`). The image lacks pytest itself, so pytest 9.1.1 packages were mounted read-only from `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/lib/python3.12/site-packages`. The container ran with 2 CPUs, 3 GiB memory and swap, 256 pids, no network, and `docker-batch.slice`; the checkout was read-only. Exact command:

```sh
docker run --rm --cpus=2 --memory=3g --memory-swap=3g --pids-limit=256 --network none --cgroup-parent=docker-batch.slice --label codex.task=lunar-event120-device44-repeat --tmpfs /tmp:rw,exec,size=3g -v "$p:/work:ro" -v /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/lib/python3.12/site-packages:/pytest-deps:ro -e PYTHONPATH=/pytest-deps -w /work lunar-preload-tests:20261014 /usr/bin/python3 -m pytest -p no:cacheprovider -q tests/test_event120_device44_repeat_boot.py tests/test_event120_device44_repeat_read.py
```

Coordinator campaign construction must use the constants from the new adapter modules, not a device-42 receipt. Read campaign `kind` is `fm1-device44-event120-repeat-rom-read`; boot campaign `kind` is `fm1-device44-event120-repeat-boot`. The read's passive snapshot and boot's fresh same-connection snapshot must each carry the exact device-44 USB binding and fresh SG mapping. The boot campaign must name the new read manifest and `commands.jsonl` SHA-256, attest `same-device44-rom-connection-after-matching-read-no-later-commands` and set `no_later_commands_attested: true`. The read bundle and boot receipt must live under the coordinator's private mode-0700 evidence root. The adapter's `--preflight` mode performs no hardware operation; the normal CLI is intentionally not exercised here.
