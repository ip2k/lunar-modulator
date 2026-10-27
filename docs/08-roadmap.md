# 08 — Roadmap

Phases with exit criteria.

**Current hardware status (2026-10-26).** A stage-7 install was interrupted
on 2026-10-15 and left the unit with no display and no USB. On 2026-10-26 it
was keyed into mask-ROM `UBOOT1.00` with a Pico 2 W running a patched
FM-1-transporter, dumped twice (identical), and the stock V15 application
region was written and read back equal [verified] and booted [reported:
owner]; it identifies as `FM-1_015`
[verified: docs/17, [recovery note](../notes/2026-10-26-fm1-stock-v15-recovery.md)].
The unit's own FM-1+VA (`FM-1_092`) image was not restored; the two 092
backups are its only copy. The owner's decisions of that day (docs/07 §4,
D1–D4): recovery of an unbootable unit with an intact boot area is proven;
docs/17 is the approved recovery route; the dump, restore and boot gate (DEVELOPERS.md's
I9) is met with stock V15 as the target; ordinary MIDI may be sent into the
unit. The AC79 dev kit (`JL_AC79_DevKitBoard V1.2`) is in hand, with a UART
bring-up on 2026-10-22 (docs/14). **Next milestone:** the first Lunar code on
the FM-1, RAM-only first, under docs/07 §4, with docs/17 as the fallback.

Earlier status (2026-10-08): soft-key
UBOOT entry, a RAM recovery loader, matching full backups and bounded sector
restoration succeeded [verified: [bench note](../notes/2026-10-07-fm1-softkey-bench.md)].
The complete post-test dump matched the backups; the owner confirmed normal
boots after the read-only session and after restoration [verified: bench note].
An offline diagnostic variant has been linked, but no full-DSP Lunar
application is linked for installation and none has run on or been installed
on the FM-1. Broken-app recovery was then untested; it was done on
2026-10-26 (above). The owner authorized firmware preparation and audit remediation; see the
[current work record](../notes/2026-10-08-audit-remediation.md) and docs/07 §4.

The following 2026-10-01 checkpoint and original phase order are historical;
their prior blanket recovery prerequisite is superseded by docs/07 §4:
- Phase 0 is done.
- Phase 1 has had one read-only bench session (`notes/2026-09-06-bench.md`).
- Phase 2's dongle is built and simulated (docs/10), and an AC79 dev kit and
  JieLi's USB updater were on order (docs/14). The kit has since arrived
  (V1.2, UART bring-up 2026-10-22); it enters download mode with its own
  UPDATE (K1) and RESET (K2) buttons, so it needs no `USB_KEY` dongle.
- Parts of Phase 4 and Phase 5 exist on the desktop and in a browser: the
  engine platform (`engines/`), the sequencer core (`engines/seq.md`) and the
  virtual FM-1 (`sim/web/`).
- Nothing has run on a JieLi chip.

## Phase 0 — Research (done, 2026-09-06)

Findings in docs/01–07. Deliverable: this repository.

## Phase 1 — Bench characterization, read-only

Detailed commands in docs/09.

- USB descriptors in normal mode; confirm `4C4A:C755`, MIDI and UAC1 interfaces.
- SysEx identity query and decoded identity (`FM-1_0xx`).
- Extract the V15 `.fwsc` from `M-UPGRADE-FM1.app`, unpack it, diff against V14
  (sizes, hashes, strings, msfa table, new feature strings such as glide).
- Optional: capture a stock update session (M-UPGRADE re-flashing the current
  version) with a MIDI monitor to validate AL-255's protocol client on this
  unit — the stock path is proven, but note it re-writes the app bank.
- Photos: chip marking, U2/U3/U5/U9/U11 markings, J12 pin count, knob types,
  the USB-C to SoC routing.
- **Exit:** notes/ contains descriptors, identity, V15 analysis, photos; the
  knob/encoder question is answered.

## Phase 2 — Recovery (gate met, 2026-10-26)

**Status:** the exit gate (dump, restore, boot; I9) is met with stock V15 as
the restore target (owner, 2026-10-26, D3; docs/07 §4). The approved
recovery route is docs/17, not this project's dongle (D2). What now gates
Phase 3 is docs/07 §4 itself: a reviewed, RAM-only first experiment with its
recovery plan, and docs/17 ready as the fallback.

