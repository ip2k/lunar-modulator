# Fail-open hardening after the PR #180 review (M7), 2026-11-08

**Result:** all seven findings are fixed, each with a desktop test. Five
(1, 2, 3, 5, 6) also passed on the AC79 dev kit, unattended, on 2026-11-09
08:03–08:12 UTC [verified: kit UART captures and the host's USB timeline,
§3]. Fix 4 was checked by negative links on the build host (§2), and fix 7 is
logged on the kit (below). On the kit:

- the three failing boots of PR #180 again ended in mask-ROM UBOOT by
  themselves;
- a build that crashed after healthy fell back after three cycles;
- a missing registration and a too-short timeout were caught;
- four racing registrations and 102,400 locked record writes from both cores
  left the record valid;
- every boot's image id equalled the host's hash of its `app.bin`.

Finding 7 is only partly answered: the raw reset registers are logged, but
the kit could only produce warm resets, so whether `P3_RST_SRC` bit 0 marks
a power cut waits for the owner's power-cut test (§6).

This note follows `notes/2026-11-08-failopen-watchdog.md` (PR #180), which
holds the design and the first kit run. It covers the seven review findings,
each fix and its test, the rerun on the AC79 dev kit, the flash-erase bounds,
what the reset registers can and cannot tell, the power-cut script for the
owner, and the open owner decision. Nothing ran on the FM-1, and nothing was
sent to the Pico 2 W transporter.

## 1. Findings and fixes

| # | Finding | Fix | Desktop test | Kit test |
| --- | --- | --- | --- | --- |
| 1 | The build id hashed only the fail-open sources, so a changed app, SDK library or link kept the old counter | The image hashes itself at boot: FNV-1a over `.text` through the load image of `.cache_ram_data`, read through XIP (`text_begin` to `cache_ram_data_lma + cache_ram_data_size`). That is exactly the flat `app.bin` the export writes [verified: export asserts the sections are contiguous]. `tools/jieli/failopen_image_id.py` gives the host value | `test_core` checks the C hash against the Python tool on a vector and on a one-bit change | every boot prints `image=… bytes=…`; compared with the host value of each `app.bin` (§3) |
| 2 | Registration was optional: an image with fewer registered tasks than intended could still be marked healthy | `LUNAR_FAILOPEN_EXPECTED_SLOTS` is required (`#error`). At the healthy time a slot count other than expected, expected 0, or any refused registration is `UNREGISTERED`: the supervisor records fault `0x20` and resets | `registration()` in the harness: none, fewer, more, refused, expected 0, stall wins | `escalate` boot 1 |
| 3 | Slot registration and record writes had no lock | Every core function that changes the record or the monitor (boot, claim, healthy, stable, fault, key, init, add, beat, poll) runs between `lunar_failopen_lock()` and `_unlock()`, which the platform must define (no weak default). The SDK glue uses `CPU_CRITICAL_ENTER`/`EXIT` | instrumented lock in `test_core` (every entry point takes it, balanced); `test_lock_under_thread_sanitizer`: 6 threads and a poller under TSan, plus a no-lock control that TSan must flag | `recover` boot 2: four racing registrations, two tasks rewriting the record for 2 s |
| 4 | Nothing checked the record's placement at link time | Five `ASSERT`s appended to the linker script: the record is at `0x1c00000 + RAM0_SIZE - 32 - 64`, at or above `_HEAP_END`, ends at or below `ORIGIN(boot_info)`, the heap is not negative, 4-byte alignment. A compile-time check keeps the record within its 64 bytes | `test_preparer` checks the text; the preparer refuses a script without `ORIGIN(boot_info)` | negative links on the build host (§2) |
| 5 | A build that reached healthy and then crashed reset its counter each time and looped forever | Record `LFO2` adds `cycles`: each healthy mark adds one, a stable mark (default 300 s up, 30 s in test images) clears it. `cycles >= limit` is FALLBACK, as sticky as `count` | `escalation()` in the harness | `escalate` boots 2–5 |
| 6 | Heartbeat timeouts could be shorter than a flash erase, which stalls every core running from flash while the clock counts | `LUNAR_FAILOPEN_MIN_TIMEOUT_MS` (3000) refuses shorter timeouts, and a refusal counts against registration (fix 2). §4 has the bound | `test_min_timeout_covers_flash_erase`; refusals in `monitor()` | `escalate` boot 1 asks for 100 ms |
| 7 | Cold-start detection relied on the SDK's reason, which ranks SOFT above power-on and caches its answer | The `setup_arch` hook now replaces the SDK's call. It reads `JL_SYSTEM->RST_SRC`, `P3_RST_SRC`, `P3_PMU_CON1` and `R3_WKUP_SRC` raw, then calls the SDK. Raw `P3_RST_SRC` bit 0 or 1 now also counts as cold. All values are logged. §5 has what this can and cannot prove | `test_sources_avoid_banned_paths` checks the order | every boot logs the raw values (§3) |

Old `LFO1` records (PR #180 images) fail the new magic and checksum, so the
first boot of a new image starts afresh (`old_record()` in the harness).

### The lock, in detail

`CPU_CRITICAL_ENTER` in the pinned SDK is `sys_local_irq_disable()`. LTO
inlines it as `cli`, a per-core `irq_lock_cnt` increment, a per-core
`cpu_lock_cnt` increment and, on the first level, `lockset`, the cross-core
hardware lock. `EXIT` undoes these and executes `sti` when `irq_lock_cnt`
returns to 0 [verified: vendor `objdump` of `lunar_failopen_lock`/`_unlock`
and `__local_irq_enable` in the linked `cycle` image]. That last point
matters in `setup_arch`, where interrupts are off and are not ours to turn
on, so the glue's lock does nothing until `lunar_failopen_app_start`. Until
then one core runs and no task or interrupt touches the record.

The heartbeat takes the lock too. In the first version it was lock-free; a
beat is a few stores, and TSan would otherwise report the beat/poll race
as a real data race, which on two cores it is.

## 2. Images

Built on the build host in `lunar-jieli-check:bookworm` (no network, labelled
`project=lunar-modulator`, `session=wave2`), from commit
`44c33658` of this branch, limit 3, healthy 10 s, stable 30 s.

| Image | Slots | Candidate SHA-256 | App bytes | Image id (host) | Sectors |
| --- | --- | --- | --- | --- | --- |
| `cycle` | 1 | `72a215453b5baad431d84a81225098f9aab616788b6db1fb12f89ecb8a7d8179` | 170,768 | `2068c52c` | 42 |
| `escalate` | 2 | `f6665ab6fd98e49a951b3e8a2c33a98b9ee480b7fedffd13f4938c587272cd23` | 170,608 | `3891f514` | 42 |
| `recover` | 4 | `be4963e120c909db0738b0a020fc312e41e11a14a48e684ba3fc041e352a3521` | 171,312 | `51f2e81a` | 42 |

All three [verified: build host]:

- are application-only on factory-A `127b2ebb…`;
- place `lunar_failopen_record` at `0x01C7FCEC` = `_HEAP_END`;
- pass `audit_link.py --elf` with 0 failures and the usual one pending item
  (`sdk_meky_check_scheduling`).

In `setup_arch`, the hook's raw reads of `P3_RST_SRC` (`0x12`) and
`P3_PMU_CON1` (`0x31`) come before the SDK's own reads and before its
`p33_or_1byte(0x31, …)` [verified: `objdump` of `cycle`].

**Negative links.** Two copies of the `cycle` tree were changed and relinked
[verified: build host]:

- record moved to `- 32 - 48`: `ld: lunar_failopen_record moved`, no ELF;
- `_HEAP_END` restored to `- 32` with the record left in place:
  `ld: lunar_failopen_record overlaps the heap`, no ELF.

The vendor Makefile does not relink when only `sdk_ld_sfc.c` changes. The
first attempt "linked" because the old ELF was kept, and only deleting
`sdk.elf` forced the check. The build script always builds a fresh tree, so
the asserts run on every real build.

## 3. Bench rerun (dev kit, 2026-11-09 UTC)

Run on 2026-11-09 between 08:03 and 08:12 UTC, after another lane's RAM-runner
session had released the kit (no process of it for five minutes). Sequence,
every step separate and unattended, with no button presses:

1. UART `PING`, acknowledged by the running app;
2. acknowledged UART `ARM`/`ENTER` into ROM; the kit enumerated as
   `4c4a:8057` at port `3-1.2`;
3. for each image: an application-only install (147 sector erases, 11.5–11.6 s),
   a receive-only UART capture plus a 0.1 s sysfs watcher of the kit's and
   the transporter's ports, and **one** loader reset, never retried;
4. a final `PING` after the last capture had exited, acknowledged.

Every ROM operation was pinned to the kit (`target_pinned role=devkit
usb_path=3-1.2` in each `install.jsonl`, PR #177's tools) under an exclusive
lock on the kit, after checking that `3-1.2` was the only JieLi device and
port `1-2` was the Pico 2 W transporter (`2e8a:000a`). The transporter's
serial ports were never opened, and its enumeration did not change in any
watcher log. The FM-1 was not connected.

Device timestamps below are the kit's own UART log times. The four
`setup_arch` lines all read `00:00:00.100`, because the clock is not running
yet there.

### `cycle` (1 slot, 90 s capture): the PR #180 rerun

| Boot | Raw `rst_src` / `p3_rst_src` / `p3_pmu_con1` | Record found | Start, decision | What the test did | Ended by |
| --- | --- | --- | --- | --- | --- |
| 1 | `0x20` / `0x40` / `0x80` | `valid=0`, left by the other lane's RAM images | `invalid`, run, count 1 | misaligned read and divide by zero at 2.13 s; neither raised | software backstop (`exception_missed`), P33 reset |
| 2 | `0x1` / `0x40` / `0x80` | this image, count 1, fault `0x81` | `continued`, run, count 2 | interrupts off at 2.13 s | hardware watchdog (no backstop line) |
| 3 | `0x1` / `0x40` / `0x80` | count 2, fault `0x82` | `continued`, run, count 3 | heartbeat stops at 2.13 s | supervisor at 7.72 s: `stall=1 slot=0 beats=4` |
| 4 | `0x1` / `0x40` / `0x80` | count 3, fault `0x10` | `continued`, **fallback** | — | `entering=uboot stage=early` |

The watcher saw the kit leave USB 0.10 s after the loader reset, and come back
as `4c4a:8057` at `3-1.2` (devnum 10) 16.45 s after it. So three bad boots
again ended in mask-ROM UBOOT by themselves.

### `escalate` (2 slots, 150 s capture): fixes 2, 5 and 6

| Boot | Record found | Start, decision | What happened |
| --- | --- | --- | --- |
| 1 | the `cycle` image's (`2068c52c`, count 3) | **`build`**, run, count 1 | `second=-1`: the 100 ms slot was refused. At 10.12 s: `unregistered=1 slots=1 expected=2 refused=1 action=reset` |
| 2 | fault `0x20`, count 1 | `continued`, run, count 2 | `healthy=1 count=0 cycles=1` at 10.12 s; deliberate reset at 12.13 s |
| 3 | count 0, cycles 1, fault `0x85` | `continued`, run, count 1, cycles 1 | `healthy=1 count=0 cycles=2`; reset at 12.13 s |
| 4 | count 0, cycles 2 | `continued`, run, count 1, cycles 2 | `healthy=1 count=0 cycles=3`; reset at 12.13 s |
| 5 | count 0, cycles 3 | `continued`, **fallback**, cycles 3 | `entering=uboot stage=early` |

The kit was back in ROM at `3-1.2` (devnum 11) 47.15 s after the loader
reset. Under PR #180 this image would have looped forever: each boot reached
healthy and cleared the count.

### `recover` (4 slots, 150 s capture): fix 3 and the way back

| Boot | Record found | Start, decision | What happened |
| --- | --- | --- | --- |
| 1 | the `escalate` image's (`3891f514`, cycles 3) | `build`, run, count 1 | four tasks registered at once: `race registered=4 slots=0,1,2,3 unique=1 cores=0x2`; interrupts off at 2.13 s; hardware watchdog |
| 2 | this image, count 1, fault `0x82` | `continued`, run, count 2 | race again: `registered=4 … unique=1 cores=0x2`. Two tasks rewrote the record for 2 s: `hammer=0 rounds=51200 bad=0 core=0`, `hammer=1 rounds=51200 bad=0 core=1`, then `lock rounds=102400 bad=0 valid=1`. `healthy=1 count=0 cycles=1` at 10.12 s; `stable=1 cycles=0` at 30.12 s; still alive at 134.14 s |

The kit stayed in the application (no ROM enumeration in the watcher) and
answered the final `PING`.

**What the race shows.** All four registrar tasks ran on core 1
(`cores=0x2`). So the registration race was settled between tasks on one
core, under preemption. The two record writers ran on different cores, so
the record lock was contended across cores: 102,400 locked writes and checks
left no invalid record. The SDK has no task-affinity API [verified:
`os_api.h`], so the core split is the scheduler's choice and is reported, not
forced. The cross-core case for registration is covered by the TSan test.

### Image ids [verified]

Every boot printed the same id and length as the host tool computed from that
image's `app.bin`:

| Image | Kit | Host |
| --- | --- | --- |
| `cycle` | `image=2068c52c bytes=170768` | `2068c52c`, 170,768 B |
| `escalate` | `image=3891f514 bytes=170608` | `3891f514`, 170,608 B |
| `recover` | `image=51f2e81a bytes=171312` | `51f2e81a`, 171,312 B |

The record survives an application install and the loader reset, because
SRAM keeps power. So the new image always found the previous image's valid
record, and the image id is what made it start afresh (`start=build`). The
first `cycle` boot found an invalid record instead. The other lane's RAM
images had overwritten the area, so the planned check against PR #180's
`LFO1` record did not happen on the kit; the desktop test covers it.

### Reset registers on warm resets [verified: kit UART, warm resets only]

| Reset | `JL_SYSTEM->RST_SRC` | `P3_RST_SRC` | `P3_PMU_CON1` | `R3_WKUP_SRC` | SDK reason |
| --- | --- | --- | --- | --- | --- |
| loader reset (ROM to app) | `0x20` | `0x40` | `0x80` | `0x0` | `0x10` |
| `cpu_reset()` (backstop, supervisor) | `0x1` | `0x40` | `0x80` | `0x0` | `0x10` |
| hardware watchdog (interrupts off) | `0x1` | `0x40` | `0x80` | `0x0` | `0x10` |

- `P3_RST_SRC` bit 0 (power-on) was clear on all 11 warm boots, as the cold
  test needs.
- `P3_PMU_CON1` bit 6 read 0 on every boot, although the previous boot's SDK
  call had set it. It is not a sticky "this was a warm reset" mark.
- The watchdog and `cpu_reset()` read the same in every register. This
  suggests the SDK's watchdog ends in the same P33 software reset [inferred],
  rather than a separate hardware reset source.

## 4. Flash-erase bounds behind the 3 s minimum

A sector or block erase stalls every core executing from flash (XIP), while
the millisecond timer keeps counting. A heartbeat timeout shorter than the
longest erase the firmware issues would therefore report a healthy task as
stalled.

| Part | Where | Sector 4 KB | Block 32 KB | Block 64 KB | Chip | Page program |
| --- | --- | --- | --- | --- | --- | --- |
| Zbit ZB25VQ64C (JEDEC `5E 40 17`) | dev kit | typ 45 ms, max 400 ms | typ 0.15 s, max 1 s | typ 0.25 s, max 2 s | typ 30 s, max 100 s | typ 0.5 ms, max 2 ms |
| Puya P25Q80H (JEDEC `85 60 14`) | FM-1 | typ 8 ms, max 20 ms | typ 8 ms, max 20 ms | typ 8 ms, max 20 ms | typ 8 ms, max 20 ms | typ 2 ms, max 3 ms |

- Kit: [reported: Zbit ZB25VQ64C datasheet, preliminary V0.0]. The JEDEC id
  matches the family [verified: loader `online()` returns `0x5e4017`]. The
  "C" revision is [inferred] from the id.
- FM-1: [reported: Puya P25Q80H datasheet V1.7; the maximum was raised to
  20 ms in its V1.3]. The id is [reported] (CLAUDE.md hardware table).

**Measured on the kit** [verified: host timestamps in the three
`install.jsonl` logs of §3, 147 sector erases each, 441 in all]. The time
from the sector-erase command (`FB01`) to the end of the first page program
after it was (min / median / p90 / max):

| Install | Time |
| --- | --- |
| `cycle` | 59.4 / 60.6 / 61.8 / 63.0 ms |
| `escalate` | 59.3 / 60.4 / 61.7 / 63.6 ms |
| `recover` | 59.3 / 60.5 / 61.6 / 63.6 ms |

The PR #180 installs gave the same picture (59.2–64.1 ms). The figure covers
a 4 KB erase, one page program and the USB round trips, so it is an upper
bound on the erase. It sits inside the datasheet's typical-to-maximum range.
The `FB01` command itself returns in 0.21–0.45 ms, before the erase ends.

**The rule.** `LUNAR_FAILOPEN_MIN_TIMEOUT_MS` is 3000:

- the kit's worst block erase is 2 s;
- one 100 ms supervisor period comes on top;
- the rest is margin.

The FM-1 alone would allow far less, but one constant keeps the kit
representative. The firmware may issue only sector or block erases, never a
chip erase (up to 100 s on the kit), and must yield between them. A longer
erase sequence must also beat between erases. The first Lunar code that
writes flash (presets, M8+) must follow this.

## 5. What the reset registers tell

The SDK's `system_reset_reason_get()` (`apps/common/system/system_reset_reason.c`,
V1.2.13) [verified: SDK source, and the linked code]:

- reads `JL_SYSTEM->RST_SRC`, `P3_RST_SRC`, `R3_WKUP_SRC`, `P3_WKUP_PND`,
  `P3_PMU_CON1` and `P3_LP_TMR0_CON`;
- ranks wake-ups first, then SOFT (`RST_SRC` bit 5 or `P3_RST_SRC` bit 6),
  then the LP timer, and only then power-on (`P3_RST_SRC` bit 0) and
  low-power (bit 1);
- ends with `p33_or_1byte(P3_PMU_CON1, BIT(6))`, commented "clear the
  power-on flag";
- caches its answer in a static, so a second call returns the cached value.

Two things follow. First, PR #180's evidence that a second call "still
reports the same bits" showed the cache, not the register. Second, a power-on
that also has a SOFT bit set reads as SOFT. The first version would then have
kept counting across a power cut.

The hook reads the raw registers before the SDK does. It treats raw
`P3_RST_SRC` bit 0 (power-on) or bit 1 (low power) as cold, whatever the SDK
ranks first. On the kit, bit 0 was clear after all 11 warm resets (loader
reset, `cpu_reset()`, watchdog) [verified: §3]. Two things are still
[inferred] until the power-cut test (§6) runs:

- that bit 0 is set after a real power cut;
- what `P3_PMU_CON1` bit 6 reads after a power cut. The SDK sets it to clear
  the power-on mark, yet it read 0 on every warm boot (§3), so it does not
  separate warm from cold by itself.

If the power-cut test shows
bit 0 does not mark power-on, the limit stays: SRAM loss alone (an invalid
record) is the only cold-start evidence, so a short power dip that keeps SRAM
could be counted as a failed boot. That costs at most one extra fallback; it
never hides a failure.

`P3_RST_SRC` is also written by the SDK's `VLVD_RST_EN`/`VLVD_WKUP_EN` macros
(bits 2 and 3, under a `P3_RST_CON0` comment), so the read and write meanings
of the address may differ [inferred: `asm/p33.h`]. The hook only reads it.

## 6. Power-cut test script for the owner

This needs a person, because the kit's power has to be removed. It is
written for the dev kit; do not use it on the FM-1. Each step lists what to
look for in the UART log. Start a capture first:
`python3 tools/devkit_uart_capture.py --out pc-N.bin --seconds 600`, one per
step, on the bench host. Before each step note the time, so the log can be
matched.

1. **Cold boot of a healthy image.** With `recover` installed and running,
   unplug the kit's USB power for 10 s and plug it back.
   Expect `raw … p3_rst_src=` with bit 0 set, `start=cold`, `count=1 cycles=0`,
   then `healthy=1` and `stable=1`. Record `p3_pmu_con1`.
2. **Warm reset for comparison.** Run `tools/devkit_boot_control.py`
   (PING), then let the image run. No reset is needed: compare with any warm
   boot in this note's §3. Bit 0 should be clear on warm boots.
3. **Power cut during a failing streak.** Install `cycle`. As soon as the log
   shows boot 2 (`boots=2 … action=irq_hang`), unplug power for 10 s and plug
   it back. Expect `start=cold`, `boots=1`, and the full three-failure
   sequence again, ending in UBOOT (`4c4a:8057` at `3-1.2`). That shows a
   power cut does not carry a half-finished count into the next streak.
4. **Power cut while in fallback with no host.** After step 3 ends in UBOOT,
   unplug the kit's USB from the bench host and power it from a USB charger
   for 30 s. It cannot enumerate, so nothing will show. Then reconnect it to
   the host. Expect, in order:
   - a cold boot (the record restarts), so `cycle` runs its failures again
     and ends in UBOOT by itself;
   - with no host attached, mask ROM waits with no visible sign. It looks
     dead until it is plugged into a host, where it enumerates as
     `4c4a:8057`.
5. **Power cut during an install** (§4 rule 5). From UBOOT, start an
   application install of `recover`, and pull power while
   `devkit_fast_iteration` prints sector addresses. Reconnect and check:
   - the kit comes back as `4c4a:8057` by itself, because the half-written
     app fails to boot or its header check fails;
   - or, if the head sector `0x4000` was already rewritten (it is written
     last), the new image runs.

   Then install `recover` completely and confirm it boots. Record which
   sector was last printed.
6. **Brown-out (optional).** If a bench supply is available, lower the kit's
   supply slowly until it resets, then raise it. Expect raw `p3_rst_src`
   bit 1 and `start=cold`.

Send back the captures. The results decide whether `P3_RST_SRC` bit 0 stays
in the cold test (§5) and whether docs/07 §4 rule 5 is met on the kit.

## 7. Owner decision: defaults and behaviour with no host

**What is being decided.** The default limit (3), healthy time (30 s) and
the new stable time (300 s). Also whether a device in fallback with no USB
host attached may sit silently in mask ROM.

**Why now.** These defaults go into the first FM-1 flash image (M8). After
that, a user's unit falls back by itself when a build fails.

**Evidence.**

- The kit runs above show each limit works.
- SLOOP's boot guard uses 30 s [reported: SLOOP, via
  `notes/2026-11-08-failopen-watchdog.md`].
- The kit's application starts 0.125 s after a reset, and a crash cycle under
  the test settings took about 12 s [verified: UART timestamps in §3].
- Mask ROM cannot see whether a host is attached. With none, the device
  waits in UBOOT with a dark screen, and only a USB connection shows
  anything (`4c4a:8057`).

**Recommendation.**

1. Keep limit 3, healthy 30 s, and stable 300 s.
2. Accept silent fallback with no host. Document it in the user guide as:
   "if the screen stays dark after three failed starts, connect USB to a
   computer and open the recovery page".
3. Before M8, add a short display message before entering ROM. It is cheap,
   because the FM-1 board layer has the TFT. Doing it later is a follow-up,
   not a blocker.

**What the costs are.**

- Shorter limits fall back on a transient fault.
- Longer healthy or stable times delay recovery after a crash loop. Each
  crash cycle costs about the healthy time.
- A deliberate user reset within 300 s of power-on, three times in a row,
  would fall back. No such reset path exists yet.

**If there is no answer.** The defaults stay as they are (3, 30 s, 300 s),
and fallback stays silent. Nothing changes on any device until M8, which
has its own owner approval.

## 8. Not done or not tested

- Power cuts (§6): need a person.
- The `app_main` ROM-entry stage, and the key-combination hook: still not
  exercised (as in PR #180).
- The FM-1: nothing ran on it. The SPL there differs from the kit's, so
  record survival is [inferred] (PR #180 note).
- Cross-core contention was shown for the record writes, not for slot
  registration. On the kit all four registrars ran on core 1 (§3), and the
  SDK has no affinity API to force a split [verified: `os_api.h`].
  Registration across cores is covered only by the desktop TSan test.
- PR #180's `LFO1` record was not met on the kit, because another lane had
  overwritten the area (§3). The rejection is covered only by the desktop
  test.
- The boot-time cost of hashing about 170 KB through XIP was not measured.
  The device clock does not advance in `setup_arch`, and the application
  started at 0.125 s on every boot.
- The CPU exception attempts (misaligned read, divide by zero) still raise
  nothing on the kit, as in PR #180. The backstop handled it.

## 9. Evidence kept

On the bench host, in the lane's private folder `lunar-failopen-hardening-2026-11-08/`
(mode 700), one subfolder per image (`cycle`, `escalate`, `recover`):

- `uart.bin` and `uart.json`: the receive-only captures;
- `usb.jsonl`: the sysfs watcher;
- `iteration/install.jsonl`, `iteration/reset.jsonl`, `installed.json` and
  `runner-exit.json`.

The runner (`tools/failopen-run.py`) and the PR #177 tool copies it used are
kept there too. The candidates were deleted after the run; they rebuild from
this branch with the commands in `firmware/devkit/README.md`.

UART capture SHA-256:

| Image | Capture | SHA-256 |
| --- | --- | --- |
| `cycle` | 14,140 B | `84fd0868fc3951129492c989e2058aa098b45126fdb58e4111d9d4c6ade1dc82` |
| `escalate` | 17,444 B | `1e5dbf422b35b540ac0bb50d1d42bf4074d15d6f19aa44796f98f63a56778f7c` |
| `recover` | 11,205 B | `25b75d6d231f5b9feff482c43eed35e94e83cde0e544a35f6c20334f4b4aa5ac` |

On the build host, in the lane's folder under the project's dataset area:

- build and preparer logs;
- the negative-link logs;
- the vendor `objdump` and symbol listings of `cycle` and of its base build;
- each image's `candidate-plan.json`.

The build trees and the binaries were deleted.

## 10. Desktop suite

- CI ran on both pushed heads, and every check passed (14 of 14):
  - `tests (ubuntu-24.04)`: 6,225 passed, 34 skipped, 2 xfailed;
  - `tests (macos-latest)`: 6,217 passed, 42 skipped, 2 xfailed.

  [verified: CI logs]
- **TSan test.** On the build host, GCC 12's ThreadSanitizer aborted at start
  with `unexpected memory mapping` in a Linux container. This is a kernel
  ASLR setting, not a race. The test now retries under `setarch -R`. It skips
  only when TSan still cannot start, or when ASLR cannot be turned off, as
  under Docker's default seccomp profile.
- **`test_core` hang.** In the same container, `test_core`'s ASan/UBSan
  binary spun at full CPU for 13 minutes on one run, and was stopped. It
  passed in that container just before, on the Mac, and in CI on both
  systems. The cause is unexplained [inferred: an environment one-off of the
  same sanitizer/ASLR kind].
