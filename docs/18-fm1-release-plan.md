# 18 — From the dev-kit soak to 1.0 on the FM-1

The plan for getting Lunar Modulator from "passes the release rule on the
AC79 dev kit" (2026-10-29) to "verified on the owner's FM-1 and released as
installable firmware". Written 2026-10-29 from a read-only inventory of
main, Codex's unmerged FM-1 branch and the bench notes. Confidence marks as
elsewhere. Every hardware step still follows docs/07 §4 and needs a fresh
owner approval; this document approves nothing.

## 1. Where we are

- **The unit runs stock V15 and identifies as `FM-1_015`** [verified:
  docs/17]. Recovery is proven for an intact boot area `0x0`–`0x4000`
  (owner, D1); the transporter writes only `[0x4000, 0x93000)`.
- **The release rule passes on the dev kit** with 8 voices at 320 MHz:
  30.4 min, zero underruns, producer mean 66%, consumer 82.8%, worst block
  explained, latency 11.61 ms [verified: `notes/2026-10-29-devkit-soak30.md`].
  The kit plays through its internal DAC; the FM-1 uses ALNK0 to an
  external codec (trap 10) at 360 MHz.
- **Main has no FM-1 image** [verified]: no board layer, no `.fwsc`
  builder, no RAM runner, no installer. It has the offline guards
  (`tools/jieli/package_guard.py`, `audit_link.py`), the panel emitter and
  fm1-nes's `boot_info` bridge, unlinked.
- **Codex's branch `feature/2026-10-11@installable-firmware`** (`cccd21cc`,
  2026-10-18, 1,238 commits ahead of main, about 31k lines under
  `firmware/`) has the FM-1 work [verified: `git diff --stat`]:
  - a native app (`firmware/native/`: `project_boot`, `project_engines`,
    `project_seq`, settings journal in flash, TLSF heap, engine adapter);
  - SPI1 display transport and panel probe (`firmware/display/`);
  - TRS MIDI in (`midi_uart_stream.c`, Arduino MIDI library, MIT);
  - RAM recovery, loader backup and reset tools, an SDK install tool and
    an installer service (`tools/fm1_*`, `tools/installer_service/`,
    `tools/jieli/trusted_fwsc_package.py`);
  - GPL code from dinghy (`firmware/third_party/dinghy/src/ota.c`).
- **The browser installer pieces are on PR #161's branch, not main**
  [verified: `gh pr view 162/164`]: the private installer build service
  (#162) and an admission-gated WebMIDI OTA controller ported from
  Felucca's GPL-3.0 protocol module (#164). The controller refuses every
  package until an audited verifier admits it; no install action is wired
  into `installer.html` yet.
- **Its images ran on this FM-1 and failed the owner's acceptance**
  [verified: that branch's `HANDOFF.md`]: audio starved (315.6 produced
  blocks/s, 373.8 underruns/s; 689.34 needed), and the last stage-7 install
  on 2026-10-15 stopped at program address `0x94600` with power lost,
  leaving the unit unbootable until 2026-10-26. The likely cause is that an
  in-place rewrite of a single-bank app is not atomic [inferred: forensics
  note `21d529ce` on that branch]. That `0x94600` is an
  absolute address inside the app region of the 092 layout the unit ran
  then, not an overrun of V15's `0x93000` [verified:
  `notes/2026-11-08-0x94600-forensics.md`].
- **The performance gap that failed that acceptance is what the dev-kit
  work closed** (cap8, trunc12, the 48-tap 51/47 resampler, the buffered
  queue) [inferred: different images; FM-1 timing at 360 MHz is scaled,
  not measured].
- **The soak image fits V15's app slot with the size profile.** `app.bin`
  is 597,916 B plain and 570,588 B with `--size-profile`, against V15's
  581,564 B slot (`0x4120` to `cfg_tool.bin` at `0x920DC`), leaving 10,976 B
  [verified: aeon build, `notes/2026-11-08-fit-size.md`]. The 16 KB margin
  target is 5,588 B short. Every SRAM-resident function is unchanged and the
  host replay hashes match; target timing of the rebuilt cold units is
  untested. The FM-1 board layer will add to the image.

### 1.1 Wave 1 results (2026-11-08)

