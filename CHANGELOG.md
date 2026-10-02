# Changelog

All notable changes to this project are recorded here, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. The project
has no releases yet; work before this file existed (research phase, bench
session 1, the `USB_KEY` dongle, the 2026-09-08 desk review) is in the git
history.

## [Unreleased]

### Added
- The sequencer host bridge (`engines/include/fm1_seq_host.h`). It is the
  per-block code that plays the sequencer through a sound engine: commands,
  advance, and renders split at each note and lock. `fm1-render` now runs on
  it, and the virtual FM-1 and the firmware are to share it next.
  - Sound, event logs and exported sets are byte-identical to before, across
    810 runs of the renderer and fm1-seq over the oracle scripts, the test
    scripts and Movy's sets.
  - `fm1-render --events N` sizes the event buffer each block's commands and
    playback share, to try a device's size. The default stays 65,536.
  - The summary adds three fields: `seq_dropped` (events that did not fit),
    `seq_max_block_events` (the most in one block) and `seq_splits` (renders
    that start inside a block).
  - engines/seq.md documents the host contract. It covers the order of work
    in a block, how much room a command needs, and which track plays the
    engine by default.
  - A new test tool, `fm1-seq-host-test`, checks the parts of the bridge
    that `fm1-render` does not use yet: typed commands, MIDI realtime input
    and live notes.
- The virtual FM-1's small text is set in Exo 2 (Natanael Gama, SIL OFL
  1.1), bundled unmodified from google/fonts in `sim/web/www/fonts/exo2/`
  with its licence and checked by hash. Before, it used Exo 2 only where
  installed and otherwise the system's sans-serif.
- docs/10 §1.1: reports from other FM-1 owners (issue #2) and what they
  mean for our dongle.
  - czietz's Raspberry Pi Pico `USB_KEY` dongle (an unlisted MicroPython
    gist they linked there) gets their FM-1 into UBOOT mode, about one
    power-on in two.
  - masanaohayashi used it to put their FM-1 into boot mode, back up its
    firmware and write firmware.
  - The dongle clocks the key on D+ (our polarity A), fakes the SOFs with a
    1 kHz square wave, and hands over by moving the cable to the PC.
  - docs/10 now recommends fixed polarity A for the first attempt.
  - It adds a relay-free minimal build that relies on the FM-1's battery.
  - It expects the FM-1 to show up as vendor `WL82`, product `UBOOT1.00`
    [inferred].
  - README, HANDOFF and docs/05 and 07 no longer say the mask-ROM route has
    never worked on an FM-1. It is reported on two other units, and not yet
    shown on this project's.
- docs/14: the verification ladder, the plan for showing 1:1 behaviour once
  the AC79 dev kit and JieLi's USB updater arrive. The rungs are the desktop
  renderer, the browser module, the dev kit and the FM-1, in that order.
  - Bit-exact wherever the arithmetic is the same: sequencer events, screens,
    LEDs and MIDI.
  - The DSP is bit-exact too, in a "ladder" build profile with float
    contraction off and one libm.
  - Named tolerances only for named causes.
  - One golden corpus, run by a heap-free runner on every rung.
  - The FM-1 rung opens only after a byte-identical dump and restore.
- Branding art in `assets/branding/`: a 1280×320 README banner (PNG and
  SVG) and a 240×240 boot screen for the FM-1's display (PNG plus raw
  RGB565 for later firmware use). A seeded script draws everything from
  code: starfield, crescent moon, an orbiting station and an FM waveform.
  The lettering is set in Audiowide (SIL OFL 1.1), committed unmodified with
  its licence, and the colours are the Rosé Pine Moon palette, as on the
  virtual FM-1. The README now opens with the banner.
