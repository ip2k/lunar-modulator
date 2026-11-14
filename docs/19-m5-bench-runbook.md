# 19 — M5 bench runbook: the first Lunar code on the FM-1, from RAM

The operator steps for milestone M5 of [docs/18](18-fm1-release-plan.md):
the approved M5 test-pattern image loaded into the FM-1's SRAM through the
mask ROM and started once, with read-only flash dumps before and after. It
turns the plan in
[`notes/2026-11-08-ram-runner-devkit.md`](../notes/2026-11-08-ram-runner-devkit.md)
§5 into numbered steps. Confidence marks as elsewhere.

**Status: run on 2026-11-10.** The image loaded and the jump was sent, but
the FM-1 showed nothing and reset to V15 3.89 s later; flash was unchanged.
The result is in
[`notes/2026-11-10-m5-fm1-ram-run.md`](../notes/2026-11-10-m5-fm1-ram-run.md).
Every step below ran as written, except that step 1 found `v15=0` (the
transporter had started before the FM-1 was on) and Part C ran about an hour
after Part B.

**m5-plan-2 (2026-11-14):** §7 adds the steps for the two RAM runs the owner
approved after it: `m5p2.bin`, and `m5p2-mailbox.bin` with a breadcrumb read
if the first is inconclusive. Not yet run; the tool's hash awaits the owner's
approval (§7.1).

## 1. What is approved, and what is not

**Owner approval, 2026-11-09** (choice recorded verbatim: "Yes, M5 as
planned"; docs/18 §3):

- **On the FM-1, RAM only, one session.**
- **Image:** `m5.bin`, 4,160 B, SHA-256
  `a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4`,
  build id `m5-plan-1`.
- **SRAM written:** only `[0x01C02000, 0x01C03040)`.
- **Route:** the Pico 2 W transporter of [docs/17](17-pico2w-recovery.md)
  (its UF2 `4f5fab3f…` unchanged), driven by the patched host tool
  [`tools/fm1-transporter/fm1t_m5.py`](../tools/fm1-transporter/fm1t_m5.py)
  (note §4.2).
- **Tool hash:** the tool as first approved (2026-11-09) had SHA-256
  `c0e704e3c6e5de4c3a37e428ea2f73092a7ac8068b1b0ff51c6851deb0d955df`. On 2026-11-10 the owner chose to patch it with the
  length rule of `fm1t_m6.py` (`memw`, `memr` and `ldr` lengths `[1-9][0-9]{0,3}`,
  because the transporter parses them with `strtoul(..., 0)`, so a leading 0 is
  octal). The patched file's SHA-256 is
  `9673ccd83622a208644ae2b467a1fa5964b01807d2639b3d409537d5136c1a72`. That hash was **approved by the owner on 2026-11-10** ("Approve 9673ccd8"),
  and `~/m5-run` on bench01 holds it; `preflight` must print exactly it.
  The change is the pattern lines only (`tests/test_fm1t_m5.py`; listed in the PR).
- **Sequence and recovery:** note §5, as below.

Not covered: any other image or build id, any flash write or erase, the soft
key, a second RAM run in the same session, upstream `fm1t.py` for any step,
and the transporter console's `k`. Each needs its own owner yes.

## 2. What the tool will and will not send

`fm1t_m5.py` can put only these lines on the transporter's data port
(interface 2), and each subcommand has its own subset
[verified: `tests/test_fm1t_m5.py`]:

| Subcommand | Lines it can send |
| --- | --- |
| `status` | `ping`, `status` |
| `rekey --fm1-is-off` | `ping`, `status`, `rekey` (only when `status` answers `uboot=0 v15=0`, so only from host mode, never while the key runs) |
| `info --loader …` | `ping`, `status`, `ldr …` ×6 (the loader into the Pico's buffer), `info` |
| `dump OUT --loader …` | the `info` lines plus `read 0x0 1048576` |
| `ramrun m5.bin --sha256 …` | `ping`, `status`, `memw 0x1c02000 4096 …`, `memw 0x1c03000 64 …`, `memr` ×2, `jump 0x1c02000 0x1` |

- **Lengths are plain decimal.** Every `memw`, `memr` and `ldr` length must
  match `[1-9][0-9]{0,3}` (no leading zero), because the transporter parses it
  with `strtoul(..., 0)` and would read `010` as 8 (patched 2026-11-10, §1).
- **Never:** `uboot` (the transporter answers it with the soft key
  `F0 22 24 35 7D F7`), `wsec` (flash erase and program), `runapp`, or any
  other line. The tool never opens the console port (interface 0, where `k`
  lives): `--port` must be the by-id path ending `-if02`.
- **No ROM entry by soft key.** Every step that needs the ROM checks that
  `status` reports `uboot=1`, and otherwise stops with the USB_KEY steps.
- **`ramrun` admits only the approved image** and refuses `--loader`,
  `FM1T_LOADER`, `--addr`, `--arg`, `--clear`, `--poke` and `--read`. It
  starts only when the transporter reports `loader=0 loader_running=0`, so
  the RAM run always follows a fresh `rekey`.
- **The gate holds the image too.** A `memw` can carry only the approved
  image's bytes, in order, inside `[0x01C02000, 0x01C03040)`; `memr` reads
  only that range; the `jump` is refused until all 4,160 bytes were written,
  and nothing is sent after it.
- **One attempt.** Just before its first `memw`, `ramrun` creates
  `fm1t_m5-ramrun.lock` next to its receipt. Any later `ramrun` from the same
  run directory refuses before opening the port, whatever happened the first
  time. A second attempt needs a new owner yes (and deleting that file is not
  a way round it).
- **`info` and `dump` accept only JieLi's `wl82loader.bin`** (24,064 B,
  `d41da612…`), which runs from RAM and reads flash.
- **Receipts.** Every invocation writes a new JSONL receipt (`--log`, never
  overwritten) with every line sent and received; payloads are logged by
  length, CRC-32 and SHA-256.

Exit codes: `0` as expected; `1` refused before the port was opened; `2`
bad arguments; `3` stopped after the port was opened (an unexpected reply,
or a refusal mid-session).

## 3. Before the session (desk, no hardware)

Claude, on the Mac:

1. Build the image and check it, as note §5 does:

   ```bash
   LUNAR_BUILD_ID=m5-plan-1 LUNAR_SESSION=<label> \
     bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> m5-test-pattern
   python3 tools/fm1-transporter/fm1t_m5.py preflight \
     --image <scratch-dir>/m5.bin --sha256 a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4
   ```

   `preflight` opens no port. It prints the image check and the tool's own
   SHA-256; write that hash down.
2. Copy `fm1t_m5.py`, `m5.bin` and `wl82loader.bin` to one run directory on
   bench01, for example `~/m5-run/`, and rerun the same `preflight` there with
   `--loader wl82loader.bin` too. The tool hash must equal the Mac's.
   **`~/m5-run` on bench01 holds the OLD tool (`c0e704e3…`).** After the owner
   approves the new hash, replace `fm1t_m5.py` there with the patched file and
   check `preflight` prints `9673ccd8…`; do not run the old file.

3. On bench01, check that nothing else will open the transporter's ports:
   `systemctl is-active ModemManager` should not say `active` (it probes
   new `ttyACM` ports with `AT` commands), and, before the console reader
   is started, no other `fm1t*`, `cat` or terminal program has the
   transporter's ports open (`fuser $P $C`, with the variables below,
   prints nothing). The tool opens `$P` exclusively.

