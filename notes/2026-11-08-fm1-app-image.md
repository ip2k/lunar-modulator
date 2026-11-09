# 2026-11-08: the first complete FM-1 application image (offline)

Branch `feature/2026-11-08@fm1-app-image`. Toward docs/18 M8–M11. **Nothing
was installed or run on an FM-1, and nothing was run on the dev kit.** No
traffic went to the FM-1 or the Pico 2 W transporter. Everything below is a
build plus its offline gates.

## What was built

`tools/jieli/prepare-fm1-app.py` prepares a private AC79 SDK tree (pinned
V1.2.13 libraries at `e30b1ee`, demo_hello shell). It builds on the dev-kit
pipeline preparer with the release-rule settings: cap8, trunc12,
`--size-profile`, the reviewed scheduler archive, and three pipeline cycles.
From that tree it:

- **removes the kit's workload**: UART boot control, `sdk_worker.c`, the
  internal-DAC transport, the fixed test pattern, and the timing and
  arithmetic probes (`tools/jieli/fm1-app.mk` filters them out of the link);
- **adds the FM-1 application** (`firmware/fm1`):
  - the pipelined app at 44,118 Hz with no lifetime bound
    (`LUNAR_PIPELINE_UNBOUNDED`, a new switch in
    `firmware/devkit/renderer_pipeline_sdk.c`; the kit's soak keeps its bound);
  - ALNK0 audio from PR #176 and the board and display layer from PR #179;
  - TRS MIDI in;
  - the fail-open counter and supervisor from PR #180, placed as
    `prepare-failopen-devkit.py` places them: the setup.c hook and a 64 B
    record below `HEAP_END`;
- **links fm1-nes's `boot_info` bridge** (Apache-2.0) with
  `--wrap=boot_info_init` and sets `__SDRAM_SIZE__` to 0 (internal RAM only,
  as `boot_compat.c` requires);
- **sets the rails to the FM-1's stock levels**: VDC14 1.60 V (DCDC on, as
  before), SYSVDD 1.38 V, VDDIOW 3.2 V, LVD 2.6 V; VDDIOM was already 3.2 V
  [reported: fm1-nes `board_power.c`, from stock FM-1_010; CLAUDE.md trap
  12];
- **unmaps the debug UART's PB3 TX** by default (PB3's role on the FM-1 is
  unknown), keeping the driver; `--debug-uart pb3` keeps the pin;
- **sets `FM1_GPL_MODS`** from `--gpl` (default 1, as the project switch says).

The clock is not switched by the app: the stock SPL sets 360 MHz before the
app runs [verified: V15 `isd_config` SYS_CLK, CLAUDE.md], and this image
contains no clock code [inferred: no clock writes added; `clk_early_init`
is the SDK's own].

Built on aeon in `lunar-jieli-check:bookworm` (`--rm`, `--network none`,
labels project=lunar-modulator, session=wave2) with
`tools/jieli/build-fm1-app-on-aeon.sh`.

## Gates (both builds)

| | FM1_GPL_MODS=0 | FM1_GPL_MODS=1 |
| --- | --- | --- |
| preparer build id | `0x46b5c0c2` | `0xb2d149ac` |
| `app.bin` | 556,540 B | 556,540 B |
| sha256 | `d204f88e…21e7ef` | `f6a1b801…aacebf` |
| V15 slot 581,564 B: spare | **+25,024 B** | **+25,024 B** |
| `.text` / `.ram0_data` / `.cache_ram_data` | 399,776 / 129,584 / 27,180 B | same |
| cache RAM (28,672 B) | 1,492 B spare | same |
| RAM static (`.ram0_data` + `.ram0_bss`) | 474,760 B, ends `0x1c73e88` | same |
| heap (HEAP_END − HEAP_BEGIN) | 48,716 B: +1,504 B over the 47,212 B minimum | same |
| `fm1_budget.py` | PASS (5/5) | PASS (5/5) |
| `audit_link.py` | PASS: 0 failed, 1 pending | PASS: 0 failed, 1 pending |

[verified: aeon build logs, `fm1_budget.py` and `audit_link.py` output]

- **`audit_link.py`**:
  - `late_initcall` is exactly `[sdk_meky_check]`;
  - none of the forbidden key-check symbols is present;
  - there is no `0x0200012E` stub and no reference to the mailbox, to IRQ 123
    or to the eFuse SFRs.
  - Its one pending item, `sdk_meky_check`'s scheduling, was checked by hand
    in the vendor objdump. It makes two `request_irq(123, 6, isr_check_key,
    0/1)` calls and one `sys_timer_add(_mkey_check, 8000)` call, which is
    the expected vendor pattern [verified: disassembly of the GPL=0 ELF].
- **`--wrap=boot_info_init` took effect.** The startup code calls
  `__wrap_boot_info_init` (`0x2001d54`), and that calls the SDK's
  `boot_info_init` (`0x2000292`) [verified: disassembly].
- **The GPL=1 build links no GPL code.** The FM-1 module list
  (`FM1_MODULES=dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance`)
  names no Felucca engine, so the two images differ only in 19 bytes: the
  build id and the receipts' hashes [verified: `cmp -l`; no `felucca` object
  in the GPL=1 build tree]. The GPL=1 image is still never to be shared
  (CLAUDE.md); the GPL=0 image is the shareable variant in principle, but
  nothing is published.