- The sequencer core, `fm1_seq` (docs/13 stage M1): a C99, heap-free port of
  Movy's sequencer with every planned fix on by default and an exact Movy
  mode for tests. It has 4–8 tracks, each routed to the engine or to USB-MIDI
  on its own channel (18,056 B at 4 tracks, 31,880 B at 8, Capture
  included). `fm1-render`
  plays Movy sets and timed command scripts, with sample-accurate notes and
  parameter locks (engines/seq.md).
- A Movy oracle (docs/13 stage M3): Movy's own unmodified `seq-core`, built
  and run in containers on the LAN, drives 24 golden fixtures and random
  scripts. Our core matches it event for event on all but undo, which is not
  ported yet (tools/movy-oracle/).
- A survey of monome, Ornament & Crime (via PaulStoffregen/O_C_T41 and
  Phazerville) and jhjlim's repositories as FM-1 sources
  (`notes/2026-10-01-monome-oc-jhjlim-survey.md`). O&C's MIT cores
  (quantiser and scales, Tonnetz, Turing and logistic generators, TB-3PO,
  Peaks/Frames/Streams modulation) and Clouds' pitch shifter are worth taking
  as code; Kria lanes, the Ansible arpeggiator, Meadowphysics and Teletype's
  interpreter model are worth reimplementing; jhjlim's repositories have
  nothing to take.
- A virtual FM-1 in the browser (`sim/web/`): every engine and effect,
  compiled to WebAssembly, behind a to-scale FM-1 panel with the firmware's
  own 240 × 240 screen. Play it with the mouse, touch, the computer keyboard
  or a MIDI keyboard; serve `sim/web/www/` from localhost. Its output equals
  the native renderer's byte for byte (Sophie aside, against glibc), and
  `sim/web/build-on-aeon.sh` rebuilds and checks it in one command. On a
  phone the panel keeps playable 25–35 px controls and scrolls sideways in
  its own box; turning the phone to landscape shows it whole. Above
  47,872 Hz, where Macro, Macro Heavy and Six-Op cannot run, it starts with
  Shapes, steps over them and says why. It wears Lunar Modulator's look:
  the Rosé Pine Moon palette on the page and on the firmware's screen,
  Audiowide for the name and the tagline "Intergalactic Modulation
  Station", and an oscilloscope that scales to the sound. The page finds
  its files relative to itself, so `sim/web/www/` publishes as static files
  over https at any path (tested under a sub-path); opened over plain http
  from another machine, Power on says it needs https or localhost. Screenshots of the engines, an effect page, a
  parameter page, the phone layout and a parity figure are in
  `assets/screenshots/`; `build-on-aeon.sh` now needs `FM1_SIM_HOST` and
  remakes them with `--readme-screenshots`.
- `sim/web/emulators.md`: there is no public emulator of the FM-1, its SoC
  or its CPU; what each route to one would take.
- `engines/include/fm1_resampler.h`: a reusable, heap-free resampler
  (polyphase windowed sinc to twice the host rate, then a 123-tap low-pass).
  Equal rates pass through bit for bit; everything above the output's
  Nyquist is at least 93 dB down (engines/resampler.md).
- docs/13: the plan to replicate Movy's sequencer (schwung-movy, MIT) on the
  FM-1, read at Movy's `9190e79`: its exact playback rules, a mapping of
  every core gesture to the FM-1's keys, knobs and screen, a no-heap C99 core
  in about 72 KiB for the full 16-track × 8-clip grid, the tests to port, and
  a staged plan. It lists seven deliberate deviations from Movy, five of them
  fixes for apparent bugs, and questions for the owner and for Movy's author.
- docs/12: feasibility of an Elektron-style sequencer with per-step parameter
  locks on the FM-1. It is feasible (well under 1 % of the CPU, about 19 KB
  for 16 locked 64-step patterns); Movy already does p-locks on the Ableton
  Move but cannot run on the FM-1; MCL (BSD-3) offers a reusable lock store
  and trig conditions; Eloquencer, LMN-3 and the Elektronauts Arduino thread
  are design references at most. Includes playback rules, a control layout
  and a desktop-first plan.
