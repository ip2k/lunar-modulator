# Changelog

All notable changes to this project are recorded here, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. The project
has no releases yet; work before this file existed (research phase, bench
session 1, the `USB_KEY` dongle, the 2026-09-08 desk review) is in the git
history.

## [Unreleased]

### Added
- Step entry on the virtual FM-1's panel, still behind the lab switch
  (`?lab`; docs/15 stage S4). In SEQ mode the white keys are the bar's 16
  steps and the black keys sequencer controls, so they no longer play the
  sound there.
  - Tap a step to enter the last chord you played (on the keys or at MIDI
    IN, each note at its own velocity), or C4; tap again to clear it.
  - Hold a step for its Step page: velocity, length (1/32 to 16 bars),
    probability (100 % to 10 %) and condition (1:1 to 8:8) on the four
    knobs, and invert on the second page (SELECT). Holding several steps
    edits them all. Hold a step and press a later one to stretch its note
    up to there.
  - SEL is SHIFT outside FX mode. With a step held, SHIFT and the white
    keys add pitches, and a tap of SHIFT alone clears the step (the owner's
    choice: pitches are only added). SHIFT and key 10 turn full velocity on
    or off; SHIFT and PLAY/STOP restart.
  - OP1 and OP3 page through the bars (one empty bar past the pattern
    grows it), or nudge held steps; OCT transposes held steps.
  - The grid marks steps with a probability, condition or invert, the
    held steps and the bar on the keys; the key lights show held steps and
    the length of a held note. On a computer keyboard, `1`–`8` and
    `C V B N M , . /` are the steps and Shift is SHIFT.
  - For developers: `fm1_seq_get_page` reads a run of steps in one pass,
    and `fm1_seq_info_t` names the recording track. 22 new gesture traces
    replay through `fm1-render` byte for byte; keys that play the sound are
    now in the replay's arguments too. A new parity scenario enters a
    two-bar pattern from the panel (25 of 25 pass). 914 screens pass the
    layout check (99 new); the screens with the lab switch off are
    unchanged. The browser module grew from 467 KB to 482 KB.
- A first look at the sequencer on the virtual FM-1's panel, behind a lab
  switch: add `?lab` (or `#lab`) to the page's address. The public page is
  unchanged until patterns can be made and recorded on the panel (docs/15
  stage S3).
  - PLAY/STOP, or the space bar, starts and stops the sequencer in any
    mode, and its light is on while it plays. A one-bar demo pattern is
    loaded at start, so there is something to hear at once.
  - SEQ shows the track: the tempo, PLAY or STOP, four bars of steps with
    the playhead, the four knobs as bars, and the name and value of the
    knob being turned. The white keys light up for the bar's steps and the
    playhead. HOME, FX or GLO go back; the keys still play the sound.
  - The status line shows the tempo and whether the sequencer plays.
  - For developers: `fm1-sim-render --lab --panel FILE` plays panel input,
    and `--log-cmds` now logs the panel's commands with a file of the
    arguments `fm1-render` needs, which replays the session sample for
    sample. A new parity scenario checks the browser module the same way
    (24 of 24 pass). The browser module grew from 459 KB to 465 KB.
- The virtual FM-1 now runs the sequencer inside its app layer, with no
  panel controls yet (docs/15 stage S2; PLAY/STOP and SEQ mode come next).
  - It plays any verb script or `movy1` set exactly as `fm1-render` does,
    natively and in the browser module: the 34 Movy oracle scripts give
    byte-identical sound and event logs, and five new parity scenarios
    (float and list locks, two tracks with swing, Capture while playing and
    while stopped) match in WebAssembly, against musl and against glibc.
  - 8 tracks (the owner's choice), a 256-event buffer and one held
    command: 36,216 B of the sequencer's 36,864 B budget. The RAM figure
    on GLO now counts it.
  - A command that could overflow the event buffer waits a block instead,
    so a burst of stops and starts never loses a note-off.
  - Track 0 plays the sound by default, as in `fm1-render`; a set's own
    routes are kept. Resetting, importing or changing the sound releases
    the sequencer's notes.
  - The browser module grew from 391 KB to 448 KB.
  - `fm1-sim-render` takes `fm1-render`'s sequencer flags (`--cmd`, `--seq`,
    `--tracks`, `--route`, `--events`, `--log-events`) and `--log-cmds`,
    which writes what it applied as a script `fm1-render` can replay.
  - CI's staleness check now covers the sequencer code and the parity
    scripts, so changing either needs a rebuilt module.
