# FM-1 recovery runbook

This runbook separates three things: routes observed on the owner's FM-1_092,
the fixed physical scratch-sector procedure, and a synthetic failure model for
future app-sector recovery. The transaction core is durable software, but its
physical writer remains limited to one known-unused sector. Model success does
not prove mask-ROM entry, CPU reset, USB_KEY timing, or firmware boot on hardware.

## Proven hardware facts and current boundary

[verified: owner FM-1_092, 2026-10-07] The normal FM-1 application accepted
the single soft key `F0 22 24 35 7D F7` and enumerated as JieLi mask-ROM UBOOT
(`4C4A:8057`, `WL80UBOOT1.00`). A pinned 24,064-byte WL82 loader was uploaded
to RAM. The existing reader took two identical 1 MiB full-flash dumps. The
bounded test programmed only `[0xD8000,0xD9000)`, read the pattern back, erased
that one 4 KiB sector to its original all-`FF` value, and read the full flash
again. The final hash matched the pre-test backups; the owner later power
cycled and confirmed a normal boot. See [the bench note](../notes/2026-10-07-fm1-softkey-bench.md).

That proves entry from a running FM-1_092 app, full-flash reads and restoration
of that fixed scratch sector. It does not prove a full-image rewrite, recovery
from a corrupt app or SPL, Lunar installation, or recovery of another unit.
There is no physical full-image writer. The physical write adapter still
permits only the fixed scratch address and exact test pattern.

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
is restricted to explicitly simulated bindings while this startup gate remains
unresolved. A separate 14-byte reset stub and its fixed three-command guard
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

## Triage hierarchy

| Observed condition | Route | Limit |
| --- | --- | --- |
| App boots and stock update service runs | Install a known-good package through the stock update path. Preserve stock `uboot.boot`, `ota.bin`, `cfg`, `isd_config.ini`, and partition layout. | Requires a running app and its update service; cannot rescue a non-booting app. |
| App runs and accepts the vetted soft key | Send the exact `7D` soft key once, observe ROM enumeration, then use the audited loader and read-only backup path. The fixed scratch proof is the only physical write currently implemented. | Proven on the owner's FM-1_092 only. `7F` is a different update command. |
| UBOOT session needs to return to the installed app | A separately reviewed exact 14-byte RAM reset stub returned this owner's session to normal USB and a responsive FM-1_092 app once. | Bare-UBOOT reset opcode is unverified; do not replay a consumed adapter or assume every warm reset reconnects. Retain a real power-cycle fallback. |
| App hangs or is corrupted | First observe whether the device enumerates normally. If the app is unusable, a USB_KEY-at-power-up route is a candidate; use only after its hardware procedure is independently reviewed and observed. Capture the ROM enumeration before loading the audited loader. | The USB_KEY dongle is simulated, not tried on the owner's FM-1. A ROM failed-boot route and successful entry from a broken app are not physically proven. The app soft key cannot help if the app does not run. |
| SPL, boot metadata, or flash contents damaged | If mask ROM still enumerates, preserve the actual image and transaction evidence; recovery needs an exact owner-matched baseline and a separately reviewed bounded writer. | No complete physical restore exists. Never overwrite the SPL or metadata as an experiment. |
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

## Interruption and recovery rules

Treat a lost acknowledgement, process exit, host crash, or power loss during a
write as an unknown live sector state. Do not repeat the last command by hand
or assume a journal intent means the command did or did not reach flash. Keep
the original transaction directory, logs, partial reads, backups and hashes.
In a new session, establish and observe a fresh loader, validate the original
transaction and backup, and read the actual full flash. Resume only through
`--recover-unused-sector` above. Its transaction core rebuilds a differing
authorized sector from durable baseline bytes after checking the rest of flash;
it refuses corrupt artifacts, a different unit, unexpected outside-range
changes, or a completed journal whose full readback does not match. It does
not run a `finally` erase on the stale session. If fresh entry, identity,
geometry, or full reads cannot be established, stop with the flash state
unknown and retain all evidence.

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
physical full-image write/recovery works. Wider app-sector write permissions
and USB_KEY recovery are model assumptions only.

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
private-fixture skips. Physical loader/recovery binding and an actual candidate
remain separate gates. Receipts explicitly mark hardware validation false.

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
