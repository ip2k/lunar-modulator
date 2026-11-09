# 2026-11-08 — M4: bounded RAM runner, run on the AC79 dev kit

Milestone M4 of docs/18: a host tool that loads one image into SRAM through
the WL82 mask ROM and jumps to it, and nothing else; a tiny RAM test image
that reports over the debug UART and resets back to the application; two
end-to-end runs on the dev kit. The second half of this note is desk work for
M5 on the FM-1, from FM-1-transporter's source only. **No traffic was sent to
the FM-1 or to the Pico 2 W transporter.** Confidence marks as in CLAUDE.md.

Run times are UTC, 2026-11-09 (the evening of 2026-11-08, bench-host local
time).

## 1. What was built

| Piece | Path | What it does |
| --- | --- | --- |
| Runner | `tools/ram_runner.py` | INQUIRY, `FB06` WRITE_MEMORY of the whole image in 512-byte blocks, `FD07` READ_MEMORY of every block and compare, one `FB08` JUMP. Nothing else |
| Runner tests | `tests/test_ram_runner.py` | 54 tests, no device |
| RAM test image | `firmware/ramtest/` | prints a banner with its build id, ten heartbeats and a reset line on UART1 TX (PB3, 1,000,000 baud), then clears the 16-byte boot marker and resets the chip through P33 as the SDK's `__cpu_reset` does |
| Image tests | `tests/test_ramtest_image.py` | 10 tests: the portable logic compiled natively against a recording register model |
| Build | `tools/jieli/link-ramtest-in-container.sh`, profile `ramtest` of `tools/jieli/link-diagnostic.sh` | the JieLi clang in a container on a Docker host, `audit_link.py --runtime sdk-free`, `diagnostic_report.py` profile `ram` |
| Pinning | `tools/bench_targets.json` | the dev kit's ROM port, `3-1.2`, is now pinned exactly (both runs below) |

### 1.1 How the runner refuses things

Refusals are in code and tested [verified: `tests/test_ram_runner.py`]:

- **Allow-list of four commands:** SCSI INQUIRY (`0x12`), `FB06`, `FD07`,
  `FB08`. Every one of the 65,536 two-byte opcodes other than those three is
  refused, by a test that tries them all.
- **Refused by name as well:** `FB01` erase, `FB04` program, `FD05` flash
  read, `FC09` key, `FC0A` online device, `FC14` buffer size, `FC0C` run app,
  `FC12`, the raw `A1` eFuse write, a CDB starting `F0` (the soft key's SysEx
  start), `5A AA A5` online-tool frames, and a vendor syscmd frame head
  `00 59` (docs/02 §6), with syscmd 33–36 and 48 named, bare or in their
  `F0 35 59` SysEx wrapper.
- **No flash-reader path.** The runner reuses `fm1_uboot_read.Reader` for
  pinning and opening, and overrides its `load`, `online` and `dump` to
  refuse, so the flash loader can never be uploaded or read from it; a test
  checks that none of them sends anything.
- **The gate checks twice.** It checks when the request is built and again on
  the final 16 CDB bytes just before `SG_IO`.
- **Addresses:** only whole 512-byte blocks inside `[0x01C02000, 0x01C07E00)`.
  That is the 24,064-byte window where the ROM already accepted and ran
  JieLi's loader on both the dev kit and the FM-1 [verified:
  `tools/fm1_uboot_read.py`, `notes/2026-10-22-devkit-uart-bringup.md`,
  `notes/2026-10-26-fm1-stock-v15-recovery.md`].
- **One pass:**
  - The steps run in order: inquiry, upload, verify, jump.
  - Nothing is resent, and the jump is never retried.
  - A read-back mismatch or a transfer failure stops the run before the jump.
- **Admission:** the image must match a SHA-256 given on the command line,
  and it is checked before any device is opened.