On bench01, every command below runs in that directory with these set
(`<serial>` from `ls /dev/serial/by-id/`):

```bash
cd ~/m5-run
unset FM1T_LOADER
P=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if02   # data port
C=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if00   # console, read only
T="python3 fm1t_m5.py --port $P"
SHA=a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4
```

**The console is for watching only.** Claude reads it with a plain reader
and never types into it (`k` there sends the soft key):

```bash
stty -F $C raw -echo 115200 && cat $C | tee -a console-N.log
```

`rekey` and a replug reboot the transporter, which ends `cat`; start it
again (a new `N`) within 10 s of every reboot.

## 4. The session

**Owner, before step 1:**

- The FM-1's battery is charged.
- The FM-1 is **switched off**. Check the switch itself; with the ROM
  running the display stays dark, so it is no guide.
- The Pico is wired as in docs/17 §3 (GP0 to D+, GP1 to D−, GND to GND,
  VBUS not connected). Its own USB goes into bench01 in step 1. Nothing else
  is connected to the FM-1.
- A camera or phone is ready to photograph the TFT and the LEDs.

### Part A: dumps before (ROM entry 1)

1. **Owner:** with the FM-1 off, plug the Pico into bench01 (or unplug it
   and plug it back in). **Claude** starts the console reader at once: the
   transporter waits up to 10 s for it, then keys by itself, because nothing
   pulls D+ up [verified: upstream `src/main.c`].
   - Expected on the console: `KEY: sending 0x16EF, polarity A (D+ clock,
     D- data). Switch the FM-1 ON now.` and a steadily rising
     `KEY: … packets` count.
   - **`status` does not answer while the key runs.** Only `ping` and
     `rekey` are served by the transporter's core 0; `status` waits for
     core 1, which is busy keying until the ROM answers
     [verified: `src/transporter_proto.c`, `src/main.c`]. So Claude does not
     run the tool here. If it is run anyway, it stops with "no reply to
     `status` … This is not a fault" (exit 3), having sent only `ping` and
     `status`.
   - **If the console instead says `D+ already pulled up … skipping
     USB_KEY`,** the FM-1 was on. The transporter then hosts the running V15
     after about 6 s. Claude runs `$T --log 01-status.jsonl status`
     (expected `v15=1`). The owner switches the FM-1 off, Claude runs
     `$T --log 01b-status.jsonl status` (expected `uboot=0 v15=0`), then
     `$T --log 02-rekey.jsonl rekey --fm1-is-off` and restarts the console
     reader within 10 s. The tool never sends anything to the running V15:
     `status` and `rekey` go to the Pico.
