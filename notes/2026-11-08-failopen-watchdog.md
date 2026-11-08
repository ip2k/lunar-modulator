# Fail-open boot and watchdog on the AC79 dev kit (M7), 2026-11-08

**Result:** a build that keeps failing now gets back to mask-ROM `UBOOT1.00`
by itself, with no dongle, no button and no host command. On the dev kit a
deliberately failing image booted three times. It failed by P33 reset, by
watchdog and by a stalled task, and on the fourth boot it entered UBOOT
[verified: dev kit]. A fixed image installed from that ROM state ran, marked
itself healthy and answered UART PING [verified: dev kit]. Nothing ran on the
FM-1. Power-cut tests are pending, because they need a person at the bench.

Scope: docs/07 §4 rule 4 (fail-open path plus a watchdog-backed failure
counter) is implemented and tested on the kit. Rule 5 (power loss at every
update stage) is not tested yet; see Pending.

## 1. Design

| Part | Where | What it does |
| --- | --- | --- |
| Core | `firmware/failopen/failopen_core.{c,h}` | Pure C, no SDK. Holds a 32-byte record (magic, build id, count, boots, last reset reason, fault, flags, FNV-1a check) and the boot decision. Also has the heartbeat monitor. |
| SDK glue | `firmware/failopen/failopen_sdk.{c,h}` | The `setup_arch` hook, the ROM entry, the `app_main` stage, the supervisor task, the heartbeat API, and a weak key-combination hook. |
| Test worker | `firmware/devkit/failopen_worker.c` | Picks a deliberate fault from the boot count (`cycle` or `recover` mode). |
| Preparer | `tools/jieli/prepare-failopen-devkit.py` | Builds on `prepare-devkit.py --boot-control`. Patches `setup.c`, the linker script, `app_main.c` and the Makefile, then writes the receipt. |
| Tests | `tests/test_failopen_core.py` | Host C harness (ASan and UBSan) for the record and the monitor. Also tests the preparer against a fake SDK and checks for banned calls. |

**Boot decision.** It runs in `setup_arch()`, right after the SDK's
`wdt_init(0xc)` and `debug_uart_init()`. The SDK ignores the value returned by
`system_reset_reason_get()`, so the preparer rewrites that one line as
`lunar_failopen_early(system_reset_reason_get())`. The record starts again
in four cases:

- it is invalid;
- the reset reason has `VDDIO_PWR_ON` or `VDDIO_LOW_PWR` set;
- the build id differs from this image's;
- the running build has reported itself healthy.

Otherwise each boot increments `count`. When `count` has reached `limit`
(3), the decision is FALLBACK. The decision stays FALLBACK until power-on, a
new build or a healthy mark.

**Two stages of ROM entry.** On FALLBACK the glue first tries ROM entry from
`setup_arch`, and records that it tried. If that boot ever comes back to
the same point, the glue skips the early stage. It enters ROM at the top of
`app_main` instead, from the task context the UART control already
verified. The early stage worked on the first try on the kit, so the
`app_main` stage has not been exercised on hardware.

**Where the record lives.** The preparer lowers `HEAP_END` by 64 bytes and
places `lunar_failopen_record` there. On this link that is `0x01C7FCEC`.
Neither `.bss` clearing nor the allocator touches it. `boot_info` (52 bytes
at `0x01C7FD4C`) and the UPDATA mailbox (`0x01C7FD80`) stay where the SDK
puts them. The record is inside the `.noinit` range Felucca reports as
surviving a reset, `0x01C7C000`–`0x01C7FD50` [reported: Felucca].

**ROM entry.** `failopen_enter_rom()` sits in `.volatile_ram_code`. It
disassembles, instruction for instruction, to the same sequence as the
verified `enter_rom()` of `boot_control.c`: `__local_irq_disable`,
`cpu_lock_cnt`/`lockset`, `csync`, then `call nvram_set_boot_state`, then
spin [verified: vendor `objdump`, both images]. The pinned `cpu.a` writes the
RAM USB-download marker and does a P33 reset. This answers the lane's
question of whether app code can enter UBOOT without breaking a rule. It can:
no eFuse write, no key, no loader command, no `-key`/`-mkey`, no V1.2.x
`uboot.boot`, SPL or loader (trap 11), and no soft-key SysEx. `audit_link.py`
passes on both images; details are in §3.