- Compile-only stage B (`tools/jieli/compile-check.sh`,
  `notes/2026-10-02-jieli-compile-check.md`). The engines, the sequencer and
  the app layer compile for the FM-1's processor with JieLi's toolchain: 63
  of 63 objects. The note has their sizes and their instance sizes at 32
  bits. No user-facing change.
- **Crush**, a new effect: a bitcrusher and sample-rate reducer. Bits (1 to
  16, smooth between whole numbers), Rate (100 Hz up to every sample, on an
  even pitch scale), Jitter (random hold lengths that repeat exactly each
  time) and Mix on the first page; Tone (a low-pass on the crushed sound) and
  Level on the second. Silence stays silent at any setting. Our own code,
  after DaisySP's Decimator and Bitcrush (Electro-Smith, MIT); documented in
  `engines/README.md` and chapter 6 of the manual, tested in
  `tests/test_engines_crush.py`.
- **Fold**, a new effect: a wavefolder, written for this project. Fold sets
  how hard the sound is driven into the folds, Symmetry makes them uneven
  (adding even harmonics), Shape goes from a bright triangle fold to a softer
  sine fold, and Mix blends it with the dry sound; a second page has Tone (a
  low-pass on the folded sound) and Level. Its anti-aliasing keeps the harsh
  digital fold-back of a plain folder 21–23 dB lower. Silence stays silent
  at any setting, and knob changes glide instead of clicking. Parameters
  and design in `engines/README.md`, and a section in chapter 6 of the
  manual.
- **Echo**, a new effect: a stereo ping-pong delay from 10 ms to 1 second, with
  Feedback, Ping-pong (from two straight delays to echoes that alternate
  left and right), Mix, Tone (damping of the repeats), Wow (a slow,
  tape-like wobble of the delay) and Level (how much of the input enters
  the echo). Beyond about 370 ms the echoes darken, like a bucket-brigade
  delay's, so that one instance stays at 64 KB. Turning Time glides the
  pitch of what is in the line, like a tape echo's speed. Written in this
  repository (MIT); `engines/README.md` documents its parameters, and
  chapter 6 of the manual has a section.
- The virtual FM-1 offers Crush, Fold and Echo in both effect slots and
  Macro's and Macro Heavy's third page; its module is rebuilt and six new
  parity scenarios (`sim/web/test/scenarios.json`) check the new effects and
  the page in the browser's module against the native renderer. A test now
  requires every engine and effect to appear in a scenario. The README's
  screenshots show the third page.
- Macro and Macro Heavy have a third page with Plaits' own envelope and
  low-pass gate controls. **Env Pitch**, **Env Timbre** and **Env Morph**
  set how far the envelope that every note restarts moves the pitch, Timbre
  and Morph (Plaits' three attenuverters; on Chip, Env Timbre sets the
  arpeggio's own fade, and on Speech, Env Pitch the words' intonation).
  **LPG** chooses Gate (the gate follows the key, as before), Ping (each
  note strikes the gate, which closes over Decay even while the key is held)
  or Off (no gate: full brightness, a plain fade after key-up). At their
  defaults both engines sound exactly as before. Six-Op FM is unchanged.
- The arpeggiator core (`engines/midi_fx/`), built and tested on the
  desktop but not yet playable in the simulator or on the FM-1.
  - 22 note orders: up, down, the up-down family, converge and diverge,
    thumb and pinky, MCL's octave-lift orders, crawl, random, shuffle, walk
    and chord. Keys are listed by pitch, as played or reversed.
  - 1–4 octaves, walked as one list as Yarns does, one pass per octave, or a
    random octave per pass.
  - Yarns' 22 rhythm patterns and Euclidean rhythms with length, fill and
    rotate.
  - Rates from 1/32 triplet to whole notes, or one step per sequencer trig.
  - Gate up to 200 %, swing as the sequencer's, ratchets, repeats.
  - Chance per step for playing, ratcheting, chords and octave jumps, and
    velocity and gate spread, all from a seed. A loop length makes a random
    phrase repeat exactly.
  - Latch, the hold pedal, joining a playing chord now or at the next pass,
    and key sync.
  - Every note it starts gets exactly one note-off, even when settings
    change mid-note.
  - It follows Yarns (Emilie Gillet, MIT), MCL (Justin Mammarella, BSD-3)
    and Super Arp (Handcrafted Media, MIT); their notices are in
    `engines/midi_fx/CREDITS.md`.