- **The heap minimum is borrowed.** The 47,212 B minimum is the dev-board
  pipeline's (measured after the kit's DAC opens). The FM-1 app uses no
  `JL_AUDIO` DAC and its ALNK0 buffers are static, so its real need is
  probably lower [inferred]. It has not been measured.
- **Against the kit baseline.** The kit's cap8 + trunc12 + size-profile
  image measured 568,988 B (+12,576 B). This image is 12,448 B smaller in
  total and 11,008 B smaller in `.text`, because the test pattern, the
  probes and the DAC path have gone [verified: same build recipe, aeon].

## Host tests

- `tests/test_fm1_input.py`, 18 tests: queue order and drops; key and button
  debounce; encoder detents in both directions; MASTER's first reading and
  its filter; MIDI and USB-MIDI decoding; the router's octave, channel map,
  note balance, panic, cutoff and resonance clamps, and its deferred
  controls.
- `tests/test_prepare_fm1_app.py`, 4 tests, using a synthetic SDK: the tree
  edits, the flag order before `include lunar-renderer.mk`, the GPL switch,
  the debug-UART option and the bad-argument refusals.
- The full numbers are in the PR's test results.

## Not done or not tested

- **No run anywhere.** This image has no UART boot control, so on the dev kit
  it would end the unattended UART ARM/ENTER recovery cycle (CLAUDE.md). It
  also drives FM-1 pins (the PA matrix lines, SPI1 on PC7–PC10, ALNK0) that
  are wired differently on the kit. The pieces that are independent of the
  board (the pipeline, cap8, trunc12 and the 360 MHz scaling) were measured
  on the kit in earlier lanes (PR #160 and others); the FM-1 adapter itself
  was not. Nothing here says how the FM-1 behaves.
- **No USB.** The image has no USB device stack:
  - the unit will not enumerate as `4C4A:C755`;
  - USB-MIDI input is not wired, although its packet decoder is written and
    tested;
  - the stock OTA update path is absent.

  Recovery from this image is the fail-open counter, the key combination or
  docs/17. M11's USB half needs the SDK's USB device route; the SDK's UAC
  headers are GPL (CLAUDE.md), so that work needs care.
- **The panel UI is fenced.** The pipelined app refuses `fm1_app_key`,
  `_button`, `_encoder`, `_pitch_bend` and `_all_notes_off` while a block is
  in flight [verified: sim/web/src/fm1_app.c]. While audio streams, that is
  nearly always. The router therefore applies only the actions that are safe
  between blocks:
  - unit note on/off for sounds 1, 3 and 4;
  - sound 1's filter cutoff and resonance;
  - MASTER, without its popup.

  Every other button and encoder, sound 2's notes and pitch bend are counted
  as deferred. Widening the fence is app work (docs/18 M10).
- **Screen.** The boot screen is the M5 test pattern labelled "LUNAR FM-1".
  There is no UI framebuffer: the app's 115,200 B TFT buffer does not fit
  beside the audio, with 25 KB of flash and 1.5 KB of heap to spare. That is
  an owner and design question, not a cut made here.
- **Other open items:**
  - LEDs stay off;
  - the battery is read but not used;
  - the encoder direction, edges per detent and button labels 2–11 are
    unconfirmed (`TODO(hardware)`);
  - the panel task scans every 10 ms tick, so fast encoder turns may lose
    detents.
- **Release rule (M9).** The images carry the release-rule pipeline, but
  nothing about the rule has been measured on an FM-1.

## Owner decisions raised (none taken here)

1. **The recovery key combination.** The image enters mask-ROM update mode
   when OCT− and OCT+ are held alone on three scans at power on. This is a
   proposal (docs/07 §4 rule 4).
2. **The debug UART.** PB3 TX is off by default. Keeping it gives a boot log
   but drives an unknown FM-1 pin.
3. **USB.** The first FM-1 install image has no USB-MIDI and no stock OTA
   path. Either accept that for a RAM-only or first install (recovery through
   fail-open or docs/17), or add the USB device route first.
4. **The display budget.** A full UI framebuffer does not fit as things
   stand. The PR #175 fit tables list the candidates; none is chosen here.
5. **Hardware.** Any FM-1 run of this image needs the separate §4 approval,
   which has not been given.

## Files left on disk

On aeon, under `/datasets/lunar-modulator/fm1-wave1/fm1-app-image`:

- kept as evidence: the logs, receipts, budget and audit JSON, and the two
  `app-fm1-gpl*.bin` images;
- removed: the build trees, the source copy and the disassembly.

No containers remain.
