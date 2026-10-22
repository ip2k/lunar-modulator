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