- docs/16: the design for modulation as a rack of modules inside the
  modulation matrix, so cables can chain module to module (A→B→C→D).
  - Up to 8 modules sit in a rack. Every module output is a source in the
    matrix, and every module parameter and gate input is a destination, so a
    chain is just one 1:1 cable per hop, in 32 slots.
  - The order is worked out from the cables, so a chain adds no delay; a
    feedback loop is allowed and marked, one control tick late.
  - A first wave of 17 modules, all MIT code, ported or our own:
    - envelopes and function generators: Segments (after Mutable
      Instruments' Stages), Function (after Make Noise's Maths), Curves (an
      arbitrary function generator drawn on the 16 white keys), Envelope,
      Bounce;
    - LFOs and randomness: LFO, Chance (sample-and-hold and smooth random),
      Register (a Turing-Machine-style looping shift register);
    - gates: Coin, Divide, Burst;
    - utilities: Calc, Mix, Slew, Compare, Logic, Quantize.
  - About 20 more modules later, after Tides, Marbles, Frames, Streams,
    Grids, Ornament & Crime (Phazerville) applets and Just Friends.
  - Where Mutable Instruments, Ornament & Crime and the disting fit: which
    code is MIT and portable, which is GPL and gets our own version, and
    which disting algorithm each of our modules covers (the disting firmware
    is closed, so ideas only).
  - Budgets: about 12.7 KB of RAM (3.3 % of the free SRAM) and 1–2 % of a
    core for a typical rack, estimated, not measured on the chip.
  - Panel: LFO opens the RACK, EDIT the MATRIX, and ENV patches any output to
    the next knob turned.
  - Stages MG0–MG9, each with its tests, and 18 owner decisions.
- The options note points to docs/16 where it is superseded.
- DEVELOPERS.md's "Research to do" adds Berry, the small MIT scripting
  language docs/11 names beside Lua: could module authors write simple
  modulation modules in it, with a few knobs, as part of the SDK?
- **Roadmap: modules from the community.** Four new lines in the README's
  roadmap and in DEVELOPERS.md's "The roadmap in detail", each with its
  status, dependencies, where it is planned and its effort (not yet
  estimated for the SDK, the builder and the catalogue):
  - develop in the simulator, checked on real hardware (docs/14), as the
    accelerator for everything below (in preparation);
  - a module SDK and friendly guides for writing and porting sound engines,
    modulation sources, MIDI effects and audio effects, after API v2
    (planned; tooling to be researched);
  - a custom firmware builder with a browser installer, for when modules no
    longer fit one image, with its own checksums and manifest on top of the
    update protocol's CRC16, and the stock path back to factory firmware
    (planned, after the installable build);
  - a hosted catalogue of community modules, after the SDK and the builder
    (planned).
- DEVELOPERS.md's "Research to do": tooling for module authors (PlatformIO
  or whatever embedded-audio developers use most today), quality and
  functionality gates for new modules, static registry against loader,
  where a custom build is made, the web flasher's verification, licence
  metadata, and hosting the catalogue.
- Modulation primitives in `engines/mod/` (`fm1_mp.h`), for the modulation
  runtime docs/16 is designing. They are heap-free C99, use no libm, and are
  not yet wired into an engine or the simulator.
  - An LFO with sine, triangle, saw up and down, square with pulse width,
    smooth random, sample-and-hold and random walk. Its rate is a ratio
    (Hz, or BPM/60 × cycles per beat), and it has retrigger, one-shot,
    half-cycle and drift-free sync.
  - Its random shapes draw once per accumulator wrap, so none is missed
    however large the block. Schwung's S&H misses wraps here: at 30 Hz in
    128-frame blocks its rule catches 99 of 174.
  - A multistage envelope after Mutable Instruments' Peaks: ADSR, AD, AD
    and ADR loops, and linear, exponential or quartic curves.
  - A slew limiter (linear or exponential, separate rise and fall),
    sample-and-hold and track-and-hold, a Turing-machine register, and a
    clock divider and multiplier on integer ticks.
  - Every random source is seeded per instance. Results are bit-identical
    whatever the block size.
  - A desktop test tool, `fm1-mod`, and `tests/test_engines_mod.py` (87
    tests).
