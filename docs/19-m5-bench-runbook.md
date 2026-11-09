# 19 — M5 bench runbook: the first Lunar code on the FM-1, from RAM

The operator steps for milestone M5 of [docs/18](18-fm1-release-plan.md):
the approved M5 test-pattern image loaded into the FM-1's SRAM through the
mask ROM and started once, with read-only flash dumps before and after. It
turns the plan in
[`notes/2026-11-08-ram-runner-devkit.md`](../notes/2026-11-08-ram-runner-devkit.md)
§5 into numbered steps. Confidence marks as elsewhere.

**Status: prepared, not run.** Nothing in this document has been sent to the
FM-1 or to the Pico 2 W transporter. The host tool was tested only against a
scripted fake of the transporter's data port (`tests/test_fm1t_m5.py`).

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
| `rekey --fm1-is-off` | `ping`, `status`, `rekey` (only when nothing is mounted) |
| `info --loader …` | `ping`, `status`, `ldr …` ×6 (the loader into the Pico's buffer), `info` |
| `dump OUT --loader …` | the `info` lines plus `read 0x0 1048576` |
| `ramrun m5.bin --sha256 …` | `ping`, `status`, `memw 0x1c02000 4096 …`, `memw 0x1c03000 64 …`, `memr` ×2, `jump 0x1c02000 0x1` |

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
- **`info` and `dump` accept only JieLi's `wl82loader.bin`** (24,064 B,
  `d41da612…`), which runs from RAM and reads flash.
- **Receipts.** Every invocation writes a new JSONL receipt (`--log`, never
  overwritten) with every line sent and received; payloads are logged by
  length, CRC-32 and SHA-256.

Exit codes: `0` as expected; `1` refused before anything was sent; `2`
bad arguments; `3` stopped after the session started (an unexpected reply).

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

`rekey` reboots the transporter, which ends `cat`; start it again (a new
`N`) within 10 s of every `rekey`.

## 4. The session

**Owner, before step 1:**

- The FM-1's battery is charged.
- The FM-1 is **switched off**. Check the switch itself; with the ROM
  running the display stays dark, so it is no guide.
- The Pico is wired as in docs/17 §3 (GP0 to D+, GP1 to D−, GND to GND,
  VBUS not connected), and plugged into bench01. Nothing else is connected
  to the FM-1.
- A camera or phone is ready to photograph the TFT and the LEDs.

### Part A: dumps before (ROM entry 1)

1. **Claude:** `$T --log 01-status.jsonl status`
   - Expected: `uboot=0 v15=0`. `v15=1` means the FM-1 is on, running V15:
     the owner switches it off, and Claude repeats this step. The tool sends
     nothing to a running V15 but `status` itself, which goes to the Pico.
2. **Claude:** `$T --log 02-rekey.jsonl rekey --fm1-is-off`, then restart the
   console reader within 10 s.
   - Expected: `OK rekey`, then on the console
     `KEY: sending 0x16EF, polarity A (D+ clock, D- data). Switch the FM-1 ON now.`
     and a steadily rising `KEY: … packets` count.
   - The transporter's "power-cycle the FM-1 now" is ignored: the FM-1 stays
     off until the count runs.
   - **Stop** if `D+ high in gap` shows within a few packets: the FM-1 is
     probably on. The owner switches it off; repeat step 2.
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
   console reader; the key runs as in step 2.
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
    - Any other result exits 3. Do not rerun `ramrun` in this ROM entry
      (there is no second attempt in this session).
13. **Owner, at the unit:**
    - The TFT should show the test pattern with `m5-plan-1`.
    - The LEDs should blink `step` times, pause, and repeat. Six blinks is
      the last step; count them over two or three cycles. What each count
      means is in [`firmware/m5/README.md`](../firmware/m5/README.md).
    - Photograph the TFT and film at least two LED cycles.
    - A dark TFT is a result, not a danger: record it, and go on.
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
20. **Claude:** the read-only identity query (D4), as in docs/17 §7:

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
- any tool step exits non-zero (3), or prints a reply not listed above;
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
  - unplug the Pico from bench01 and plug it back in, with the FM-1 off;
  - a transporter that boots with nothing pulling D+ up starts keying by
    itself [verified: upstream `src/main.c`], the same as `rekey`;
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