2. **Stop** if the console shows `D+ high in gap` within a few packets: the
   FM-1 is probably on after all. The owner switches it off and replugs the
   Pico (step 1).
3. **Owner:** switch the FM-1 **on**. Note what the TFT does (it should stay
   dark).
   - **Claude** watches for `PULSE`, then `HANDOFF` within 6 s, then
     `INQUIRY OK: vendor="WL82    " product="UBOOT1.00       "` and
     `UBOOT READY` about 2 s later.
   - **Stop** if the key keeps running with no acknowledgement: wiring
     (docs/17 §4).
4. **Claude:** `$T --log 04-status.jsonl status`
   - Expected: `uboot=1 v15=0 loader=0 loader_running=0`.
5. **Claude:** `$T --log 05-info.jsonl info --loader wl82loader.bin`
   - Expected: exactly `OK key=980F type=3 id=856014`. The tool stops on
     anything else.
6. **Claude:** `$T --log 06-dump.jsonl dump before-A.bin --loader wl82loader.bin`
7. **Claude:** `$T --log 07-dump.jsonl dump before-B.bin --loader wl82loader.bin --compare before-A.bin`
   - Expected: `IDENTICAL over the whole 1 MiB`, exit 0. Then also
     `python3 fm1t_m5.py compare before-A.bin before-B.bin` and
     `sha256sum before-*.bin`.
   - Informational, if the stock package `FM-1.fwsc` (docs/17 §1) is on
     bench01: `before-A.bin` over `[0, 0x93000)` should equal the V15 image,
     the package's type-0 entry at file offset `0x414` (prints `True`). If it
     does not, stop and ask the owner before going on.

     ```bash
     python3 -c "d=open('before-A.bin','rb').read(); p=open('FM-1.fwsc','rb').read(); print(d[:0x93000]==p[0x414:0x414+0x93000])"
     ```
8. **Owner:** switch the FM-1 **off**. **Claude:**
   `$T --log 08-status.jsonl status` must show `uboot=0 v15=0`.
   - With the power off the loader is gone from SRAM [inferred].
   - If it still shows `uboot=1`, the switch did not cut the SoC (note §5's
     open point). Stop and decide with the owner. Do not go on to the RAM
     run in that state; the tool's `rekey` refuses anyway.

### Part B: the RAM run (ROM entry 2)

9. **Claude:** `$T --log 09-rekey.jsonl rekey --fm1-is-off`; restart the
   console reader; the key runs as in step 1. `rekey` works here because the
   transporter is in host mode after step 8 (its `status` answered).
   - The Pico reboots 50 ms after writing `OK rekey`, so the reply can be
     lost (exit 3, "no reply to rekey"). If the console shows the
     transporter rebooting and `KEY: sending`, the rekey took effect;
     otherwise replug the Pico with the FM-1 off, as in step 1.
10. **Owner:** start filming the TFT and LEDs, then switch the FM-1 **on**.
    **Claude** waits for `UBOOT READY` as in step 3.
11. **Claude:** `$T --log 11-status.jsonl status`
    - Expected: `uboot=1 v15=0 loader=0 loader_running=0`. `loader=1`
      would mean the Pico was not rebooted since Part A; `ramrun` refuses
      that by itself.
12. **Claude:** `$T --log 12-ramrun.jsonl ramrun m5.bin --sha256 $SHA`
    - It sends `memw` ×2 (`0x1c02000` 4,096 B, `0x1c03000` 64 B), `memr`
      ×2 and compares, then one `jump 0x1c02000 0x1`, then nothing more.
    - Expected output: `loaded 4160 B at 0x1c02000; read-back equal`, then
      `ERR jump after ~2000 ms: … Image presumed running`, exit 0.
    - Any other result exits 3. Do not rerun `ramrun` (there is no second
      attempt in this session; the lock file refuses it anyway).
    - **If it exits 3 after sending the jump** (the receipt has a `tx` line
      `jump 0x1c02000 0x1`), the image may still be running: do step 13's
      observation and photographs first, then power off and stop (§5). If it
      stops before the jump, nothing ran: power off and stop.