Earlier: the soft-key path has completed matching full backups and one bounded 4 KiB
unused-sector write/readback/restore, followed by a byte-identical complete
flash comparison and an owner-confirmed normal boot [verified:
[bench note](../notes/2026-10-07-fm1-softkey-bench.md)]. Recovery of a
nonbooting unit through mask ROM, two identical full dumps and a verified
stock V15 application write followed on 2026-10-26 with a Pico 2 W and
FM-1-transporter (docs/17) [verified]. This project's own dongle, recovery
from a damaged boot area `0x0`–`0x4000`, and a restore of the unit's own
`FM-1_092` image remain untested. The remaining recovery work below follows
docs/07 §4; a prior whole-image
restore is not a blanket prerequisite for firmware preparation or evaluating
a concrete prototype experiment.

- Optional, off the critical path (D2): build the RP2040 `USB_KEY` dongle
  from docs/10 (firmware in `dongle/`, UF2 from CI, logic tested against a
  ROM model). It is the open-drain design that docs/10 E1/E2 require, and is
  useful for other owners. The dev kit needs no dongle (UPDATE/RESET
  buttons, UART), so there is no kit rehearsal of the key.
  - czietz's MicroPython dongle, reported working on two FM-1s (issue #2),
    can also run on our dongle board as a second implementation: SPI1 on
    GP14/GP15 instead of GP10/GP11, relay energised, pull-ups off.
  - It drives push-pull, so E1/E2 rule it out for this project's FM-1
    (docs/10 §1.1); the only approved push-pull exception is docs/17's
    route (D2).
- Done 2026-10-26: reach `UBOOT1.00` (D+ clock, FM-1 off while keying, then
  switched on; `WL82`/`UBOOT1.00`), read `key=980F type=3 id=856014`, two
  identical full 1 MB dumps, compare to the stock package, write and verify
  [verified: docs/17, recovery note].
- Evaluate further restoration tests with exact reviewed images/ranges and a
  recovery plan. Take and compare full backups before every erase/program
  operation, then compare complete flash and confirm normal boot afterward.
  Broken-app recovery for an intact boot area is closed (D1); a damaged
  boot area is not.
- Done 2026-10-26: the procedure with exact commands is
  `docs/17-pico2w-recovery.md`. A dongle-based variant would follow docs/10
  §6 if the dongle is ever run.
- **Milestone passed (2026-10-26):** recovery of an unbootable unit and the
  I9 gate, with stock V15 as the restore target (D1, D3). **Current
  milestone:** the first Lunar code on the FM-1, RAM-only first (Phase 3),
  under docs/07 §4 with docs/17 as the fallback.

## Phase 3 — First custom code (current)

Unblocked by the Phase 2 gate (met 2026-10-26). The first step on the FM-1
runs from RAM only; flash writes come after that, each under docs/07 §4 with
its image, ranges and docs/17 as the recovery plan (owner, 2026-10-26, D3).

- Install the JieLi Linux toolchain and post-build tools; build the SDK's
  `demo_hello` for AC791N (`make ac791n_demo_demo_hello`).
- Create a `board_fm1.c` from the pin map in docs/01 §3.1 (Felucca and
  fm1-nes [reported], checked against V15 in DEVELOPERS.md's I4): SPI1
  display pins, key matrix ports, the matrix encoders and the MASTER ADC,
  the ALNK0 I2S audio path. The TRS jack is UART RX only, so log over USB
  CDC or on the TFT.
- Run from RAM first, then flash via mask-ROM USB; confirm the log; blink
  the key LEDs; draw on the TFT.
- Add the fail-open boot path (key combo held at power-up → USB update mode)
  and a watchdog failure counter. Test both.
- **Exit:** "hello" firmware runs, logs, and can always be replaced.

## Phase 4 — The synth

- Port Synth_Dexed `EngineMsfa` (or msfa directly) to pi32v2 with the JieLi
  toolchain (C++11, no exceptions/RTTI; AL-255's branch already did the host
  build and shims).
- Audio output over ALNK0 (I2S) to the board's external codec, through the
  SDK's `iis_open` or a direct DMA ping-pong (AL-255 read an internal DAC;
  Felucca and fm1-nes use I2S [reported]); 44,117.6 Hz, 64-frame halves;
  measure voice count vs. CPU.