| Lane | PR | Result |
| --- | --- | --- |
| Size profile | #178 merged | fits with 10,976 B spare (above) |
| Fit tables | #175 merged | dropping Terrain and Wavetable Macro models gives +38,656 B; Drums off frees 23.7 KB heap |
| `0x94600` forensics | #172 merged | settled (§4) |
| ALNK0 audio | #176 merged | the DAC needs no control bus; a clean-room MIT driver for ALNK0, host-tested, not run on a chip. U9 has 10 leads; its part number is unread |
| Board layer (M3) and M5 image | #179 | display, keys, LEDs, ADC, TRS MIDI in; an SDK-free M5 RAM test-pattern image, built, not run |
| Fail-open (M7) | #180 | boot counter and supervisor; on the kit, three bad boots in a row entered mask-ROM UBOOT by themselves. Power-cut tests need a person at the bench |
| Bench target pinning | #177 | every tool that opens a `4c4a:8057` device requires `--usb-path` and a role, so the kit and the FM-1 cannot be confused |
| Web recovery | #173 | Web Serial page for the Pico 2 W transporter, D2 enforced in code, 40 offline tests |
| Web flasher | #174 | install and roll-back panel on the admission-gated controller; still admits nothing |

### 1.2 Wave 2 results (2026-11-08 to 2026-11-09)

| Lane | PR | Result |
| --- | --- | --- |
| `.fwsc` builder (M12) | #182 merged | builds the package from the user's own V15 and passes `package_guard.py`; web admission done offline (`notes/2026-11-08-fwsc-builder.md`) |
| FM-1 app image (M10, M11) | #183 merged | builds for pi32v2 and fits V15's slot with keys, OCT, KNOB1/2, MASTER and TRS in wired; no USB device stack yet (`notes/2026-11-08-fm1-app-image.md`) |
| RAM runner (M4) | #184 merged | done on the kit: two runs loaded, read back, ran and reset to the app (`notes/2026-11-08-ram-runner-devkit.md`) |
| Fail-open hardening (M7) | #185 merged | image hash, required heartbeat slots, link-time placement asserts, crash-loop escalation; the FM-1 app build carries them; power cuts still pending (`notes/2026-11-08-failopen-hardening.md`) |
| M5 host tool | #186 merged | `tools/fm1-transporter/fm1t_m5.py` and the runbook [docs/19](19-m5-bench-runbook.md); adversarially reviewed: writes held to the approved range and image, one attempt per run directory; tested against a fake transporter only |

## 2. Milestones

Approval labels: **bench yes** is a fresh owner approval for one run;
**§4 approval** is a docs/07 §4 experiment approval naming the image, the
ranges and the recovery plan.

