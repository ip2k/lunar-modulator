# Hand-off package — Lunar Modulator

**INTERGALACTIC MODULATION STATION.** Lunar Modulator is open firmware for
the M-VAVE FM-1; until 2026-10-01 the project was called "Open firmware for
the M-VAVE FM-1". Naming rules are in `CLAUDE.md` → "What this is".

This file lets a fresh session, or a human, carry on without the earlier
conversations. It was first written on 2026-09-06 at the end of the research
session that created the repository, and rewritten on 2026-10-05 for the
state of `main` after PRs #3–#57 (2026-09-29 to 2026-10-05, `8ef2335`).
Read it first, then `DEVELOPERS.md` (everything technical, including where
development stands and the roadmap; `README.md` is the product page, for
users), then `CLAUDE.md` (mirrored for Codex in `AGENTS.md`: edit the two
together), then the `docs/` a task needs. It is a summary: where it and a
doc disagree, the doc wins and this file is stale.

A bare PR or issue number means this repository, `ip2k/lunar-modulator`;
any other repository is named. "Issue #2" exists both here and at aroum's,
so it is always written in full.

## 1. Where things stand (2026-10-05)

- **The code runs on a desktop and in a browser, not yet on a JieLi chip or
  an FM-1. This project has flashed nothing**, and has sent the owner's unit
  nothing since 2026-09-29. Every object compiles for pi32v2 with JieLi's
  toolchain (#30, compile-only, `notes/2026-10-02-jieli-compile-check.md`),
  but nothing has been linked into firmware or run on a chip, so speed on
  pi32v2 is not measured.
- **What anyone can use:** the virtual FM-1 and the user manual on GitHub
  Pages, https://ip2k.github.io/lunar-modulator/ (the simulator at `/`, the
  manual and its PDF at `/manual/`; #24, redeployed from `main` by
  `.github/workflows/pages.yml`). The public page plays one of five sound
  engines through two effect slots, from mouse, touch, keyboard or Web MIDI.
  Behind `?lab` it also runs the sequencer (docs/15 stages S3–S6 and S8),
  four sound units with inserts and a RAM meter, and the modulation pages
  (MG3); #55, open and asked for by the owner, makes them public. Tested in
  Chromium only; issue #53 reports no audio in Safari on iOS (unanswered).
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
  - A flash dump taken now captures FM-1+VA, not stock (docs/07 §4 note,
    docs/14 §4.1). The way back to stock, V15's `.fwsc` through the same
    installer, is [reported] and has not been tried here. A rollback is a
    write through the stock updater, so whether to do it before the first
    dump is the owner's decision and the owner's action, like the FM-1+VA
    install; this project does not send it.
- **Recovery is closer, but not proven on this unit.**
  - Other owners report reaching the FM-1's mask-ROM mode (docs/10 §1.1,
    docs/07 §4 note) [reported]: czietz's Pico dongle (in
    [issue #2 here](https://github.com/ip2k/lunar-modulator/issues/2), from
    2026-09-16) about one power-on in two, and masanaohayashi's backup and
    write with it; kurogedelic's FM-1-transporter (dumps and a sector
    rewrite on a V15 unit; D+ only); Keitark's fm1-nes (a 51-sector install
    on a V14 unit). Nobody has reported a byte-identical restore, and none
    of it is on this unit. czietz's tool and FM-1-transporter drive the
    lines push-pull, which docs/10 §2 E1 rules out here, and
    FM-1-transporter sends the soft key by itself (trap 9): never run either
    against the owner's unit.
  - Our own `USB_KEY` dongle (docs/10, `dongle/`) is specified, implemented
    and simulated; CI builds its UF2, but nobody has built the hardware or
    run it. A pull-up wiring bug was fixed in #17 (D−'s pull-up now on
    GP19), and since #19 it keys with D+ as the clock (polarity A) by
    default (docs/10 §2 E3, §6).
  - **On order** (the owner, 2026-10-01): the JL-AC79-DevKit V1.0 (AC7916)
    and JieLi's USB updater dongle (docs/14). No arrival is recorded as of
    2026-10-05. The dump and restore get rehearsed on the kit first
    (docs/14 §5).
  - The stock SysEx "soft key" `F0 22 24 35 7D F7` reboots stock V15 into
    mask ROM [reported]. It is forbidden before the gate (CLAUDE.md trap 9).
    #54 (open, desk-only) drafts a read-only soft-key test plan that would
    need the owner to amend the one rule for one session; until the owner
    decides, nothing changes.
  - We have not answered ip2k/lunar-modulator#2. A reply is drafted in
    `scratch/drafts/2026-10-01-issue-2-reply.md` (git-ignored, unsent).
    Whether and when to post it is the owner's decision. Never post it
    ourselves.
