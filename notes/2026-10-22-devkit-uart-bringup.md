# Dev-kit UART bring-up — 2026-10-22

## Objective and acceptance

Identify the received development board, capture its factory boot log, establish
the actual clock/memory configuration, then prepare a board-specific DSP timing
experiment. USB enumeration alone does not establish firmware performance or
authorize replacing the factory application. No target firmware writes so far.

## Observations

- [verified] Owner photo shows `JL_AC79_DevKitBoard V1.2`, dated `20230609`.
  Carrier exposes a `TX / PB3` row, 3.3V and GND. Core model/revision is not
  established by this photo. Do not substitute the older V1.0 documentation's
  chip identity for identification of this unit.
- [verified] Owner disconnected KA6 MIDI OUT from the carrier MIC IN. MIC IN
  is not a MIDI input. Board audio output is not connected to the KA6 yet.
- [verified] bench01 enumerates JieLi CDC `3654:5155`, serial
  `9127AF1910855C53`, at `/dev/ttyACM0`. An eight-second receive-only CDC
  capture before the Tigard connection received zero bytes. No protocol data
  was transmitted. This does not establish a failed boot.
- [verified] Tigard enumerates as `0403:6010`, product `Tigard V1.1`, serial
  `TG1108fc`. UART is
  `/dev/serial/by-id/usb-SecuringHardware.com_Tigard_V1.1_TG1108fc-if00-port0`
  (`/dev/ttyUSB0`); the second interface is not the UART.
- [verified] Both adapters are behind the same USB hub. JieLi re-enumerated
  from device 78 to 79 between observations; the cause is unestablished.
  Earlier kernel history contains hub overcurrent and descriptor errors.

## Receive-only UART setup given to owner

Disconnect USB power while wiring. Tigard voltage switch **VTGT**; UART pin 1
VTGT to carrier **3.3V**, pin 2 GND to **GND**, pin 4 RX to **TX / PB3**.
Leave TX, RTS, CTS and other interfaces disconnected. Reconnect USB, wait for
capture to be armed, then request one normal Reset press. No Update-button
sequence or firmware upload is part of this step.