13. **Owner, at the unit:**
    - The TFT should show the test pattern with `m5-plan-1`.
    - The LEDs should blink `step` times, pause, and repeat. Six blinks is
      the last step; count them over two or three cycles. What each count
      means is in [`firmware/m5/README.md`](../firmware/m5/README.md).
    - Photograph the TFT and film at least two LED cycles.
    - A dark TFT is a result, not a danger: record it, and go on.
    - **If V15's normal screen appears** (the chip reset after the jump and
      booted its application, which the transporter then hosts), photograph
      it and do not run any tool command; go on with step 14, then stop and
      ask the owner before Part C. The tool cannot send the soft key, but
      nothing in this plan expects a V15 attached to the transporter.
    - **If that happens some seconds after the test pattern appeared**, read
      the delay from the video and record it. `m5.bin` never clears the
      watchdog, so a reset a few seconds in would mean the FM-1's
      cold-entered ROM leaves the watchdog armed [inferred]; M6's image
      clears it only if armed, and needs to know (notes/2026-11-09-m6-image.md
      §5). It is a result, not a danger.
14. **Owner:** switch the FM-1 **off**. SRAM, and the image with it, is lost
    [inferred]. **Claude:** `$T --log 14-status.jsonl status` must show
    `uboot=0 v15=0`. If it does not, see §5, "The transporter is stuck".

### Part C: dump after (ROM entry 3)

15. **Claude:** `$T --log 15-rekey.jsonl rekey --fm1-is-off`; restart the
    console reader. **Owner:** switch the FM-1 **on**. **Claude** waits for
    `UBOOT READY`.
16. **Claude:** `$T --log 16-dump.jsonl dump after-A.bin --loader wl82loader.bin --compare before-A.bin`
    - Expected: `IDENTICAL over the whole 1 MiB`, exit 0: the run left flash
      untouched. Then `python3 fm1t_m5.py compare before-A.bin after-A.bin`.
17. **Owner:** switch the FM-1 **off**.

### Part D: back to V15

18. **Owner:** **disconnect the Pico's wires from the FM-1** before switching
    it on (docs/17 §7). This differs from the order in note §5, which
    disconnects afterwards: a transporter left attached hosts the booting
    V15, and the identity query needs the FM-1 on bench01's own USB.
    **Claude** stops the console reader.
19. **Owner:** switch the FM-1 **on**. V15 should boot with its normal
    display. Plug the FM-1 into bench01 with a data cable.
20. **Claude:** the read-only identity query (D4), as in docs/17 §7, from
    the Lunar checkout on bench01 (not `~/m5-run`), as on 2026-10-26:

    ```bash
    tools/fm1_identify.sh
    amidi -p hw:X,0,0 -S 'F0 00 32 45 00 00 00 40 7F F7' -r id.syx -t 3
    python3 tools/fm1_identify.py --decode-file id.syx
    ```

    Expected: `identity: FM-1_015`, `checksum_ok: True`.

### After the session

- **Claude** copies the receipts (`*.jsonl`), the console logs and the
  `sha256sum` of every dump to the session scratch, and the photos go with
  them.
- The dumps stay private: never committed, never shared. Keep `before-A.bin`
  on bench01 until the note is written.
- **The bench note** `notes/YYYY-MM-DD-m5-fm1-ram-run.md` records:
  - the tool hash, the image hash and the console lines quoted;
  - the jump reply and its `ms`;
  - what the TFT and LEDs showed;
  - the dump hashes and the identity.
- **docs/18:** the M5 row is updated from the note.

## 5. Stop conditions and recovery

**Stop at once, power the FM-1 off, and do not retry, when:**

- `info` is anything but `OK key=980F type=3 id=856014`;
- `before-A` and `before-B` differ, or `after-A` differs from `before-A`;
- any tool step exits non-zero (3), or prints a reply not listed above
  (after a jump was sent, observe and photograph first: step 12);
- the console shows anything that suggests the FM-1 is not the one in the
  ROM (a different INQUIRY string);
- the owner sees smoke, heat or a swelling battery, or simply says stop.

Then Claude records what happened from the receipts and the console log
before anything else is tried.

**Recovery:**

- **A power cycle returns V15.** Nothing in this session writes flash, so
  the next normal power-on (Pico disconnected) boots stock V15 [inferred:
  RAM-only image; confirmed on the dev kit, note §3].