- **Other firmware on FM-1s** (docs/04, `notes/2026-10-05-community-repos.md`),
  all through the stock update path with rollbacks to V15: Echomatter's
  `FM-1_016` (2026-09-04, AL-255/FM-1-RE PR #2); Baud Girl's FM-1+VA
  (`FM-1_020` … `FM-1_092`, closed source); Felucca 1.0 (hugelton) and its
  fork SLOOP 2.2 (isod89), bare metal and GPL-3.0-only. fm1-nes runs an
  AC79 SDK app on one V14 unit, written through mask ROM [reported]. Their
  code maps the board (docs/01 §3.1, [reported]): audio is ALNK0 (I2S) to an
  external codec, not the internal DAC, and the seven encoders are scanned
  in the key matrix.
- **Tests:** 3,389 collected; 3,379 pass, 2 xfail (both undo, not ported
  yet) and 8 skip where a local reference clone or the manual's `markdown`
  module is missing [verified: `pytest` at `8ef2335`, 2026-10-05]. By group:
  2,430 engine tests (487 of them comparing against upstream reference
  renders and their controls, 157 for the arpeggiator, 147 for modulation),
  557 for the sequencer core, 362 for the virtual FM-1 and its sequencer UI,
  27 for the tools and the dongle, and 13 for the manual. CI runs the suite
  on Linux and macOS, runs the engine, sequencer and simulator tests again
  as a 32-bit build and under ASan + UBSan, builds the dongle's UF2, runs
  AL-255's suite on our fork (`.github/workflows/ci.yml`), and builds the
  site and manual on pull requests (`pages.yml`). CI does not run Movy; it
  replays the oracle's committed fixtures.
- **Where the repo lives:** `~/Developer/mvave-fm1-firmware` on the owner's
  MacBook (the folder keeps its old name), remote `ip2k/lunar-modulator`
  (published 2026-09-06 as `ip2k/mvave-fm1-open-firmware`, renamed with the
  project on 2026-10-01; GitHub redirects the old URLs). Work goes on
  short-lived branches and merges through pull requests; several sessions
  often work at once (`git worktree list` in the main checkout).
  - The repository is public. Before a branch's first push, search its
    whole history (`git log -p origin/main..HEAD`) for LAN addresses, local
    usernames and the unit's USB serial. A LAN address and an SSH user
    already reached `main`'s history through #14 and #16; they are out of
    the tree, those PRs record it, and history is not rewritten. Build hosts
    are named only through variables (`FM1_SIM_HOST`, `MOVY_ORACLE_HOST`,
    `FM1_JIELI_HOST`).
  - The cloud session's stray branch `claude/mvave-fm1-open-firmware-ly2w6u`
    on `ip2k/busybar-dual-timer` was deleted on 2026-09-06.
- **Open pull requests** at 2026-10-05, all waiting for the owner:
  - #55, the sequencer, multi-sound and modulation go public (no more
    `?lab`; the owner asked for it). The manual gains a chapter, so chapter
    URLs from 8 on change.
  - #54, notes on the soft key and the SDK's key and eFuse checks, with the
    draft read-only test plan above.
  - #56, building against the SDK V1.2.13 libraries (never its SPL or
    loader) behind a link audit and a package guard; it records the owner's
    2026-10-05 decision, contains #54, and rewrites trap 11 and fact 8 below.
  - Echomatter closed #1 on 2026-10-05 and offered to coordinate, saying
    this is the repository they will support. Answering is the owner's call.
- **Unrelated to the BUSY Bar project.** Do not mix the two.

### What is in the repository