| # | Milestone | Exit criterion | Risk to the unit | Approval | Status |
| --- | --- | --- | --- | --- | --- |
| M0 | Recovery route | two identical dumps, verified write, boot (docs/17) | — | — | **done** 2026-10-26 |
| M1 | Release rule on the kit | 30 min, no underrun, means ≤ 85%, worst block explained | — | — | **done** 2026-10-29 |
| M2 | Size and SRAM budget gate | a tool that reads a pi32v2 image and map and checks it against V15's app slot and the FM-1's free SRAM; the soak image's real figure recorded | none | none | **done** 2026-11-08 (#171, #178) |
| M3 | FM-1 board layer on main | display, keys, LEDs, MIDI in, ALNK0 audio and codec init, clocks and power left as the SPL sets them, `boot_info` bridge; built for pi32v2, `audit_link.py` and M2 pass. Sourced from Codex's branch where its licence allows, clean-room where not (decision 2) | none | none (licence: decision 1) | code in #176, #179 |
| M4 | Bounded RAM runner on the kit | upload and jump only; erase, program, `0xFC12`, `0xA1`, syscmd 33–36/48, `5A AA A5` and the soft key refused in code; a RAM test image reports over UART | none (kit) | bench yes | **done on the kit** 2026-11-08: two runs, image loaded, read back, run and reset to the app (`notes/2026-11-08-ram-runner-devkit.md`) |
| M5 | First Lunar code on the FM-1 since recovery, from RAM | build id and test pattern on the TFT, LEDs blink; a power cycle returns V15; a read-only dump before and after has the same hash | RAM only | §4 approval | **approved 2026-11-09** (§3); host tool `tools/fm1-transporter/fm1t_m5.py` ready and tested offline; run pending, with the owner at the bench ([docs/19](19-m5-bench-runbook.md)) |
| M6 | Audio path on the FM-1 from RAM | ALNK0 at about 44,118 Hz, one reduced engine plays cleanly, per-block timing at 360 MHz reported. The full image does not fit in SRAM [inferred] | RAM only | §4 approval | image built (`m6-plan-2`); kit run passed 2026-11-09 (40,960 blocks, 0 late/missed, about 44.1 kHz by the host clock [verified], 24 MHz oscillator [inferred], ROM clock not 360 MHz; review: images unchanged, note corrected); FM-1 run **not approved**, request in `notes/2026-11-09-m6-image.md` §5; needs M5 first |
| M7 | Fail-open boot and watchdog, power-cut tested on the kit | a boot-looping build reaches update mode by itself; a power cut at every update stage recovers (docs/07 §4 rules 4–5) | none (kit) | bench yes per run | kit-tested in #180, hardened after review (notes/2026-11-08-failopen-hardening.md); power cuts pending (owner script there) |
| M8 | First flash install on the FM-1 | backups first; `package_guard.py` passes; the head is unchanged; writes stay inside `[0x4000, 0x93000)`; Lunar boots; fail-open tested; V15 restored and read back | **flash app region** | §4 approval | blocked on M5–M7 |
| M9 | Release rule on the FM-1 | 8 voices at 360 MHz for ≥ 30 min: no underrun, means ≤ 85%, worst block explained, pre-DAC hashes equal to the host replay, the stereo out captured clean; 12 voices measured as the stretch goal | flash app | bench yes | blocked on M8 |
| M10 | Controls and display | 27 keys, 14 buttons, 7 encoders, MASTER, LEDs, battery; screens hash-equal to R0 | flash app | bench yes | code now; the first app image (2026-11-08) builds and fits with the keys, OCT, KNOB1/2 and MASTER wired, the rest fenced (`notes/2026-11-08-fm1-app-image.md`); 2026-11-09: all 27 keys, 14 buttons, 7 encoders, bend, panic, LEDs and the battery class are wired behind `LUNAR_FM1_FULL_UI` through a drain barrier and match the unpipelined app on the host (screens, LEDs, PCM); the full-UI image is 39,136 B over V15's slot, so the default stays fenced and the fit is an owner decision; the FM-1 image draws no app screen yet (`TODO(display)`), so the display half is not started (`notes/2026-11-09-controls.md`) |
| M11 | MIDI | TRS in and USB-MIDI (`4C4A:C755`, product `FM-1`); one hour under MIDI from both with no underrun | flash app | bench yes | code now; TRS in (`notes/2026-11-08-fm1-app-image.md`); USB-MIDI device behind `--usb-midi on` (off by default): descriptors host-tested against V15, GPL 0/1 builds pass `audit_link.py` and `fm1_budget.py`; MIDI in only, nothing sent to the host; adversarially reviewed (one OUT packet a read, SET_CONFIGURATION checks); not run on any device (`notes/2026-11-09-usb-midi.md`, #190) |
| M12 | Install and roll back through the stock path | the `.fwsc` builder makes the package from the user's own V15 and passes `package_guard.py`; V15 → Lunar → V15; an interrupted transfer and a power cut recover without the dongle; the head never changes | flash app via the stock path | §4 approval per experiment, each interruption case on the kit first | builder and web admission done offline 2026-11-08 (`notes/2026-11-08-fwsc-builder.md`); every hardware case pending |
| M12w | Web flasher and web recovery tool | the flasher installs and rolls back through WebMIDI and the stock OTA path (`native-ota-controller.js`, GPL-3.0 module, licence and source named on the page); the recovery page drives the Pico 2 W transporter over Web Serial (CDC `2e8a:000a`), because WebUSB cannot claim the ROM's mass-storage interface (`notes/2026-10-14-web-recovery-interface-constraint.md` on Codex's branch); offline tests against fake ports first, then each hardware run as in M8/M12 | flash app via the stock path; recovery via docs/17 | §4 approval per hardware run | UI and offline tests now; hardware after M8 |
| M13 | Release 1.0 | a shareable build with `FM1_GPL_MODS=0`; no vendor binary redistributed; CHANGELOG `[Unreleased]` moved to `[1.0.0]`, the GitHub release body is that section; README status updated | none | owner publication gate | last |

### 2.1 What a shared 1.0 image may contain

A shared image links JieLi's libraries, so it is built with
`FM1_GPL_MODS=0` (CLAUDE.md, "The GPL switch"):

- nothing from dinghy, Felucca or SLOOP (GPL-3.0-only), including their
  audio, USB, OTA and recovery code; Codex's `firmware/third_party/dinghy/`
  stays out of it;
- the three Felucca engines in `engines/third_party/felucca/` drop out;
- `uac_audio*.h` stays excluded;
- the modified pipeline `system.a` used on the kit (SHA-256 `792c7599…`)
  needs its origin and redistribution rights written down before M13.

GPL modules keep running in personal test builds.

## 3. Owner decisions

Asked 2026-10-29; answers recorded here when they come.

