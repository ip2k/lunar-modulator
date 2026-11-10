# 20 — M6 bench runbook: the audio path on the FM-1, from RAM

The operator steps for milestone M6 of [docs/18](18-fm1-release-plan.md):
the approved M6 audio image loaded into the FM-1's SRAM through the mask ROM
and started once, with read-only flash dumps before and after, exactly as
M5's session in [docs/19](19-m5-bench-runbook.md). This document lists only
what differs from docs/19 and repeats the steps where M6 changes them. The
image and its evidence are in
[`notes/2026-11-09-m6-image.md`](../notes/2026-11-09-m6-image.md).
Confidence marks as elsewhere.

**Status: prepared, not run.** Nothing in this document has been sent to the
FM-1 or to the Pico 2 W transporter. The host tool
[`tools/fm1-transporter/fm1t_m6.py`](../tools/fm1-transporter/fm1t_m6.py) is
**written and awaiting review**: it was tested only against the scripted fake
of the transporter's data port (`tests/test_fm1t_m6.py`), and run end to end
against that fake with the real `m6.bin` (`notes/2026-11-10-m6-tool.md`).
docs/18 says the tool is to be reviewed before use; until a review passes,
do not run it.

## 0. The gate: M5 first, and what M5 says about the watchdog

The approval is "to run after M5". Do not start this session until docs/19
has been run and its bench note written. One M5 result decides how M6 goes:

- **Why it matters.** M5's image never clears the watchdog. M6's image
  clears it at entry, after the full-frame draw, after the first pass of the
  eight lines, and then every 256 blocks (`firmware/m6/main_fm1.c`)
  [verified: source]. The full-frame draw (panel set-up and 57,600 pixels
  over polled SPI1) is not timed and has no clear inside it. On the dev kit
  the watchdog period was 4 s (`WDT_4S`), but only because the kit's ROM was
  entered from its running application (note §3) [verified]. Whether a
  watchdog runs under the FM-1's cold-entered ROM is unknown [inferred].
- **What M5 shows.** M5's step 13: a test pattern that is replaced, some
  seconds later, by V15's normal screen means the ROM leaves a watchdog
  armed, and the delay from the jump to the reset is its period (docs/19,
  step 13; record the delay).

| M5 result | M6 |
| --- | --- |
| Test pattern stays until power-off (no reset) | Run as below. Expect `F 0` on the STEP line (no watchdog armed) |
| Test pattern, then V15 after *T* seconds | **Owner decision before M6.** Recommended: run `m6-plan-2` as approved. Its failure mode is a reset into V15 with nothing on the panel, which is safe and itself bounds the frame draw. The alternative is a new build `m6-plan-3` that clears the watchdog inside the frame draw: new hash, new approval, and this tool changed to admit it. Without an answer, M6 waits |
| M5 did not run, or stopped before its jump | M6 waits. Nothing in M6 replaces M5's first-light check |

## 1. What is approved, and what is not