**Supervisor.** It is a task at priority 26 (above the app's 8–18), polling
every 100 ms. Tasks register with `lunar_failopen_watch(timeout_ms)` and call
`lunar_failopen_beat()`. When every registered slot has beaten and
`LUNAR_FAILOPEN_HEALTHY_MS` has passed, the supervisor clears `count`. The
default is 30 s, the same window SLOOP's boot guard uses [reported: SLOOP];
the test images use 10 s. A slot that misses its timeout makes the
supervisor record `FAULT_STALL+slot` and reset through P33.

The supervisor is needed because `CPU_TASK_SW` calls `wdt_clear()` on every
task switch, on both cores [verified: SDK `asm/cpu.h`]. A task that stops
working while the scheduler still runs never trips the hardware watchdog.
A build with no registered task never becomes healthy, so it falls back
after three boots. That is deliberate.

**Key combination.** `lunar_failopen_key_requested()` is a weak hook that
returns 0. The kit has no key matrix. The FM-1 build must override it with a
read of the matrix before USB starts (docs/07 §2.3). This part is not built.

## 2. Bench evidence (dev kit, 2026-11-08)

The protocol was the streamlined one. The kit was running the soak30 image.
The steps were:

1. UART `PING`, acknowledged.
2. Acknowledged `ARM` and `ENTER`.
3. A target check, then one install of `cycle` with no readback.
4. A receive-only UART capture of 180 s and a sysfs watcher sampling every
   0.1 s.
5. One FC0C loader reset, not retried.

Then a target check and one install of `recover`, a 90 s capture and one
reset. Last, a `PING`. There was no button press, no backup and no KA6
capture. The FM-1 got no traffic; the sysfs watcher logged it as `4c4a:c755`
at `1-2` throughout.

**Target safety.** The runner checked the target before the install and
again before the reset, and refused if any check failed:

- exactly one `4c4a:8057` on the host, at `3-1.2`;
- `1-2` still `4c4a:c755`;
- exactly one SCSI generic node, `sg0`, resolving under `3-1.2`.

Before each install the check printed
`{"kit": "3-1.2", "devnum": "5"|"6", "fm1": "4c4a:c755"}`.

| Image | Build id | Candidate SHA-256 | App bytes | Sectors |
| --- | --- | --- | --- | --- |
| `cycle` | `0x0064f631` | `83059014b5ea5fbd4cca729bafb318731c386a46aa7be609f9a5c832cf1484cf` | 169,776 | 42 (`0x4000`–`0x2d000`) |
| `recover` | `0x7030c637` | `6c2f763817a9d002925393e8546331b9b2fa3d1f68d67d09acc1f28f20185cd8` | 169,552 | 42 (`0x4000`–`0x2d000`) |

Both candidates are application-only: the base is factory-A, `127b2ebb…`,
and only the app sectors change. Both pass `audit_link.py` with 0 failures
and 1 pending item, `sdk_meky_check_scheduling`, which every SDK image
carries. `no_efuse_controller_access` passes on both. An earlier `recover`
build, made before the supervisor race fix, also flagged that check's
relative-operand heuristic at an offset inside the SDK's `__fat_unmount`,
not in our code.

### `cycle`: three failures, then UBOOT by itself

These are UART lines, abridged. The device's timestamps restart at every
boot.

```
reason=0x10 start=invalid   decision=run      count=1   (record was SRAM garbage, valid=0)
TEST count=1 action=exception   misaligned_read=0x0d36ff80 raised=0  div0=0x00000000 raised=0
                                backstop=exception_missed action=p33_reset
before ... count=1 boots=1 fault=0x81 valid=1
reason=0x10 start=continued decision=run      count=2
TEST count=2 action=irq_hang core=0
  exception_analyze DEBUG_MSG = 0x1 ... current_task : lunar_devkit
  exception reason : wdt_timout_err   system_reset...
before ... count=2 boots=2 fault=0x82 valid=1
reason=0x10 start=continued decision=run      count=3
TEST count=3 action=stall core=0     ...   stall=1 slot=0 beats=4 action=reset   (at 7.72 s)
before ... count=3 boots=3 fault=0x10 valid=1
reason=0x10 start=continued decision=fallback count=3
LUNAR_FAILOPEN entering=uboot stage=early
```

The sysfs watcher logged the following. The kit (`3-1.2`) disappeared at the
reset, 0.10 s after the request, and **came back as `4c4a:8057` 16.45 s
after the reset request, with devnum 5 → 6**. No host command was sent in
between [verified: `usb.jsonl`].

Findings [verified: dev kit, this capture]:

- **The counter survives a warm reset.** `count` climbed 1, 2, 3 across a P33
  reset, a watchdog reset and a supervisor reset. The record also survived
  ROM mode, the fixed-loader upload, the 42-sector program and the FC0C
  reset: the `recover` image's first boot read the `cycle` record intact
  (`count=3 boots=4 flags=0x2 valid=1`) and then restarted it, because the
  build id differed (`start=build`).
- **Every reset reads `SOFT` (`0x10`).** This includes the reset after the
  FC0C loader reset, the P33 reset and the watchdog. The watchdog on this SDK
  shows up as a CPU exception (`DEBUG_MSG` bit 0, `wdt_timout_err`), and
  `exception_analyze()` then resets through software. So the reason bits never
  show `WDT` (`0x4`) here, and a design must not rely on them.
  `system_reset_reason_get()` called again in `app_main` returns the same bits
  as the call in `setup_arch`.
- **One core hanging with IRQs off does trip the watchdog**, even though the
  other core stayed up. The test task ran on core 0 and `app_main` on core 1.
  `CPU_CRITICAL_ENTER` also takes the cross-core `lockset`. The backstop (at
  least 6.25 s) never ran. The device's millisecond clock stops while core 0
  has interrupts off, so the log cannot time the watchdog. The 16.45 s total
  for four boots is consistent with the SDK's 4 s setting [inferred].
- **A misaligned word read and an integer division by zero do not trap** in
  this configuration. The read returned data and the division returned 0. Boot
  1 therefore tested the P33 backstop, not the SDK exception path. The
  exception path itself was exercised by the watchdog in boot 2.
- **ROM entry from `setup_arch`, before the OS starts, works.** The early
  stage entered UBOOT on its first attempt.

### `recover`: the kit returns to the app

```
before ... build=0064f631 count=3 boots=4 last_reason=0x10 fault=0x10 flags=0x2 valid=1
reason=0x10 start=build decision=run count=1 build=7030c637
TEST count=1 action=irq_hang  ->  exception reason : wdt_timout_err  system_reset...
reason=0x10 start=continued decision=run count=2
TEST count=2 action=healthy
LUNAR_FAILOPEN healthy=1 count=0 uptime_ms=10120
TEST alive=1 count=0 ms=12130 ... ms=82130   (every 10 s until the capture ended)
```

After the capture, `tools/devkit_boot_control.py` returned `Diagnostic PING
acknowledged` [verified]. The kit was left running this image, with UART
boot control, for the next lane.

## 3. Checks run

- `python -m pytest tests/test_failopen_core.py`: 4 passed. The cases are
  the host C harness under `-fsanitize=address,undefined`, the preparer on a
  fake SDK, refusals on an unknown layout, and a source scan for banned calls.
- The full suite was run before the PR; the counts are in the PR body.
- Builds ran on the build host with `lunar-jieli-check:bookworm` and
  `docker run --rm --network none`, labels `project=lunar-modulator
  session=fm1-wave1-failopen`. The SDK was AC79 V1.2.13 (`cpu.a` SHA-256
  `fe18129b…`, the same as the `e30b1ee` sparse checkout). The preparer's
  receipts carry every input hash.
- `tools/jieli/audit_link.py --elf`: PASS on both images (0 fail, 1 pending:
  `sdk_meky_check_scheduling`, the standing objdump item).
- Vendor `objdump` checks:
  - `setup_arch` calls `wdt_init`, then `system_reset_reason_get`, then the
    inlined fail-open decision, then the early `failopen_enter_rom` call;
  - `app_main` has the second call site;
  - `lunar_failopen_record` and `HEAP_END` are both `0x01C7FCEC`.

## 4. What this does not show, and what is pending

- **Power-cut tests (docs/07 §4 rule 5) are pending. They need a person**
  to remove power at each update stage: during the install, between the
  install and the reset, and during each failing boot. A power-on resets the
  counter by design (`start=cold`), so a power cut during a failing boot
  starts the count again. It does not need to fall back sooner. Not tested.
- **On the FM-1 the counter is only inferred to survive.** The FM-1 boots
  through the stock V1.1.9 SPL, not the kit's. Felucca reports that the same
  RAM range survives there [reported]. Check this on the first RAM-only Lunar
  run on the FM-1 (D3). Ending in UBOOT with no USB host attached
  (does ROM wait for ever, or time out and re-boot?) is also unverified. On
  the kit a host was attached every time.
- **The `app_main` ROM-entry stage has not run on hardware.** The early
  stage worked on its first try.
- **The key-combination path is a hook only.**
- **The real SDK exception path from a code fault** (bus error, illegal
  instruction) was not triggered. Only the watchdog's exception was.
- **Reaching the stock OTA updater is out of scope.** Fallback lands in mask
  ROM, which a host recovers through UBOOT. An updater over USB-MIDI needs a
  USB-MIDI class the SDK does not have; that is M12 scope [reported].

## 5. Community facts used (facts only, nothing copied)

These are recorded in `notes/2026-10-05-community-repos.md` §3.6 and docs/07
§2.3:

- Felucca keeps a `.noinit` range near the top of RAM across resets, and
  uses the `usb_update_mode` mailbox at `0x01C7FD80` followed by a P33 reset
  [verified there: Felucca source].
- SLOOP's boot guard clears on power-on and after 30 s healthy. Two failed
  early boots lead to its USB rescue mode, then to UBOOT [verified there:
  SLOOP source].
- fm1-nes enters UBOOT through `go_mask_usb_updata()`, which uses the same
  `nvram_set_boot_state(2)` as Lunar [reported].

Felucca and SLOOP are GPL-3.0-only; none of their code is in this change.

## 6. Data on disk

- Bench host, `~/lunar-failopen-2026-11-08/`: captures (`uart.bin`,
  `uart.json`), `usb.jsonl`, the install and reset JSONL logs and the PING
  logs, all kept as evidence. Also kept: the runner (`tools/failopen-run.py`,
  which does the target check, install, capture, sysfs watcher and one reset)
  and the copied iteration tools. The candidate images and the copy of the
  fixed loader were deleted after the run.
- The build host's scratch (`/datasets/lunar-modulator/fm1-wave1/failopen/`)
  was deleted once this note was written. It is reproducible from the
  preparer, the pinned SDK, factory-A and the application-only export
  recipe.
