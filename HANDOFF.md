# Hand-off package — Lunar Modulator

**INTERGALACTIC MODULATION STATION.** Lunar Modulator is open firmware for
the M-VAVE FM-1; until 2026-10-01 the project was called "Open firmware for
the M-VAVE FM-1". Naming rules are in `CLAUDE.md` → "What this is".

This file lets a fresh session, or a human, carry on without the earlier
conversations. It was first written on 2026-09-06 at the end of the research
session that created the repository, and rewritten on 2026-10-01 for the
state of `main` after PRs #3–#20 (2026-09-29 to 2026-10-01, `a534dd4`).
Read it first, then `DEVELOPERS.md` (everything technical; `README.md` is
the product page, for users), then `CLAUDE.md` (mirrored for Codex in
`AGENTS.md`: edit the two together), then the `docs/` a task needs. It is a
summary: where it and a doc disagree, the doc wins and this file is stale.

A bare PR or issue number means this repository, `ip2k/lunar-modulator`;
any other repository is named. "Issue #2" exists both here and at aroum's,
so it is always written in full.

## 1. Where things stand (2026-10-01)

- **The code runs on a desktop and in a browser, not yet on a JieLi chip or
  an FM-1. This project has flashed nothing.** Every object compiles for
  pi32v2 with JieLi's toolchain (#30, compile-only,
  `notes/2026-10-02-jieli-compile-check.md`), but nothing has been linked
  into firmware or run on a JieLi chip, so speed on pi32v2 is not measured.
- **Owner:** Sean (GitHub `ip2k`), on a MacBook with Claude Desktop / Claude
  Code. A personal, non-commercial project (`CLAUDE.md`). There is **one
  FM-1** (do not brick it). The official updater (`M-UPGRADE-FM1`) embeds
  V14, not V15 (V15 is only on the CDN, docs/02 §1). Its disk image was in
  `~/Downloads` on 2026-09-06 and is gone; the carved updater binary, the
  V14 package carved from it, V15's CDN package and Baud Girl's
  `FM-1_092.fwsc` are in the main checkout's git-ignored `scratch/`.
