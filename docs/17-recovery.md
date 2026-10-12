# FM-1 recovery runbook

This runbook separates routes observed on the owner's FM-1_092, the fixed
physical scratch-sector procedure, the exact SDK diagnostic install/restore
procedure, and a synthetic failure model. The diagnostic's 30 changed sectors
have been installed and restored with complete readback verification. Diagnostic
execution is supported conditionally by a retained RAM record; visible display,
recovery after diagnostic execution, and physical interrupted-write recovery
remain separate acceptance gates. Model success does not prove mask-ROM entry,
CPU reset, USB_KEY timing, or firmware boot on hardware.

## Proven hardware facts and current boundary

[verified: owner FM-1_092, 2026-10-07] The normal FM-1 application accepted
the single soft key `F0 22 24 35 7D F7` and enumerated as JieLi mask-ROM UBOOT
(`4C4A:8057`, `WL80UBOOT1.00`). A pinned 24,064-byte WL82 loader was uploaded
to RAM. The existing reader took two identical 1 MiB full-flash dumps. The
bounded test programmed only `[0xD8000,0xD9000)`, read the pattern back, erased
that one 4 KiB sector to its original all-`FF` value, and read the full flash
again. The final hash matched the pre-test backups; the owner later power
cycled and confirmed a normal boot. See [the bench note](../notes/2026-10-07-fm1-softkey-bench.md).

That historical test proves entry from a running FM-1_092 app, full-flash reads
and restoration of that fixed scratch sector. It does not prove a full-image
rewrite, recovery from a corrupt app or SPL, or recovery of another unit.
The original scratch adapter still permits only its fixed address and pattern;
the separate diagnostic adapter below has its own exact-image authorization.

The owner has authorized continued software and simulated recovery work without
requiring the FM-1 to be returned to normal mode first. The unit may remain in
UBOOT until a later manual power cycle. This supersedes the historical
away-from-bench restriction in the earlier runbook draft; it does not authorize
an arbitrary physical write. Do not assume a software reboot or VBUS switch
electrically resets this battery-powered device.

[verified: 2026-10-11 single RAM-only probe] After fresh FM-1_092 identity and
soft-key entry, two exact RAM uploads succeeded. One jump caused immediate
USB disconnection and a new UBOOT enumeration on the same port. No flash
command was sent or found in the capture. This does not establish P33 execution,
application-origin reset, unchanged flash, or recovery from a damaged app.
Linux sent ordinary storage probes during that observation. The later minimal
reset attempt below returned the unit to its installed application.
See [the bounded result](../notes/2026-10-11-fm1-ram-probe.md).

[verified: exact loader disassembly] The pinned WL82 LoaderV2's `FC0C` with
argument 1 requests a core soft reset. It is not a documented command of bare
mask-ROM UBOOT. Its default handler does not clear the stock recovery mailbox,
so this is not proof that a normal boot or USB reconnection will follow.
Loader startup itself can parse configuration left in RAM beyond the uploaded
image and set the NOR quad-enable status bit. Loading a RAM image therefore
does not by itself establish absence of flash effects. The fixed reset guard
was initially restricted to simulated bindings until the retained-configuration
startup path was reviewed. The later fixed-loader configuration and reset
adapters are separately bound to actual private backup/install evidence; see
the diagnostic procedure below. A separate 14-byte reset stub and its fixed
three-command guard
pass offline native build, static review and 170 combined Hera checks. Its
separately reviewed private physical adapter has since been attempted once.
The stub leaves the recovery marker untouched. See
[the command and initialization audit](../notes/2026-10-11-loader-run-app-reset.md)
and [the minimal-stub investigation](../notes/2026-10-11-rom-core-reset-stub.md).

