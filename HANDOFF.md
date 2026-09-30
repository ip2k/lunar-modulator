# Hand-off package — M-VAVE FM-1 open firmware

Written 2026-09-06 at the end of the research session that created this
repository, so a fresh Claude project (or a human) can continue without the
original conversation; last updated 2026-09-29 (Baud Girl's FM-1+VA, the
owner's PCB photos). Read this first, then `README.md`, then `docs/`.

## 1. Where things stand

- **Owner:** Sean (GitHub `ip2k`). Works from a MacBook with Claude Desktop /
  Claude Code; has **one FM-1** on his desk (do not brick it) and has downloaded
  the official updater disk image **`M-UPGRADE-FM1*.dmg` into `~/Downloads`**
  (that updater embeds **V14**, not V15; V15 is only on the CDN, docs/02 §1).
- **This repository** is the research output: nine documents, three tools, one
  research log, plus bench session 1 (`notes/2026-09-06-bench.md`): the unit
  answered the identity query as `FM-1_015`, V15 is unpacked and diffed against
  V14. This project has written nothing to the device. The case has been
  opened for photos (2026-09-29, `photos/2026-09-29/`, described in
  `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`).
- **The owner's unit now runs Baud Girl's FM-1+VA**: the owner installed it
  through Baud Girl's browser installer, and the unit identifies as
  `FM-1_092` [verified 2026-09-29]. The `FM-1_092` package is V15 plus 90 hook
  patches and 110 KB of appended code, with VM moved to `0xD9000` (note §3).
  The way back to stock is V15's `.fwsc` through the same installer.
- **Elsewhere, non-stock firmware runs on FM-1s**: Echomatter's `FM-1_016`
  (2026-09-04), and since 2026-09-26 **Baud Girl's FM-1+VA**, a modified V15
  with a virtual-analog engine installed from a browser (`FM-1_020` …
  `FM-1_092`; source not published). See docs/04.
- **Where the repo lives now:** `~/Developer/mvave-fm1-firmware` on the
  owner's MacBook, branch `main`, remote `ip2k/mvave-fm1-open-firmware`. Moved there on
  2026-09-06 from the orphan branch `claude/mvave-fm1-open-firmware-ly2w6u` of
  `ip2k/busybar-dual-timer`, which the cloud session used because its GitHub
  integration could not create repositories. Delete that branch once a remote
  exists — see `README.md` → "Repository history".
- **Unrelated to the BUSY Bar project.** Do not mix the two.

## 2. The ten facts that matter

1. SoC = **JieLi AC791N** (WL82), custom **pi32v2** CPU, one core used at
   240 MHz, 578 KB SRAM, 1 MB flash (probably in-package), XIP from
   `0x02000000`, RAM at `0x01C00000`. Marking `C156211-11B8` (aroum's unit) /
   `C188612-11B8` (the owner's), LQFP48.
2. Stock firmware = JieLi AC79 SDK (FreeRTOS-derived kernel, closed `.a` libs
   for BT/audio/fs/cpu) + M-VAVE glue + **Google msfa (Dexed) FM engine**.
   Verified here: msfa algorithm table at `0x8C46C` (V13) / `0x8CBCC` (V14) of
   `app.bin`, with the Dexed-family fix in algorithms 4 and 6.
3. Update = **USB-MIDI SysEx**, device-pull protocol, **CRC16 only, no
   signature**, chip key `0x980F` in the package. Two stages: verifier in the
   app → reboot into a RAM OTA loader (`4D4A:4155`) → flash write → reset.
4. **The step-1 gate is a same-version refusal; content is not
   authenticated.** Baud Girl measured on hardware that a package with the
   running version stops after 9 requests, even when its contents differ,
   while any other version installs. Echomatter's `FM-1_016` and Baud Girl's
   `FM-1_020` … `FM-1_092` all went through the stock path, with rollbacks to
   V15. Two further reported facts: the OTA loader **can rewrite the flash
   head** (`uboot.boot`, `isd_config.ini`), so keep it byte-identical; and a
   loader left waiting after step 1 (`ota-FM-1`) can be resumed (docs/03 §5).
5. **No proven recovery path**: single flash bank, no debug pads/buttons (the
   one candidate header was the battery connector's leads, 2026-09-29),
   mask-ROM USB boot never demonstrated on an FM-1. AL-255's verdict:
   NO-GO for non-stock flashing. This is the gate for everything. The
   `USB_KEY` dongle that should open it is specified and implemented
   (docs/10, `dongle/`), not yet tried.
6. Most promising recovery: JieLi **`USB_KEY`** (`0x16EF` bit-banged on D+/D−
   at ~50 kHz at power-up, ACK = both lines low 1–2 ms, then SOF clock
   detection) → mask-ROM "UBOOT1.00" mass-storage mode → `jl-uboot-tool`
   with its `wl82loader.bin` (`0x1C02000`) or vendor `isd_download`. The two
   kagaimiq docs disagree on which line is clock; try both.
7. Toolchain = JieLi's closed **Clang/LLVM 4.0.1** fork (`pi32v2` backend),
   Linux build available from `pkgman.jieliapp.com`; AL-255 built C++11 with
   it. No Rust, no GCC/LLVM upstream, no JS runtime.
8. Vendor SDK `fw-AC79_AIoT_SDK` (Gitee; GitHub mirrors) is Apache-2.0 with a
   public register map `WL82.h`, linker scripts, `demo_hello`, flashing tools,
   `wl82loader.bin`, a JTAG/debug-TAP folder, and datasheets; ~110 closed `.a`
   libraries per CPU. JieLi's `fw-Bootloader` (Apache-2.0) targets wl82.
9. **schwung-movy is not portable** (TS + Rust on a quad-A72 Linux box). Reuse
   its *design*: 8-knob parameter pages (FM-1 has 8 knobs), Move-style
   sequencer semantics, `seq-core` as a desktop test oracle.
10. USB IDs: normal `4C4A:C755` ("FM-1 Midi" + "FM-1 Audio" UAC1), OTA
    `4D4A:4155`. Identity query `F0 00 32 45 00 00 00 40 7F F7` → 41-byte
    reply `F0 00 32 45 58 01 00 00 23 4D 5A 44 …` (verified; the owner's unit
   decodes to `FM-1_015`, see docs/03 §2).

## 3. Decisions taken

- Target **L1** first (open application on the vendor SDK), then open
  bootloader (L4), then blob removal (L2); an open compiler (L3) is out of
  scope unless a contributor wants it. See docs/05.
- **Recovery before any flash.** Bench work is read-only until docs/07
  Phase 2 is done. Rules of engagement in docs/07 §4.
- Do not port Movy; reimplement in C with Movy as the reference (docs/06).
- Never commit vendor firmware (`.fwsc`, `app.bin`) or the JieLi toolchain;
  `.gitignore` enforces the first.
- Confidence marks **[verified]/[reported]/[inferred]** in all docs; keep them
  honest (the owner's other projects work the same way).
- License MIT for our material.

## 4. Open questions (ranked)

1. Does `USB_KEY` reach the AC791N's mask ROM through the FM-1's USB-C port,
   and with which clock/data polarity and power sequence?
2. ~~What does the step-1 verifier compare?~~ Largely answered (2026-09-29,
   [reported] Baud Girl): it refuses the running version; whether by version
   string or file list is still open, and matters little.
3. Knobs: `RW1` is a potentiometer (MASTER, probably) and the other seven are
   encoders ([verified] owner's photo 2026-09-29); still to reconcile with the
   firmware's 2 hardware decoders + 2 ADC channels.
4. Flash: in-package or discrete, exact size (JEDEC ID)?
5. AC791N variant and pinout; UART and debug-TAP pins reachable on LQFP48?
   There is no header: the 3-pin "header" left of U2 is the battery
   connector's leads (2026-09-29). Still unread: the bottom-side SOIC-8 `U12`
   (charger or external flash?) and the SOP-10 `SLS316D` (docs/09 §5).
6. ~~Does the SoC enumerate on USB with the power switch off?~~ No (verified
   2026-09-06): the unit vanishes from USB when switched off, so the switch is
   the power-up moment for the `USB_KEY` attempt.
7. Any GPL-only Dexed code in the stock image (licensing lever)?

## 5. Immediate next actions (in order)

1. ~~Move the repo.~~ Done 2026-09-06: `~/Developer/mvave-fm1-firmware`,
   pushed to `ip2k/mvave-fm1-open-firmware`.
2. ~~docs/09 §1–§3.~~ Done 2026-09-06 (`notes/2026-09-06-bench.md`).
3. ~~Power-switch-off enumeration test.~~ Done 2026-09-06 (no enumeration when
   off). Still open: the case-open photo list (docs/09 §5).
4. **Buy JieLi's "JL USB Updater 4.0" dongle** (US$8–18, AliExpress/Taobao;
   docs/07 §2.1) plus a USB-A-female-to-USB-C-male adapter, and use it with
   jl-uboot-tool on a Linux PC for read-only dumps (docs/10 §5). The RP2040
   dongle in docs/10 is the open fallback (UF2 from CI). Ideally also a
   JL_AC79_DevKit or a second FM-1 to rehearse on.
5. ~~Contact aroum and AL-255.~~ Done 2026-09-06: AL-255 PR #3 (V15 package),
   comments on their PR #2 and issue #1, aroum issue #2 (docs/04). Watch those
   threads for replies before posting anything further.
6. **Baud Girl's FM-1+VA (2026-09-29).** Done: `FM-1_092.fwsc` diffed
   against V15 (note §3; the package stays in `scratch/`). Still the owner's
   call: (b) whether to contact Baud Girl about the FINDINGS document and
   emulator; (c) whether AL-255's thread should hear about the same-version
   finding (oss-contributions rules); drafts for both are in `scratch/drafts/`,
   unsent. The owner installed FM-1+VA on the unit themselves; docs/07 §4
   still governs this project's own images.
7. **Engine / plugin platform (docs/11, 2026-09-29).** The feasibility report
   says: Schwung modules from source through a shim (subset), Mutable
   Instruments engines first (Plaits' light engines, Braids), and a static
   engine registry before any loader. Next is stage A, the desktop engine API
   and MI ports, which needs no hardware. Stage B, the pi32v2 benchmark and a
   `-fPIC` test, wants the AC79 dev board from item 4.

## 6. Reference material already gathered (clone these locally)

| Repo | Commit inspected | Why |
| --- | --- | --- |
| `aroum/fm1-custom-fw` | `d08360f` 2026-08-21 | updater analysis, photos, untested flasher |
| `AL-255/FM-1-RE` (`main`) | `95eca84` 2026-08-16 | disassembly, protocol, safety, firmware images V13/V14 |
| `AL-255/FM-1-RE` (`with-custom-firmware`) | `628fcaf` 2026-08-02 | experimental pi32v2 firmware, package builders, Synth_Dexed port |
| `kagaimiq/jielie` | `1657d25` 2024-09-15 | JieLi docs: ISA, USB_KEY, formats |
| `kagaimiq/jl-uboot-tool` | `adb3f18` 2025-03-16 | UBOOT dumper/flasher, `wl82loader.bin` |
| `kagaimiq/jl-misctools` | `0a5b12d` 2025-02-20 | `fwunpack_newfw.py` |
| `jeffreywugz/fw-AC79_AIoT_SDK` (`release/AC79NN_SDK_V1.0.3`) | mirror | vendor SDK: `WL82.h`, `cpu/wl82/tools`, datasheets |
| `DimaDake/schwung-movy` | `5627d51` 2026-09-05 (v0.31.0) | design reference only |

Web pages that were **blocked** from the research sandbox and still need a
human read: cuvave.com product page, the user manual PDF, synthanatomy.com
articles, fwradar.com history, elektronauts/gearspace/reddit threads,
fm1-editor.com, kagaimiq.github.io (use the repo), gitee.com (use mirrors),
madushan.caas.lk blog post.

## 7. Kick-off prompt for the new Claude project

Paste this as the first message of the new project (adjust paths):

> This project is the open-source firmware effort for the M-VAVE FM-1 FM
> synthesizer. The repository (`~/Developer/mvave-fm1-firmware`) contains a
> completed research phase: read `HANDOFF.md`, then `README.md`, then
> `docs/01`–`09` and `CLAUDE.md`. Rules: the FM-1 on my desk is the only unit;
> nothing may be flashed or sent to it beyond the read-only identity query
> until recovery is proven (docs/07). Today's tasks: (1) run
> `docs/09-first-session-checklist.md` §1 to extract and analyse the V15
> firmware from `~/Downloads/M-UPGRADE-FM1*.dmg`; (2) §2–§3 USB descriptors and
> identity query with the FM-1 plugged in; (3) write results to
> `notes/<date>-bench.md` and update the open questions in `docs/01` §6 and the
> version table in `docs/02` §1. Keep the [verified]/[reported]/[inferred]
> marks honest.