- **If V15 does not boot:** docs/17 is the fallback, and only on the owner's
  go-ahead:
  - USB_KEY entry (docs/17 §4);
  - two new dumps, compared with each other, with `before-A.bin` and with
    the 2026-10-26 images;
  - then a stock V15 write (docs/17 §6), dry run first.
  - Those steps use upstream `fm1t.py` with the V15 shim. Its `write` path
    is outside `fm1t_m5.py` on purpose.
- **If the TFT stays dark:** the run has still proven nothing harmful. Go on
  with Part C.
- **The transporter is stuck** (no `PONG`, or `status` still says `uboot=1`
  with the FM-1 off):
  - unplug the Pico from bench01 and plug it back in, with the FM-1 off.
    This is the same move as step 1: a transporter that boots with nothing
    pulling D+ up starts keying by itself [verified: upstream `src/main.c`],
    the same as `rekey`;
  - reopen the console and go on from the step that needs a ROM entry.
  - Never re-flash the Pico, and never open its console at 1,200 baud
    (BOOTSEL).

## 6. Open points this session answers

From note §5:

- whether the FM-1's power switch cuts the SoC fully with the battery in
  (steps 8 and 14);
- whether the ROM's own work RAM overlaps the M5 stacks (the image runs or
  it does not);
- how the transporter behaves after an unanswered `jump` (step 14's
  `status`, and the console log).

## 7. m5-plan-2: run 1 and, if needed, run 2 (approved 2026-11-14)

The steps for M5's successor, from
[`notes/2026-11-14-m5-plan-2.md`](../notes/2026-11-14-m5-plan-2.md) §5–§7.
Sections 1–6 above stay the record of the 2026-11-10 M5 run; this section
reuses their steps and lists only what differs.

**Status: not yet run.** The tool's hash (§7.1) **awaits the owner's
approval**; the bench session does not start before it is given.

### 7.1 What is approved, and what is not

**Owner approval, 2026-11-14** (HANDOFF "Owner decisions, 2026-11-14"; note
§9):

- **Run 1, "Approve":** `m5p2.bin`, 7,920 B, SHA-256
  `aba6ed7ceaa0cac990dedcaf664b10707632a139be83b3bea5e0f62739bf968c`, build
  id `m5-plan-2`, may run once in RAM on the FM-1, **its watchdog kicks (P33
  `WDT_CON` writes) included**, with the owner at the bench.
- **Run 2, "Approve now too":** `m5p2-mailbox.bin`, 7,920 B, SHA-256
  `b63a643e14983ac07a883867d073368733f6f714b7f35116aa85a4e91d80421c`, build
  id `m5-plan-2m`, may run once, in the same bench session, **only if run 1
  is inconclusive** (§7.5). It also writes the `usb_update_mode` marker at
  `0x01C7FD80`, so that a watchdog reset returns to the mask ROM, and the
  host then reads the 48 B of breadcrumbs at `0x01C05FC0` once.
- **SRAM the tool writes:** only `[0x01C02000, 0x01C03EF0)`, two `memw`
  chunks (4,096 + 3,824 B). The image itself writes its stacks and
  breadcrumbs below `0x01C06000`, and run 2 the marker.
- **Tool:** [`tools/fm1-transporter/fm1t_m5p2.py`](../tools/fm1-transporter/fm1t_m5p2.py),
  SHA-256
  `2cbdaa687aa03f6df7b15c7d6214ee7b75d1486a00c8abafcad277402d21f7ab`.
  **This hash needs its own owner approval before the bench run**; the image
  approvals do not cover it. `preflight` must print exactly it, on the Mac
  and in the run directory.
- **Route:** the Pico 2 W transporter of [docs/17](17-pico2w-recovery.md),
  its UF2 unchanged, as for M5.

Not covered: any other image, build id or tool hash; run 2 when run 1 was
conclusive; a second attempt of either run; any flash write or erase; the
soft key `F0 22 24 35 7D F7`, syscmd 33–36/48, `5A AA A5` frames or the
`7F` upgrade command; loader command `0xFC12` or a raw `0xA1` write; any
eFuse access; any write to `0x0`–`0x4000`; upstream `fm1t.py`, and
`fm1t info`, `dump`, `write`, `uboot` or console `k` while a running V15 is
attached. Each needs its own owner yes. (`dump` reads the whole 1 MiB,
`0x0`–`0x4000` included, as in Parts A and C; it never writes.)

### 7.2 What the tool will and will not send

`fm1t_m5p2.py` is `fm1t_m5.py` with the lines below changed and nothing
else [verified: `tests/test_fm1t_m5p2.py` pins every differing code line].
§2's rules all hold, with these rows:

| Subcommand | Lines it can send |
| --- | --- |
| `ramrun m5p2.bin --run 1 --sha256 …` | `ping`, `status`, `memw 0x1c02000 4096 …`, `memw 0x1c03000 3824 …`, `memr` ×2 (the same ranges), `jump 0x1c02000 0x1` |
| `ramrun m5p2-mailbox.bin --run 2 --sha256 …` | the same lines, with run 2's bytes |
| `crumbs` | `ping`, `status`, `memr 0x1c05fc0 48` |

- **Two pinned images.** `--run 1` admits only `aba6ed7c…`, `--run 2` only
  `b63a643e…`. Each `memw` must carry that run's bytes, in order; the jump
  waits for all 7,920.
- **One lock per run.** Run 1 creates `fm1t_m5p2-ramrun.lock`, run 2
  `fm1t_m5p2-mailbox-ramrun.lock`, next to the receipt, just before the
  first `memw`. A run whose lock exists refuses before opening the port.
  **Run 2 refuses unless run 1's lock is in the same run directory**, and run
  1 refuses where run 2's lock is. Either refuses beside M5's or M6's lock.
- **`crumbs` runs once, after run 2.** It is admitted only in a run directory
  holding run 2's lock and no `fm1t_m5p2-crumbs.lock`. `status` must answer
  `uboot=1 v15=0 loader=0 loader_running=0`: the flash loader is loaded at
  `0x01C02000` and is 24,064 B long, so it would overwrite the breadcrumbs.
  `memr` is the transporter's existing ROM memory read (FD07); no
  transporter or Pico change is involved. The lock is created when the
  transporter answers `DATA 48`: a read that never happened (no reply, or
  `ERR …` on a stale mount, §7.6) may be tried again, and a read that
  happened may not. The 48 bytes go into the receipt as hex before they are
  checked or decoded.
- **`v15=0` wherever the ROM is needed.** `ramrun` and `crumbs` stop at
  `status` unless it answers `uboot=1 v15=0`, so with a running V15 attached
  the tool sends only `ping` and `status`, which the Pico answers itself.

Exit codes as in §2; `crumbs` also exits 3 when the read worked but the
magic or its complement does not match (the bytes are kept).

### 7.3 Before the session (desk, no hardware)

Claude, on the Mac:

1. Build the images as the note §2 did (`link-diagnostic.sh … m5-plan-2`,
   [`firmware/m5p2/README.md`](../firmware/m5p2/README.md)) and check both:

   ```bash
   python3 tools/fm1-transporter/fm1t_m5p2.py preflight \
     --image <scratch-dir>/m5p2.bin --sha256 aba6ed7ceaa0cac990dedcaf664b10707632a139be83b3bea5e0f62739bf968c
   python3 tools/fm1-transporter/fm1t_m5p2.py preflight \
     --image <scratch-dir>/m5p2-mailbox.bin --sha256 b63a643e14983ac07a883867d073368733f6f714b7f35116aa85a4e91d80421c
   ```

   Expected: `approved run 1 image (m5-plan-2), 7920 B` and `approved run 2
   image (m5-plan-2m), 7920 B`, and the tool hash of §7.1.