1. **Basis for the FM-1 board layer:** harvest from Codex's branch (MIT
   parts only, reviewed), or clean-room. Wave 1 took the MIT-only harvest
   plus clean-room code (#179); open for the owner to reverse.
2. **What 1.0 contains** if M2 confirms the image overflows the slot. Not
   needed while the size profile fits; revisit when the board layer is
   linked in.
3. **SDK application (L1) or bare metal (L2)** for 1.0.
4. **Whether to restore `FM-1_092`**, or drop "092 → Lunar → V15" from
   the install criteria.
5. **M5 on the FM-1 (docs/07 §4 approval). Approved 2026-11-09,** choice
   recorded verbatim: "Yes, M5 as planned". Scope:
   - RAM only, one session;
   - image `m5.bin`, 4,160 B, SHA-256
     `a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4`,
     build id `m5-plan-1`;
   - SRAM written only `[0x01C02000, 0x01C03040)`;
   - route: the docs/17 Pico 2 W transporter, UF2 unchanged, with the
     patched host tool of `notes/2026-11-08-ram-runner-devkit.md` §4.2
     (`tools/fm1-transporter/fm1t_m5.py`);
   - sequence and recovery as in that note's §5, written out as operator
     steps in [docs/19](19-m5-bench-runbook.md).

   This also settles §4's doubt about using docs/17's route to enter the ROM
   for this one Lunar RAM run. The run happens later, with the owner at the
   bench. Any other image, a second run or any flash write needs a new yes.
6. **M6 on the FM-1 (docs/07 §4 approval). Approved 2026-11-10, to run after
   M5,** choice recorded verbatim: "Yes, after M5 (Recommended)". Scope:
   - RAM only, one session, after the M5 session;
   - image `m6.bin`, 9,796 B, SHA-256
     `37334c76760831e3137ec1c9d45943c3ef383f91a8fe632bfd78db07cbde3647`,
     build id `m6-plan-2`; image bytes `[0x01C02000, 0x01C04644)`, nothing
     used at or above `0x01C06C70`, inside the accepted `0x01C07E00` bound;
   - accepted with it: timing at the ROM's clock (360 MHz timing moves to the
     first image that sets the clock) and the -18 dBFS test arpeggio until
     power-off (notes/2026-11-09-m6-image.md §5–6);
   - route: docs/17's transporter with a host tool extended from
     `fm1t_m5.py` (note §5 sketch; not written yet, and reviewed before use);
     recovery a power cycle, then docs/17.

   Any other image, a second run or any flash write needs a new yes.
7. **USB-MIDI default (#190). Answered 2026-11-10:** "Off until measured
   (Recommended)". `--usb-midi` stays off until a hardware run measures heap
   use (with controls it leaves +128 B over the minimum).
8. **The M10 soft locks. Answered 2026-11-10:** "Must lift before 1.0". The
   full-UI FM-1 build must let engines, effect order and Macro's model change
   while audio plays, as R0 does; this is added M10 work.
9. **How the full UI fits V15's slot** (39,136 B over). Open: the owner asked
   whether Terrain and Wavetable fail on the FM-1. They do not fail as
   engines; today's pipelined build runs Macro's model 0 only, and the two
   share a 50,688 B wave table (notes/2026-11-08-fit-tables.md). With item 8,
   dropping them would remove playable models.

## 4. Doubts to settle

- ~~The 10-15 install's last program address `0x94600` against the
  transporter's `[0x4000, 0x93000)`.~~ Settled 2026-11-08: the install
  targeted the FM-1+VA layout (app to `0xD9000`); V15's boundary does not
  apply to it. M8 must take its write range from the identity-read layout
  and protect VM `0x93000`+ on V15 (`notes/2026-11-08-0x94600-forensics.md`).
- The soak note's 5,332 B of heap after DAC open against 96–1,568 B in
  `pipeline-image-sizes.json`: possibly different images.
- The RAM load-and-jump route works on WL82's ROM on the dev kit (two runs,
  2026-11-08, `notes/2026-11-08-ram-runner-devkit.md`); on the FM-1 the
  ROM has still only loaded JieLi's own loader. `FB08` does not answer for
  an image that never returns [inferred], so the transporter's `jump` will
  report `ERR jump` for M5.
- The DAC (U9, 10 leads) is unidentified. No known code writes a codec
  register, so ALNK0 alone starts audio [inferred, strong: #176]; I2S
  against left-justified is unsettled until U9 is read.
- ~~Using docs/17's route to enter the ROM for Lunar RAM runs is beyond the
  approval for the V15 shim and needs a fresh yes.~~ Given for the M5 run
  only, 2026-11-09 (§3 item 5).