[Tigard upstream documentation](https://github.com/tigard-tools/tigard#uart)
establishes UART pinout, first-interface selection, and target-powered VTGT
operation. [JieLi download guide](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.0.3/getting_started/project_download/download.html)
and the pinned local SDK DevKitBoard configuration identify PB3 debug TX at
1,000,000 baud. [inferred] This factory image may use that configuration;
the boot capture must verify it. Start at 1,000,000 baud, 8N1, no flow control.

## Performance context and next dependency

The separate installable-firmware branch records a best physical diagnostic
run of 498.453089 64-frame blocks/s against 689.34375 required (27.69% short).
This is an FM-1 measurement, not a dev-kit result. A paired schema-7/schema-9
target build already exists on Aeon under
`/home/claude/mvave-fm1/resampler-stage-profile-pair-aeon-20261017-codex/`,
source `36988d0c2ef1b793e5f9d343fac1b9f6c4b7891f`. It has not run on this board.
Do not flash an FM-1 image onto a dev kit with different peripherals/memory.

Await owner wiring confirmation; arm receive-only capture before requesting
Reset. Preserve boot log in ignored research storage, summarize non-sensitive
hardware facts here. SWD/JTAG suitability is not established for pi32v2.

## Tool coverage

Rarefaction status and Serena initial instructions/current project were checked
on the primary absolute checkout. Their bounded `fm1_resampler_pop` navigation
agreed with the primary header. Rarefaction C has no root compilation database;
fallback analysis is not pi32v2 ABI or firmware code-generation verification.
The new worktree is separate; do not claim primary indices cover its edits.
No existing graph was found; no graph was built. No new agents were started.

Branch: `feature/2026-10-22@devkit-performance`, based on `659c3aa9`.
Raw USB evidence: ignored `scratch/devkit-20261022/` in this worktree.

## First captured reset

[verified] Owner moved the initial TDI connection to the separate UART RX
header, confirmed VTGT/GND/PB3 wiring, and pressed Reset once after capture
was armed. Capture opened exclusively at 1,000,000 baud, 8N1, no flow control,
DTR/RTS deasserted, with no serial writes. Raw capture is private on bench01:
`/home/claude/fm1-devkit-captures/uart-20261022T165500Z.bin`.

[verified] Readable factory boot output reports:

- `WL82(AC791N) CHIP_ID: 0x6f01`, setup build July 26, 2024.
- CPU 320 MHz; SDRAM 192 MHz; HSB 160 MHz; LSB 53,333,333 Hz;
  SFC 80 MHz. These are firmware-reported settings, not measured frequencies.
- SDRAM 8,388,608 bytes; heap 6,987,712 bytes; internal RAM accounting
  523,596 bytes with 421,452 remaining at startup.
- SDK banner `AC79NN SDK on branch [master]`, with July 2024 component builds;
  do not identify this as our pinned V1.2.13 without matching its provenance.
- SDFILE logical disk capacity 8192 KB; physical flash capacity/JEDEC ID
  is not independently established by that message.
- Display `dc->width : 320, dc->lines : 480`.
- DAC analog initialization succeeds. Demo later reports
  `1open_audio_dec_err!!!`; application UI and network activity continue.
- Reset reason `LOW POWER` is the literal firmware label; no conclusion
  about a brownout or wiring fault follows without further evidence.

UART bring-up is demonstrated. Lunar DSP performance is still unmeasured on
this dev kit. Next: preserve factory/recovery provenance and prepare a minimal
board-specific timing image without assuming FM-1 peripheral compatibility.

## Diagnostic preparation and current dependency

[verified] Carrier and Tigard are behind the owner's BLACKBOX ICI202A powered
hub. Its documented maximum is 12 Mbps, matching the observed USB tree;
that speed alone is not evidence of the DSP slowdown. Earlier descriptor and
overcurrent messages remain observations, not a diagnosed cause.
[Manufacturer specification](https://www.blackbox.com/en-ca/store/product/detail/industrial-usb-20-hub-with-isolation---4-port/ici202a).

[verified] Factory audio failure follows an unsuccessful open of
`/audlogo/poweron.mp3`; this is evidence of a missing startup asset, not a
failed DAC test. The completed receive-only capture was copied to ignored
`scratch/devkit-20261022/uart-20261022T165500Z.bin`, SHA-256
`03fb70ab41d9bb4de74f2326d3f850e17f3442fbf845805fc121732871456268`.
Do not publish that raw log: factory networking identifiers are present.
The original ten-minute capture has ended; arm a new capture before a watched
experimental boot.

New source, backed up at `6b2ee8edfbce6e603e0cf0d444997fe1b76c032d`:

- `firmware/devkit/benchmark.c`, `.h`, `sdk_worker.c`: allocation-free
  resampler-only benchmark; 44,118 / 47,872.34 / 96,000 Hz inputs, silence,
  active signal and decay to silence; IRQ enabled. Checksum and UART output
  are outside the timed block. The producer-size field controls fixture
  bookkeeping only; it is not a complete instrument producer benchmark.
- `tools/jieli/prepare-devkit.py`: prepares an isolated private SDK hello
  tree, disables its automatic downloader, and compiles benchmark state into
  internal SRAM. SDK source is a private git archive of pinned `e30b1ee`;
  the preparer records the required revision but does not authenticate an
  arbitrary input tree. It must not be used with an unverified SDK archive.
- `tools/devkit_flash_backup.py`: pinned RAM loader and two bounded 8 MiB
  reads, denying flash program/erase/eFuse commands. Requires independently
  observed USB path/device number and matching 8 MiB JEDEC capacity.

[verified] Aeon isolated build v4 successfully linked the real pi32v2 ELF.
ELF SHA-256: `3f4e744ce601c2c13a891d0ec58f56218445da99d3348c7cf4a24aeba00b418b`.
Vendor objdump places `signal_table` at `0x01c02c50`, `state` at
`0x01c03050`, and `outputs` at `0x01c03558`, all `.ram0_bss`.
`audit_link.py --elf ... --sources firmware/devkit` reports 0 failures and
one manual scheduling item: vendor disassembly confirms `sdk_meky_check`
registers IRQ 123 twice (CPU arguments 0 and 1), and schedules `_mkey_check`
through `__sys_timer_add` with interval 8000. This signs off that item's
scheduling only; no vendor protection code was changed.

Build v4 is **not an admitted installation package**: its generated demo
configuration retained the SDK's 2 MiB SDRAM default. Follow-up preparation
sets 8 MiB to match the factory-reported capacity, hashes all diagnostic
inputs, and rebuilds as v5. Flash 8 MiB is still a hypothesis pending JEDEC
query. The benchmark uses the public main resampler header, not the separate
installable-firmware branch's latest optimization. No target Lunar timings
have been measured.

Remote private build root:
`claude@192.168.1.25:/home/claude/mvave-fm1/devkit-performance-20261022/`.
`build-sdk-v4/` holds ELF/sections/symbols/disassembly, `build-sdk-v5/` the
follow-up build. Containers have no network/USB and use docker-batch.slice,
4 CPUs and 4 GiB RAM/swap limits. Mac copies are ignored under
`scratch/devkit-20261022/build-v4/`.

[verified] After the owner's first Update/Reset attempt, USB still enumerates
as normal CDC `3654:5155`, device 85, not WL82 UBOOT. A direct owner prompt
asks to move USB from the carrier to the core board's USB-C beside
Update/Reset and repeat hardware download entry. Await that confirmation;
do not guess that it happened. No loader upload or flash write has occurred.
Once UBOOT is observed: identify the exact USB path/devnum, obtain two matching
factory reads, preserve private recovery data, review the candidate's boot and
partition layout, and only then proceed with an authorized target experiment.
Do not run vendor blanket erase/key/program commands. No audio output is
required for the first timing diagnostic.

### Follow-up build verified

[verified] v5 links successfully; ELF SHA-256
`bc8566d9d73e41951050e4ecc7a3a71c5355e3212a1375b65901b5f59ab97337`.
Benchmark state addresses remain in internal SRAM as above. Link audit again
has 0 failures; `sdk_meky_check` vendor disassembly is identical to manually
reviewed v4, signing off the scheduling item for v5 as well. Focused checks:
`tests/test_devkit_diagnostics.py tests/test_uboot_read.py` all pass (18 tests),
including ASan/UBSan execution of the real resampler workload. No target run,
installation package approval, CI run or merge is claimed by these checks.

Backup client, base transport and hash-pinned loader are privately staged on
bench01 at `/home/claude/fm1-devkit-tools-20261022/` with mode 0600. Loader
hash was independently rechecked there. Staging copied files only; it did not
open the USB target. At the latest check the board remains CDC device 85.
Owner action is still pending. Work is on
`feature/2026-10-22@devkit-performance`; implementation/config checkpoint
`0b30074679a0d7818bdded7974b58a0e83103fe6` is verified pushed. This final
note update is committed on the same branch; recover the exact tip from Git.

## Core USB download entry and first factory backup

[verified] Owner connected both carrier and core USB, repeated hardware
Update/Reset entry, and bench01 enumerated `4c4a:8057` on `3-1.2`, device 91,
`/dev/sg0`. USB descriptors say WL80UBOOT1.00; SCSI INQUIRY independently
returns vendor `WL82`, product `UBOOT1.00`. No model inference from the USB
product string is needed.

[verified] The original pinned loader `d41da612...` executed in RAM, reported
SPI NOR JEDEC `5e4017` (8 MiB), and returned two complete matching 8,388,608-byte
reads. SHA-256 of both:
`127b2ebbef9da3469f0bf7ea3841a5515d01721ebac9bbdc7fc739032d7b5ec1`.
Private bench directory: `/home/claude/fm1-devkit-backups/factory-20261022-first`.
Mac copies: ignored `scratch/devkit-20261022/factory/`; re-compared byte for byte.
Receive-only UART was armed before upload, ten-minute capture at
`/home/claude/fm1-devkit-captures/uart-download-20261022T181200Z.bin`.
The filename is a label, not an authoritative timestamp.

**Correction/limit:** no flash erase/program command was sent, but the original
loader is not a sufficient basis for asserting that NOR status registers were
untouched. The later October 11 native review identifies possible status writes
in its initialization. This caveat was reported directly to the owner. The
original receipt's `flash_written:false` must be interpreted only as no
host-issued erase/program, not an audit of every loader side effect.

The dev-kit adapter now admits only the separately reviewed fixed loader
`fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c`,
which bypasses the identified quad-status programming branch. The historical
base Reader and its original pin are unchanged. Private blob copied from the
existing reviewed bench campaign to `fm1-devkit-tools-20261022/loader.fixed.bin`;
actual SHA checked. Twenty focused tests pass; a private real-blob fake-transport
check verifies exact 47 upload blocks, inquiry/jump/buffer ordering, and rejects
the actual original blob before device access. No fixed-loader upload to this
dev board has occurred yet. Owner has been directly asked to repeat Update/Reset
for a fresh ROM session before the cross-check; do not reuse current loader
state as if it were ROM.

## Owner RE authorization and offline layout

Owner explicitly approved private analysis/unpacking/decoding/decompilation and
reverse engineering of **this dev board and the SDK**, using REA or other tools,
for Lunar firmware and/or recovery of the physical FM-1 (2026-10-22). This covers
the protected-target analysis question just raised; do not re-ask for the same
scope. It does not authorize publication of vendor material or arbitrary eFuse,
blanket erase or other destructive commands.

[verified: decoded factory bytes] Top header and four directory records validate
their CRCs. Bootloader at offset 160, 14,536 bytes; isd_config at offset 14,696,
765 bytes; application directory at `0x4000`; key/MAC reserved at `0x7ff000`.
Configuration payload and embedded key-blob CRC validate. Derived SFC decoding
produces valid application directory records: app_area_head size 2,411,235;
app.bin offset `0x120` within that area, 2,410,564 bytes; cfg_tool.bin 383 bytes;
VM/PRCT/BTIF descriptors separately retained. Full payload CRC validation and
candidate construction/review are still pending. Decoded bytes and expanded
layout remain private; this note contains no vendor code or key material.

Semantic-tool limit: Rarefaction rejects this worktree via an outside-root
`project` path, so it was not used as proof of the new Python adapter's callers.
Serena remains on the primary checkout; no sibling session was switched.
Focused source inspection and actual compiler/tests supply the checks above.

### Payload validation and offline candidate

[verified] Factory app-area payload, app.bin and cfg_tool.bin CRCs all pass.
Decoded SPL bank header, payload and enclosing record CRCs also pass.
One SPL bank loads 14,520 bytes at `0x01c02000`, file offset 16; decoded
SPL SHA-256 `4e3b4c220dc96641cb5a723f41e68ce41d5261ae9434bb33fbd7f2c59976ded4`.
A private analysis-only ELF wraps that exact bank at its recorded address;
vendor pi32v2 objdump produced the private listing. REA's exposed native
architecture choices do not include pi32v2; no REA decompilation is claimed.
Vendor instruction decoding remains the source of truth for this CPU.

[verified] Diagnostic app flattened in the SDK's documented section order
`.text + .data + .dynamic_data + .ram0_data + .cache_ram_data`: 161,776 bytes,
SHA-256 `a8be4d4d7b1feeb7c2a4c468b503b965249e386344759c39937e6720acd8753c`.
Independent vendor objcopy exports concatenate to that same hash on Aeon.

Private **offline, not hardware-admitted** candidate:
`scratch/devkit-20261022/factory/candidate-v5-OFFLINE-NOT-ADMITTED.bin`,
SHA-256 `912e0b8d07afcc702c0e85e06d484c1b1c213304ebefdfa01780ce4629742db8`.
App length/CRC and directory/area CRCs are updated in the existing allocation;
old tail and other components remain. It changes 40 4-KiB sectors from 0x4000
through 0x2b000; all raw bytes before 0x4000 and from 0x2b920 onward match the
factory dump exactly. The private candidate plan lists pending gates:
fixed-loader backup cross-check, factory SPL's 92-byte boot-info ABI review,
SDK startup flash side-effect review, and independent candidate/bounded-writer
validation. Existing FM-1-specific 1-MiB writer policies are not applicable to
this 8-MiB dev kit and must not be bypassed by pretending it is an FM-1.

Current source checkpoint before this note: `8351f7348c5d36b1260a4a0cf08022dab1fbee5c`,
verified pushed. Current USB observation is still device 91, active original
loader; fresh owner Update/Reset confirmation remains pending. No new target
command was sent after the first backup completed. No diagnostic has booted.

### SDK settings initialization reachability

[verified: v5 vendor objdump and linked init-table bytes] `app_task_handler`
walks the platform init table before creating `lunar_devkit_worker`. Its entry
at `0x02024bc4` points to `syscfg_tools_init` (`0x02008234`), which walks the
28-byte settings-operation records and calls each non-null initialization
callback. The VM record at `0x02024be8` starts with `syscfg_vm_init`
(`0x02009b70`). That initializer contains conditional calls to `vm_reset`,
`_vm_area_erase` and defragmentation/recovery routines. This proves startup
reachability, not that any particular erase branch would execute against this
factory VM. Candidate boot remains pending a bounded decision on this startup
behavior, alongside the boot-info ABI and fresh fixed-loader backup gates.

[verified] Source/docs tip `2c8f661966b83374fe92c9048fcd4605b3a85edd` was
pushed and matched the remote branch. A subsequent live USB inventory still
shows device 91 on `3-1.2`; no new ROM session or fixed-loader execution is
claimed. The requested owner Update/Reset sequence remains outstanding.

## Fresh fixed-loader backup and v6 startup restriction

[verified] Owner repeated hardware entry; USB changed from device 91 to 92
on `3-1.2`, with the expected sg0 ancestry. Fixed-loader hash was rechecked
before execution. Two new complete 8-MiB dumps match the original factory
SHA `127b2ebbef9da3469f0bf7ea3841a5515d01721ebac9bbdc7fc739032d7b5ec1`.
Remote `cmp` confirms both fixed reads equal the original read byte for byte.
Private receipts: bench `fm1-devkit-backups/factory-20261022-fixed-crosscheck`,
Mac ignored `scratch/devkit-20261022/fixed-crosscheck/receipt.json`. No host
erase/program command sent; restore still not demonstrated. Receive-only
UART capture armed before upload at
`/home/claude/fm1-devkit-captures/uart-fixed-crosscheck-20261022.bin` (ten-minute
bounded capture).

The preparer now moves settings-backend records outside their linker
registration range, preserving the vendor implementations and records.
[verified: actual v6 target ELF] `syscfg_ops_begin == syscfg_ops_end ==
0x02024bcc`, with `cfg_vm` retained at `0x02024be8`. This prevents that table
walker from initializing persistent settings; it is not a blanket proof that
all vendor startup code is free of flash side effects. Twenty focused tests
pass. v6 ELF SHA `3e313f06be8b12880085a4a43e83820c333767d184c447d4c896cc0d66bc33f1`;
flat app 161,776 bytes, SHA
`75731dfffb67c6c0ab8afcf5ef3ed92ad16d2eea223ba9c1bdf33ef1632fce3a`.
`audit_link.py`: zero failures, scheduling manual item pending in its output;
byte comparison confirms the vendor scheduling function is identical to the
previously reviewed v5. No diagnostic boot or candidate flash yet.

Boot-handoff investigation: [verified: decoded factory SPL vendor listing]
`0x01c0531c` passes `r14+136` to the application; six words are copied there
at `0x01c0526e`, followed by a header pointer and 32-byte header. The listing
also has conditional writes at `r14+216` (argument +80). Do not infer the
remaining extended ABI is initialized solely from the SPL date/version;
this review remains open. v5 offline candidate is superseded for startup
behavior; do not install it.

### Exact v6 transaction prepared; bench rehearsal not yet executed

[verified] Independent reference `jltech.cipher` decoding of the v6 candidate
validates directory, application-area and application CRCs, exact v6 payload,
unchanged cfg-tool payload and protected raw regions. Candidate SHA
`e77ee8af309fc57d1a8eddaac95dec253dda031f269021382c9cb1e977baa103`;
private ignored generator/validator scripts and candidate are under
`scratch/devkit-20261022/`. Factory application entry at `0x02000228`
consumes the same boot fields (+80/+88) as this SDK. This is ABI-consumer
compatibility evidence, not proof of all SPL producer branches.

`tools/devkit_flash_transaction.py` admits only the exact factory/v6 image
hashes and their forty changed sectors, ending directory sector 0x4000 last.
It has no loader upload/reset/chip-erase/eFuse command, verifies each sector
and complete flash, and supports explicit exact-factory restoration after a
partial transaction. The initial USB path/devnum and exact JEDEC must match.
35 focused tests pass, including exhaustive rejection of unrelated opcodes.
A private actual-image NOR model passes installation, restoration, and injected
partial-page failure then restoration. These are offline checks; no physical
erase/program or restore rehearsal has occurred. Remaining bench gate is
install/readback/restore/full-factory comparison before diagnostic boot.

GitHub DNS resolution failed for `f871ce61`; it is saved locally and pushed
to the existing Aeon exchange remote, but is not yet verified backed up on
GitHub. Retry GitHub push and verify SHA; do not call that backup complete.

### Physical v6 rehearsal in progress

[verified] Fixed-loader session dev92: v6 install transaction passed all
forty sector readbacks and the full 8,388,608-byte comparison, target SHA
`e77ee8af309fc57d1a8eddaac95dec253dda031f269021382c9cb1e977baa103`.
No reset/boot sent. Bench evidence `fm1-devkit-backups/v6-install-rehearsal`.
Explicit exact-factory restoration is now running into
`fm1-devkit-backups/v6-restore-rehearsal`; do not infer restore success before
its receipt and full factory comparison. Main exec session65040; live UART
session53925 (ten-minute bounded capture). Firmware launch remains pending.

GitHub backup recovered using a per-command HTTPS DNS override from bench01's
actual resolution (TLS checks retained; no DNS service changed). Remote branch
verified `9272c5c7f09895f3fd3b50bd34c0bb254f897af5`.

[verified] Physical exact-factory restoration completed successfully. Full
8-MiB SHA returned to
`127b2ebbef9da3469f0bf7ea3841a5515d01721ebac9bbdc7fc739032d7b5ec1`;
remote `cmp` independently confirms identical bytes to the original backup.
This demonstrates restoration of the forty rewritten application sectors
with complete-image comparison, not an erase/rewrite of all 8 MiB or a
factory boot-acceptance result. Private receipts copied to ignored
`scratch/devkit-20261022/rehearsal-receipts/`.

A second v6 installation for boot is running into bench
`fm1-devkit-backups/v6-install-for-boot` (exec session61005). Wait for full
readback success before owner Reset. No diagnostic has booted yet.

### Diagnostic installed, awaiting owner first Reset

[verified] Second installation completed with full 8-MiB readback SHA
`e77ee8af309fc57d1a8eddaac95dec253dda031f269021382c9cb1e977baa103`.
Private evidence `fm1-devkit-backups/v6-install-for-boot`; receipt copied
to ignored `scratch/devkit-20261022/rehearsal-receipts/install-for-boot.json`.
No software reset sent. Owner directly prompted to press/release Reset once,
without Update. Diagnostic is UART-only, no display/audio output. No target
timing or successful diagnostic boot is claimed before capture evidence.

Earlier ten-minute rehearsal capture was deliberately stopped (own PID
verified against its output-file descriptor) before rearming receive-only
UART for thirty minutes. Active exec session40982; bench path
`/home/claude/fm1-devkit-captures/uart-v6-first-boot-20261022.bin`; companion
JSON records actual UTC start and duration. Inspect that file after owner
Reset. UART PB3 at 1 Mbaud is verified against this candidate's board config.
SDK FreeRTOS headers specify 100 ticks/second: ten OS ticks are nominally
100 ms, so an OSC24M timer calibration near 2,400,000 ticks is expected;
validate observed calibration before converting benchmark ticks to time.

Latest prior checkpoint `4f3de8a0bcd6cb75898d528319895c04ec29e853` is
verified pushed to GitHub. No PR/merge yet: actual first boot is pending.

### Owner first Reset reported; UART retrieval blocked by bench reachability

Owner reports pressing Reset once without Update. [verified] Log retrieval
could not connect: bench01.local resolution stalls, documented IPv4 .181
SSH times out, and documented IPv6 link-local fails via Mac en12/en0 and
Aeon bond0. Aeon resolves bench01.localdomain to .181; its ARP/NDP entries
for those addresses are FAILED/INCOMPLETE. No changed DHCP address is
confirmed. This is a host/network access failure, not diagnostic boot or
firmware-fault evidence. No new target command or reset sent.

Owner directly asked to check bench01 power/Ethernet lights and leave dev
board/Tigard unchanged, avoiding a bench reboot until capture preservation
is assessed. First-boot capture was armed on the previous turn, but its
current process state and bytes cannot be verified while bench is unreachable;
old exec40982 is no longer recognized by the local tool. Do not claim the
benchmark ran, failed, or produced timing data. Next: restore bench access,
copy/private-hash the UART capture, then inspect actual startup and benchmark
lines. Re-arm before requesting any repeat Reset if necessary.

## 2026-10-23: bench access recovered; empty capture and repeat armed

[verified] bench01 is reachable again at DHCP .181 and the documented IPv6
link-local address, with strict existing host-key verification. Usual .local
lookup still stalled in the initial attempt. Uptime approximately 29 days;
no bench reboot inferred or performed. Saved first-boot file is zero bytes.
Its metadata records start `2026-10-22T21:29:13Z` and duration 1800 seconds;
this does not establish when the owner Reset occurred relative to listening.
No diagnostic boot/failure/timing claim can be made from the empty capture.
Dev board absent from current USB inventory; Tigard and KA6 still present.
USB absence is compatible with this UART-only diagnostic, not boot proof.

Added receive-only `tools/devkit_uart_capture.py`: exclusive Tigard RX at
1 Mbaud, DTR/RTS low, no serial writes, durable raw-byte flushes and lifecycle
JSON. Compiles with py_compile; actual remote open/read verifies armed state.
Launched under nohup independently of SSH, PID3550891, duration3600 seconds,
start `2026-10-23T15:33:01Z` (08:33 Pacific). File
`/home/claude/fm1-devkit-captures/uart-v6-repeat-20261023.bin`; companion JSON
reports armed and two bytes initially, no readable startup log yet.
Owner directly prompted for Reset once without Update. No reflashing or
target protocol command sent. Next inspect repeat capture after owner action;
if it has no boot text, investigate UART/boot evidence without inventing a
firmware outcome. Prior exact-image restore/install receipts remain valid.

## Verified first benchmark boot, 2026-10-23

Owner repeated Reset without Update while the durable capture was armed.
[verified] Capture contains all eighteen unique benchmark cases followed by
`LUNAR_DEVKIT complete=1` at SDK uptime 2.060 seconds. No assertion or
exception was captured between the cases. Raw capture snapshot 5,637 bytes,
SHA `80010643450d410aa89dc7718be16b314e76ac7d92b9239efc6c8a376cfd832f`.
Private Mac copy and parsed JSON are under `scratch/devkit-20261023/`.
See [measured results and limits](2026-10-23-devkit-resampler-results.md):
nominal conversion cost is about 27–28% or 35% of a 64-frame block at the
reported 320 MHz, versus about 2% at equal rates. These are resampler-only
measurements, not a complete instrument, real producer batching or live
audio/dropout test. No physical FM-1 command was sent.