[verified: owner's FM-1_092, 2026-10-11] One fixed INQUIRY/upload/jump attempt
with that 14-byte stub returned the normal `4c4a:c755` interface about 1.5
seconds after jump. A subsequent read-only query confirmed a responsive
FM-1_092 app using its exact known checksum-bug reply. No owner power cycle
was needed. Jump itself lost its reply; the adapter stopped without retry.
This is an observed exit from that UBOOT session, with no independent CPU-reset
witness or general broken-app recovery proof. No flash command was sent and
no flash reread was made. The consumed private adapter cannot be reused for
a different enumeration. See [the actual bench receipt](../notes/2026-10-11-fm1-core-reset-bench.md).

[verified: owner's FM-1_092, 2026-10-11] A separately reviewed fixed-loader
rehearsal installed the exact diagnostic target, verified all 1 MiB, restored
the exact stock baseline, and verified all 1 MiB again. Each direction changed
30 authorized sectors and committed directory sector `0x4000` last. A distinct
one-shot loader reset lost its SG completion during detach; a new normal USB
enumeration and the exact `FM-1_092` identity response then verified restored
stock operation without a physical power cycle. No successful reset reply or
diagnostic application boot is inferred from that result. After new matching
dual backups, a separate install-only campaign again verified the complete
diagnostic target. One later target reset was transmitted and lost its reply on
detach; the same port returned to ROM about 22 seconds later. The immediate
stage chooser stopped before reading RAM because its capture guard rejected
one SCSI media-lock command. That return alone does not establish diagnostic
execution or recovery. A distinct reviewed successor later completed exactly
INQUIRY36 and FD07 IN32, returning coherent stage6/result0/elapsed20000/heartbeat1976
and the native write pointer. Independent review accepts conditional diagnostic
execution evidence. Stage6 precedes the P33 lock; the record does not prove
visible pixels, RAM-retention semantics or recovery cause. Preserve the original
snapshot, reset capture and every consumed marker. Before any loader upload,
a distinct recovery adapter must admit this completed read lineage and take
fresh matching full target backups. The retained record would be overwritten
by the fixed loader upload. See
[the first RAM read](../notes/2026-10-11-diagnostic-first-ram-read.md),
[the rehearsal](../notes/2026-10-11-sdk-rehearsal.md) and
[the current boot trial](../notes/2026-10-11-diagnostic-boot-trial.md).

## Triage hierarchy

| Observed condition | Route | Limit |
| --- | --- | --- |
| App boots and stock update service runs | Install a known-good package through the stock update path. Preserve stock `uboot.boot`, `ota.bin`, `cfg`, `isd_config.ini`, and partition layout. | Requires a running app and its update service; cannot rescue a non-booting app. |
| App runs and accepts the vetted soft key | Send the exact `7D` soft key once, observe ROM enumeration, then use the reviewed fixed-loader backup path. Any write needs its separate exact-image campaign and matching dual backups. | Entry and exact diagnostic install/stock restore are proven on the owner's FM-1_092. `7F` is a different update command. |
| UBOOT session needs to return to the installed app | A separately reviewed exact 14-byte RAM reset stub returned this owner's session to normal USB and a responsive FM-1_092 app once. | Bare-UBOOT reset opcode is unverified; do not replay a consumed adapter or assume every warm reset reconnects. Retain a real power-cycle fallback. |
| App hangs or is corrupted | First observe whether the device enumerates normally. If the app is unusable, a USB_KEY-at-power-up route is a candidate; use only after its hardware procedure is independently reviewed and observed. Capture the ROM enumeration before loading the audited loader. | The USB_KEY dongle is simulated, not tried on the owner's FM-1. A ROM failed-boot route and successful entry from a broken app are not physically proven. The app soft key cannot help if the app does not run. |
| SPL, protected boot metadata, or arbitrary flash contents damaged | If mask ROM still enumerates, preserve the actual image and transaction evidence; recovery needs an exact owner-matched baseline and a separately reviewed bounded writer. | The exact diagnostic's application-sector restore is verified; arbitrary full-flash/SPL recovery is unproven. Never overwrite the SPL or protected metadata as an experiment. |
| ROM does not enumerate, or SoC, power, USB, or flash hardware failed | Diagnose the electrical path and component. Consider an external programmer only after identifying the actual flash device and interface. | Software cannot repair a failed ROM, SoC, power path, or inaccessible flash. Do not infer the flash is discrete from a photo. |

An interrupted stock update transfer is different from a bad installed app.
Reports of transfer resumption while the updater loader remains available do
not establish recovery of an app that cannot boot. See [docs/07](07-recovery-and-risk.md)
and [docs/03](03-update-protocol.md).

## Fixed physical scratch-sector transaction

The durable transaction engine (`tools/fm1_flash_transaction.py`) is
transport-independent. It stores two identical full backups, a full target,
an immutable plan, and an atomically replaced journal with its own SHA-256
record checksum. New private directories and their parent entries are synced
before mutation. It validates artifact hashes and exact unit/flash geometry,
reads the whole actual flash before mutation, rejects changes outside the
authorized ranges, records durable intent before each erase/program, verifies
each sector, and verifies the complete final image. It does not trust a saved
page cursor. A failed or interrupted operation leaves recovery intent for a
fresh session; it never sends cleanup on a possibly stale handle.

The physical adapter in `tools/fm1_uboot_restore_test.py` accepts only the
fixed scratch sector `[0xD8000,0xD9000)` and its exact pattern. It does not
expose the wider simulated writer. For a new scratch proof, the preconditions
are two matching, complete owner backups showing that sector as all `FF`, a
matching live unit and flash geometry, and an independently observed loader
session. The command creates a durable transaction under the new output
directory, writes and verifies the pattern, restores the original sector, and
checks a complete final dump. Keep the device in UBOOT afterwards if desired;
boot and normal app operation can be checked after a later manual power cycle.

Example new-test invocation (replace every placeholder with values from a
fresh local inventory):

```sh
python3 tools/fm1_uboot_restore_test.py \
  --device /dev/sgN --backup PRIVATE_SESSION/backup \
  --out PRIVATE_SESSION/new-scratch-proof --test-unused-sector
```

For an interrupted prior scratch transaction, preserve its directory exactly
and invoke the recovery mode with the original matching backup. Use a fresh
output directory for this recovery receipt:

```sh
python3 tools/fm1_uboot_restore_test.py \
  --device /dev/sgN --backup PRIVATE_SESSION/backup \
  --out PRIVATE_SESSION/scratch-recovery \
  --recover-unused-sector \
  --transaction PRIVATE_SESSION/new-scratch-proof/transaction
```

Before opening the device, this mode validates the backup manifest and both
backup hashes, then validates the saved transaction plan, journal checksum,
transaction artifacts, scope, baseline and target. It requires the original
backup to agree with the transaction's saved image through `0xD9000`. The
connected unit must match the transaction's identity (which includes the
observed USB port path), and the loader must answer its flash query. It then
takes two fresh full reads; the transaction engine independently reads the
complete live flash and checks every byte outside the one authorized sector
against the saved baseline before writing. A mismatch is a stop condition.

This recovery CLI expects an already available, freshly observed loader
session; it does not send the soft key, establish ROM entry, upload the loader,
or automatically recover a stale device handle. A process restart while the
device remains in the loader may use the new physical enumeration only if it
still matches the transaction identity. If the device or loader reset, first
re-establish ROM and the audited loader through the separately observed and
reviewed entry sequence. If the current physical tool cannot establish that
sequence safely, stop; do not bypass its checks. The entry/backup commands and
known FM-1_092 checksum exception are documented in [the historical bench
note](../notes/2026-10-07-fm1-softkey-bench.md); stale `/dev` paths are never
reusable evidence.

## Exact physical SDK diagnostic procedure

The C-only private SDK diagnostic uses the pinned V1.2.13 application libraries
and preserves the owner's stock SPL, OTA, configuration and partition layout.
Its raw target is
`df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`;
the matching stock baseline is
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
These hashes identify this owner's private artifacts, not a general firmware
download or permission to install on another unit. Vendor/SDK files remain
ignored and undistributed.

`tools/fm1_sdk_rehearsal.py` binds the actual dual-backup receipts, reviewed
fixed loader, actual app/ELF/audit, immutable transaction and exact derived
erase/program geometry. Its Linux transport holds an advisory flock on the
direct SG descriptor and verifies that descriptor and USB/sysfs ancestry before
and after every request. The one-use
marker precedes opening hardware; durable intent precedes each write. It
permits only the fixed INQUIRY/FC0A status and geometry queries, aligned reads, derived sector erases
and direction-bound page programs. Each direction requires full readback
before mutation, per-sector verification and a complete final readback. The
directory sector is last. `tools/fm1_sdk_install.py` is a distinct install-only
adapter sharing the original consumption boundary; it does not silently reboot
or restore after installing.

[verified: physical rehearsal and independent replay] The complete install and
stock-restore transcript passed independent review. Subsequent stock USB/MIDI
identity response verified restored application operation. The later
install-only transcript also passed independent review, with the exact target
read back. This verifies application-sector installation and stock restoration
within the observed loader sessions. It does not verify an arbitrary full-flash
rewrite, visible pixels or recovery from a corrupted or interrupted physical
write. The separate later retained RAM read supports diagnostic execution only
conditionally, with the record and native-code limits above.

For a new campaign, first establish fresh reviewed entry and take two matching
complete backups. Freeze the concrete campaign, source hashes and recovery
plan, then run file-only preflight and independent review before the one-shot
hardware wrapper. Preserve capture, command transcript, result, transaction
journal and consumed markers. After a device reset, the old SG/USB binding is
invalid: a new enumeration needs its own reviewed provenance and backup/recovery
adapter. Do not change an old manifest or remove a consumed marker to reuse it.
The SDK diagnostic does not provide the stock OTA service; its intended route
back is the separately verified ROM/loader recovery procedure.

## Interruption and recovery rules

Treat a lost acknowledgement, process exit, host crash, or power loss during a
write as an unknown live sector state. Do not repeat the last command by hand
or assume a journal intent means the command did or did not reach flash. Keep
the original transaction directory, logs, partial reads, backups and hashes.
In a new session, establish and observe a fresh loader, validate the original
transaction and backup, and read the actual full flash. For the fixed scratch
transaction, resume only through `--recover-unused-sector` above. Its core rebuilds a differing
authorized sector from durable baseline bytes after checking the rest of flash;
it refuses corrupt artifacts, a different unit, unexpected outside-range
changes, or a completed journal whose full readback does not match. It does
not run a `finally` erase on the stale session. If fresh entry, identity,
geometry, or full reads cannot be established, stop with the flash state
unknown and retain all evidence.

The SDK diagnostic's returned-ROM backup/restore software and composed private
models have passed independent review. Its closed interrupted-restore replay
kernel also passes its separate sixteen-chunk gate, but provides no hardware
opener. Original-lineage evidence, fresh partial-flash acquisition and physical
interrupted-write recovery remain separate development gates. The original
successful rehearsal cannot be replayed after an ambiguous request or a new
enumeration. Preserve the original intent and actual bytes; bind each new exact
physical adapter to accepted actual evidence before execution. The current
historical capture stop also needs its own reviewed successor; do not bypass
it, widen the scratch CLI or invoke a manual erase/program sequence.

The original scratch-sector bench test predates this transaction engine. Its
post-test hash and owner-confirmed normal boot remain historical physical
evidence; the new journal and process-recovery behavior are software-tested,
not retroactively claimed as part of that hardware test.

## Synthetic app-sector failure model

`tools/fm1_simulated_device.py` and `tools/fm1_recovery_campaign.py` model a
persistent 1 MiB flash, generation-scoped sessions, USB_KEY entry, and power
loss. The public fixture changes only two synthetic app sectors at
`[0x4000,0x6000)`, while preserving all other bytes. The campaign injects
torn page programs, torn erases, disconnects before operations, lost
acknowledgements, verification corruption, process exit after durable intent
or a write, stale handles, corrupt artifacts, wrong identity, out-of-range
plans and unexpected baseline changes. It reopens the process/device, uses
fresh actual modeled bytes, and verifies exact restoration of the full image.

Run the synthetic campaign on an appropriate development host, not against a
physical device:

```sh
python3 tools/fm1_recovery_campaign.py --list
python3 tools/fm1_recovery_campaign.py --case-range START:STOP \
  --output PRIVATE_OR_IGNORED_RECEIPTS/recovery.json
```

`START:STOP` is a half-open range from the catalog printed by `--list`; omit
the selection options to run the complete catalog. The campaign creates only
synthetic fixtures and a modeled device. Existing focused tests cover the
transaction core, representative reopened failures, and simulated USB_KEY
recovery; the recorded device-model test receipt is 58 passing tests. That is
not evidence that the physical USB_KEY dongle reaches ROM, that a damaged app
can enter ROM, that the FM-1 executes the synthetic app image, or that any
physical interrupted-write recovery works. This synthetic fixture's wider
permissions and USB_KEY route are model assumptions; the separate exact SDK
diagnostic's successful application-sector rehearsal is physical evidence.

[verified: Hera, 2026-10-11] The final reviewed source passed all **497**
catalogued cases across four bounded containers, with zero failures and exact
index coverage `0..496`. The focused campaign suite passed 32 tests. Each
receipt explicitly reports `model_only=true` and `hardware_validated=false`.
This tests deterministic torn-prefix writes and process termination; it does
not reproduce every electrical NOR failure or an actual host filesystem power
loss. Source and receipt hashes are in
[the continuation note](../notes/2026-10-11-installable-firmware.md#reviewed-interruption-campaign).

## Offline bound diagnostic command policy

[verified: source and Hera model tests] `tools/fm1_bound_diagnostic.py` adds a
separate injected-transport adapter. `load_policy(...)` revalidates actual
baseline/target files, both backup records, FM-1_092 raw geometry and the
app/ELF/audit before accepting a transport. Its immutable policy fixes the
transaction directory, install/restore direction, exact image pages and derived
changed sectors. Erase/program commands additionally require a matching durable
journal intent from the transaction run; direct write calls are rejected.
Malformed CDBs and arbitrary ROM/loader/eFuse commands are rejected before I/O.
Ambiguous transport, response or binding failures close the handle; resume and
restore require a fresh binding and the core's full readback checks.

This adapter has **no physical opener or CLI**. Loader/session/unit bindings are
injected assertions, not hardware attestation. Python caller code and
cooperative file locks are not a security sandbox; a future real transport must
own and validate its exclusive handle across re-enumeration. The 51 new model
cases passed, with 115 passing combined raw/stock/report checks and two optional
private-fixture skips. Its receipts explicitly mark hardware validation false.
The distinct SDK policy and native adapters described above add actual
candidate/session binding; that later physical evidence does not change this
injected adapter's scope.

## Future installable image and deferred work

Any installable package must preserve the stock SPL, `ota.bin`, `cfg`,
`isd_config.ini` and partition layout under the existing package guards. Keep
the stock updater service usable when the app runs. A future image may add an
early fail-open gesture and a bounded boot-failure route, but source checks,
simulated reset, and a modeled USB_KEY route do not prove those paths on the
FM-1. Any physical app-sector/full-image writer requires a separate command
allowlist, exact image/unit binding, reviewed erase geometry, durable recovery
plan, post-write full readback, and explicit hardware validation. Never
perform a blanket chip erase, arbitrary vendor command, eFuse/key operation,
or use a V1.2.x loader. The USB_KEY recovery route needs a working physical
USB_KEY device and independently observed ROM enumeration before it can be
claimed.

The Cynthion experiment remains deferred to later work. VBUS switching is not
proof that the battery-powered FM-1 CPU reset; observe reset and enumeration
separately if that experiment proceeds.