- docs/15: the plan for the sequencer in the virtual FM-1 (docs/13 stage M4
  in the browser), in stages S1–S10, each with its tests and exit numbers.
  - S1 moves `fm1-render`'s per-block sequencer hosting into a shared,
    heap-free C99 bridge, with no change in behaviour.
  - S2 hosts the sequencer in the app with no UI, and proves it plays every
    oracle script exactly as `fm1-render` does, natively and in WebAssembly.
  - S3 is the first playable stage: PLAY/STOP and a SEQ grid. Later stages
    add step entry, record and Capture, tracks, engine API v2 (a silent stage,
    then SMOOTH), parameter locks, Session, and sets saved in the browser.
  - Outside SEQ mode every printed button keeps its meaning; in SEQ mode the
    black keys carry the sequencer's roles.
  - Memory: at most 36,216 B of the 36,864 B half budget at 8 tracks, and
    22,392 B at 4.
  - 24 owner decisions, each with a proposed default and the stage it
    blocks. docs/13 §9 points to it.
- notes/2026-10-01-arp-modulation-effects-options.md: open-source options
  for an arpeggiator, configurable LFOs and envelopes, a modulation matrix
  and eurorack-type effects such as sample-and-hold, with every licence
  checked at a pinned commit.
  - Arpeggiator: our own C core, `fm1_arp`, after Yarns' `ClockArpeggiator`,
    with MCL's extra orders and Super Arp's seeded modifiers. It would be the
    first `FM1_KIND_MIDI_FX`, so ARP and SEQ can run together.
  - Modulation: 2 global LFOs, 2 envelopes and a 16-slot host-side matrix
    first, then per-note sources once engine API v2 exists. Modulation is an
    offset from a base value, which locks and knobs set.
  - Effects first: CRUSH, S&H FILTER, FOLD and CHORUS; ECHO and REPEAT once
    the engines get tempo.
  - Every pick is MIT or BSD; GPL sources serve as design references only.
    It lists twelve owner decisions. It also answers the cores question: the
    stock firmware uses both cores, and nothing from this project runs on
    the device yet.
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
- The user manual (`manual/`, `tools/manual/`): chapters for welcome and
  safety, getting started, a panel tour with a measured drawing of the panel,
  playing, the sound engines, effects, the sequencer, MIDI, settings,
  updating and recovery, troubleshooting, specifications and credits, a
  glossary and a generated index of controls. Every function says where it
  runs today: in the browser simulator, in the desktop tools, or planned for
  the device. Parameter tables, list values, the sequencer's figures and its
  script verbs are generated from the code at build time. Published on GitHub
  Pages at `/manual/` beside the simulator, with an A5 PDF, by a new
  workflow (`.github/workflows/pages.yml`) that also builds and checks it on
  pull requests. Every chapter is written in full, with the firmware's own
  screen shown from the simulator, and the published simulator links to it.
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
- **Engine API v2: every parameter has a fixed id and says what it allows.**
  Each parameter of every sound engine and effect now carries an id that
  never changes, so a sequencer lock (and later a modulation route or a
  preset) keeps its target even when a parameter list is reordered or
  extended. Each also says whether it can be locked, whether it is read only
  when a note starts, whether it should glide when it changes, and whether
  it can be modulated, plus a unit and a short name for the coming
  modulation matrix. What you hear changes in one case only: a sequencer
  lane on a parameter whose change cuts every sounding note (Macro's and
  Macro Heavy's Model, Shapes' Shape) is now refused instead of applied,
  and so is one on Sophie's Pad, which only picks the pad her other knobs
  edit; `fm1-render` counts the refusals. PSX Verb's Model, which empties
  the reverb, is marked the same for when effects can be locked. Six-Op
  FM's Patch and Sophie's Model stay lockable: they change the next notes
  only. Lane names in saved sets stay as they were
  (`synth:Timbre`). Every other render is byte-identical, over 1,458 renders
  before and after. Details in `engines/README.md`, "Parameters", and
  `engines/seq.md`; the ids are pinned in `tests/fixtures/param-uids.json`.
  Not in the browser simulator yet.