**Owner approval, 2026-11-10** (choice recorded verbatim: "Yes, after M5
(Recommended)"; docs/18 §3 item 6):

- **On the FM-1, RAM only, one session, after the M5 session.**
- **Image:** `m6.bin`, 9,796 B, SHA-256
  `37334c76760831e3137ec1c9d45943c3ef383f91a8fe632bfd78db07cbde3647`,
  build id `m6-plan-2`. Rebuilt reproducibly on 2026-11-10
  [verified: `notes/2026-11-10-m6-tool.md`].
- **SRAM written by `memw`:** only `[0x01C02000, 0x01C04644)`, in three
  chunks of 4,096, 4,096 and 1,604 B. At run time the image uses SRAM up to
  `0x01C06C70` and nothing at or above it, inside the accepted bound
  `0x01C07E00`, the window where the ROM ran JieLi's loader on this unit
  [verified: note §1].
- **Accepted with it:** timing at the ROM's clock, not 360 MHz, and the
  −18 dBFS test arpeggio until power-off.
- **Route:** docs/17's Pico 2 W transporter (UF2 unchanged), driven by
  `fm1t_m6.py`, a copy of `fm1t_m5.py` with the approved image swapped and
  one hardening from its review (lengths, §2).
  `fm1t_m5.py` was patched with the same length rule on 2026-11-10 (new
  SHA-256 `9673ccd8…`, awaiting the owner's approval; docs/19 §1) and is pinned
  by `tests/test_fm1t_m6.py`.
- **Recovery:** a power cycle, then docs/17.
- **The loader:** "loader not uploaded" in the M6 note's scope is read as
  M5's note words it, "not uploaded in the RAM-run session": Part B's ROM
  entry never sees JieLi's loader, while Parts A and C upload it for the
  read-only `info` and `dump`, exactly as docs/19 does. The M6 note's own
  sequence ("as docs/19 for M5 … checks the identity") needs it there
  [inferred: reading of the two notes].

Not covered: any other image or build id (including `m6-plan-3`), any flash
write or erase, the soft key, a second RAM run in the session, upstream
`fm1t.py` for any step, and the transporter console's `k`. Each needs its
own owner yes.

## 2. What the tool will and will not send

`fm1t_m6.py` has the same subcommands, allow-lists, refusals and exit codes
as `fm1t_m5.py` (docs/19 §2), except that every `memw`, `memr` and `ldr`
length must be plain decimal with no leading zero. The transporter parses
lengths with `strtoul(..., 0)` (`src/transporter_proto.c` at `80c5012`), so
`010` would be 8 B there and 10 B here [verified: source]; the tool's own
code never writes one, and the allow-list now refuses one too. `tests/test_fm1t_m6.py` pins every code line
on which the two differ. What changes:

| Subcommand | Lines it can send |
| --- | --- |
| `status`, `rekey --fm1-is-off`, `info`, `dump`, `compare`, `preflight` | as docs/19 §2 |
| `ramrun m6.bin --sha256 …` | `ping`, `status`, `memw 0x1c02000 4096 …`, `memw 0x1c03000 4096 …`, `memw 0x1c04000 1604 …`, `memr` ×3, `jump 0x1c02000 0x1` |

- **Only m6.bin.** `ramrun` admits only the image above, checked against
  `--sha256` before the port opens. It refuses `m5.bin` (and `fm1t_m5.py`
  refuses `m6.bin`) [verified: test].
- **Only the image's range.** `memw` and `memr` are admitted at
  `0x1c02000`, `0x1c03000` and `0x1c04000` only, and must end at or before
  `0x01C04644`; the gate also holds the bytes, their order, and refuses the
  jump until all 9,796 B were written [verified: test].
- **How the transporter writes it.** Each `memw` goes to the ROM in 512 B
  writes, so the third chunk ends with a 68 B write (M5's image ends with a
  64 B one) [verified: transporter `do_memw`, `JL_IO_SIZE` 512]. This
  project's records show no RAM-run write with a short final ROM write on
  hardware yet, so M5 is its first test here [inferred: this repo's notes;
  other transporter users' runs not checked]. If the
  ROM handles it differently, the three `memr` read-backs differ and the tool
  stops before the jump [verified: test with a corrupted `memr`].
- **One attempt.** The lock is `fm1t_m6-ramrun.lock` next to the receipt.
  A run directory that holds M5's `fm1t_m5-ramrun.lock` is refused too, so
  M6 runs from its own directory.
- **Never:** `uboot` (the soft key `F0 22 24 35 7D F7`), the `7F` upgrade
  command, `wsec`, `runapp`, syscmd 33–36/48, `5A AA A5` frames, loader
  command `0xFC12` or the raw `0xA1` eFuse write, or any write below
  `0x4000` or to flash at all. None of these is on any allow-list
  [verified: test].

Exit codes: `0` as expected; `1` refused before the port was opened; `2`
bad arguments; `3` stopped after the port was opened.

## 3. Before the session (desk, no hardware)

As docs/19 §3, with these values:

1. Build and check, on the Mac:

   ```bash
   LUNAR_BUILD_ID=m6-plan-2 LUNAR_SESSION=<label> \
     bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> m6
   python3 tools/fm1-transporter/fm1t_m6.py preflight \
     --image build/jieli-m6/m6.bin --sha256 37334c76760831e3137ec1c9d45943c3ef383f91a8fe632bfd78db07cbde3647
   ```

   The build must give `m6.bin` `37334c76…` and `audit_link: PASS`. If the
   hash differs, stop: never change the pinned hash to match a build.
   `preflight` prints the tool's own SHA-256; it must equal the hash the
   review approved (owner item, §6).
2. Copy `fm1t_m6.py`, `m6.bin` and `wl82loader.bin` to a **new** run
   directory on bench01, for example `~/m6-run/` (not `~/m5-run/`: the tool
   refuses M5's directory), and rerun `preflight` there with
   `--loader wl82loader.bin`.
3. The ModemManager and `fuser` checks of docs/19 §3.

On bench01 (`<serial>` from `ls /dev/serial/by-id/`):

```bash
cd ~/m6-run
unset FM1T_LOADER
P=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if02   # data port
C=/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if00   # console, read only
T="python3 fm1t_m6.py --port $P"
SHA=37334c76760831e3137ec1c9d45943c3ef383f91a8fe632bfd78db07cbde3647
```

The console reader is the same read-only `cat` as docs/19 §3; never type
into the console.

## 4. The session

**Owner, before step 1:** everything in docs/19 §4, plus:

- **Something to listen with, at a low level.** The image plays an
  A3–C#4–E4–A4 arpeggio at −18 dBFS, about 0.74 s per note, until
  power-off. The image does not read the MASTER pot, so the knob may not
  change the level [verified: no ADC symbol in the rebuilt `m6.symbols.txt`; the
  effect on the analogue path is inferred]. Do not wear
  headphones when the unit is switched on; listen to the speaker or line
  output with the monitor turned down first, then bring it up.
- A camera or phone ready to photograph the TFT and record the sound.
- A tuner app, or a reference A (220 or 440 Hz), for the pitch check.

### Part A: dumps before (ROM entry 1)

docs/19 steps 1–8 unchanged, with `$T` as above and the receipts named the
same way. The dumps are read-only and use JieLi's loader exactly as in M5;
the RAM run in Part B starts from a fresh ROM entry with no loader.

### Part B: the RAM run (ROM entry 2)

9. **Claude:** `$T --log 09-rekey.jsonl rekey --fm1-is-off`; restart the
   console reader (docs/19 step 9).
10. **Owner:** start filming the TFT with sound, then switch the FM-1
    **on**. **Claude** waits for `UBOOT READY`.
11. **Claude:** `$T --log 11-status.jsonl status`
    - Expected: `uboot=1 v15=0 loader=0 loader_running=0`.
12. **Claude:** `$T --log 12-ramrun.jsonl ramrun m6.bin --sha256 $SHA`
    - It sends `memw` ×3 (`0x1c02000` 4,096 B, `0x1c03000` 4,096 B,
      `0x1c04000` 1,604 B), `memr` ×3 and compares, then one
      `jump 0x1c02000 0x1`, then nothing more.
    - Expected output: `loaded 9796 B at 0x1c02000; read-back equal`, then
      `ERR jump after ~2000 ms: … Image presumed running; the TFT and the
      codec's output are the proof`, exit 0 [verified: fake transporter].
    - Any other result exits 3; do not rerun. If the receipt has a `tx` line
      `jump 0x1c02000 0x1`, observe and record step 13 first.
13. **Owner, at the unit:** what to look for and listen for is in the table
    below. Photograph the panel at about 5 s and again at about 30 s after
    the jump (when the tool prints its verdict), and record at least 10 s of
    sound. Write down how long after the jump each thing appeared; the
    receipt's `jump` line has the time it was sent.
14. **Owner:** switch the FM-1 **off**; the sound stops and SRAM is lost
    [inferred]. **Claude:** `$T --log 14-status.jsonl status` must show
    `uboot=0 v15=0`.

**The panel.** First a frame with "LUNAR M6" and `m6-plan-2`, then eight
lines, redrawn a few bytes per block (`firmware/m6/m6_screen.c`)
[verified: source]:

| Line | Expected | What it means |
| --- | --- | --- |
| `BLK n` | rising by about 690 per second | 64-frame blocks played |
| `TPB n` | about 2176 if the FM-1 matches the kit | stopwatch ticks per block over the last 1,024 blocks |
| `FS24 n` | about 44118 | the rate if the stopwatch's oscillator is 24 MHz |
| `FS40 n` | about 73529 | the rate if it is 40 MHz |
| `LOAD x.y MAX x.y` | small, on the kit 11.6 for the render; record it | render and busy time as % of a block, at the ROM's clock |
| `LATE n MISS n` | `LATE 0 MISS 0` | blocks rendered late, or missed |
| `PCM <hex>` | **`PCM 92CF0315`** once 1,024 blocks have played (about 1.5 s) | hash of the first 1,024 blocks; equal on host and kit [verified: note §3] |
| `STEP n RC [-]n F n` | `STEP 8 RC 0 F 0` (or `F 64`) | 8 = hashed and still playing; it never reaches 9 on the FM-1, which plays until power-off |

`TPB`, `FS24` and `FS40` cannot tell the rate on their own: if the
stopwatch and ALNK0 share a clock root, the ratio is the same at either
oscillator (note §3) [verified: kit run]. **The pitch does:** the
arpeggio's lowest note is A3, 220 Hz, at 44.1 kHz, and about 367 Hz at
73.5 kHz, which sounds about a major sixth high [inferred: arithmetic]. A
tuner reading of A for the first and last notes settles it.

**Reading the STEP line** (`firmware/m6/m6_core.h`) [verified: source]. Steps
1–9 are `ENTERED`, `CORE_OK`, `TIMER_OK`, `REPORT_OK`, `STOPWATCH_OK`,
`ALNK0_OK`, `FIRST_BLOCK`, `HASHED`, `FINISHED`. `F` is the sum of: 1 timer
fallback, 2 no ALNK0 clock, 4 stall, 8 pins masked (kit only), 16 report
failed, 32 ALNK0 start refused, 64 watchdog armed at entry (and being
cleared), 128 a watchdog clear hit a busy P33 bus.

| What the owner sees and hears | Reading |
| --- | --- |
| Frame, eight lines, `PCM 92CF0315`, `STEP 8 RC 0`, a clean arpeggio at A | **Pass.** Record `TPB`, `FS24`, `LOAD`, `MAX` and the pitch |
| As above with `F 64` | Pass. A watchdog was armed under the ROM and the image is clearing it: record it, it matters for every later image |
| Lines and `PCM 92CF0315` but silence | ALNK0 runs but the codec did not start from ALNK0 alone (#176's assumption [inferred, strong] fails). A finding, not a fault |
| `STEP 6 … F 2` | ALNK0 never produced a block (no clock) |
| `STEP 5` with `RC` not 0 and `F 32` | `lunar_alnk0_start` refused; `RC` is its result code |
| `LATE` or `MISS` not 0 | timing trouble at the ROM clock; record the numbers |
| The sound stops, the lines keep redrawing, `F 4` | ALNK0 stopped delivering blocks after it started (a stall): the image stops ALNK0 and keeps the panel up (`firmware/m6/m6_core.c`) [verified: source]. Record `BLK` and when the sound stopped |
| Lines with `BLK 0`, `STEP 4`, silence | the stopwatch (TIMER4) did not count, so ALNK0 was never started [verified: `main_fm1.c`] |
| Dark TFT but the arpeggio plays | the panel failed (`F 16`, not visible) and audio ran without it; record it and go on with step 14 |
| The arpeggio a sixth high | the rate is about 73.5 kHz: the oscillator is 40 MHz, not 24 |
| Frame, then V15's normal screen before the lines | a watchdog reset during the frame draw (§0). Safe. Do not run any tool command against the running V15; go on with step 14, then stop and ask the owner before Part C (docs/19 step 13) |
| Dark TFT and silence | record it; the run has proven nothing harmful. Go on with step 14 |

If V15's normal screen appears at any point, photograph it and send nothing
to it, as in docs/19 step 13: step 14, then the owner decides on Part C.

### Part C: dump after (ROM entry 3)

docs/19 steps 15–17, with `$T` as above: the after-dump must be identical
to `before-A.bin`.

### Part D: back to V15

docs/19 steps 18–20 unchanged: disconnect the Pico's wires, switch the
FM-1 on, and run the read-only identity query from the Lunar checkout.
Expected `identity: FM-1_015`, `checksum_ok: True`.

### After the session

As docs/19, with the note at `notes/YYYY-MM-DD-m6-fm1-ram-run.md`
recording: the tool hash and the review that approved it, the image hash,
the console lines, the jump reply and its `ms`, the panel photographs with
every line transcribed, the pitch reading and the recording, the dump hashes
and the identity. docs/18's M6 row is updated from the note.

## 5. Stop conditions and recovery

docs/19 §5 applies unchanged: any non-zero exit, any difference between the
dumps, an `info` other than `OK key=980F type=3 id=856014`, or the owner
saying stop. M6 adds one: **if the sound is loud, harsh or unexpected,
switch the FM-1 off at once**; the image has no other way to stop.

Recovery is the same: a power cycle returns V15 (RAM only); if V15 does not
boot, docs/17 on the owner's go-ahead.

## 6. Open points and owner items

- **Owner item: the tool's review and hash.** `fm1t_m6.py` must be reviewed
  before use (docs/18 §3 item 6). Its SHA-256 at this writing is in
  `notes/2026-11-10-m6-tool.md`; any change after the review changes it,
  and `preflight` prints it on bench01.
- **M5's tool length gap: resolved for M5, pending approval.** The owner
  answered 2026-11-10 "Patch M5 too". `fm1t_m5.py` now has the same length
  rule as `fm1t_m6.py`; its new SHA-256 is
  `9673ccd83622a208644ae2b467a1fa5964b01807d2639b3d409537d5136c1a72` (was `c0e704e3…`) and is **not yet
  approved**: the owner must approve it before the M5 bench session
  (docs/19 §1). The M6 tool is unchanged (`d3714c83…`).
- **Owner item, only if M5 shows a watchdog reset:** the §0 decision.
- **Answered by this session:** whether ALNK0 alone starts the FM-1's codec;
  the FM-1's audio rate (by pitch); the stopwatch's ticks per block on the
  FM-1; timing at the ROM's clock; and, from `F`, whether a watchdog runs
  under the cold-entered ROM (if M5 did not already show it).