- An evaluation of CHOMPI's open-sourced firmware (Chase Bliss, MIT) as a
  source of FM-1 effects: its ping-pong echo, DJ filter and Warble are worth
  porting; its samplers need an SD card and external RAM; its copy of DaisySP
  carries LGPL code under an MIT label and must not be used
  (`notes/2026-10-01-chompi-evaluation.md`).
- `fm1-render` scripts pitch bends (`--bend`) and parameter changes during a
  render (`--param-at`). Tests bend every pitched engine by +2 and -12
  semitones and back, and turn every parameter of every sound engine through
  its range while a chord sounds.
- Stage A's exit test: reference renderers that drive upstream Plaits and
  Braids code as the modules do, and about 350 tests comparing every engine
  and effect with them (`engines/reference-plaits.md`,
  `engines/reference-braids-fx.md`). At the upstream rates the engines match
  sample for sample or within half a 16-bit step; the differences at the
  FM-1's rate are measured and documented.
- More engines on the platform (docs/11 stage A, `engines/`):
  - **Macro Heavy**, Plaits' other 13 engines (string machine, chords,
    speech, formant, additive, swarm, noise, particle, string, modal and
    three drums), 4 voices; and **Six-Op FM**, Plaits' DX7-style engine with
    its 96 patches, 8 voices.
  - The first effects: **Plate** (Rings' reverb), **Ensemble** and
    **Diffuse** (Plaits), chainable after any engine.
  - A Schwung v2 compatibility shim, with two MIT Schwung modules compiled
    through it unmodified: **Sophie**, a 16-pad FM percussion kit, and
    **PSX Verb**, a PlayStation-style reverb.
  - Renderer options for testing: `--fx` chains, `--fill` (instance memory
    contents) and `--fault` (bad samples injected on the bus).
  - CI runs every engine test on a 32-bit build and under ASan + UBSan.
- `engines/`: the engine platform's first code (docs/11 stage A).
  - A C engine API with no heap: typed parameters, four to a page.
  - Two 12-voice engines built from Mutable Instruments code: **Macro**, from
    Plaits' light engines, and **Shapes**, from Braids' 47 shapes. They run
    at the FM-1's 44,118 Hz with pitch compensation, and the vendored sources
    are unmodified.
  - A bus limiter, and `fm1-render`, a desktop renderer that writes WAVs.
  - 69 tests (tuning, every model and shape, a 12-note chord, release,
    determinism, memory) and a 32-bit CI build.
- `notes/upstream-candidates.md`: a running list of findings worth sending
  upstream, including a Plaits `WavetableEngine` arena overrun that only
  shows in polyphonic ports.
- docs/11: feasibility of a Schwung-style plugin platform on the FM-1. It
  covers which Schwung modules could compile through a shim, why Mutable
  Instruments' MIT code is the best engine source (with the RAM, flash and
  porting steps per engine), a staged loader design modelled on logue, OWL,
  disting NT and CTAG TBD, licence constraints, and a desk-then-bench plan.
- Baud Girl's FM-1+VA, the first third-party FM-1 firmware that users install
  from a browser, is recorded as prior art: what it is, how it installs, and
  what it settles about the stock update path (docs/04,
  `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`).
- A byte-level comparison of Baud Girl's `FM-1_092` package with M-VAVE's
  V15. It is V15's application with 90 small patches and 110 KB of new code
  appended, and the settings (VM) partition is moved to make room. The
  bootloader, OTA loader and configuration are untouched.
- The owner's unit now runs FM-1+VA (identifies as `FM-1_092`); the status
  lines say so.
- Photos of the owner's opened unit and the evidence crops, in
  `photos/2026-09-29/`.
- Observations from photos of the owner's opened unit: SoC lot marking
  `C188612-11B8`, board batch `260708`, the MIDI IN photocoupler, an
  unidentified `SLS316D` part, and the knob layout matched to the control
  names in Baud Girl's manual.