- **The owner's unit runs Baud Girl's FM-1+VA**, which the owner installed
  themselves through Baud Girl's browser installer. It answered `FM-1_015`
  on 2026-09-06 and `FM-1_092` since [verified 2026-09-29]. The package is
  V15 plus 90 hook patches and 110 KB of appended code, with VM moved to
  `0xD9000` (`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §3).
  - This project has only ever sent the unit read-only requests.
  - A flash dump taken now captures FM-1+VA, not stock (docs/07 §4 note,
    docs/14 §4.1). The way back to stock, V15's `.fwsc` through the same
    installer, is [reported] and has not been tried here. A rollback is a
    write through the stock updater, so whether to do it before the first
    dump is the owner's decision and the owner's action, like the FM-1+VA
    install; this project does not send it.
- **Recovery is closer, but not proven on this unit.**
  - Other owners report reaching the FM-1's mask-ROM mode. In
    [issue #2 here](https://github.com/ip2k/lunar-modulator/issues/2)
    ("Working UBOOT dongle (fyi)", from 2026-09-16), czietz's quick
    Raspberry Pi Pico dongle gets their FM-1 into UBOOT mode about one
    power-on in two. On 2026-09-29 masanaohayashi reported that it worked on
    their FM-1 too, and that they backed up and wrote firmware with it
    [reported: docs/10 §1.1]. Neither named the tool or commands, and nobody
    has reported a byte-identical restore. Nobody here has run it. It
    drives the lines push-pull, so it is not for this project's FM-1
    (docs/10 §2, E1).
  - Our own `USB_KEY` dongle (docs/10, `dongle/`) is specified, implemented
    and simulated; CI builds its UF2, but nobody has built the hardware or
    run it. Checking it against czietz's tool found a wiring bug, fixed in
    PR #17: both pull-ups went to GP16, which tied D+ to D− when switched
    off, so the SOF phase would have timed out every time. D−'s pull-up now
    has its own pin, GP19 (docs/10 §2, E3). Since PR #19 it keys with D+ as
    the clock (polarity A) by default (docs/10 §6).
  - **On order** (the owner, 2026-10-01): the JL-AC79-DevKit V1.0 (core
    board with an AC7916) and JieLi's USB updater dongle (docs/14). They are
    the first real pi32v2 target and a second way into mask-ROM mode; the
    dump and restore get rehearsed on the kit first. The updater's version,
    and whether the USB-A-female-to-USB-C adapter it needs is on hand, are
    not recorded (docs/07 §2.1).
  - We have not answered ip2k/lunar-modulator#2. A reply is drafted in
    `scratch/drafts/2026-10-01-issue-2-reply.md` (git-ignored, unsent).
    Whether and when to post it is the owner's decision, not taken on
    2026-10-01. Never post it ourselves.
- **Elsewhere, non-stock firmware runs on FM-1s**, installed through the
  stock update path with rollbacks to V15: Echomatter's `FM-1_016`
  (2026-09-04, AL-255/FM-1-RE PR #2, merged 2026-09-08), and since
  2026-09-26 Baud Girl's FM-1+VA (`FM-1_020` … `FM-1_092`, source not
  published). See docs/04 and docs/03 §5.
- **Open firmware runs on FM-1s too** (2026-10-05,
  `notes/2026-10-05-community-repos.md`): Felucca 1.0 (hugelton) and its
  fork SLOOP 2.2 (isod89), bare metal and GPL-3.0-only, install and roll back
  through the stock path; fm1-nes (Keitark) runs an AC79 SDK app on one V14
  unit, written through mask ROM [reported]. Their code maps the board
  (docs/01 §3.1): audio is ALNK0 (I2S) to an external codec, not the internal
  DAC, and the encoders are scanned in the key matrix. Stock V15 also enters
  mask ROM on the SysEx "soft key" `F0 22 24 35 7D F7`, which this project
  must not send before the gate (CLAUDE.md trap 9).
- **Tests:** 1,443 collected; 1,441 pass and 2 xfail, both undo, which is
  not ported yet [verified: `pytest` at `a534dd4`, 2026-10-01]. Of those,
  963 are engine tests (427 of them in the two reference-render files,
  `tests/test_engines_reference_*.py`, which compare against upstream
  Mutable code and hold its negative controls), 427 sequencer tests, 26 for
  the virtual FM-1 and 27 for the tools and the dongle. CI runs the suite on
  Linux and macOS, and the engine, sequencer and virtual-FM-1 tests again as
  a 32-bit build and under ASan + UBSan. It also builds the dongle's UF2 and
  runs AL-255's suite on our fork (`.github/workflows/ci.yml`). CI does not
  run Movy; it replays the oracle's committed fixtures.
- **Where the repo lives:** `~/Developer/mvave-fm1-firmware` on the owner's
  MacBook (the folder keeps its old name), remote `ip2k/lunar-modulator`
  (published 2026-09-06 as `ip2k/mvave-fm1-open-firmware`, renamed with the
  project on 2026-10-01; GitHub redirects the old URLs). Work goes on
  short-lived branches and merges through pull requests.
  - The repository is public. Before a branch's first push, search its
    whole history (`git log -p origin/main..HEAD`) for LAN addresses, local
    usernames and the unit's USB serial. A LAN address and an SSH user
    already reached `main`'s history through PRs #14 and #16; they are out
    of the tree, those PRs record it, and history is not rewritten.
  - The cloud session's stray branch `claude/mvave-fm1-open-firmware-ly2w6u`
    on `ip2k/busybar-dual-timer` was deleted on 2026-09-06; it is gone from
    GitHub's branch list [verified 2026-10-01].
- **Open pull requests** at 2026-10-01:
  - #1, Echomatter's "WIP: Decode FM-1 firmware and add reversible local
    workbench" (2026-09-15): 47 files, about 10,300 lines, based on `main`
    before #3, with docs numbered 11–22, of which 11–14 collide with ours.
    Nobody has reviewed or answered it. The owner's call.
- **Published:** the virtual FM-1 and the user manual are on GitHub Pages
  at https://ip2k.github.io/lunar-modulator/ (the simulator at `/`, the
  manual at `/manual/`; #24, `.github/workflows/pages.yml`). Other sessions'
  branches and worktrees: `git worktree list` in the main checkout.
- **Unrelated to the BUSY Bar project.** Do not mix the two.

### What is in the repository

| Path | What | Detail |
| --- | --- | --- |
| `docs/01`–`14` | Hardware, stock firmware, update protocol, prior art, feasibility, Movy and Schwung, recovery and risk, roadmap, first-session checklist, the `USB_KEY` dongle, the plugin platform, the sequencer, the Movy port plan, the verification ladder | README "Repository map" |
| `notes/` | Bench session 1 and the research log (2026-09-06), the desk review (2026-09-08), FM-1+VA and the PCB photos (2026-09-29), the CHOMPI evaluation and the monome / O&C / jhjlim survey (2026-10-01), `upstream-candidates.md` | |
| `engines/` | The engine platform, stage A: a C API with no heap; five sound engines (Macro, Shapes, Macro Heavy, Six-Op FM, Sophie) and four effects (Plate, Ensemble, Diffuse, PSX Verb), plus a test engine and effect; the Schwung shim; the desktop renderer `fm1-render`; reference renderers | `engines/README.md` |
| `engines/seq/` | `fm1_seq`, the sequencer core (docs/13 stage M1), about 4,600 lines of C99 | `engines/seq.md` |
| `tools/movy-oracle/` | Movy's own `seq-core` run in containers on a LAN Docker host (`MOVY_ORACLE_HOST`), and a random script generator; its golden fixtures are committed under `tests/fixtures/movy/` | its README |
| `sim/web/` | The virtual FM-1: the app layer in WebAssembly behind a to-scale panel, with the firmware's own screen. The built module is committed; it runs from a copy of the repository and on GitHub Pages. Rebuilt in containers on a Docker host (`FM1_SIM_HOST`) | `sim/web/README.md` |
| `dongle/` | The RP2040 `USB_KEY` firmware (PIO + C) and a ROM/dongle co-simulator | docs/10 |
| `tools/` | The read-only identity query (`fm1_identify.py`, verified on hardware), the msfa table finder, the `.fwsc` carver, `seq_bench.py` (the sequencer's worst cases for stage B) | `CLAUDE.md` "Commands" |
| `assets/branding/`, `photos/` | The banner and boot screen, Audiowide and its licence; the owner's photos of the unit, by date | |

## 2. The ten facts that matter

1. SoC = **JieLi AC791N** (WL82), two custom **pi32v2** cores at 240 MHz
   (stock: the OS on cpu0, the msfa voices bare-metal on cpu1 [inferred],
   docs/11 §2), 578 KB SRAM, 1 MB flash (probably in-package), XIP from
   `0x02000000`, RAM at `0x01C00000`. Marking `C156211-11B8` (aroum's unit) /
   `C188612-11B8` (the owner's), LQFP48.
2. Stock firmware = JieLi AC79 SDK (FreeRTOS-derived kernel, closed `.a` libs
   for BT/audio/fs/cpu) + M-VAVE glue + **Google msfa (Dexed) FM engine**.
   Verified here: the msfa algorithm table at `0x8C46C` (V13) / `0x8CBCC`
   (V14) / `0x8BE8C` (V15, intact in `FM-1_092`) of `app.bin`, with
   algorithms 4 and 6 changed (`0x41` for `0xC1`), the fix carried in the
   Dexed family [inferred: docs/02].
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
5. **No recovery path proven on this project's unit.**
   - Single flash bank, no debug pads or buttons. The one candidate header
     was the battery connector's leads (2026-09-29).
   - AL-255's verdict: NO-GO for non-stock flashing. This is the gate for
     everything.
   - Other owners report the mask-ROM route working on *their* FM-1s, as far
     as a backup and a write [reported: ip2k/lunar-modulator#2, docs/10
     §1.1]. FM-1-transporter (kurogedelic) and fm1-nes report dumps and
     writes through mask ROM too (docs/10 §1.1, docs/04). None of that meets
     the one rule, which asks for a dump and a byte-identical restore on this
     unit.
   - The ways to try it here are JieLi's updater dongle (on order) and ours.
6. Most promising recovery: JieLi **`USB_KEY`** (`0x16EF` bit-banged on D+/D−
   at ~50 kHz at power-up, ACK = both lines low 1–2 ms, then SOF clock
   detection) → mask-ROM "UBOOT1.00" mass-storage mode → read-only dumps
   with `jl-uboot-tool` and its `wl82loader.bin` (`0x1C02000`) on a Linux PC
   (docs/10 §5). JieLi's `isd_download` is a writer and is never run against
   the FM-1 (docs/07 §2.1).
   - The clock is D+: czietz's dongle reached UBOOT mode that way on two
     FM-1s, then handed over by moving the cable to the PC [reported].
   - kagaimiq's `usb-key.md` and the diagram in `how-to-enter-uboot.md`
     agree; only that page's prose says D−.
   - Our dongle keys polarity A (D+ as the clock) by default since #19;
     holding its button at boot selects B, and alternating is a build option
     (docs/10 §6).
7. Toolchain = JieLi's closed **Clang/LLVM 4.0.1** fork (`pi32v2` backend),
   Linux build available from `pkgman.jieliapp.com`; AL-255 built C++11 with
   it. No Rust, no GCC/LLVM upstream, no JS runtime. Here it runs in a
   container on a Docker host (`tools/jieli/compile-check.sh`,
   `FM1_JIELI_HOST`): all 63 objects compile, compile-only so far (#30,
   docs/14 §5.2).
8. Vendor SDK `fw-AC79_AIoT_SDK` (Gitee, current to V1.2.13; our pin is tag
   V1.1.9 `8eae664`, because `system.a` gains key checks from V1.2.7,
   CLAUDE.md trap 11) is Apache-2.0 (with GPL parts, docs/12 §6) with a
   public register map `WL82.h`, linker scripts, `demo_hello`, flashing tools,
   `wl82loader.bin`, a JTAG/debug-TAP folder, and datasheets; ~110 closed `.a`
   libraries per CPU. JieLi's `fw-Bootloader` (Apache-2.0) targets wl82.
9. **schwung-movy cannot run on the FM-1** (TS + Rust on a quad-A72 Linux
   box), but its sequencer is now the specification. `fm1_seq` is a C99,
   heap-free rewrite of Movy's `seq-core` at `9190e79`, with an exact-Movy
   `compat` mode for tests and deviations D1–D13 on by default; Movy's own
   code runs as its test oracle (docs/13, `engines/seq.md`). The FM-1 has
   **four free parameter knobs**, KNOB1–4; MASTER, SELECT, PRESETS and
   ALGORITHM have fixed jobs [layout verified in the owner's photos; names
   reported from Baud Girl's manual; mapping inferred: docs/01 §3]. Movy's
   8-knob pages become pages of four, as the engine API already pages its
   parameters.
10. USB IDs: normal `4C4A:C755` ("FM-1 Midi" + "FM-1 Audio" UAC1), OTA
    `4D4A:4155`. Identity query `F0 00 32 45 00 00 00 40 7F F7` → 41-byte
    reply `F0 00 32 45 58 01 00 00 23 4D 5A 44 …` [verified on `FM-1_015`,
    docs/03 §2]. FM-1+VA keeps V15's checksum byte, so on `FM-1_092`
    `fm1_identify.py` reports a failed checksum: read the plain field and do
    not gate on the checksum (notes/2026-09-29 §4).

## 3. Decisions taken

- Target **L1** first (open application on the vendor SDK), then open
  bootloader (L4), then blob removal (L2); an open compiler (L3) is out of
  scope unless a contributor wants it. See docs/05.
- **Recovery before any flash.** The one rule in `CLAUDE.md` stands: nothing
  gets flashed to, or written on, the FM-1 until a full flash dump and a
  byte-identical restore have been demonstrated on that unit, and until then
  the only traffic allowed is the read-only identity query
  `F0 00 32 45 00 00 00 40 7F F7` and passive captures (docs/14 §4.1 lists
  what that excludes). docs/08 Phase 2's exit is two byte-identical
  dump/restore cycles on the FM-1. The rules of engagement are in docs/07
  §4. The owner's own install of FM-1+VA does not relax them, and neither
  do reports from other units.
- **Licences** (`CLAUDE.md` → "Project status and licences"): the repository
  is MIT. GPL or LXR code may come in only under `third_party/<name>/`, with
  its licence and an `UPSTREAM.md`, behind a build switch; a binary that
  links JieLi's closed libraries and contains it must not be shared. The
  vendored engine code (Mutable Instruments, Schwung, Sophie, PSX Verb) is
  MIT and unmodified. CHOMPI's copy of DaisySP holds LGPL headers under an
  MIT label and is never used (`notes/2026-10-01-chompi-evaluation.md`).
- **Engines** (docs/11): Mutable Instruments code first, a static engine
  registry before any loader, Schwung modules through a shim. The Mutable
  engines run at their native rates (Braids 96 kHz, Plaits 47,872.34 Hz) and
  are resampled once per engine to the FM-1's 44,118 Hz; effects stay at
  the host's rate (`engines/resampler.md`, engines/README.md). Six-Op FM
  patches named after trademarks or people get descriptive names on our own
  reading, not a legal clearance; `-DFM1_SIXOP_ORIGINAL_NAMES` restores the
  originals for personal builds (`engines/plaits-heavy.md`).
- **Sequencer** (docs/12, docs/13 §10): Movy is the target. Its semantics are
  reproduced exactly in `compat` mode, with every planned fix on by default.
  4–8 tracks, each routed to the engine or to USB-MIDI; about half of
  docs/13's 72 KiB; 7-bit locks; Capture on by default with 256 packed
  12-byte events (the owner's choice, #21). It is credited as "after Movy by
  megadake (MIT)" and the UI calls it
  "Sequencer" (docs/13 §8). Movy is read through the GitHub API and built or
  run only through `tools/movy-oracle/`, in containers.
- **Verification** (docs/14): bit-exact wherever both sides do the same
  arithmetic; a tolerance only for a named cause. One golden corpus runs on
  every rung: desktop, browser, dev kit, then the FM-1 once the one rule
  allows.
- Never commit vendor firmware or the JieLi toolchain. `.gitignore` blocks
  `.fwsc`, `.bin` and the vendor folders, but not a `uboot.boot` or a
  `.dmg`, so look before adding files.
- Confidence marks **[verified]/[reported]/[inferred]** in all docs; keep them
  honest.
- The name and the look (Audiowide, the Rosé Pine Moon palette, no NASA,
  M-VAVE or Cuvave marks) follow `CLAUDE.md` and `assets/branding/README.md`.

## 4. Open questions (ranked)

1. Does `USB_KEY` reach the mask ROM on *this* unit? Reported yes on two
   other FM-1s (§1). What is still unknown, and what the ip2k/lunar-modulator#2
   draft asks the reporters, is in docs/10 §8.
2. Flash: in-package or discrete, exact size (JEDEC ID)? Answerable once
   UBOOT mode is reached.
3. pi32v2 cost, measured on the dev kit in stage B (docs/14 §5, step 8):
   cycles per block for the engines, the effects, the resampler (keep the
   full second stage or take the cheaper half-band) and the sequencer's
   worst cases (`tools/seq_bench.py`; exit: at most 2 % of any block);
   whether a `-fPIC` build works; FPU edge cases and libm (docs/14 §6).
   Shapes needs 206,212 B for 12 voices on 32-bit and, with PSX Verb and
   Plate, does not fit the 387,924-B stock gap [inferred]; a lower voice cap
   or a split is decided with those numbers (engines/README.md).
4. Knobs: `RW1` is a potentiometer (MASTER, probably) and the other seven
   are encoders [verified: owner's photo 2026-09-29]; still to reconcile with
   the firmware's 2 hardware decoders + 2 ADC channels (docs/01 §6).
5. The board: AC791N variant and pinout, UART and debug-TAP pins (there is
   no header), the display controller's ID, and markings still unread
   (`U12`, `SLS316D`, `U2`, `U5`, `U9`, `U11` and others). The full lists
   are docs/01 §6 and docs/09 §5.
6. What the sequencer UI needs from the hardware (docs/13 §10, question 6):
   what the 14 buttons say, whether KNOB1–4's push switches are readable,
   whether the key LEDs dim, whether the keys sense velocity, the scan rate,
   and room in flash for sets. Also undo's depth.
7. Engines: Six-Op FM's output is inverted relative to Macro and Macro
   Heavy, and effects at native rates are not done (engines/README.md "Open
   questions and next steps"). Six-Op's patch data needs review before
   anything commercial (same section), and PSX Verb's presets before
   shipping (`engines/third_party/schwung-modules/psxverb/UPSTREAM.md`).
8. Any GPL-only Dexed code in the stock image (licensing lever)?

Answered since 2026-09-06: the step-1 verifier refuses only the running
version [reported: Baud Girl]; the SoC does not enumerate with the power
switch off [verified], so the switch is the power-up moment for `USB_KEY`.

## 5. Next actions

Done, for the record: the repository move and bench session 1
(2026-09-06); contact with aroum and AL-255 (2026-09-06); FM-1+VA diffed
against V15 and the board photographed (2026-09-29); engine stages A and A2,
the reference renders and native rates (2026-09-30 to 10-01); the sequencer
core and the Movy oracle (M1 and M3); the virtual FM-1, the rename and
docs/14; the issue #2 write-up, the dongle fix and its D+ default; the
README's status and credits (all 2026-10-01).

Now, roughly in order:

1. **Open PRs** (§1): Echomatter's #1 needs the owner's answer.
2. **ip2k/lunar-modulator#2**, if the owner chooses to answer it from the
   draft: its questions (the UBOOT name, the tool and commands, the number
   of tries, battery during the cable swap) shape the first attempt here.
3. **When the dev kit and JieLi's updater arrive**, docs/14 §5's first week:
   record the parts, set up the toolchain, the kit's own dump and restore
   through the vendor dongle with jl-uboot-tool read-only, blink and UART,
   FPU probes, audio out, then rung R2 offline and the stage B numbers. The
   owner has asked whether both of the AC791N's cores can be used (stock
   runs the msfa voices on cpu1 [inferred], docs/11 §2); a second-core probe
   fits that week.
4. **Recovery on the FM-1** (docs/08 Phase 2, docs/10 §5–§6): once the owner
   has decided about a rollback to V15 (§1), enter UBOOT mode, dump the
   flash twice and compare, restore byte for byte, twice. Only then does the
   one rule allow writing anything.
5. **Sequencer** (docs/13 §9, `engines/seq.md`): wiring it into the
   virtual FM-1 (stage S1), where SEQ, PLAY/STOP and REC still
   say "not in the simulator yet"; the rest of M2 (engine API v2: a stable
   uid per parameter, LATCH/SMOOTH/NOLOCK, a MIDI-effect kind); M4 (the UI
   state machine, TFT views, a command ring, undo); stage B on the kit;
   stages C and D on the FM-1 after the dump and restore.
6. **Engines:** Shapes' voice cap and the resampler variant, with stage B's
   numbers; Six-Op's polarity.
7. **The owner's queued requests** (2026-10-01), in this order after the
   sequencer is in the simulator: arpeggiators; configurable LFOs,
   envelopes and a modulation matrix; eurorack-style effects such as
   sample-and-hold (MIT/BSD/Apache code preferred, §3). Also a development
   roadmap in the README. The user manual and GitHub Pages are already in
   flight (§1).
8. **The owner's calls, all unsent:** the 2026-09-29 email to Baud Girl and
   issue for AL-255 (`scratch/drafts/`); the items in
   `notes/upstream-candidates.md` (Plaits bugs, the Movy questions D3–D6,
   kagaimiq's D−/D+ sentence, an O&C shift); whether to ask aroum to tone
   down their README, which since `cb5796c` (2026-09-13) links our dongle as
   if it enabled recovery. Anything upstream follows the
   `oss-contributions` rules: we draft, the owner posts. The threads have
   been quiet: AL-255/FM-1-RE PR #3 has only a third-party comment
   (2026-09-12), and AL-255/FM-1-RE issue #1 and aroum/fm1-custom-fw#2 (our
   extractor report) have no reply.
9. **Docs that lag behind**, found during this refresh and left for a
   follow-up PR: docs/02's V15 row ("running on the owner's unit"); docs/04
   (AL-255's PR #2 merged, aroum's head moved); docs/06 (`5627d51` labelled
   v0.31.0, "8 knobs"); docs/08 ("if one can be bought", "the dongle is
   built"); docs/11 ("about 360 engine tests"); docs/13 §10 answer 1 ("D1–D7
   are the defaults"); docs/14 ("about 350" reference tests, now 427);
   README's "Repository history"; and the GitHub repository description
   ("Research stage").
10. **The dead-code audit is due** (`CLAUDE.md` → Conventions). The mark is
    7,463 lines (2026-09-30). The same scope now holds about 24,200 lines,
    plus about 4,800 in `sim/` [by a `wc -l` count on 2026-10-01 that gives
    7,457 at the mark]: about 21,500 added, against an interval of about
    10,000.

## 6. Reference material

Clone into `reference/` (git-ignored), except Movy (§3). The pins are what
the docs cite; where an upstream has moved since, its head on 2026-10-01 is
noted.

| Repo | Commit | Why |
| --- | --- | --- |
| `aroum/fm1-custom-fw` | `d08360f` 2026-08-21 (head `cb5796c`, 2026-09-13: a README link to us) | updater analysis, photos, untested flasher |
| `AL-255/FM-1-RE` (`main`) | `95eca84` 2026-08-16 (head `ec832f2`, 2026-09-08: Echomatter's PR #2 merged) | disassembly, protocol, safety, firmware images V13/V14 |
| `AL-255/FM-1-RE` (`with-custom-firmware`) | `628fcaf` 2026-08-02 | experimental pi32v2 firmware, package builders, Synth_Dexed port |
| `kagaimiq/jielie` | `1657d25` 2024-09-15 | JieLi docs: ISA, USB_KEY, formats |
| `kagaimiq/jl-uboot-tool` | `adb3f18` 2025-03-16 | UBOOT dumper/flasher, `wl82loader.bin` |
| `kagaimiq/jl-misctools` | `0a5b12d` 2025-02-20 | `fwunpack_newfw.py` |
| Gitee `Jieli-Tech/fw-AC79_AIoT_SDK` | `e30b1ee` 2026-06-09 (= V1.2.13 + README); tag V1.1.9 `8eae664` is our pin; branch `AC791N_OTA_loader` `79eda0c` | vendor SDK: `WL82.h`, `cpu/wl82/tools`, datasheets, the OTA loaders. Gitee's SSL is flaky: pin by commit, clone blobless and sparse with `tools/jieli/ac79-sdk-sparse.txt`. The GitHub mirrors are stale (`amitv87` to 2024-07, `jeffreywugz` V1.0.3): do not cite them |
| `hugelton/Felucca` | `727f272` 2026-10-05 (v1.0) | bare-metal FM-1 firmware; pin map, update-service design (GPL-3.0-only: facts only) |
| `isod89/sloop-fm1` | `f2b44c2` 2026-10-04 (v2.2) | Felucca fork; boot guard, loader checks (GPL-3.0-only: facts only) |
| `Keitark/fm1-nes` | `870f305` 2026-10-03 | SDK app on an FM-1; board support, sparse mask-ROM planner (Apache-2.0 root) |
| `kurogedelic/FM-1-transporter` | `a632d92` 2026-10-01 | RP2040 `USB_KEY` + USB host recovery tool (MIT); read through the API; never run against the owner's unit (CLAUDE.md trap 9) |
| `pichenettes/eurorack`, `pichenettes/stmlib` | `08460a6` 2023-08-16; `e3bd7c9` 2023-05-30, eurorack's submodule pin (head `d18def8`, 2023-09-03) | the Plaits, Braids and Rings code behind the engines (`engines/third_party/mutable/UPSTREAM.md`) |
| `charlesvestal/schwung`, `charlesvestal/schwung-psxverb`, `mestela/schwung-sophie` | `70c4171` (head `ba3b39d`, 2026-09-30); `b0b44db`; `5682295` (head `abd132d`, 2026-10-01) | the Schwung module API, PSX Verb and Sophie (`engines/third_party/schwung*/`) |
| `DimaDake/schwung-movy` (MIT, megadake) | `9190e79` 2026-10-01 (`module.json` 0.34.0) | the sequencer `fm1_seq` replicates, and the oracle; docs/06 read the earlier `5627d51`, which is not the v0.31.0 tag (docs/13) |
| czietz's "Quick and very dirty JieLi UBOOT tool" (gist `9a94cf3c…`) | revision of 2026-09-27, no licence | the Pico dongle of ip2k/lunar-modulator#2; summarized in docs/10 §1.1, not copied |

Baud Girl's FM-1+VA has no public repository (Baud Girl mentions a private
one [reported]); its pages and installer were read on 2026-09-29
(`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`, Sources and §1). The
sources surveyed but not used yet (CHOMPI, O&C, monome, jhjlim) are pinned
in their notes.

Web pages the 2026-09-06 research sandbox could not reach: since read are
the user manual PDF (docs/12), fm1-editor.com through its source repository
(desk review §2) and the updater dongle's manual (docs/07 §2.1);
kagaimiq.github.io is covered by its repository, and gitee.com was reached
on 2026-10-05 (the SDK row above). Still unread: the cuvave.com product page, synthanatomy.com,
fwradar.com, the elektronauts/gearspace/reddit threads and the
madushan.caas.lk blog post.

## 7. Starting a new session

Paste this as the first message (adjust the task):

> This is Lunar Modulator, open firmware for the M-VAVE FM-1, in
> `~/Developer/mvave-fm1-firmware`. Read `HANDOFF.md`, `DEVELOPERS.md` and
> `CLAUDE.md` first. Rules: the FM-1 on my desk is the only unit; nothing
> is flashed to or written on it, and nothing but the read-only identity
> query is sent to it, until a full dump and a byte-identical restore have
> been shown on it (`CLAUDE.md`, docs/07 §4); keep the
> [verified]/[reported]/[inferred] marks honest; feature work goes on a
> branch and merges through a PR. Before starting, check the open PRs, and
> ask me whether the dev kit and JieLi's updater have arrived. Today's
> task: …

<details>
<summary>The 2026-09-06 kick-off prompt (historical)</summary>

Its tasks were done in bench session 1 (`notes/2026-09-06-bench.md`). Its
premise that the updater disk image holds V15 was wrong: it holds V14, and
V15 came from the CDN. The path is the one the repository moved to the same
day.

> This project is the open-source firmware effort for the M-VAVE FM-1 FM
> synthesizer. The repository (`~/Developer/mvave-fm1-firmware`) contains a
> completed research phase: read `HANDOFF.md`, then `README.md`, then
> `docs/01`–`09` and `CLAUDE.md`. Rules: the FM-1 on my desk is the only
> unit; nothing may be flashed or sent to it beyond the read-only identity
> query until recovery is proven (docs/07). Today's tasks: (1) run
> `docs/09-first-session-checklist.md` §1 to extract and analyse the V15
> firmware from `~/Downloads/M-UPGRADE-FM1*.dmg`; (2) §2–§3 USB descriptors
> and identity query with the FM-1 plugged in; (3) write results to
> `notes/<date>-bench.md` and update the open questions in `docs/01` §6 and
> the version table in `docs/02` §1. Keep the [verified]/[reported]/[inferred]
> marks honest.

</details>
