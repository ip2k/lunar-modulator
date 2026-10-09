# Hand-off package — Lunar Modulator

**INTERGALACTIC MODULATION STATION.** Lunar Modulator is open firmware for
the M-VAVE FM-1; until 2026-10-01 the project was called "Open firmware for
the M-VAVE FM-1". Naming rules are in `CLAUDE.md` → "What this is".

Written 2026-09-06 at the end of the research session that created this
repository, so a fresh Claude project (or a human) can continue without the
original conversation; last updated 2026-09-29 (Baud Girl's FM-1+VA, the
owner's PCB photos) and 2026-10-01 (engines, sequencer, the new name). Read
this first, then `DEVELOPERS.md` (the README is the product page), then `docs/`.

## Audit remediation — 2026-10-08

Resume on `fix/2026-10-08@firmware-readiness-audit`, in the managed
`full-code-audit` worktree. The full audit is recorded in
[its report](notes/2026-10-07-full-code-audit.md); verified corrections,
test results and remaining firmware prerequisites are in
[the remediation ledger](notes/2026-10-08-audit-remediation.md).
Native sanitizer and four-profile target compile checks pass (164 unique
objects per profile, now including the previously omitted state codecs). This is not a
linked firmware application: simulator arenas and persistence scratch exceed
device SRAM and require a device layout. No hardware traffic in this work.
PR #100 holds this batch. The codec suite passes (105 passed, one corpus skip),
including compressed stream termination and duplicate-field rejection. The committed Wasm has been rebuilt: all 104 parity scenarios pass and
Chromium's LAN page storm reports zero underruns. The preceding CI checkpoint
failed stale-Wasm and Chromium storm checks; verify the rebuilt commit's CI
before merging. The runtime choice
(independent permissive board implementation versus Felucca GPL reuse) is
pending; no board runtime has been implemented. The concrete next milestone
and memory/link/audio gates are in
[the device bring-up plan](notes/2026-10-08-device-bringup-plan.md).
The separate editor improvements branch/PR #99 remains unmerged.

## Latest hardware update — 2026-10-07

The original research summary below is historical. The owner authorized
staged recovery experiments, superseding the prior dump-and-restore
prerequisite. Soft-key UBOOT entry works on FM-1_092; the audited loader ran
in RAM, matching full backups were saved off-host, and an unused 4 KiB
sector was programmed and restored with the entire flash unchanged
[verified: [bench note](notes/2026-10-07-fm1-softkey-bench.md)]. Full-image
restoration and a Lunar application on hardware remain untested. Normal
boot after both the initial dump and the restoration was owner-confirmed. The mobile hardware editor is explicitly deferred
until installable firmware; see [its resume plan](notes/2026-10-07-mobile-advanced-editor.md).

## 1. Where things stand

- **Owner:** Sean (GitHub `ip2k`). Works from a MacBook with Claude Desktop /
  Claude Code; has **one FM-1** on his desk (do not brick it) and has downloaded
  the official updater disk image **`M-UPGRADE-FM1*.dmg` into `~/Downloads`**
  (that updater embeds **V14**, not V15; V15 is only on the CDN, docs/02 §1).
- **This repository** is the research output: nine documents, three tools, one
  research log, plus bench session 1 (`notes/2026-09-06-bench.md`): the unit
  answered the identity query as `FM-1_015`, V15 is unpacked and diffed against
  V14. At that research checkpoint, this project had written nothing to the device. The case has been
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
- **Open firmware runs on FM-1s too** (2026-10-05,
  `notes/2026-10-05-community-repos.md`): Felucca 1.0 (hugelton) and its
  fork SLOOP 2.2 (isod89), bare metal and GPL-3.0-only, install and roll back
  through the stock path; fm1-nes (Keitark) runs an AC79 SDK app on one V14
  unit, written through mask ROM [reported]. Their code maps the board
  (docs/01 §3.1): audio is ALNK0 (I2S) to an external codec, not the internal
  DAC, and the encoders are scanned in the key matrix. Stock V15 also enters
  mask ROM on the SysEx "soft key" `F0 22 24 35 7D F7`, which was subsequently verified on this unit under the revised staged
  policy (see the latest hardware update above).
- **Where the repo lives now:** `~/Developer/mvave-fm1-firmware` on the
  owner's MacBook (the folder keeps its old name), branch `main`, remote
  `ip2k/lunar-modulator` (published 2026-09-06 as
  `ip2k/mvave-fm1-open-firmware` and renamed with the project on
  2026-10-01; GitHub redirects the old URLs). Moved there on
  2026-09-06 from the orphan branch `claude/mvave-fm1-open-firmware-ly2w6u` of
  `ip2k/busybar-dual-timer`, which the cloud session used because its GitHub
  integration could not create repositories. That branch was deleted on
  2026-09-06.
- **Unrelated to the BUSY Bar project.** Do not mix the two.

## 2. The ten facts that matter

1. SoC = **JieLi AC791N** (WL82), two custom **pi32v2** cores at 240 MHz
   (stock: the OS on cpu0, the msfa voices bare-metal on cpu1 [inferred],
   docs/11 §2), 578 KB SRAM, 1 MB flash (probably in-package), XIP from
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
5. **No recovery path proven on this project's unit.**
   - Single flash bank, no debug pads or buttons. The one candidate header
     was the battery connector's leads (2026-09-29).
   - AL-255's verdict: NO-GO for non-stock flashing. This is the gate for
     everything.
   - Our `USB_KEY` dongle, which should open it, is specified and implemented
     (docs/10, `dongle/`), not yet tried.
   - Since 2026-09-16, other owners report that mask-ROM USB boot works on
     *their* FM-1s with czietz's simpler Pico dongle. One of them backed up
     and wrote firmware that way [reported: issue #2, docs/10 §1.1].
     FM-1-transporter (kurogedelic) and fm1-nes report dumps and writes
     through mask ROM too (docs/10 §1.1, docs/04).
6. Most promising recovery: JieLi **`USB_KEY`** (`0x16EF` bit-banged on D+/D−
   at ~50 kHz at power-up, ACK = both lines low 1–2 ms, then SOF clock
   detection) → mask-ROM "UBOOT1.00" mass-storage mode → `jl-uboot-tool`
   with its `wl82loader.bin` (`0x1C02000`) or vendor `isd_download`.
   - The clock is D+: czietz's dongle reached UBOOT mode that way on two
     FM-1s (issue #2).
   - kagaimiq's `usb-key.md` and the diagram in `how-to-enter-uboot.md`
     agree; only that page's prose says D−.
   - Try D+ first (docs/10 §1 item 3).
7. Toolchain = JieLi's closed **Clang/LLVM 4.0.1** fork (`pi32v2` backend),
   Linux build available from `pkgman.jieliapp.com`; AL-255 built C++11 with
   it. No Rust, no GCC/LLVM upstream, no JS runtime.
8. Vendor SDK `fw-AC79_AIoT_SDK` (Gitee, current to V1.2.13; our pin is the
   V1.2.13 libraries at `e30b1ee` since 2026-10-05, never its SPL or loader:
   the key check it carries is inert on the FM-1, gated by
   `tools/jieli/audit_link.py` and `tools/jieli/package_guard.py`, CLAUDE.md
   trap 11) is Apache-2.0 (with GPL parts, docs/12 §6) with a
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
   and with which clock/data polarity and power sequence? Reported yes on two
   other FM-1s (issue #2, docs/10 §1.1):
   - the clock is D+;
   - the FM-1 is switched on while the key runs;
   - the cable is then moved to the PC.

   Not yet tried on this project's unit; try polarity A first.
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
   pushed to the repository now named `ip2k/lunar-modulator`.
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
   engine registry before any loader. **Stage A, 2026-09-30**, in `engines/`:
   the API and desktop renderer; sound engines Macro, Shapes, Macro Heavy and
   Six-Op FM from Mutable code; effects Plate, Ensemble and Diffuse; the
   Schwung v2 shim with Sophie and PSX Verb compiled through it unmodified;
   about 360 engine tests, also run 32-bit and under ASan/UBSan in CI
   (`engines/README.md`). The exit test is met: at the upstream rates the
   engines match upstream Mutable code sample for sample or within 0.5 LSB,
   which found and fixed a Shapes block-size bug (drift and a crash). Left
   before stage B: Shapes' memory (207 KB for 12 voices). Since 2026-10-01
   the Mutable engines run at their native rates (Braids 96 kHz, Plaits
   47,872.34 Hz) through `fm1_resampler.h` and match upstream at 44,118 Hz. Six-Op
   FM's 23 patch names that are trademarks or a person's name are shown
   under names of our own since 2026-10-01, because the browser simulator is
   going public; `-DFM1_SIXOP_ORIGINAL_NAMES` restores them for personal
   builds (`engines/plaits-heavy.md`). Stage B, the pi32v2 benchmark and a
   `-fPIC` test, wants the AC79 dev board from item 4
   (the JL-AC79-DevKit V1.0 with an AC7916; docs/07 §3).
8. **Sequencer (docs/12, docs/13, 2026-10-01).** An Elektron-style
   sequencer with parameter locks is feasible (docs/12). The owner then chose
   Movy as the target: docs/13 is the port plan, pinned to Movy `9190e79`,
   for a no-heap C99 `fm1_seq` core with Movy's semantics, a `compat` mode
   for tests, and seven deliberate deviations. Waiting on the owner: the
   docs/13 §10 questions (deviations, track count, a 72 KiB budget, and
   approval to build Movy's `seq-core` as a test oracle). **Since then
   (2026-10-01):** the owner answered (fix everything; 4–8 routed tracks;
   about half the budget; oracle approved; 7-bit locks), and stages M1 and
   M3 are built: `fm1_seq` (engines/seq.md) matches Movy's own code in 23 of
   24 golden fixtures (undo is not ported) and in thousands of random
   scripts. Capture is on by default with 256 packed 12-byte events (the
   owner's choice; 31,944 B at 8 tracks since stage E1). Open: undo, the note-index
   rebuild cost on pi32v2 (stage B).

## 6. Reference material already gathered (clone these locally)

| Repo | Commit inspected | Why |
| --- | --- | --- |
| `aroum/fm1-custom-fw` | `d08360f` 2026-08-21 | updater analysis, photos, untested flasher |
| `AL-255/FM-1-RE` (`main`) | `95eca84` 2026-08-16 | disassembly, protocol, safety, firmware images V13/V14 |
| `AL-255/FM-1-RE` (`with-custom-firmware`) | `628fcaf` 2026-08-02 | experimental pi32v2 firmware, package builders, Synth_Dexed port |
| `kagaimiq/jielie` | `1657d25` 2024-09-15 | JieLi docs: ISA, USB_KEY, formats |
| `kagaimiq/jl-uboot-tool` | `adb3f18` 2025-03-16 | UBOOT dumper/flasher, `wl82loader.bin` |
| `kagaimiq/jl-misctools` | `0a5b12d` 2025-02-20 | `fwunpack_newfw.py` |
| Gitee `Jieli-Tech/fw-AC79_AIoT_SDK` | `e30b1ee` 2026-06-09 (= V1.2.13 + README) is our pin for the libraries since 2026-10-05; tag V1.1.9 `8eae664` holds the FM-1's SPL; branch `AC791N_OTA_loader` `79eda0c` | vendor SDK: `WL82.h`, `cpu/wl82/tools`, datasheets, the OTA loaders. Gitee is reachable but its SSL is flaky: pin by commit, clone blobless and sparse with `tools/jieli/ac79-sdk-sparse.txt`, and avoid commands that fetch blobs lazily, which hung. The GitHub mirrors are stale (`amitv87` to 2024-07, `jeffreywugz` V1.0.3): do not cite them |
| `hugelton/Felucca` | `727f272` 2026-10-05 (v1.0); `b0dcd53` 2026-10-06 for the vendored engines | bare-metal FM-1 firmware; pin map, update-service design (GPL-3.0-only: facts only, but WHEEL, TRIO and PHASE, vendored behind the GPL switch in `engines/third_party/felucca/`) |
| `charlesvestal/fm1-x0x` | `80b7d40` 2026-10-05 | open FM-1 firmware with a 303, 909 and 808 and TB-3PO; those four vendored behind the GPL switch in `engines/third_party/fm1-x0x/` (GPL-3.0-only; `notes/2026-10-06-fm1-x0x.md`) |
| `isod89/sloop-fm1` | `f2b44c2` 2026-10-04 (v2.2) | Felucca fork; boot guard, loader checks (GPL-3.0-only: facts only) |
| `Keitark/fm1-nes` | `870f305` 2026-10-03 | SDK app on an FM-1; board support, sparse mask-ROM planner (Apache-2.0 root) |
| `kurogedelic/FM-1-transporter` | `a632d92` 2026-10-01 | RP2040 `USB_KEY` + USB host recovery tool (MIT); read through the API |
| `DimaDake/schwung-movy` | `5627d51` 2026-09-05 (v0.31.0) | design reference only |

Web pages that were **blocked** from the research sandbox and still need a
human read: cuvave.com product page, the user manual PDF, synthanatomy.com
articles, fwradar.com history, elektronauts/gearspace/reddit threads,
fm1-editor.com, kagaimiq.github.io (use the repo), madushan.caas.lk blog
post. gitee.com was on that list; it was reached on 2026-10-05 (above).

## 7. Kick-off prompt for the new Claude project

Paste this as the first message of the new project (adjust paths):

> This project, Lunar Modulator, is the open-source firmware effort for the
> M-VAVE FM-1 FM synthesizer. The repository
> (`~/Developer/mvave-fm1-firmware`) contains a completed research phase:
> read `HANDOFF.md`, then `DEVELOPERS.md`, then `docs/01`–`09` and `CLAUDE.md`. Rules: the FM-1 on my desk is the only unit;
> nothing may be flashed or sent to it beyond the read-only identity query
> until recovery is proven (docs/07). Today's tasks: (1) run
> `docs/09-first-session-checklist.md` §1 to extract and analyse the V15
> firmware from `~/Downloads/M-UPGRADE-FM1*.dmg`; (2) §2–§3 USB descriptors and
> identity query with the FM-1 plugged in; (3) write results to
> `notes/<date>-bench.md` and update the open questions in `docs/01` §6 and the
> version table in `docs/02` §1. Keep the [verified]/[reported]/[inferred]
> marks honest.