### Changed
- Capture (record-after: turn what you just played into a clip) is on by
  default. The sequencer remembers your last 256 note events, about 128
  notes, and each takes 12 bytes instead of 20 with nothing lost, so the
  whole sequencer fits in 31,880 B at 8 tracks (86 % of its budget) and
  18,056 B at 4. Captures land exactly as before, and as on Movy.
- The `USB_KEY` dongle now keys with D+ as the clock (polarity A) by
  default. That is the polarity czietz's Pico dongle reached UBOOT mode with
  on two FM-1s (docs/10 §1.1).
  - The button held at boot still selects D− (polarity B).
  - Alternating between the two is now a build option.
  - docs/10 §6 and dongle/README.md follow, and a test checks the default.
- The README no longer describes the project as "research, and later
  code".
  - The intro says what you can use today: the virtual FM-1 in a browser,
    with five engines and four effects, and a sequencer core on the
    desktop.
  - The status (2026-10-01) says where things stand: nothing runs on a JieLi
    chip or an FM-1, and nothing has been flashed. The AC79 dev kit and
    JieLi's updater are on order. Other owners report reaching the FM-1's
    mask-ROM mode (issue #2).
  - The Credits now cover:
    - Baud Girl's FM-1+VA findings;
    - czietz's and masanaohayashi's dongle reports and what they taught us;
    - Echomatter;
    - Emilie Gillet's Mutable Instruments code;
    - Charles Vestal's Schwung and PSX Verb, and Matt Estela's Sophie;
    - the Rosé Pine palette and Audiowide.
  - The recommended path, the Movy paragraph (four free knobs, not eight)
    and the repository map's test row are current.
  - CLAUDE.md, AGENTS.md, docs/05, 07 and 08, sim/web/README.md and
    engines/README.md lose matching stale lines: "research and, later, code",
    "nothing else has started", "the mask-ROM path remains undemonstrated",
    and "about 350" reference tests (427).
- The project is now **Lunar Modulator**, tagline **INTERGALACTIC
  MODULATION STATION**: open firmware for the M-VAVE FM-1, formerly "Open
  firmware for the M-VAVE FM-1". The repository becomes
  `ip2k/lunar-modulator` (GitHub redirects `ip2k/mvave-fm1-open-firmware`).
  The short form is "Lunar"; the look is a space theme with a NASA-style
  typeface, using no NASA, M-VAVE or Cuvave marks. README, HANDOFF,
  CLAUDE.md and AGENTS.md carry the new name; CLAUDE.md and AGENTS.md set
  out the naming rules.
- Six-Op FM lists 23 of its 96 patches under names of our own, because the
  browser simulator is going public: the stored names that are trademarks
  or a person's name (`FENDER 1`, `STEINWAY`, `*Hammond 1`, `VANGELIS 1`,
  `CARLOS   2`...) become descriptive ones (`TINE EP 1`, `BIG GRAND`,
  `*Drawbar 1`, `CINEMA 1`, `BAROQUE 2`...). The patches, their order and
  their sound are unchanged. Personal builds can restore the stored names
  with `-DFM1_SIXOP_ORIGINAL_NAMES` (the mapping is in
  engines/plaits-heavy.md). `fm1-render --list` now also prints the names
  of enum parameters' values.
- docs/13 records the owner's choice of 7-bit locks with smoothing, and of
  Capture with 256 packed events, on by default. docs/11 corrects its claim
  that Clouds' spectral mode needs its own FFT.
- The Mutable engines run at their modules' own sample rates, whatever the
  host's: Shapes at 96 kHz, and Macro, Macro Heavy and Six-Op at
  47,872.34 Hz. Each resamples its mix to the host. At the FM-1's 44,118 Hz
  bells and drums now decay as on Braids, Plaits' envelopes keep their
  length, the noise engine's clock and the string model are in tune, and
  the engines match upstream byte for byte or within 1 LSB on all but
  Six-Op (close). The cost is CPU: Shapes 2.5–3×, the Plaits engines
  1.1–1.5× on the desktop. Hosts faster than an engine's native rate are
  refused.
