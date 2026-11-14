# 22 — M8 runbook: the first Lunar flash install on the FM-1

The operator steps for milestone M8 of [docs/18](18-fm1-release-plan.md):
a Lunar install package written into the FM-1's application region
`[0x4000, 0x93000)` through the mask ROM and the Pico 2 W transporter of
[docs/17](17-pico2w-recovery.md), read back, booted, and restored to stock
V15 with the same tool. Confidence marks as elsewhere.

**Status: prepared, not run.** Nothing in this document has been sent to the
FM-1 or to the transporter. The host tool
[`tools/fm1-transporter/fm1t_m8.py`](../tools/fm1-transporter/fm1t_m8.py) was
tested only against a fake of the transporter's data port
(`tests/test_fm1t_m8.py`), whose `wsec` follows the transporter source
(kurogedelic FM-1-transporter `80c5012`, `do_write_sector` and
`jl_flash_write_sector`) [verified: source]. **No Lunar image is approved**:
M5 showed nothing on the FM-1 (`notes/2026-11-10-m5-fm1-ram-run.md`), so the
image M8 will write does not exist yet. `install` refuses every package until
the owner approves one (§1).

## 0. Where M8 sits

M8 is the first time Lunar code is written to the FM-1's flash. docs/18 puts
it after M5–M7: a Lunar image must have run from RAM on the FM-1 and shown
that it survives the ROM watchdog before it is written to flash. Until then
this runbook and its tool are ready, and nothing else happens.

What M8 does not do:

- It never writes `[0x0, 0x4000)` (the stock SPL and boot area) or anything
  at or above `0x93000` (V15's VM, the settings area).
- It never sends the soft key `F0 22 24 35 7D F7`, syscmd 33–36/48, a
  `5A AA A5` frame, the `7F` upgrade command, loader command `0xFC12` or the
  raw `0xA1` eFuse write (CLAUDE.md traps 7, 9 and 11).
- It never runs while a working V15 is attached (D2): its first two lines
  are `ping` and `status`, and it stops on `v15=1`.
- It does not use the stock OTA path. That is M12w's job.

## 1. What the owner approves

Three separate approvals, each recorded in HANDOFF.md with its date and the
owner's words:

1. **The image.** The owner approves one install package by its SHA-256 and
   size. That hash, the size and a build id go into `APPROVED_PACKAGE_SHA256`,
   `APPROVED_PACKAGE_BYTES` and `APPROVED_BUILD_ID` at the top of
   `fm1t_m8.py`, in a reviewed PR. There is no command-line override. Today
   all three are `None` and `install` refuses before it opens the port.
2. **The tool.** The owner approves `fm1t_m8.py` by its own SHA-256, after
   the image hash is in it (changing the file changes the hash). `install
   --write` and `restore --write` refuse unless `--tool-sha256` equals the
   running file's hash. `preflight` prints it.
3. **The session** (docs/07 §4, docs/18 §4): the bench session itself, with
   the owner at the FM-1.

**The restore precondition is wider than the install precondition, on
purpose.** `install` needs the app region to be a known image (stock V15
today) and the identity read before keying to match it. `restore` accepts
any app region, because an interrupted install leaves a mix of old and new
sectors that no hash can name. It still needs two identical fresh reads, the
stock head `[0x0, 0x4000)` and the pinned V15 package, and it writes only
inside `[0x4000, 0x93000)`. `restore` takes no one-attempt lock, so it can
be rerun. This is the owner's to confirm with the §1 approvals.

## 2. What the tool sends

Every line goes through one class (`Link`), which checks it against an
allow-list for the subcommand and logs it to the JSONL receipt (`--log`, a
new file). In `install` and `restore`:

| Line | When | Limits |
| --- | --- | --- |
| `ping`, `status` | first | stop unless `uboot=1 v15=0` |
| `ldr offsets N CRC`, then the loader | always for `install --write` (which refuses a transporter already holding a loader); otherwise only if none is held | loader pinned by SHA-256 `d41da612…`, 24,064 B |
| `info` | once | must be exactly `OK key=980F type=3 id=856014` |
| `read 0x0 1048576` | twice before, once after | full 1 MiB dumps, saved next to the receipt |
| `wsec 0xADDR CRC` + 4,096 B | each planned sector, once | `0x4000 ≤ ADDR < 0x93000`, sector-aligned, lower-case hex with no leading zero (the transporter reads a leading `0` as octal); the payload is checked against the target's own bytes before the header goes out |
| `read 0xADDR 4096` | after each `wsec` | same range as `wsec` |

Never sendable: `uboot`, `k`, `runapp`, `memw`, `jump`, `memr`, `rekey`
(except in its own subcommand), and anything else not in the table.

The transporter itself refuses a `wsec` outside `[0x4000, 0x93000)` (`ERR
range`) and erases, programs and verifies each sector [verified: source,
`JL_WRITE_MIN`/`JL_WRITE_END`]. The tool checks the same range independently,
then reads every written sector back and compares all 4,096 bytes.

## 3. Before the session (desk, then a read-only check)

1. **Check the package.** On the approved package:

   ```bash
   python3 tools/jieli/build_fwsc.py verify lunar.fwsc
   python3 tools/jieli/package_guard.py --package <staged tree> --stock <unpacked V15>
   ```

   Both must pass. `fm1t_m8.py` does not repeat these checks (it is one file
   with no project imports, so its hash covers all its logic); it checks the
   package hash, its size, and that its flash region keeps V15's head.
2. **Preflight**, on the bench host, with no hardware touched:

   ```bash
   python3 fm1t_m8.py preflight --package lunar.fwsc --sha256 <approved> \
       --v15 FM-1.fwsc --loader wl82loader.bin
   ```

   It prints the tool's SHA-256 (compare with the approved one), the pinned
   port, the loader and V15 checks, and the sectors the install would write
   from stock V15 and the restore would write back. Record the output.
3. **Read the identity** before the unit is keyed, with the FM-1 on the
   computer, not on the Pico (docs/17 §7 step 5):

   ```bash
   tools/fm1_identify.sh
   ```

   It must say `FM-1_015`. Pass exactly that to `install --identity`. The tool
   checks it against the layout it reads from flash; a mismatch stops before
   any write.

## 4. The session

Wiring, the console and ROM entry are docs/17 §2–§4: FM-1 off, console open,
`rekey`, FM-1 on, wait for `UBOOT READY`. Use `fm1t_m8.py`'s own `status` and
`rekey --fm1-is-off`, not upstream `fm1t.py`.

```bash
P=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_560A5ACCF298BDCB-if02
python3 fm1t_m8.py --port $P --log s1/status.jsonl status    # uboot=1 v15=0
```

1. **Dry run.** Reads twice, checks, plans, writes nothing:

   ```bash
   python3 fm1t_m8.py --port $P --log s1/dry.jsonl install lunar.fwsc \
       --sha256 <approved> --identity FM-1_015 --loader wl82loader.bin
   ```

   The plan must match preflight's. Keep `s1/dry-before-a.bin` and
   `-before-b.bin`: they are this session's backups (the two must be equal;
   the tool checks).