| Path | What | Detail |
| --- | --- | --- |
| `DEVELOPERS.md` | The technical home: getting started, how the software works, the hardware, where development stands, the roadmap in detail, the path to an installable build (I0–I15), research to do, contributing | its contents list |
| `docs/01`–`16` | Hardware, stock firmware, update protocol, prior art, feasibility, Movy and Schwung, recovery and risk, roadmap, first-session checklist, the `USB_KEY` dongle, the plugin platform, the sequencer, the Movy port plan, the verification ladder, the sequencer in the simulator (S1–S10, owner decisions O1–O24), modulation (MG0–MG9) | DEVELOPERS.md "Documents" |
| `notes/` | Bench session 1 and the research log (2026-09-06), the desk review (09-08), FM-1+VA and the PCB photos (09-29), the CHOMPI, monome/O&C and arp/modulation/effects studies (10-01), the delay/reverb/EQ/gates and filters/dynamics options and the JieLi compile check (10-02), the community firmware and current SDK study (10-05), `upstream-candidates.md` | |
| `engines/` | The engine platform: a C API with no heap (v3 since #57), five sound engines and 20 effects plus test entries, the Schwung shim, the desktop renderer `fm1-render`, reference renderers | `engines/README.md` |
| `engines/seq/` | `fm1_seq`, the sequencer core (docs/13 M1), and the host bridge that `fm1-render` and the simulator share (#25): about 6,000 lines of C99 | `engines/seq.md` |
| `engines/mod/`, `engines/midi_fx/` | The modulation runtime: a rack of modules inside a 32-slot matrix, 16 kinds (MG1–MG3); `fm1_arp`, the arpeggiator core, built but not wired | `engines/mod/README.md`, docs/16; `engines/midi_fx/README.md` |
| `sim/web/` | The virtual FM-1: the app layer in WebAssembly behind a to-scale panel, with the firmware's own screen; the built module is committed. Rebuilt and checked in containers on a Docker host (`FM1_SIM_HOST`) | `sim/web/README.md` |
| `manual/`, `tools/manual/` | The user manual, generated from the code and published with its PDF to Pages | `manual/README.md` |
| `tools/` | The read-only identity query (`fm1_identify.py`, verified on hardware), the msfa table finder, the `.fwsc` carver, `seq_bench.py`, `movy-oracle/` (Movy's own `seq-core` in containers, `MOVY_ORACLE_HOST`), `jieli/` (the pi32v2 compile check in a container, `FM1_JIELI_HOST`, and the SDK's sparse-clone list) | `CLAUDE.md` "Commands" |
| `dongle/` | The RP2040 `USB_KEY` firmware (PIO + C) and a ROM/dongle co-simulator | docs/10 |
| `assets/branding/`, `photos/` | The banner and boot screen, Audiowide and its licence; the owner's photos of the unit, by date | |

## 2. The ten facts that matter

1. SoC = **JieLi AC791N** (WL82), two custom **pi32v2** cores at 240 MHz
   (stock: the OS on cpu0, the msfa voices bare-metal on cpu1 [inferred],
   docs/11 §2), 578 KB SRAM, 1 MB flash (JEDEC `0x856014`, Puya [reported],
   probably in-package), XIP from `0x02000000` (app entry `0x02000120`
   [verified]), RAM at `0x01C00000`. Marking `C156211-11B8` (aroum's unit) /
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
   while any other version installs. Echomatter's, Baud Girl's, Felucca's
   and SLOOP's packages all went through the stock path, with rollbacks to
   V15; step 1 also accepts a loader that is not M-VAVE's [reported:
   Felucca, SLOOP]. The OTA loader **can rewrite the flash head**
   (`uboot.boot`, `isd_config.ini`), so keep it byte-identical; a loader
   left waiting after step 1 (`ota-FM-1`) can be resumed (docs/03 §5).
5. **No recovery path proven on this project's unit.**
   - Single flash bank, no debug pads or buttons. The one candidate header
     was the battery connector's leads (2026-09-29).
   - AL-255's verdict: NO-GO for non-stock flashing. This is the gate for
     everything.
   - Other owners report the mask-ROM route working on *their* FM-1s, as far
     as backups and writes (§1). None of that meets the one rule, which asks
     for a dump and a byte-identical restore on this unit.
   - The ways to try it here are JieLi's updater dongle (on order) and ours.
6. Most promising recovery: JieLi **`USB_KEY`** (`0x16EF` bit-banged on D+/D−
   at ~50 kHz at power-up, ACK = both lines low 1–2 ms, then SOF clock
   detection) → mask-ROM `UBOOT1.00` mass-storage mode (`4C4A:8057`
   [reported]) → read-only dumps with `jl-uboot-tool` and its
   `wl82loader.bin` (`0x1C02000`; works on FM-1s with 256-byte I/O
   [reported: fm1-nes]) on a Linux PC (docs/10 §5). JieLi's `isd_download`
   is a writer and is never run against the FM-1 (docs/07 §2.1, trap 11).
   Finish a dump, compare and write in one UBOOT session: the chip boots
   flash if the host drops it [reported].
   - The clock is D+: czietz's dongle and FM-1-transporter both key that
     way; the other polarity never worked for FM-1-transporter [reported].
   - Our dongle keys polarity A by default since #19; holding its button at
     boot selects B, and alternating is a build option (docs/10 §6).
7. Toolchain = JieLi's closed **Clang/LLVM 4.0.1** fork (`pi32v2` backend),
   Linux build from `pkgman.jieliapp.com`. No Rust, no GCC/LLVM upstream, no
   JS runtime. Here it runs in a container on a Docker host
   (`tools/jieli/compile-check.sh`): at #30 all 63 objects compiled in four
   profiles, with no fused multiply-adds, i386's instance sizes, newlib's
   libm and a single-precision FPU; linking and cycles are still to do
   (docs/14 §5.2).
8. Vendor SDK `fw-AC79_AIoT_SDK` on Gitee (current to V1.2.13; the GitHub
   mirrors are stale). On `main` our pin is tag V1.1.9 `8eae664`, because
   `system.a` gains key checks from V1.2.7 (CLAUDE.md trap 11); #56 would
   move to the V1.2.13 libraries. Apache-2.0, but not GPL-free: `system.a`
   holds FreeRTOS (GPLv2 with the exception) and `uac_audio*.h` are GPL-2.0,
   never to be included (CLAUDE.md, docs/12 §6). It has `WL82.h`, linker
   scripts, `demo_hello`, flashing tools, `wl82loader.bin` and datasheets,
   and ~110 closed `.a` libraries per CPU; it has no USB-MIDI device class.
9. **schwung-movy cannot run on the FM-1** (TS + Rust on a quad-A72 Linux
   box), but its sequencer is the specification. `fm1_seq` is a C99,
   heap-free rewrite of Movy's `seq-core` at `9190e79`, with an exact-Movy
   `compat` mode for tests and deviations D1–D13 on by default; Movy's own
   code runs as its test oracle (docs/13, `engines/seq.md`). The FM-1 has
   **four free parameter knobs**, KNOB1–4; MASTER (a pot), SELECT, PRESETS
   and ALGORITHM have fixed jobs [layout verified in the owner's photos;
   names reported from Baud Girl's manual; mapping inferred: docs/01 §3].
   Parameters page four at a time.
10. USB IDs: normal `4C4A:C755` ("FM-1 Midi" + "FM-1 Audio" UAC1), OTA
    `4D4A:4155`, mask ROM `4C4A:8057` [reported]. Identity query
    `F0 00 32 45 00 00 00 40 7F F7` → 41-byte reply
    `F0 00 32 45 58 01 00 00 23 4D 5A 44 …` [verified on `FM-1_015`,
    docs/03 §2]. FM-1+VA keeps V15's checksum byte, so on `FM-1_092`
    `fm1_identify.py` reports a failed checksum: read the plain field and do
    not gate on the checksum (notes/2026-09-29 §4). The soft key
    `F0 22 24 35 7D F7` is a different message and forbidden (trap 9).

## 3. Decisions taken

- Target **L1** first (open application on the vendor SDK), then open
  bootloader (L4), then blob removal (L2); an open compiler (L3) is out of
  scope unless a contributor wants it (docs/05). Felucca and SLOOP show L2
  running on FM-1s; whether that changes the plan is one of the community
  study's open owner decisions (`notes/2026-10-05-community-repos.md` §6).
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
  its licence and an `UPSTREAM.md`. Since 2026-10-05 GPL modules sit behind
  one switch, `FM1_GPL_MODS`, on by default while testing; while it is on,
  no firmware image that links JieLi's libraries may be shared, and the
  public simulator is offered under GPL terms. No GPL code is in the tree
  yet. The vendored engine code (Mutable Instruments, Schwung, Sophie, PSX
  Verb) is MIT and unmodified. Felucca and SLOOP are facts and ideas only;
  CHOMPI's copy of DaisySP is never used.
- **Docs:** `README.md` is the product page and stays free of technical
  material; `DEVELOPERS.md` holds the rest (#23, CLAUDE.md).
- **Engines** (docs/11, engines/README.md): Mutable Instruments code first,
  a static registry, Schwung modules through a shim. The Mutable engines run
  at their native rates and are resampled to the FM-1's 44,118 Hz. Engine
  API v2 added parameter uids and flags (#34), per-note offsets (#47) and
  2.5 ms SMOOTH ramps inside the engines (#49); v3 adds an effect extension
  with key input, tempo, beats and transport, 16-bit flags, a dB unit and
  LOG knobs (#57). Six-Op FM patches named after trademarks or people get
  descriptive names (not a legal clearance).
- **Sequencer** (docs/13 §10, docs/15 §8): Movy is the target, reproduced
  exactly in `compat` mode with every planned fix on by default; 8 tracks in
  the app, each routed to one of up to four sound units or to a MIDI
  channel; 7-bit locks; Capture on by default with 256 packed 12-byte
  events (#21). It is credited as "after Movy by megadake (MIT)" and the UI
  calls it "Sequencer" (docs/13 §8). Movy is read through the GitHub API and
  built or run only through `tools/movy-oracle/`, in containers.
- **Modulation** (docs/16 §9): a rack of modules inside the matrix (G = 32
  frames, 8 positions, 32 slots, an 8 KB arena); per-voice modulation (MG9)
  is essential; envelopes retrigger on every note.
- **Verification** (docs/14): bit-exact wherever both sides do the same
  arithmetic; a tolerance only for a named cause. One golden corpus runs on
  every rung: desktop, browser, dev kit, then the FM-1 once the one rule
  allows.
- Never commit vendor firmware or the JieLi toolchain. `.gitignore` blocks
  `.fwsc`, `.bin` and the vendor folders, but not a `uboot.boot` or a
  `.dmg`, so look before adding files.
- Confidence marks **[verified]/[reported]/[inferred]** in all docs; keep them
  honest.
- The name and the look (Audiowide; Rosé Pine Moon for the simulator, Dawn
  for the manual; no NASA, M-VAVE or Cuvave marks) follow `CLAUDE.md` and
  `assets/branding/README.md`.

## 4. Open questions (ranked)

1. Does `USB_KEY` reach the mask ROM on *this* unit? Reported yes on other
   FM-1s (§1). What is still unknown, and what the ip2k/lunar-modulator#2
   draft asks the reporters, is in docs/10 §8. Whether the soft key is ever
   used is #54's question for the owner.
2. Flash: in-package or discrete (`U12`?), and this unit's JEDEC ID.
   Answerable once UBOOT mode is reached.
3. pi32v2 cost, measured on the dev kit in stage B (docs/14 §5): linking
   against the pinned SDK and its size, cycles per block for the engines,
   effects, resampler, modulation kinds and the sequencer's worst cases
   (`tools/seq_bench.py`; exit: at most 2 % of any block), FPU edge cases,
   newlib's libm against the desktop's, and whether `-fPIC` links. Shapes'
   memory (about 207 KB for 12 voices; with PSX Verb and Plate it does not
   fit the 387,924-B stock gap [inferred]) is decided with those numbers.
4. The second core: whether a `#C1` task-name prefix pins a task to cpu1
   (docs/14 §5.1, probes C6a–C6f).
5. The board, still open on this unit (docs/01 §6, docs/09 §5): the exact
   variant (AC7911B8 hypothesis [inferred]), the debug TAP, the display
   controller's ID, which part is the I2S codec, the LED drive, unread
   markings. The pin map from community code is in docs/01 §3.1
   [reported], to be checked against V15 (DEVELOPERS.md I4).
6. Hardware the sequencer UI needs (docs/13 §10, question 6): what the 14
   buttons say, KNOB1–4's push switches, LED dimming, key velocity, the scan
   rate, room in flash for sets. Also undo's depth.
7. Owner questions recorded in the docs: docs/15 §8 (O15–O20 for S9 and
   S10), docs/16 §9 (Q10–Q18, including the GPL switch's first use) and the
   MG3 questions in docs/16 §8; the effects notes' decisions; the community
   study's ten decisions (§6 of the note).
8. Engines (engines/README.md "Open questions and next steps"): Braids
   faults at extreme settings, Six-Op's polarity, effects at native rates,
   Six-Op's patch data and PSX Verb's presets before anything is shipped.
9. Any GPL-only Dexed code in the stock image (licensing lever)?

Answered since 2026-09-06: the step-1 verifier refuses only the running
version [reported: Baud Girl]; the SoC does not enumerate with the power
switch off [verified]; the knobs are seven matrix-scanned encoders and one
pot, and audio is I2S to a codec [reported: Felucca, fm1-nes; docs/01 §3.1].

## 5. Next actions

Done, for the record: the research phase and bench session 1 (2026-09-06);
FM-1+VA diffed against V15 and the board photographed (09-29); engine
stages A and A2, the reference renders and native rates (09-30 to 10-01);
the sequencer core and the Movy oracle (M1, M3); the rename, the virtual
FM-1, docs/14, the issue #2 write-up and the dongle fixes (10-01); the
README and DEVELOPERS.md split, the manual on Pages, stage B compile-only,
the sequencer in the simulator S1–S8, engine API v2 and v3, the arpeggiator
core, modulation MG1–MG3, four effect packs, and the community study
(10-01 to 10-05). The CHANGELOG has the detail.

Now, roughly in order:

1. **Open PRs** (§1): #55 (public sequencer), #54 and #56 (soft key, SDK
   move) wait for the owner; Echomatter's offer on #1 needs an answer.
2. **ip2k/lunar-modulator#2**, if the owner chooses to answer it from the
   draft; and issue #53 (iOS Safari).
3. **When the dev kit and JieLi's updater arrive**, docs/14 §5's first week:
   record the parts against the SDK's schematics, link `demo_hello` at the
   pinned SDK, the kit's own dump and restore (its UPDATA and RESET keys
   first, then the vendor dongle) with jl-uboot-tool read-only, blink and
   UART, FPU probes, the second-core probes, audio out, then rung R2 and
   the stage B numbers. The kit's audio is its DAC; the FM-1's is I2S
   (trap 10).
4. **Recovery on the FM-1** (docs/08 Phase 2, docs/10 §5–§6): once the owner
   has decided about a rollback to V15 (§1), enter UBOOT mode, dump the
   flash twice and compare, restore byte for byte, twice. Only then does the
   one rule allow writing anything.
5. **Sequencer** (docs/15 §5): S9 (session, scenes, song, the Loop view,
   COPY, CLEAR) and S10 (sets in the browser, MIDI realtime in); undo and
   the command ring (2 xfails); the MIDI-effect slot that wires `fm1_arp`;
   stages C and D on the FM-1 after the dump and restore.
6. **Modulation and effects:** MG4–MG9, with per-voice modulation (MG9)
   next (docs/16 §8); the remaining effects stages and the side-chain (the
   2026-10-02 options notes). The order of the owner's 2026-10-05 build plan
   is in DEVELOPERS.md "The roadmap in detail".
7. **The owner's calls, all unsent:** the 2026-09-29 email to Baud Girl and
   issue for AL-255 (`scratch/drafts/`); the rows of
   `notes/upstream-candidates.md`; contacting kurogedelic and Keitark (not
   drafted); whether to ask aroum to tone down their README, which since
   `cb5796c` links our dongle as if it enabled recovery and now lists Lunar
   Modulator as "Research / bench stage". Anything upstream follows the
   `oss-contributions` rules: we draft, the owner posts. AL-255/FM-1-RE PR
   #3 and issue #1 and aroum/fm1-custom-fw#2 have been quiet since
   2026-09-12.
8. **Docs that lag behind**, being fixed by a separate session started on
   2026-10-05 (not on `main` yet): DEVELOPERS.md's status block (dated
   2026-10-01: "more than 1,400 tests", nothing compiled); the README's
   product lines (four effects, "sequencer coming next", 287 screens; #55
   lists them, and the README's copy is the owner's); docs/02, 04, 06, 08,
   11, 13 §10 and 14 (see that session's PR); and the GitHub repository
   description ("Research stage", "Movy-style").
9. **The dead-code audit is far past due** (`CLAUDE.md` → Conventions; a
   separate session started on 2026-10-05 is running it). The mark is 7,463
   lines (2026-09-30). The same scope now holds about 77,800 lines, plus
   about 16,300 in `sim/` [by a `wc -l` count that gives 7,457 at the
   mark]: about 86,700 added, against an interval of about 10,000.

## 6. Reference material

Clone into `reference/` (git-ignored), except Movy (§3). The pins are what
the docs cite; where an upstream has moved since, its head is noted.

| Repo | Commit | Why |
| --- | --- | --- |
| `aroum/fm1-custom-fw` | `d08360f` 2026-08-21 (head `4e9d6d3`, 2026-10-04: links us and lists community firmwares) | updater analysis, photos, untested flasher |
| `AL-255/FM-1-RE` (`main`) | `95eca84` 2026-08-16 (head `ec832f2`, 2026-09-08: Echomatter's PR #2 merged) | disassembly, protocol, safety, firmware images V13/V14 |
| `AL-255/FM-1-RE` (`with-custom-firmware`) | `628fcaf` 2026-08-02 | experimental pi32v2 firmware, package builders, Synth_Dexed port |
| `kagaimiq/jielie` | `1657d25` 2024-09-15 | JieLi docs: ISA, USB_KEY, formats |
| `kagaimiq/jl-uboot-tool` | `adb3f18` 2025-03-16 | UBOOT dumper/flasher, `wl82loader.bin` |
| `kagaimiq/jl-misctools` | `0a5b12d` 2025-02-20 | `fwunpack_newfw.py` |
| Gitee `Jieli-Tech/fw-AC79_AIoT_SDK` | `e30b1ee` 2026-06-09 (= V1.2.13 + README); tag V1.1.9 `8eae664` is the pin on `main`; branch `AC791N_OTA_loader` `79eda0c` | vendor SDK. Gitee's SSL is flaky: pin by commit, clone blobless and sparse with `tools/jieli/ac79-sdk-sparse.txt`. The GitHub mirrors are stale (`amitv87` to 2024-07, `jeffreywugz` V1.0.3): do not cite them |
| `hugelton/Felucca` | `727f272` 2026-10-05 (v1.0) | bare-metal FM-1 firmware; pin map, update-service design (GPL-3.0-only: facts only) |
| `isod89/sloop-fm1` | `f2b44c2` 2026-10-04 (v2.2) | Felucca fork; boot guard, loader checks (GPL-3.0-only: facts only) |
| `Keitark/fm1-nes` | `870f305` 2026-10-03 | SDK app on an FM-1; board support, sparse mask-ROM planner (Apache-2.0 root) |
| `kurogedelic/FM-1-transporter` | `a632d92` 2026-10-01 | RP2040 `USB_KEY` + USB host recovery tool (MIT); read through the API; never run against the owner's unit (trap 9) |
| `pichenettes/eurorack`, `pichenettes/stmlib` | `08460a6` 2023-08-16; `e3bd7c9` 2023-05-30, eurorack's submodule pin (head `d18def8`) | Plaits, Braids, Rings and Clouds code behind the engines and Room; Peaks and Braids files as test oracles; Yarns as the arp's design source (`engines/third_party/mutable/UPSTREAM.md`) |
| `charlesvestal/schwung`, `charlesvestal/schwung-psxverb`, `mestela/schwung-sophie` | `70c4171` (head `ba3b39d`); `b0b44db`; `5682295` (head `abd132d`) | the Schwung module API, PSX Verb and Sophie (`engines/third_party/schwung*/`) |
| `DimaDake/schwung-movy` (MIT, megadake) | `9190e79` 2026-10-01 (`module.json` 0.34.0) | the sequencer `fm1_seq` replicates, and the oracle; docs/06 read the earlier `5627d51`, which is not the v0.31.0 tag (docs/13) |
| `jmamma/MCL`, `handcraftedcc/schwung-superarp` | `693a410` (BSD-3), `6eefd02` (MIT) | the arpeggiator's design sources, read only (`engines/midi_fx/CREDITS.md`) |
| czietz's "Quick and very dirty JieLi UBOOT tool" (gist `9a94cf3c…`) | revision of 2026-09-27, no licence | the Pico dongle of ip2k/lunar-modulator#2; summarized in docs/10 §1.1, not copied |

Baud Girl's FM-1+VA has no public repository (Baud Girl mentions a private
one [reported]); its pages and installer were read on 2026-09-29
(`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`). Sources surveyed but
not used (CHOMPI, O&C, monome, jhjlim) are pinned in their notes.

Web pages the 2026-09-06 research sandbox could not reach: since read are
the user manual PDF (docs/12), fm1-editor.com through its source repository
(desk review §2) and the updater dongle's manual (docs/07 §2.1);
kagaimiq.github.io is covered by its repository, and gitee.com was reached
on 2026-10-05. Still unread: the cuvave.com product page, synthanatomy.com,
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
> branch and merges through a PR. Before starting, check the open PRs and
> `git worktree list`, and ask me whether the dev kit and JieLi's updater
> have arrived. Today's task: …

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