- **Target:**
  - The role is fixed to `devkit`, and every open goes through
    `tools/bench_target.py` (`--usb-path`, `--devnum`; PR #177).
  - The FM-1's port `1-2` is refused, and a test proves it.
  - There is no FM-1 mode.
- **Logging:** each command's CDB goes to `commands.jsonl`, and the run's
  result to `receipt.json`.

The image itself touches only the UART1, clock, IOMAP and PORTB registers it
needs, the P33 port and the four boot-marker words. A test pins that set and
asserts that nothing in the eFuse controller or the `mkey` words is touched
[verified: `tests/test_ramtest_image.py`]. The register facts and their
sources are in the header comment of `firmware/ramtest/ramtest.c`.

## 2. Builds

```bash
LUNAR_BUILD_ID=m4-ramtest-3 LUNAR_SESSION=<label> \
  bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> ramtest
# -> build/jieli-ramtest/: ramtest.elf, ramtest.bin, map, disasm, audit_link.json, report.json, sha256.txt
```

- **Toolchain:** `clang version 4.0.1 () ()`, the JieLi pi32v2 build already
  used for the soak images [verified: `toolchain.txt`].
- **Reproducible:** two builds from commit `c3116000` in separate scratch
  directories gave identical outputs [verified]:
  - `ramtest.bin`: `74104cb2bb60a8c58479b62ff454f09aaac12beb944a793efaf24f1e84dcca5b`, 1,840 B;
  - `ramtest.elf`: `d1a68cadd6b549b6fcdfd40589f1c9218b33f23e537ddf27be4b9a3c9452dca8`;
  - `audit_link.json`: passed, `runtime: sdk-free`, 0 failures, 0 pending.
- **Layout:** the image ends at `0x01C02730`. Its stacks reach `0x01C04750`.
  All of it sits inside the 16 KiB `[0x01C02000, 0x01C06000)` that `app.ld`
  asserts [verified: `report.json`].
- **Run 1 used an earlier build.** That was build `m4-ramtest-2` from commit
  `ed8b7486`:
  - `ramtest.bin`: `327a6e84a130d4148d2d81d6159e5c747dc77bc5e3c2e9f6561151a2cd2e4259`;
  - `ramtest.elf`: `285e38eddd6f14999e88fb311ca1e5b5a5d5e5f969d0d3e2040765bfc7074bc9`;
  - it also built identically twice [verified];
  - the only change since is that a dead UART now costs one timeout rather
    than one per byte.
- **Run 1 also used the earlier runner,** `tools/ram_runner.py` at
  `ed8b7486`. Run 2 used the one at `c3116000` (SHA-256 `b855c1e9…`, the copy
  staged on the bench host) [verified: hashes]. The opcodes, addresses and
  argument bytes sent are the same in both logs; only block 4's CRC differs,
  because the image differs [verified: both `commands.jsonl`]. Run 1's log
  labels each command with the stage after it rather than at request time,
  so its last write reads `verify`, its last read `jump` and the jump
  `done`; `c3116000` fixed that labelling.

## 3. The two runs on the dev kit

Same sequence both times, all unattended, no button pressed:

1. **Check the app is up.** `tools/devkit_boot_control.py` (PING):
   acknowledged. No other process held the Tigard.
2. **Enter the ROM.** `tools/devkit_boot_control.py --enter-uboot`: the app
   acknowledged ARM/ENTER over the Tigard UART.
   - `4c4a:8057 WL80UBOOT1.00` appeared within about 1 s at sysfs path
     `3-1.2`, `/dev/sg0`.
   - That `/dev/sg0` resolves to `3-1.2` [verified: sysfs].
3. **Start the capture.** `tools/devkit_uart_capture.py --seconds 150`
   started; it is receive-only, so it cannot send anything.
4. **Upload and jump.** The runner:

   ```bash
   sudo python3 tools/ram_runner.py run --device /dev/sg0 --usb-path 3-1.2 --devnum <n> \
       --image <image> --sha256 <sha256> --out <run>/runner
   ```

5. **Confirm the app is back.** After the capture: PING acknowledged by the
   freshly booted application.

| | Run 1 (`m4-a`) | Run 2 (`m4-b`) |
| --- | --- | --- |
| ROM entry acknowledged | 07:48:56 | 07:54:46 |
| ROM device | `3-1.2`, devnum 7, `/dev/sg0` | `3-1.2`, devnum 8, `/dev/sg0` |
| Image | `m4-ramtest-2`, `327a6e84…`, 1,840 B | `m4-ramtest-3`, `74104cb2…`, 1,840 B |
| INQUIRY | `WL82` / `UBOOT1.00` | `WL82` / `UBOOT1.00` |
| Upload | 4 × `FB06`, blocks at `0x01C02000`…`0x01C02600`, written range `[0x01C02000, 0x01C02800)` (image padded to whole blocks) | same |
| Read-back | 4 × `FD07`, equal | same |
| Jump `FB08 0x01C02000 arg 1` | no answer; `SG_IO` host status 7 after 3,888 ms | no answer; `SG_IO` host status 3 after 3,897 ms |
| Runner exit | 0 | 0 |
| `4c4a` device 8 s later | none | none |
| UART | banner, beats 1–10, `reset=app`, then the app's boot | same |
| PING after the capture | 07:51:42, acknowledged | 07:57:30, acknowledged |

The `commands.jsonl` of each run has 15 lines:

- the pinning record;
- 1 INQUIRY;
- 4 writes;
- 4 reads;
- 1 jump;
- 4 result events.

No other opcode appears [verified].

UART text of run 2, quoted from the capture [verified]:

```text
LUNAR_RAMTEST ready=1 build=m4-ramtest-3 entry=0x01c02000 bytes=1840 uart=uart1-pb3-1000000
LUNAR_RAMTEST beat=1
...
LUNAR_RAMTEST beat=10
LUNAR_RAMTEST reset=app
[00:00:00.100]========= system reset reason: SOFT =========
...
[00:00:00.128]LUNAR_CONTROL ready=1 rx=PA5 baud=1000000 protocol=1
```

### 3.1 What the runs show

- **Load-and-jump works on WL82's ROM** [verified, dev kit]. The ROM accepted
  `FB06` writes of a non-JieLi image into SRAM, `FD07` read every block back
  equal after deciphering, and `FB08` ran it from `0x01C02000`. Until now the
  ROM had only loaded JieLi's own loader (docs/18 §4).
  - What the read-back proves: the transfer, and no corruption on the way.
    It cannot by itself tell whether SRAM holds the plain image or the ROM
    kept the ciphered bytes, because both read back identically through the
    cipher [inferred: the cipher is its own inverse]. The image's own UART
    banner is what proves SRAM held the plain image [verified, dev kit].
- **`FB08` calls the image before it answers** [inferred]. The image never
  returns: it resets the chip. So the jump command never completed:
  - The kernel gave up after the runner's 3,000 ms `SG_IO` timeout plus its
    abort handling. That is 3.9 s in both runs, with a different host status
    each time (7 `DID_ERROR`, 3 `DID_TIME_OUT`).
  - The runner records that as `answered: false` and does not retry.
  - A RAM image that never returns should end this way on any host
    [inferred].
- **The image's own reset lands in the application** [verified, dev kit]:
  - the app reported `system reset reason: SOFT`, booted, and answered PING;
  - no ROM device remained.
- **Clearing the boot marker may not be needed** [inferred]. The image clears
  the 16-byte `usb_update_mode` marker at `0x01C7FD80` before the reset. It
  was not tested whether the ROM or the SPL would read it otherwise.
- **The CPU clock under the ROM is not known.** The heartbeat pause is an
  uncalibrated spin, so the beats prove progress, not timing.
- **The application was not changed** [verified: no flash command was sent].
  The installed application is another lane's fail-open test build
  (`7030c637`). Its own boot counter took each reset as a boot:
  - on the first boot it hangs on purpose (`irq_hang`, watchdog);
  - on the second it is healthy (`LUNAR_FAILOPEN healthy=1`);
  - that is how that build is designed to behave. Its counter `boots` went
    2→3 in run 1 and 4→5 in run 2.
- **The reset adapter was not used.** The fixed-loader reset adapter
  (`tools/devkit_loader_reset.py`) was not needed: the image resets the chip
  itself.

Evidence is private, in the session scratch (`uart.log`, `uart.json`,
`receipt.json`, `commands.jsonl` for both runs) and in the run directories on
the bench host. Nothing from it is committed beyond what is quoted here.

## 4. The same load-and-jump on the FM-1 through the Pico 2 W (desk study)

From FM-1-transporter's source only (kurogedelic, MIT). The project pins
upstream `a7fb5e8` plus our RP2350 patch (docs/17); the reference clone is at
`80c5012`, which is `a7fb5e8` plus that patch upstreamed. All facts below are
[verified: source at both commits] unless marked.

### 4.1 How it works

- **The Pico is a USB host for the FM-1.** It drives USB_KEY, and then the
  FM-1's ROM (`4c4a:8057`) enumerates on the Pico's PIO USB host. The ROM
  never enumerates on the bench host, so the bench host is not bridged to
  ROM USB. It talks to the Pico, which issues the SCSI commands itself
  (`src/pio_host.c`, bulk-only transport).
- **The bench host sees only the Pico,** as `2e8a:000a` "FM-1 Transporter"
  with two CDC ports:
  - interface 0 is the console;
  - interface 2 is the data port, which `fm1t.py` uses (`src/usb_device.c`).
  - `tools/bench_target.py` pinning does not apply on this route: the target
    is chosen by the Pico's `/dev/serial/by-id/...-if02` path.
- **Data-port commands for RAM runs** (`src/transporter_proto.c`):
  - `memw <addr> <len> <crc32>` then `len` raw bytes, 1–4,096 bytes. The
    Pico checks the CRC-32 and splits the data into ≤512-byte ciphered
    `FB06` writes.
  - `memr <addr> <len>` answers `DATA <len>`, the bytes, then `END <crc32>`,
    from `FD07`.
  - `jump <addr> <arg>` is one `FB08`. It replies `OK ms=…` or
    `ERR jump ms=…`.
  - All three refuse with `ERR loader-running` once the flash loader has
    been started.
  - **None of them bounds the address:** the firmware will write any RAM the
    ROM accepts.
- **Timing.** Each bulk transfer times out after 2,000 ms (`XFER_TIMEOUT_MS`).
  The loader resets the chip after about 3 s without a command, and the Pico
  sends keepalives, but only while the loader runs; plain ROM mode needs
  none.
- **What a non-returning image does.** `jump` is documented as for code that
  returns within about 2 s. A RAM image that never returns, such as M5's,
  will make `jump` reply `ERR jump ms≈2000` [inferred: the 2,000 ms transfer
  timeout, and §3.1's dev-kit behaviour]. That is the expected outcome, not a
  failure.
- **`fm1t.py ramrun`:**
  - It calls `ensure_uboot()`, refuses if the loader is running, and applies
    `--clear`/`--poke`.
  - It writes the image in 4,096-byte `memw` chunks, reads it back with
    `memr` and compares.
  - Then it calls `jump <addr> <arg>` (default address `0x1C02000`, default
    arg `0`), exits 1 on anything but `OK`, and only then does any `--read`.
- **`ensure_uboot()` sends the soft key.** It does nothing when the
  transporter already reports `uboot=1`. But if no UBOOT is up and a V15 is
  mounted, it sends the `uboot` request, and the transporter answers that
  with the soft key `F0 22 24 35 7D F7`. That is the path D2 bans while a
  running V15 is attached (docs/17 §8).
- **`dump` and `info` need the loader,** which lives at `0x1C02000`, the
  same address as a RAM image. Once the loader has run, `memw`/`memr`/`jump`
  are refused until a fresh ROM entry.

### 4.2 What must be patched before M5 (host side, `fm1t.py`)

Keep the docs/17 UF2 (`4f5fab3f…`) unchanged, so the transporter firmware
stays the one already proven on this unit. Patch only the host tool, as a new
file under `tools/fm1-transporter/`, reviewed like the shim:

1. **Never send the soft key.** Replace `ensure_uboot()` with a check that
   exits unless `status` reports `uboot=1`. Never send `uboot`, and refuse
   the `uboot` subcommand. ROM entry is by USB_KEY only (docs/17 §4: FM-1
   off, `rekey`, FM-1 on).
2. **Bound `ramrun`:**
   - the address is fixed at `0x01C02000`;
   - the image must end at or before `0x01C06000` (the M5 link budget,
     inside the 24,064-byte loader window);
   - the image's SHA-256 is required on the command line and checked before
     the port is opened;
   - `--clear`, `--poke` and `--read` are refused;
   - `arg` is fixed at 1, the value the ROM honoured on the dev kit and the
     value the transporter itself uses for the loader (`LOADER_ARG`).
3. **Treat the jump result correctly.** Treat `ERR jump` after about 2 s as
   "image running, ROM gone", and never retry the jump or any `memw`.
4. **Keep the loader out of the run.** Refuse `--loader` and an
   `FM1T_LOADER` in the environment for `ramrun`, so the loader is never
   uploaded in the RAM-run session.
5. **Log each line sent and received** to a receipt, as `ram_runner.py` does.

The firmware itself could also bound `memw` to the window and drop `uboot`
and the console `k`. That changes the UF2 and its proven hash, so it is not
proposed for M5.

## 5. M5 run plan, for owner approval

Milestone M5 (docs/18): the first Lunar code on the FM-1, from RAM only. This
is a plan. **Nothing in it has been run, and it needs a fresh owner yes**
(docs/18 §4: using docs/17's route to enter the ROM for Lunar RAM runs is
beyond the V15-shim approval; docs/07 §4 approval naming image, ranges and
recovery).

**Image.** `firmware/m5/` from PR #179 (merged at `532510b1`), built with:

```bash
LUNAR_BUILD_ID=m5-plan-1 LUNAR_SESSION=<label> \
  bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> m5-test-pattern
```

- **Output:** `m5.bin`, 4,160 B, SHA-256
  `a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4`.
- **ELF:** `adb1358b3d9bc12a09a80f844b8fd6ec64d51856cba5869a629ff39f45c2c969`.
- **Reproducible:** two builds in separate scratch directories gave the same
  output [verified].
- **Pinned to this build id:** the hash depends on `LUNAR_BUILD_ID`, so the
  build id above is part of the approval.
- **Audit:** `audit_link.json` passes `sdk-free`.

**Address ranges, all SRAM:**

- **Written by `memw`:** exactly `[0x01C02000, 0x01C03040)`, the image, in
  two `memw` chunks (4,096 B + 64 B), as 9 `FB06` blocks.
- **Used at run time:**
  - `.bss` `[0x01C03040, 0x01C03118)`;
  - stack `[0x01C03120, 0x01C04130)`;
  - SSP stack `[0x01C04130, 0x01C05140)`;
  - nothing at or above `0x01C05140` [verified: `report.json`, map].
- **Inside proven ground:** all of this lies inside
  `[0x01C02000, 0x01C07E00)`, where the ROM already loaded and ran JieLi's
  loader on this unit on 2026-10-26 [verified: recovery note].
- **No flash command is sent,** and the loader is not uploaded in the RAM-run
  session.
- **What the image touches:** the M5 image writes SFRs only for PA2, TIMER4,
  SPI1, the matrix GPIOs and the LED lines (`firmware/m5/README.md`).
  - The register list is in the board-layer note.
  - M5 does not set clocks and does not touch P33 or eFuse [reported: PR
    #179's `audit_link.py` and its tests].

**Sequence.** Three separate ROM entries, because `dump` needs the loader at
the same address. The FM-1 is off at every `rekey`, so no V15 runs while the
transporter is attached:

1. **Dumps before.** FM-1 off; `rekey`; FM-1 on; UBOOT ready.
   - `fm1t.py --loader … info` must show `key=980F type=3 id=856014`;
   - `dump before-A.bin`;
   - `dump before-B.bin --compare before-A.bin`;
   - the two must be identical.
   - Patched host tool (§4.2), so no soft key can be sent.
2. **Power off.** FM-1 off. The loader is gone with the power
   [inferred: SRAM].
3. **RAM run.** `rekey`; FM-1 on; UBOOT ready. Run the patched
   `ramrun m5.bin --sha256 a60410de…`, without the loader:
   - `memw` ×2, `memr` ×2 and a compare, then one `jump 0x1C02000 1`;
   - expected reply: `ERR jump ms≈2000`.
   - **Watch the unit:** the test pattern with `m5-plan-1` on the TFT, and
     the LEDs blinking `step` times (6 = everything ran; README above).
   - Photograph both.
4. **Power off.** FM-1 off. SRAM is lost and the image with it [inferred].
5. **Dumps after.** `rekey`; FM-1 on;
   - `dump after-A.bin`, which must equal `before-A.bin` byte for byte;
   - FM-1 off.
6. **Normal boot.** FM-1 on without the key: V15 boots.
   - The read-only identity query (D4) must read `FM-1_015`.
   - Disconnect the Pico wires (docs/17 §8).

**Recovery:**

- **A power cycle returns V15.** Nothing was written to flash, so the next
  normal power-on boots the stock application [inferred: RAM-only image,
  confirmed on the dev kit, §3].
- **If V15 does not boot:** docs/17 is the fallback. That means USB_KEY, two
  dumps, compare against `before-A.bin` and the 2026-10-26 images, and a
  stock V15 write, only on the owner's go-ahead.
- **If the TFT stays dark:** the run has still proven nothing harmful. Power
  off and continue with step 5.
- **A stop condition at any step** (identity not `980F/856014`, dumps
  differing, any reply but the expected ones): power off and stop; do not
  retry.

**Open points for that session:**

- **The reported power-switch behaviour:** whether the FM-1's switch cuts
  the SoC completely while the battery is in. docs/17's keying already
  depends on it [reported: owner's 2026-10-26 run].
- **Whether the ROM's own work RAM overlaps the M5 stacks.** It did not
  overlap the loader's 24,064 B, which is the same window [inferred].
- **The transporter's behaviour after an unanswered `jump`:** whether the
  Pico recovers its host stack cleanly once the device vanishes. Recovery
  of the Pico is a re-plug or `rekey`, which reboots it [inferred].

## 6. Review (2026-11-09)

An adversarial review of PR #184 re-checked the claims above without
touching any device:

- **Rebuilds match** [verified]. `ramtest` from `c3116000` with
  `LUNAR_BUILD_ID=m4-ramtest-3` gave `ramtest.bin` `74104cb2…` and
  `ramtest.elf` `d1a68cad…`; `m5-test-pattern` from the PR head with
  `LUNAR_BUILD_ID=m5-plan-1` gave `m5.bin` `a60410de…` and `m5.elf`
  `adb1358b…`. Both audits passed (12 checks each). The image layouts are
  as stated in §2 and §5 (symbol tables).
- **Run evidence** [verified: read on the bench host]. Both
  `commands.jsonl` files have 15 lines and only `12`, `FB06`, `FD07` and
  `FB08` CDBs; both receipts say `readback: equal` and `answered: false`
  (host status 7 after 3,888 ms, 3 after 3,897 ms); both UART logs have the
  banner, beats 1–10 and `reset=app`, then `reset reason: SOFT`; the
  fail-open counter read `boots=2`→`3` and `4`→`5`. The bench copies of both
  images hash to the values in §2.
- **Fixed in review:** syscmd frames refused by name and tested; the
  inherited flash-reader methods refused; a read-back error branch that
  could never run removed; the read-back claim qualified (§3.1); a wrong,
  skipped baud-rate test row corrected; `app.ld`'s comment said 8 KiB where
  it reserves 16 KiB. None of these changes the bytes a run sends, which
  `test_full_run_uploads_verifies_and_jumps_once` pins; the runner was not
  run again on the kit.
- **Pinning's reach.** Exact `3-1.2` now binds every dev-kit-role ROM tool,
  not only this one: `devkit_flash_backup.py` and the tools built on it
  (`devkit_flash_transaction.py`, `devkit_loader_reset.py`). If the kit's
  ROM device ever enumerates on another port they refuse, and the new port
  must be observed and recorded in `tools/bench_targets.json` first.

## 7. Not done

- Nothing was sent to the FM-1 or the Pico; §4 and §5 are desk work.
- The patched `fm1t.py` of §4.2 is specified, not written.
- No timing or clock measurement under the ROM.
- The fixed-loader reset adapter path was not exercised in these runs.
