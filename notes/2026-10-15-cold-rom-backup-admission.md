# Cold-ROM paired-backup admission prototype

Status: offline implementation only. This branch adds a distinct cold-ROM
backup path for a later owner-observed Cynthion `USB_KEY` entry. It does not
claim that Cynthion gateware has run or that recovery was physically verified.
The current owner-reported state is power-interrupted, blank display, and no
USB enumeration; do not use any prior retained-loader/soft-key receipt for
this route. No device commands were run while implementing or testing it.

## Admission evidence

The campaign pins the new adapter, the unchanged fixed loader adapter, the
unchanged ROM reader, the exact audited RAM loader/profile and profile source,
the Cynthion firmware file, and a build-receipt file. The cold-entry JSON is
separate from the historical FM-1 identity flow. It must explicitly record:

- the exact uploaded firmware SHA-256 and build-receipt SHA-256, with a
  coordinator record that it uploaded that exact image;
- the owner's one USB_KEY operation, selection of the physical unit, and
  correlation of the subsequently enumerated ROM device to that selection;
- a literal status observation from owner-visible LEDs or the coordinator's
  read-only JTAG capture, without imposing a console, nonce, ACK, or `DONE`
  protocol or requiring an ABI parser;
- that the ROM USB port was absent before the operation, followed by exactly
  one fresh ROM candidate at the observed topology, VID/PID and devnum;
- timestamps for upload, owner key action, status observation, and ROM
  enumeration.

The ROM has no serial in this schema. The report therefore leaves
`unit_identity` and `usb_serial` null and calls the identity basis
`owner-attested-physical-selection`. It does not convert a user's observation
or a successful dump into proof that recovery works. The mapping is checked
again against the live USB/SG topology immediately before each bounded SG_IO
operation.

Campaign and entry evidence must be direct children of one private mode-0700
directory. The campaign names a new direct-child receipt. Entry age is bounded
to 120 seconds at admission/SG open; the entire active session is bounded to
600 monotonic seconds. A durable O_EXCL consumed marker is fsynced before SG
open, so a failed or ambiguous attempt cannot reuse the entry under another
receipt name. Each SG exchange has a durable intent first and a completion
record afterward. The unchanged request inventory is 8,757 operations: ROM
inquiry, 47 reviewed RAM-loader uploads, RAM jump, loader status/JEDEC checks,
and two complete 1 MiB reads in 256-byte pages. There are no erase, program,
reset, or boot requests in the inventory. Both durable dumps are reread by
hash and must match before a success manifest is written. The manifest keeps
write admission, physical recovery verification, and kernel exclusivity false.

The campaign JSON has exactly these top-level fields: `schema=1`,
`kind="fm1-cold-rom-backup-campaign"`, `adapter_sha256`,
`fixed_adapter_sha256`, `reader_sha256`, `loader_path`, `profile_path`,
`profile_source_path`, `entry_path`, `entry_sha256`, `dongle_firmware_path`,
`dongle_firmware_sha256`, `dongle_build_receipt_path`,
`dongle_build_receipt_sha256`, `usb_binding`, and `receipt_path`. All staged
source files are hash-pinned; the campaign file and entry file share the
private evidence directory. `usb_binding` is the exact current
`{path,busnum,devnum,vid,pid}` ROM mapping.

The entry JSON has exactly these top-level fields: `schema=1`,
`kind="fm1-cold-rom-entry"`, `source="cynthion-usb-key"`, `owner_attestation`,
`dongle_upload`, `attempt_started_at`, `uploaded_at`, `owner_key_action_at`,
`status_observed_at`, `status_observation`, `target_port`, `rom_enumeration`,
and `rom_usb`. `owner_attestation` contains true assertions
for `performed_usb_key_once`, `selected_physical_unit`,
`rom_device_is_selected_unit`, the literal identity basis
`owner-attested-physical-selection`, and `usb_serial=null`. `dongle_upload`
contains the exact firmware and build receipt hashes plus
`coordinator_uploaded_exact_image=true`. `status_observation={method,value}`
is separate from owner attestation; method is `owner-leds` or
`coordinator-read-jtag`. Its value is a bounded literal observation, not a
claim that an inferred register protocol or recovery ABI was verified.
`target_port={path,was_absent_before_attempt:true}`;
`rom_enumeration={observed_at,candidates:[<exact rom_usb mapping>]}` with one
candidate only; `rom_usb` must equal campaign `usb_binding`. The five event
timestamps are numeric Unix seconds and ordered attempt start, coordinator
upload, owner key action, status observation, then enumeration. The owner
attests only physical selection/key action; upload and JTAG observation are
attributed to the coordinator. These fields are records, not machine proof of
human assertions.

This prototype does not generate authentic owner evidence or obtain the
Cynthion build receipt; these artifacts must come from the actual build, a
coordinator-recorded exact-image upload, owner physical selection/key action,
status observation, and fresh enumeration. It does not replace review of the
actual gateware, USB_KEY electrical behavior, host SG exclusivity, or a recovery
test.

## Offline verification

Using `/tmp/lunar-installer-service-test-venv/bin/python`:

```text
pytest -q -p no:cacheprovider -o addopts='' tests/test_cold_rom_backup.py tests/test_fixed_loader_backup.py
75 passed
```

The new campaign tests inject a fake transport and synthetic pages; they do
not call sysfs, USB, SG_IO, Cynthion, or a device. They exercise admission
rejections, stale evidence, unique enumeration, one-use claim, expiry before
transport open, refusal to complete an unknown operation, and two equal full
synthetic images. The original fixed-loader unit tests pass unchanged. Python
bytecode compilation and `git diff --check` also pass. Rarefaction/Serena
reported the configured project root as `/Users/likwid/Developer/mvave-fm1-firmware`,
not this isolated worktree; semantic indexing was not treated as evidence.

## Next gates

1. Parent reviews the schema and exact unchanged inventory against the current
   Cynthion gateware and owner operation plan.
2. Parent obtains owner-controlled genuine build/upload/status and fresh USB
   enumeration evidence only after the USB_KEY source succeeds; synthetic test
   fixtures cannot satisfy this gate.
3. Before any live backup, prepare and independently review a campaign that
   pins those actual files and the current ROM topology. Run once on Linux; keep
   resulting private full-flash dumps out of Git.
4. Independently inspect the durable event log and manifest. This backup path
   grants no installation, write, reset, or boot permission.

Current source pins: `tools/fm1_cold_rom_backup.py` SHA-256
`6f1928732159232c3c923bb133a6fcca350e9d3738bd5ad41bde84984e2219c5`;
`tools/fm1_fixed_loader_backup.py`
`79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb`;
`tools/fm1_uboot_read.py`
`28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57`.
The campaign must use this cold-adapter hash and these exact unchanged
dependency pins.
