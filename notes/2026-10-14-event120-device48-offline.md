# Device 48 Event120 read and repeat-boot adapter

[verified] This change is based on `6360dd57262eb3b4bdbcf4f0a202f15aab573938` and adds separate device-48 source, campaign, manifest, marker, and tests. The adapter is bound to USB path `1-1`, bus `1`, device `48`, VID:PID `4c4a:8057`. It accepts only the pinned installed target digest `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`.

[verified] The device-46 implementation was the closest template. It is deliberately enumeration-specific rather than a generic parameterized transport. I carried forward its fixed-loader/source pins, 8,757-command inventory, two complete matching 1 MiB reads, exact source-hash chain into the boot adapter, fresh post-read USB/SG snapshot, same-connection/no-later-command assertion, 10-second descriptor lifetime, and one-use reset marker. I gave device 48 its own namespaces and corrected inherited error/event names; the dependent read-adapter SHA is recalculated and pinned in the boot adapter. No device-46 receipt can satisfy the device-48 kind/binding/source checks.

[verified] The boot action remains one FC0C arg1 request using the unchanged CDB. It does not retry if completion is incomplete or ambiguous, and records boot and physical recovery as unobserved. This is testable offline only; no bench read or boot command was performed.

[verified] Files added:
- `tools/fm1_event120_device48_rom_backup.py` SHA-256 `94ce92b5f787b2e511206f6aae7fe4a2cc5046ca934f2dd27e7a3edee7ae47c3`
- `tools/native/event120_device48_repeat_boot.py` SHA-256 `5da21b7e297019a0cc5be2f7eaecb02f50d59e574b1be8ef20dbed9fa0d78f31`
- `tests/test_event120_device48_repeat_read.py`
- `tests/test_event120_device48_repeat_boot.py`

[verified] Focused validation passed: Python bytecode compilation and 25 pytest cases. Coverage includes wrong enumeration IDs 42/44/45/46/47, truncated or changed dumps, consumed read marker reuse, source and receipt verification, stale or changed connection mapping before SG open, one-shot completion and ambiguous-status no-retry. The exact test log is outside Git at `/home/claude/.local/share/codex-coordination/receipts/lunar-event120-device48-offline/pytest.log`, SHA-256 `ff7e5bd826b942aa2f99bd2eaeeaf35ec86e3ced3bc00018b9d14ea2b22001d4`. Run used the pinned network-none container `lunar-preload-tests@sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`, 1 CPU, 2 GiB memory/swap, 256 pids, `docker-batch.slice`, with the read-only pytest dependency mount.

## Staged invocation for coordinator review

[verified] These are schemas required by the adapters, not a command to run on the bench. First prepare a fresh, private 0700 evidence directory and obtain a new passive device48 snapshot through the coordinator's reviewed inventory process. The read snapshot fields are exactly `schema=1`, `kind=fm1-passive-device48-rom`, current `observed_at`, USB binding `{path:1-1,busnum:1,devnum:48,vid:4c4a,pid:8057}`, and the current `sg_binding`. Create `read-campaign.json` in that same private directory with exactly: `schema`, `kind=fm1-device48-event120-repeat-rom-read`, `adapter_sha256` (SHA-256 of the committed read-adapter file), snapshot path/hash, fixed loader path, pinned loader profile path, pinned profile-source path, exact USB binding, and a new read receipt path. Run the read adapter's `--preflight` first; it must report 8,757 commands and zero flash/reset operations. Only then, under the coordinator's hardware procedure, run it once. It must produce two full reads matching the pinned digest.

[verified] A boot campaign cannot be prepared from a read alone. Immediately after the completed read, the coordinator must capture a fresh passive boot snapshot on that same live connection with kind `fm1-passive-device48-boot-same-connection`; preserve the exact USB and SG mapping and attest that no later commands occurred. The boot campaign fields are exactly `schema=1`, `kind=fm1-device48-event120-repeat-boot`, boot-adapter source hash, read manifest path/hash, read transcript hash, fresh boot snapshot path/hash/time, USB and SG bindings, `active_session_state=same-device48-rom-connection-after-matching-read-no-later-commands`, `no_later_commands_attested=true`, and a new boot receipt path under the same evidence root. Review the boot adapter `--preflight` output before a single authorized `run`; after any ambiguous result, do not retry. Fresh live identity and the coordinator's separate authorization remain required.

[reported] The coordinator's passive inventory identified bus 1/device 48 at USB path 1-1 with VID:PID 4c4a:8057. This worker did not independently observe it.

[verified] Tests and hashes validate the offline adapter contract only. They do not establish a current device identity, matching read, boot, install history, recovery path, application behavior, or hardware acceptance. No USB, MIDI, flash, reset, power, or reboot operation was performed.