- **DEVELOPERS.md is reorganized** so it reads in order: a welcome, a
  linked table of contents and a short callout of the one rule; then
  getting started (build, test and play in five minutes, where to go next,
  all the commands), how Lunar Modulator works (its layers first), the
  hardware, where development stands (the status, the roadmap in detail,
  the path to an installable build, research to do), contributing (the one
  rule, conventions, licences, pull requests, credits) and reference (key
  facts, formerly "The short version"; the recommended path; the documents
  by topic). The roadmap's wide table became one entry per line, grouped,
  and the path to an installable build gained a table of its milestones.
  Nothing was dropped.
- The README shows the virtual FM-1 screenshot right under the
  introduction, before the preview notice, instead of further down.
- **The roadmap, rewritten from the 2026-10-01 studies.**
  - The README's roadmap gives each line a status and says where it stands.
    The arpeggiator (our own, after Yarns, with MCL's note orders, in the
    first MIDI-effect slot so it plays alongside the sequencer) and the
    LFOs, envelopes and 16-slot modulation matrix are planned with their
    design chosen. Sample-and-hold is now researched: random and
    Turing-style sources first, then a bitcrusher, a random-stepped filter,
    a wavefolder and a chorus, and an echo and a beat-repeat once effects
    follow the tempo.
  - The README's install section says Lunar will bring its own installer
    and update service, and that the first preview goes first to owners who
    can already restore their FM-1.
  - DEVELOPERS.md's "The roadmap in detail" gives each line its
    dependencies, where it is planned and a rough effort, and links the
    arpeggiator, modulation and effects options note.
  - A new DEVELOPERS.md section, "The path to an installable build", lays
    out milestones I0–I15 from today to a release, with the owner's bench
    work, the earliest safe preview, and two needs no plan covered: Lunar's
    own update service (the public SDK has no USB-MIDI class and the FM-1's
    update loader is M-VAVE's own) and its own installer.
  - DEVELOPERS.md's hardware notes add what is known about MIDI out on the
    jack (probably needs a hardware change) and over USB (stock already
    exposes a sending port; the SDK has no USB-MIDI class), Bluetooth's code
    size by AL-255's two indexes (55–115 KB), and a list of bench checks
    that write nothing.
- docs/14 adds step 5b to the dev kit's first week: a second-core probe
  (§5.1) that measures how cpu1 starts, per-core counters, the FPU on each
  core, one core against two, cross-core ordering, three ways to keep audio
  on cpu1 and flash-write stalls. It decides how Lunar splits its work
  across the cores. §4.3 gains a Cores row and §6 five risks; the USB CDC
  question is settled (the SDK has `cdc.c`).
- **The README is now the product page.** It covers what Lunar Modulator
  does, how to try it in a browser, a roadmap, and why it is not installable
  on an FM-1 yet.
- **Everything technical moves to a new `DEVELOPERS.md`:**
  - where development stands, "The short version" and the path to the
    device;
  - how the software works, including the reference-render comparison;
  - the hardware, with what is known about MIDI out, BLE MIDI and the second
    core;
  - the roadmap in detail, building and testing, and the conventions.
- The two files link to each other, and each says what it is for.
- "Repository history" is gone, and the repository map sits at the bottom of
  the README.
- The product page calls it "Sequencer", following docs/13 §8. Its credit
  now reads "Sequencer design and logic after Movy by megadake (MIT)".
- The credits add the Exo 2 typeface.
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
  The short form is "Lunar"; the look is a space theme set in Audiowide,
  using no NASA, M-VAVE or Cuvave marks. README, HANDOFF,
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
- Macro Heavy: a parameter set to NaN now falls back to its default, as
  the engine API says (`fm1_param_clamp`), instead of to its minimum.
- **The second core is not idle.** The stock firmware renders its msfa
  voices on cpu1, outside the OS, and runs the OS, the UI and the effects
  on cpu0. The routine at V13 file `0x86AD6` polls `0x01C16EC0` and calls
  the voice render, its only caller [verified: V13 disassembly]; that it
  runs on cpu1 is inferred from the `cpu1_run_flag` and AL-255's symbol
  names. `CPU_CORE_NUM 1` is the SDK's mode with the OS on one core, not
  one core used. AL-255's docs, which this project followed, read cpu1 as
  unused because their addresses assume `app.bin` runs from `0x02000000`;
  it appears to run from `0x02000120`. Corrected in docs/01, 05, 06, 08
  and 11, DEVELOPERS.md, the README roadmap, HANDOFF, `engines/plaits-heavy.md`,
  `sim/web/README.md`, `sim/web/emulators.md` and a comment in
  `sim/web/www/worklet.js`.
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