- USB-MIDI class device (SDK `usb.h`), UART MIDI, DX7 SysEx bulk/single/param
  messages; program change, CC map compatible with stock where sensible.
- Preset storage in flash (32-voice VMEM banks), factory bank from any DX7
  ROM `.syx` the user provides (do not ship M-VAVE's bank).
- **Exit:** plays DX7 banks from a DAW over USB, on par with stock polyphony.

## Phase 5 — UI, sequencer, effects

- Parameter pages following Movy's model (docs/06), four knobs to a page
  (KNOB1–4 are the free parameter knobs; SELECT/ALGORITHM navigate);
  envelope and algorithm graphics on the 240×240 TFT; oscilloscope view like
  stock.
- Swappable engines behind one C API (docs/11): msfa, then engines derived
  from Mutable Instruments code (Plaits' light engines, Braids), MI effects,
  and a Schwung v2 shim for MIT Schwung modules. Engines compiled in first;
  RAM-loaded units over USB-MIDI later.
- Arpeggiator; step sequencer with Movy-style step parameters; optional
  desktop harness diffing against Movy's `seq-core`.
- Effects: filter, reverb, delay, chorus, phaser, distortion (open-source DSP;
  e.g. Freeverb/Dattorro, simple SVF) — or the SDK's `lib_reverb_cal.a` at L1.
- BLE-MIDI via the vendor stack (L1) — decide whether to keep it.
- **Exit:** daily-usable instrument; manual in `docs/`.

## Phase 6 — Distribution

- Install over the stock OTA path so stock units can take the open firmware
  over USB-MIDI. Echomatter showed (2026-09-04) that a package with a bumped
  version identity is accepted, and Baud Girl's browser installer (docs/04)
  has done it publicly since 2026-09-26. The remaining work is our own
  client: start from AL-255's `fm1_ota.py` with PR #2's framing fix and
  `build_fwsc.py`, plus a check that the flash head equals stock (the loader
  can rewrite it) and resume from the loader. Alternatively publish the
  dongle design and a "one-time unlock".
- Reversible: the tool must restore stock (users keep their `.fwsc`).
- Release process, versioning, changelog; coordinate with aroum and AL-255.

## Phase 7 — Deeper openness (long term)

- Replace `uboot.boot` with a build of JieLi's Apache-2.0 `fw-Bootloader`.
- Remove `.a` dependencies one by one: UI (`ui.a`) first, then `fs.a`, audio
  server, `system.a`/`cpu.a` — against `WL82.h` and kagaimiq's peripheral docs.
- Toolchain: document the pi32v2 ISA formally from the vendor objdump +
  ghidra-jieli; fix ghidra-jieli's `80 ff` long-call decoding; evaluate an LLVM
  backend as a separate project.
- Second core: stock already renders its voices on cpu1, outside the OS
  (docs/11 §2). Whether an SDK build can do the same is tested on the dev
  kit (docs/14 §5.1). A blob-free firmware must also start cpu1 itself
  (the mailbox and `C1_CON` writes, not yet understood).

## Research items (any time)

- **Engine platform, desk and bench stages (docs/11 §8).** Stage A (desktop
  engine API, MI ports at 44.1 kHz / 64 frames, Schwung shim) needs no
  hardware; stage B benchmarks pi32v2 DSP throughput and tests `-fPIC` on a
  JieLi AC79 dev board.

- Verify the algorithm 4/6 `0x41` variant against upstream Dexed's
  `Source/msfa/fm_core.cc`; check whether any GPL-only Dexed/Synth_Dexed code
  (e.g. `PluginFx`, compressor) is present in the stock app.
- Read fm1-editor.com's JavaScript for the exact patch SysEx and any vendor
  extensions beyond DX7.
- Confirm whether the flash is in-package. The JEDEC ID from UBOOT mode is
  `856014` (1 MB) [verified 2026-10-26, docs/17].
- Identify the AC791N variant and pinout; document the FM-1 pin assignment.
- Understand how the syscmd callback table (`ENG+1336`/`ENG+1400`) is populated.
- Ask aroum and AL-255 whether they want to pool efforts; both repos were
  active in August 2026.