2. Copy `fm1t_m5p2.py`, `m5p2.bin`, `m5p2-mailbox.bin` and `wl82loader.bin`
   to **one new run directory** on bench01, for example `~/m5p2-run/` (not
   `~/m5-run`: the tool refuses beside M5's lock). Rerun both `preflight`
   commands there with `--loader wl82loader.bin` too. Both runs use this one
   directory: run 2 needs run 1's lock beside it.
3. As §3 step 3 (ModemManager, nobody else on the ports).

On bench01, every command below runs in that directory with:

```bash
cd ~/m5p2-run
unset FM1T_LOADER
P=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if02   # data port
C=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if00   # console, read only
T="python3 fm1t_m5p2.py --port $P"
SHA1=aba6ed7ceaa0cac990dedcaf664b10707632a139be83b3bea5e0f62739bf968c
SHA2=b63a643e14983ac07a883867d073368733f6f714b7f35116aa85a4e91d80421c
```

The console reader is §3's, watching only.

**Owner, before step 1:** as §4, plus a clock (a phone stopwatch or a clock
with seconds) that stays in the video frame next to the TFT and the LEDs.

### 7.4 Parts A and B: dumps, then run 1

- **Part A (steps 1–8):** as §4, with `$T` above and
  `python3 fm1t_m5p2.py compare …` in step 7.
- **Steps 9–11:** as §4.
- **Step 10:** the owner starts filming **before** switching the FM-1 on,
  with the clock in frame, and keeps filming until step 14.
- **Step 12:** `$T --log 12-ramrun.jsonl ramrun m5p2.bin --run 1 --sha256 $SHA1`
  - It sends `memw` ×2 (`0x1c02000` 4,096 B, `0x1c03000` 3,824 B), `memr`
    ×2, then one `jump 0x1c02000 0x1`, then nothing more.
  - Expected output: `loaded 7920 B at 0x1c02000; read-back equal`, then
    `ERR jump after ~2000 ms: … Image presumed running`, exit 0.
  - On exit 3, as §4 step 12: after a jump, observe first; before it,
    nothing ran. Do not rerun: the lock refuses.
- **Step 13, owner at the unit, for at least 2 minutes after the jump.**
  What to expect if PA2 is the backlight and the clocks are as on the kit
  (note §5, option 1):
  1. **The backlight comes on at once.**
  2. **Cadence A:** three off/on flashes; each half is
     `0.4 s × 40 MHz / f_osc` (0.67 s at 24 MHz, 0.40 s at 40 MHz).
  3. **Cadence B:** three off/on flashes (five if TIMER4 is dead); each
     half is about `56 M cycles / f_cpu` (1.18 s at 48 MHz).
  4. **The panel:** the test pattern with the label
     `m5-plan-2 <WDT_CON hex> <ticks per block hex>`, about 11.5 s after
     the jump on kit clocks. **Photograph the label so both numbers can be
     read.**
  5. **The LED code**, repeating: 3 blinks per cycle = frame sent with
     TIMER4 alive, 2 = frame sent on spin waits, 1 = the panel failed. Count
     it over three cycles.
  6. The image kicks and blinks until power-off; it never ends by itself.
  - From the video: `f_osc ≈ 16 MHz·s / T_A` and `f_cpu ≈ 56 M cycles / T_B`,
    where `T_A` and `T_B` are one half (one off or one on) of each cadence,
    averaged over its halves [inferred: assumes the kit's cycles per spin,
    note §5]. The label gives the same ratio: ticks per block
    `= 200,000 × 14.1 × f_osc / (16 × f_cpu)`.
  - **A reset to V15's screen** is now a result about the kicks, not a
    danger. Read its time after the jump from the video (within ~4 s: the
    kicks do not reach the FM-1's watchdog). Photograph V15's screen and run
    no tool command (§4 step 13 applies unchanged).
  - A dark TFT is a result: record it and go on.
- **Step 14:** as §4: the owner switches the FM-1 off; `$T --log
  14-status.jsonl status` must show `uboot=0 v15=0`. Then decide §7.5
  before Part C.

### 7.5 Was run 1 inconclusive?

Claude and the owner look at the video together, after step 14, and decide
by this table. Run 2 follows only on an "inconclusive" row.

| What run 1 showed | Verdict | Next |
| --- | --- | --- |
| The label photographed and legible (both hex numbers) | conclusive | Part C |
| Both cadences seen and timed, no reset before the end of cadence B (panel dark or not) | conclusive on the clocks | Part C |
| Nothing at all: no backlight change, no panel, no LEDs, no reset | inconclusive | run 2 (§7.6) |
| A reset to V15 (or a console `device gone`) before cadence A's three flashes ended | inconclusive | run 2 |
| The video is unusable (missed, out of focus, no clock) | inconclusive | run 2 |
| Cadences seen but the panel dark, or a reset during cadence B or the frame | borderline: the owner decides at the bench | run 2 adds the stage reached and the panel result |

Run 2's breadcrumbs give the numbers the video could not: the last stage,
`WDT_CON` at entry, ticks per block, the longest kick gap, the kick counts,
the panel result and the elapsed time.

### 7.6 Run 2 and the breadcrumb read (only after an inconclusive run 1)

Same run directory, same session, after step 14.

- **R1.** `$T --log r1-rekey.jsonl rekey --fm1-is-off`; restart the console
  reader (as step 9).
- **R2. Owner:** start filming with the clock in frame, then switch the FM-1
  **on**. **Claude** waits for `UBOOT READY`.
- **R3.** `$T --log r3-status.jsonl status`: expected
  `uboot=1 v15=0 loader=0 loader_running=0`.
- **R4.** `$T --log r4-ramrun.jsonl ramrun m5p2-mailbox.bin --run 2 --sha256 $SHA2`
  - The same lines and expected output as step 12; exit 0.
  - It refuses (exit 1, nothing sent) if run 1's lock is not in the
    directory.
- **R5. Owner, at the unit: the same sequence as step 13**, then the end:
  - after 18,000 nominal ms of waits (about 40 s after the jump at kit
    clocks; minutes if TIMER4 is dead) the image stops kicking at the end of
    an LED cycle, with the LEDs off;
  - about 4 s later the armed watchdog resets the chip into the mask ROM,
    with SRAM kept [verified on the kit; inferred on the FM-1];
  - if the kicks never reach the watchdog, that reset comes ~4 s after the
    jump instead.
  - **Do not switch the FM-1 off before R7.** Power-off clears SRAM and
    the breadcrumbs with it [inferred]. Do not `rekey`: it needs the FM-1
    off (and refuses while `uboot=1`).
- **R6. Wait** until one of these, at most **15 minutes** after the jump:
  - **(a)** the console shows the ROM back: `INQUIRY OK: … product="UBOOT1.00 …"`
    and a new `UBOOT READY` after the jump. Go to R7.
  - **(b)** the LEDs have gone dark and stayed dark for 30 s, with no new
    `UBOOT READY`. Go to R7 anyway; if it fails, see "Stale mount" below.
  - **(c)** V15's screen appears, or `status` answers `v15=1`: the FM-1 did
    not honour the marker. Photograph it, run no other tool command, and go
    to R8. The breadcrumbs are lost; this is a result.
  - **(d)** 15 minutes pass with the LEDs still blinking or no change: the
    watchdog is not armed or never fired. Go to R8; no readback.
- **R7.** `$T --log r7-status.jsonl status`, then, only if it answers
  `uboot=1 v15=0 loader=0 loader_running=0`:
  `$T --log r7-crumbs.jsonl crumbs`
  - Expected: the twelve words by name, then
    `stage …, timer_dead …, panel …, valid True` and
    `breadcrumbs read and valid; last stage …`, exit 0.
  - Exit 3 with `does not match`: the read worked but the breadcrumbs did
    not survive or were never written. The raw bytes are in the receipt.
    That is the result; there is no second read.
  - **Never** run `info` or `dump` before `crumbs`: the loader would land on
    top of the breadcrumbs.
- **R8. Owner:** switch the FM-1 **off**. **Claude:**
  `$T --log r8-status.jsonl status` must show `uboot=0 v15=0`. Then Part C.

**Stale mount: the readback gap.** Whether the transporter notices the ROM
coming back is untested [inferred: unknown]. The Pico's host stack clears its
"mounted" state only on a detach. On the kit, a watchdog reset into the ROM
showed Linux only a port reset, no detach
(`notes/2026-11-10-devkit-watchdog-probes.md`); on the FM-1, M5's reset into
V15 did show a detach 3.89 s after the jump, and nothing mounted after it
(`notes/2026-11-10-m5-fm1-ram-run.md`). So `status` may answer `uboot=1` for
a device that is no longer enumerated, and `crumbs` then gets `ERR …` or no
reply. It exits 3 **without taking its lock**, so the read may be tried
again:

1. With the FM-1 left **on**, unplug the Pico's own USB from bench01 and plug
   it back in; restart the console reader at once.
2. The transporter boots, finds D+ already pulled up by the ROM, skips the
   key and hosts the device after about 6 s, as in §4 step 1's
   `D+ already pulled up` case [inferred: that path was seen with V15
   attached, never with the ROM]. Expected on the console: `INQUIRY OK: …
   UBOOT1.00` and `UBOOT READY`.
3. Repeat R7.

If that still fails, the breadcrumbs cannot be read with the tools we have:
go to R8. Closing the gap for good would need a transporter firmware change,
which this plan does not make: a data-port command that forces a USB bus
reset and re-enumeration of the attached device, or a mount counter in
`status` so the host can tell a fresh enumeration from a stale one; and, if
the ROM does not pull D+ up again without VBUS, a VBUS feed (docs/17 §3 leaves
VBUS unconnected). Each would be a new Pico UF2 and needs its own owner yes.

### 7.7 Parts C and D

As §4 steps 15–20, after step 14 (or R8): `rekey`, power on,
`dump after-A.bin --compare before-A.bin` (expected `IDENTICAL`: neither run
wrote flash), power off, Pico disconnected, V15 boots, identity `FM-1_015`.
Use `$T` and `fm1t_m5p2.py compare`.

### 7.8 Stop conditions, open points and the record

- **Stop conditions and recovery:** §5, unchanged, plus: stop at R6 (c) or
  (d) without any further tool command but `status`.
- **Open points** (note §7): the FM-1's cold-ROM oscillator and CPU clocks;
  whether PA2 is the backlight; whether the panel path (SPI1, ST7789,
  display-on before the frame) works; whether the kicks hold the FM-1's
  watchdog; and, for run 2, whether the marker returns the FM-1 to the ROM,
  whether the transporter re-mounts it, and whether SRAM survives.
- **The bench note** `notes/YYYY-MM-DD-m5p2-fm1-ram-run.md` records, as §4
  "After the session" does: the tool and image hashes, the jump replies,
  the flash and label timings from the video, the §7.5 verdict and why, the
  crumbs receipt's raw hex and decode, the dump hashes and the identity.
  Copy the `*.lock` files with the receipts.