- docs/12 defers to docs/13 where Movy and Elektron differ, and corrects its
  claim that Movy waits 300 ms before locking; docs/06 and docs/12 correct
  Movy's version label (`9190e79` is 299 commits past the v0.34.0 tag).
- docs/06: Movy has gained per-step parameter locks since v0.31.0.
- Licence policy: the project is personal and non-commercial, and GPL code
  may be used. Firmware binaries that contain GPL (or LXR) code and link
  JieLi's closed libraries are for personal builds only, not for sharing
  (CLAUDE.md, docs/11 §7, docs/12 §6).
- The engine API states that instance memory is not zeroed, that engines
  emit finite samples, that `create` may refuse a host, and which calls may
  run concurrently; `fm1_param_clamp` clamps parameters NaN-safely.
- Vendored Mutable Instruments code builds with `-fwrapv`, which defines
  the wrapping integer arithmetic Braids and stmlib rely on.
- docs/06 and docs/08: the FM-1 has four free parameter knobs, not eight, so
  a Movy-style page becomes two pages of four. The roadmap gains the engine
  platform.
- The identity reply's checksum is not reliable on modified firmware:
  FM-1+VA keeps V15's checksum byte, so parse the version and do not gate on
  the checksum (docs/03).
- The stock update gate is now described as a same-version refusal with
  unauthenticated content, and the docs say the stock path installs non-stock
  firmware routinely; it is still not a recovery path (docs/03, 05, 07, 08,
  README, HANDOFF).
- New risk recorded: the OTA loader can rewrite the flash head (`uboot.boot`,
  `isd_config.ini`), so any package must keep that region byte-identical to
  V15 (docs/07).

### Fixed
- The `USB_KEY` dongle's two 2.2 kΩ pull-ups each get their own pin (GP16
  for D+, GP19 for D−; docs/10 §3).
  - On the one pin they shared, switching them off still joined D+ and D−
    through 4.4 kΩ, so D− followed the chip's D+ pull-up.
  - The SOF phase, which waits for D+ high and D− low, would have failed on
    every attempt.
  - The co-simulation modelled the pull-ups as independent and could not
    see this; a test now reproduces it with the shared wiring.
  - The pull-up pins' pad pull-downs are now disabled, so "off" is hi-Z as
    the code says.
  - Found by a review of the docs/10 update, before anyone built the
    dongle.
- docs/10 §1 credited the D−-clock reading to the diagram in kagaimiq's
  `how-to-enter-uboot.md`. In fact that diagram clocks on D+; only the page's
  prose says D−. The `USB_KEY` trap in CLAUDE.md, AGENTS.md, HANDOFF and
  docs/07 now says D+ is the clock, as reported on two FM-1s.
- Shapes crashed on 11 of its 47 shapes when rendered in blocks that were
  not a multiple of 24 samples, and 22 shapes drifted from Braids (bells and
  drums decayed too fast, some shapes glitched). It now always renders Braids
  in its own 24-sample blocks.
- The mix-bus limiter stopped limiting for good after one NaN sample; it
  now treats non-finite samples as silence and clamps extreme ones.
- A NaN parameter value could reach undefined float-to-int conversions in
  Macro and Shapes, or silence Shapes, Test Sine and Test Gain.
- The "unpopulated 3-pin header" (candidate UART) from the 2026-09-08 desk
  review is the battery connector's through-hole leads, and `J14` carries the
  electrolytics' leads. The board has no debug header (docs/01, 07, 09).
- `U2`/`U3` are SOIC-16 `74HC595`, not SOIC-20; `U5` is a QFN, not a SOIC-8.
