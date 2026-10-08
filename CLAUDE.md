# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this is

**Lunar Modulator** (tagline **INTERGALACTIC MODULATION STATION**) is open
firmware for the **M-VAVE FM-1** (JieLi AC791N SoC, pi32v2 CPU; the stock
firmware's FM engine is msfa/Dexed).

Status, 2026-10-01: **the code runs on a desktop and in a browser, not yet on
a JieLi chip or an FM-1; nothing flashed by this project.**
- Built and tested on the desktop: an engine platform with Mutable- and
  Schwung-derived engines and effects (`engines/`, checked against reference
  renders), and a C99 port of Movy's sequencer core with its Movy oracle
  (`engines/seq.md`).
- A virtual FM-1 runs the engines and effects in a browser (`sim/web/`).
- The research phase and one read-only bench session are done
  (`notes/2026-09-06-bench.md`).
- An AC79 dev kit and JieLi's USB updater are on order (docs/14).

The owner's unit ran stock `FM-1_015` until
the owner installed Baud Girl's FM-1+VA; it identifies as **`FM-1_092`** since
(2026-09-29). The `USB_KEY` recovery
dongle (docs/10, `dongle/`) is implemented and simulated, not yet tried. Other
owners report that czietz's simpler Pico dongle reaches UBOOT mode on their
FM-1s, and one reports a firmware backup and a write that way (issue #2,
docs/10 §1.1).
Elsewhere, Echomatter ran a version-bumped V15-derived package on their FM-1
via the stock OTA path and rolled it back (AL-255 PR #2, 2026-09-04), and
since 2026-09-26 Baud Girl's FM-1+VA (a modified V15, source not published)
installs from a browser for anyone (docs/04, `notes/2026-09-29-*`).
Open firmware runs on FM-1s too: Felucca 1.0 (hugelton) and its fork SLOOP
2.2 (isod89), bare metal and GPL-3.0-only, install and roll back through the
stock path, and fm1-nes (Keitark) runs an AC79 SDK app on one V14 unit,
written through mask ROM [reported; `notes/2026-10-05-community-repos.md`].
`HANDOFF.md` is the context summary. `README.md` is the product page, for
users. `DEVELOPERS.md` holds everything technical: specifications, the
hardware, how the software works, the research, where development stands,
and how to build and contribute. `docs/` has the detail.

Keep technical material out of the README and put it in DEVELOPERS.md.

**The name** (owner's choice, 2026-10-01). Until then the project was "Open
firmware for the M-VAVE FM-1", repository `ip2k/mvave-fm1-open-firmware`; it
is now `ip2k/lunar-modulator`. The local folder `~/Developer/mvave-fm1-firmware`
keeps its old name. Rules:

- Full name **Lunar Modulator**; short form **Lunar**. Never "Lunar Module"
  (the Apollo spacecraft), "Lunar Mod" or "LM".
- Tagline **INTERGALACTIC MODULATION STATION**, in capitals.
- Wherever the project is described, keep the descriptor "open firmware for
  the M-VAVE FM-1". The device's name only says what the firmware runs on;
  it implies no tie to M-VAVE or Cuvave.
- The look is a space theme set in Audiowide (SIL OFL 1.1); the art, the
  font and its licence are in `assets/branding/` (see its README). In
  published text name the typeface, never "the NASA font". Never use NASA's
  insignia (the "meatball"), its "worm" logotype, its seal, or any other
  NASA name or mark, and nothing that suggests NASA endorsement. Never use
  M-VAVE's or Cuvave's logos. Mutable Instruments module names (Plaits,
  Braids, Clouds, …) are credited as sources, never used as product names.

This project is unrelated to the BUSY Bar timer repo it was briefly hosted in.

## Project status and licences

**Personal, non-commercial project** (owner, 2026-10-01). The repository is
MIT. GPL code, and code under similar terms such as LXR's, may be brought in
when needed, each in its own `third_party/<name>/` directory with its licence
and an `UPSTREAM.md`. Those licences only bite on distribution: a firmware
binary that links JieLi's closed SDK libraries must not be shared (released,
or sent to anyone) if it contains GPL or LXR code. Personal builds may; keep
such code behind a build switch so an MIT/BSD-only build stays shareable.
GPL and LXR code cannot be combined in one shared work. MIDIbox code needs
its author's permission. Details: docs/12 §6, docs/11 §7. The SDK itself
is not GPL-free: `system.a` holds a modified FreeRTOS V9 (GPLv2 with the
FreeRTOS exception), and `uac_audio.h`/`uac_audio_v2.h` are GPL-2.0, so
never include those headers. Felucca and SLOOP are GPL-3.0-only: take facts
and ideas, with credit; their code comes in only as a GPL module behind the
GPL switch (docs/12 §6), as three of Felucca's engines have
(`engines/third_party/felucca/`, 2026-10-06).

**The GPL switch** (owner, 2026-10-05: "gated with a switch but ON by
default, everywhere while we test"): GPL modules sit behind one build
switch, `FM1_GPL_MODS`, **on by default in every build while we test**.
While it is on, no firmware image that links JieLi's libraries may be shared,
and the public simulator's module is offered under GPL terms (licence named
on the page, source linked). Bare-metal builds without JieLi's libraries are
to be explored later. The switch is built (2026-10-06): `FM1_GPL_MODS ?= 1`
in `engines/Makefile`, read by fm1-render, the simulator's builds and the
JieLi check; a GPL module's registry entry and licence row go under `#if
FM1_GPL_MODS`, its sources in its own fragment; CI tests both settings, and
`tests/test_gpl_switch.py` fails if the switch-off build compiles, links or
lists anything GPL. Details: docs/12 §6.

## Hardware experimentation policy (owner revised, 2026-10-07)

The owner explicitly replaced the blanket dump-and-byte-identical-restore
precondition, authorizing exploration of soft-key UBOOT entry and dump/restore
on bench01 without waiting for the development kit. A prior full restore is
**not** required to attempt recovery entry, read flash, or prepare a prototype.

Proceed in recorded stages: identify the connected unit; send the vetted
`F0 22 24 35 7D F7` soft key once and observe USB enumeration; use a reviewed,
allowlisted RAM loader for private full-flash backups; then evaluate a bounded
restore or prototype installation with its concrete image and recovery plan.
Take and compare backups before any flash erase/program operation. Do not infer
proven recovery from UBOOT enumeration alone. No blanket erase, arbitrary vendor
commands or eFuse programming is authorized. Keep the stock SPL, OTA/cfg and
partition safeguards; a prototype must retain a route back to USB update mode.

The current experiment and authorization are recorded in
`notes/2026-10-07-fm1-softkey-bench.md`; docs/07 §4 holds the revised rules.
Historical references to "the one rule" describe the superseded policy.

## Hardware in one table

| | |
| --- | --- |
| SoC | JieLi AC791N (WL82), LQFP48, marking `C1xxxxx-11B8` (lot varies; owner's `C188612-11B8`); pi32v2 core, 240 MHz used of 320; 578 KB SRAM; 1 MB flash, JEDEC `0x856014` (Puya) [reported], probably in-package |
| Memory map | flash XIP `0x02000000`, app entry `0x02000120` [verified: V15 `jlfw.yaml`], RAM `0x01C00000`, SFRs `0x1xxxx…0x5xxxx`, mask ROM `0xFFC0xxxx` |
| USB | normal `4C4A:C755` (USB-MIDI + UAC1, full-speed, product string `FM-1`), OTA loader `4D4A:4155`, mask ROM `4C4A:8057` `UBOOT1.00` [reported] |
| Display | 240×240 RGB565 ST7789V TFT on SPI1 (`0x11D00`): CS PC7, D/C PC8, SCK PC9, MOSI PC10; backlight PA2, active low [reported] |
| Controls | 27 keys + 14 buttons in an 11×6 matrix behind two 74HC595s (PA4/PA3/PA1), read on PA0, PA5–PA8, PB7; all 7 encoders scanned in the matrix; MASTER is a pot on PB6 (ADC 4); ADC 3 is the battery on PB1 [reported: Felucca `727f272`, fm1-nes `870f305`] |
| Audio | ALNK0 (I2S) to an external codec, not the internal DAC, IRQ 11 [reported: Felucca/SLOOP and fm1-nes, two code lineages]; 64-frame halves as in stock [reported: fm1-nes]; about 44,118 Hz (Felucca times 44,117.6 Hz; AL-255 reads stock's as 44,118) [reported]; 12 msfa voices |
| MIDI jack | TRS, input only: UART1 RX on PH8 [reported: Felucca] |
| Update | USB-MIDI SysEx, CRC16 only; step 1 refuses only the running version, so rebuilt packages with a new version install, and it accepts a non-M-VAVE `ota.bin` [reported: Felucca, SLOOP]; the OTA loader can rewrite `uboot.boot` |

## Commands

```bash
python3 tools/check_msfa_table.py path/to/app.bin            # msfa table finder (tested on V13/V14)
python3 tools/extract_fwsc_from_updater.py M-UPGRADE-FM1 -o FM-1.fwsc   # carve package from the updater
python3 reference/jl-misctools/firmware/fwunpack_newfw.py FM-1.fwsc     # unpack (needs: pip install crcmod)
python tools/fm1_identify.py                                   # read-only identity query + decode, any OS (verified on hardware)
python -m pytest                                               # tools, PIO emulation, dongle/ROM co-simulation and engine tests
make -C engines && engines/build/fm1-render --list             # engine platform, desktop build (docs/11, engines/README.md)
cd sim/web/www && python3 -m http.server 8000                  # the virtual FM-1 at http://localhost:8000/ (sim/web/README.md)
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh                # rebuild and check its WebAssembly module in containers on a Docker host
tools/fm1_identify.sh                                          # Linux, ALSA raw MIDI, read-only, untested
python3 reference/FM-1-RE/tools/fm1_ota.py scan                # AL-255's client, read-only scan
```

`reference/` and `scratch/` are git-ignored; clone third-party repos and keep
vendor packages there.

## Conventions

- **Dead-code audit:** first done 2026-10-05 (PR #74) over the tree at
  `d781f07` (PR #52): 91,901 lines of the repo's own source, 91,732 after its
  removals (`db24f89`). Scope: `dongle/`, `engines/` and `firmware/` less
  `third_party/`, `sim/`, `tests/` and `tools/`. The count is `wc -l` over the
  tracked files less Markdown, data (JSON, verb, panel and mod scripts, fonts,
  the built module) and `tests/fixtures/`; by the same count the stage A2 mark
  of 2026-09-30 was 7,440. The candidates left for the owner's decision are in
  PR #74. The ~28,300 lines that merged after `d781f07` (19 PRs, #55 to #75;
  120,007 in all at the merge with #75, `401e83c`) were not read, so the next
  audit is due already: start from `git diff d781f07`, then audit again after
  about every 10,000 lines.
- **Confidence marks in every technical claim:** `[verified]` (checked here
  against binaries, photos or SDK files), `[reported]` (named source, not
  re-checked), `[inferred]`. Never upgrade a claim without doing the check.
- **Never commit vendor binaries** (`.fwsc`, `app.bin`, `uboot.boot`, the JieLi
  toolchain, updater apps). `.gitignore` blocks the common ones; link to
  sources instead.
- Credit prior work by name (aroum, AL-255, kagaimiq, probonopd, czietz,
  Baud Girl, Felucca by hugelton, FM-1-transporter by kurogedelic, SLOOP by
  isod89, fm1-nes by Keitark, JieLi's AC79 SDK, Google msfa, Dexed family,
  Schwung/Movy). Quote, summarize and link; do not copy whole
  documents or photos (aroum's repo has no license).
- Docs are numbered `docs/NN-topic.md`; bench results go to
  `notes/YYYY-MM-DD-*.md`; answered open questions are removed from `docs/01`
  §6 and the answer written where it belongs.
- Read the device identity (`FM-1_0xx`) from the package or device; never infer
  a version from a filename (the "V13" package identifies as `FM-1_009`).
- Future firmware code: C/C++11 for JieLi's clang (`-fno-exceptions -fno-rtti`),
  built against the Apache-2.0 AC79 SDK V1.2.13 libraries (trap 11, with its
  safeguards); msfa/Synth_Dexed for the engine; keep
  `uboot.boot`, `ota.bin`, `cfg` and the partition layout byte-identical to
  stock in any experimental package until the verifier gate is understood.

## Traps that have already cost people time

1. **`JL-BR22` in the binary is not the SoC.** It is Bluetooth-library lineage;
   the chip is AC791N/WL82 (package ID, SPL match). Register maps borrowed from
   BR2x docs are unsafe until checked against `WL82.h`.
2. **The stock updater is not a recovery tool.** It needs a running app with
   the update service; it installs non-stock images fine (Baud Girl, Felucca,
   SLOOP), but it cannot save one that does not boot. `0xF0000000/"success"`
   is a terminal acknowledgement, not authorization.
3. **The `USB_KEY` clock is D+.**
   - czietz's Pico dongle clocks on D+ and has reached UBOOT mode on two FM-1s
     (issue #2, docs/10 §1.1); FM-1-transporter reports D+ only, the other
     polarity never worked.
   - kagaimiq's `usb-key.md` and the diagram in his `how-to-enter-uboot.md`
     agree; only that page's prose says D−.
   - Try D+ first, and keep both roles in the dongle.
4. **ghidra-jieli mis-decodes the `80 ff` long-call prefix**; use the vendor
   `objdump` from the JieLi Linux toolchain as the source of truth.
5. **Raw MIDI on Linux is unusable while PipeWire/JACK/aseq hold the port**;
   the updater and AL-255's client use the ALSA sequencer.
6. **Version numbers are inconsistent** between filenames, marketing (V09/V14/
   V15) and the identity string. Always read the identity.
7. **Do not send syscmd 33–36 or 48** or any `5A AA A5` online-tool frame; some
   copy memory or touch flash (online-tool 0x24 erases, 0x25 writes, 0x26
   reboots into mask ROM, 0x27 reads [verified: SDK `cfg_tool.h`,
   `new_cfg_tool.c`]).
8. **Movy/Schwung are Linux-only by nature**; do not plan around porting them.
9. **The "soft key" `F0 22 24 35 7D F7` is not the identity query.**
   - Stock V15 reboots into mask-ROM `UBOOT1.00` on it [reported:
     FM-1-transporter `a632d92`]; FM-1_092 is unchecked. The upgrade command
     `F0 22 24 35 7F F7` differs by one byte.
   - Send it only through the authorized staged hardware plan above; a prior
     full restore is no longer a precondition for this probe.
   - FM-1-transporter's `fm1t.py` sends it by itself when it sees V15
     [verified: its README]: do not run its unreviewed automatic path against the owner's unit.
     Its key drive is also push-pull with no series resistors, which docs/10
     E1 rules out [verified: `pio/usb_key.pio`, README].
10. **Audio is ALNK0 (I2S, `0x12E00`) to an external codec, not the
    `JL_AUDIO` DAC (`0x12F00`)** [reported: Felucca, fm1-nes]. The SDK's
    audio demos and the dev kit's DAC path do not match the FM-1.
11. **The SDK pin is V1.2.13 libraries, never its SPL or loader** (owner's
    decision, 2026-10-05; `notes/2026-10-05-softkey-efuse.md`). Build against
    Gitee `release/AC79NN_SDK_V1.2.0` at `e30b1ee` (= tag V1.2.13), pinned by
    commit; the GitHub mirrors are stale. `system.a` carries `sdk_meky_check`
    (from V1.2.7) and `sdk_chip_key_verify_v2` (V1.2.13), but the check is
    **inert on the FM-1**: nothing registers a licence blob, so `_mkey_check`
    returns at its "nothing registered" branch and the app never touches
    eFuse [verified: IR of every release]. So do not stub it — leave the
    vendor code intact and gate the link with `tools/jieli/audit_link.py`
    (`late_initcall` exactly `[sdk_meky_check]`; no surviving `mkey_check`/
    `sdk_mkey_lock`/`sdk_chip_key_verify_v2`/`key_check_demo`, no `0x0200012E`
    stub, no writes to `0x01C80108-0x01C80110` but the SDK's own
    `mkey_dummy_func` store, IRQ 123 reserved, no SDK key-blob bytes, no
    eFuse SFR access). **Never ship any V1.2.x `uboot.boot`,
    `uboot_no_ota.boot`, `wl82loader.bin` or `ota.bin`:** every package must
    pass `tools/jieli/package_guard.py`, which asserts the stock SPL hash
    `730e54f0…` and byte-identical `isd_config.ini`/`ota.bin`/`cfg`, and
    refuses any other SPL or loader (only V1.1.9's SPL is the FM-1's;
    Felucca's and SLOOP's carry V1.2.1's `uboot.boot`). Link fm1-nes's
    `boot_info` bridge (`firmware/third_party/fm1-nes/`, Apache-2.0; 6 words
    copied, words 6-22 zeroed) because V1.2.1+ `boot_info_init` reads to +92
    while the stock SPL fills only 6 words plus a 32-byte header. The only
    eFuse-burning code is JieLi's USB download loader `wl82loader.bin`,
    reached from PC tools, not from anything on the device: never send loader command `0xFC12` or the raw `0xA1` eFuse
    write, and never pass `-key`/`-key1`/`-mkey` to `isd_download` for the
    FM-1 or the dev kit (V1.2.12+ `isd_download` is a writer: dev kit only).
12. **SDK demo power settings are not the FM-1's.** Stock runs VDDIOM 3.2 V,
    VDC14 1.60 V with DCDC, SYSVDD 1.38 V and LVD 2.6 V [reported: fm1-nes
    `board_power.c`, from stock FM-1_010].