2. **Write, in a fresh ROM entry.** The dry run left the pinned loader on the
   transporter, and `install --write` refuses a held loader so that the one it
   writes with is the one it uploaded itself. So: FM-1 off, `rekey
   --fm1-is-off`, FM-1 on, `UBOOT READY`, `status`, then the same command plus
   `--write --tool-sha256 <approved>`, with a new `--log`. Run it as your own
   user, not root or sudo (the lock is under your home; give your user the
   serial port through the `dialout` group). It takes the one-attempt lock
   (`~/.local/state/fm1t_m8/install-<sha>.lock`) just before the first
   `wsec`, writes each planned sector once, reads each back, and ends with a
   full read that must equal the package over `[0, 0x93000)` and the
   before-dump above it. It prints each sector as it goes.
3. **Boot.** FM-1 off, **disconnect the Pico** (docs/17 §7 step 2), FM-1 on.
   Record what the display shows and the identity (`tools/fm1_identify.sh`).
   This is the M8 result: Lunar boots, or it does not.
4. **Back to V15.** Rekey (§4 opening), then:

   ```bash
   python3 fm1t_m8.py --port $P --log s2/restore.jsonl restore --v15 FM-1.fwsc \
       --loader wl82loader.bin --write --tool-sha256 <approved>
   ```

   Boot as in step 3. The identity must read `FM-1_015`.

Write the bench note (`notes/YYYY-MM-DD-m8-fm1-flash-install.md`) with the
receipts' summary lines, the hashes of the dumps and what the display showed.
Keep dumps and receipts in `scratch/`; never commit them.

## 5. Stop conditions and recovery

| The tool says | What it means | Do |
| --- | --- | --- |
| no `PONG` | the wrong port, or an earlier session stopped inside a 4,096-byte payload and the transporter is still counting bytes (it has no timeout) | replug the Pico only, not the FM-1; then `status` [inferred: the FM-1 runs on its battery with no VBUS from the Pico, so it stays on; not yet checked on the bench] |
| no reply to `status` after a failed write | core 1 may still be finishing a `wsec` | leave the FM-1 on, wait 30 s, `status` again |
| `D2` / `v15=1` | a running V15 is attached | nothing more; disconnect, start over from docs/17 §4 |
| `uboot=0` | the ROM is not entered | rekey (docs/17 §4) |
| `info` other than expected | another chip key or flash part | stop; not this unit |
| the two reads differ | unstable read | stop; rekey and run again |
| head is not V15's | the boot area is not stock | stop; nothing here applies (docs/17 does not write it either) |
| not a known region | the unit is not on stock V15 | `restore` first, then install |
| identity does not match | wrong `--identity`, or the wrong unit | read the identity again (§3 step 3) |
| a failed `wsec`, no reply, or a read-back mismatch | a sector is erased or partly written | **do not power-cycle and do not retry the install**: keep the FM-1 on and in UBOOT, and run `restore` |
| final read differs | something outside the planned sectors changed | keep the FM-1 on; run `restore`; then compare the dumps |
| any stop, or Ctrl-C, after a `wsec` went out | the tool adds "run `restore`" and lists `wsec_sent` in the receipt | keep the FM-1 on; run `restore` |

`restore` uses the loader a failed install left on the transporter (and
records that it did), so it needs no rekey. It rereads the flash twice, writes back only the sectors that differ
from stock V15, and checks each one. It can be run again after it fails. If
the transporter itself stops answering, power-cycle the transporter, not the
FM-1, if you can; otherwise follow docs/17 from §4, which recovers an
unbootable FM-1 with an intact head (D1).

The one-attempt lock is never removed by the tool. A second install of the
same image needs the owner's decision and a new approval.

## 6. Open points

- **The image.** Waits on M5–M7 (the watchdog question in docs/20 §0).
- **Approvals.** §1 items 1–3, including the restore precondition.
- **Other flash parts.** Units with UCUN UC25HQ80 (`0xB36014`) are refused by
  the `info` pin; adding them is a separate change
  (`notes/2026-11-10-flash-uc25hq80.md`).
- **Other layouts.** Only stock V15's app region is a known region. A unit on
  FM-1_092 or another layout must first be restored to V15 by docs/17.
