# Changelog

All notable changes to this project are recorded here, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. The project
has no releases yet; work before this file existed (research phase, bench
session 1, the `USB_KEY` dongle, the 2026-09-08 desk review) is in the git
history.

## [Unreleased]

### Added
- **FM6, a new sound engine: six-operator FM that plays DX7 voices.** It
  runs msfa, the FM core Google published for Android and the core the
  FM-1's own firmware runs, and plays all 32 algorithms with six operators,
  their envelopes and keyboard scaling, feedback, the LFO (vibrato and
  tremolo) and the pitch envelope. Twelve notes at once.
  - **32 voices of its own:** electric pianos, clav, harpsichord, koto,
    marimba, vibes, bells, organs, brass, flute, clarinet, strings, pads,
    basses, leads and a small drum kit, written for this project.
  - **Your own DX7 voices:** single voices and 32-voice banks load from
    SysEx files into 32 user slots (on the desktop for now:
    `fm1-render --engine dx7 --sysex bank.syx`). Bad checksums, out-of-range
    values and other SysEx in the file are handled, not trusted.
  - **Four macros** shape any voice while it plays: Brightness (how hard
    the modulators drive, ±24 dB), Env Time (every envelope up to 8 times
    faster or slower), Feedback and Volume. All four glide, and each note
    can take its own setting from a sequencer lock or a modulation route.
  - **Beyond msfa itself:** tremolo (msfa ignores the voice's AM settings)
    and the feedback loops of algorithms 4 and 6, which msfa, and with it
    probably the stock FM-1, plays without feedback; the voice's transpose
    is applied too.
  - The same output, bit for bit, from the Mac, 32- and 64-bit Linux and the
    browser (three new parity scenarios, 72 of 72 pass; the browser module
    grew from 786 KB to 813 KB); compiles for the FM-1's processor with
    JieLi's toolchain. About 15 KB of memory, plus
    29 KB of tables shared by every FM6 sound; twelve voices cost about a
    third of Macro's twelve on the desktop.
  - Checked against an independent port of the same core, Felucca's
    `fm6_core.c` (Apache-2.0; a test tool here, in no build): every
    algorithm within 0.3 dB. Documented in engines/msfa.md and chapter 5 of
    the manual.
- **Drums, a new sound engine:** a sixteen-pad drum kit after the classic
  analogue drum machines, on MIDI notes 36 to 51 like Sophie.
  - Two kits: Deep, with a deep kick that booms for over a second, round
    toms and analogue-style hi-hats; and Punch, with a short kick that
    sweeps down, a crisp snare and ring-modulated hi-hats. Both have two
    snares, a clap, a rim shot, six toms, a crash and a ride, and any pad
    can play a cowbell instead.
  - Each pad has its own Tune, Decay, Level, Tone, Snap, Sweep, Drive and
    sound (Model); Pad chooses which pad the knobs edit, as on Sophie. The
    knobs start in the middle, which is the pad as the kit sets it up. Kit,
    Accent (how much velocity matters) and Volume are the whole kit's.
  - A closed or pedal hi-hat cuts the open one short. Up to twelve hits
    ring at once, and a pad struck again while it rings is struck again,
    as a drum is; a thirteenth takes over the quietest hit, so a cymbal
    still ringing loud keeps going.
  - The kicks, toms, snares and hi-hats are Plaits' drum models by Emilie
    Gillet; the rim shot, clap, cowbell and cymbals are new, after
    published studies of the analogue circuits.
  - It plays the same, sample for sample, in the browser as on the
    desktop, and fits in about 7 KB.
- **The virtual FM-1's keys play any drum kit's pads:** with Sophie or
  Drums as the current sound, the sixteen white keys play the sixteen pads
  at any octave. Step recording, and adding a pitch to a held step with
  SHIFT, enter the pad a white key plays (they entered a pitch the kit
  ignores, so the steps played nothing). For developers: an engine says it
  is a kit with two new fields in the engine API, `pad_first_note` and
  `pad_count`.
- **JieLi SDK upgraded to the V1.2.13 libraries, with safeguards** (owner's
  decision, 2026-10-05; notes/2026-10-05-softkey-efuse.md §4). The pin is now
  Gitee `release/AC79NN_SDK_V1.2.0` at `e30b1ee` (= tag V1.2.13), by commit.
  The SDK's key check is left intact, not stubbed, because it is inert on the
  FM-1 (nothing registers a licence blob, and the app never touches eFuse).
  The safeguards instead:
  - a post-link audit, `tools/jieli/audit_link.py` (modelled on fm1-nes's
    `audit_boot.py`): it fails the build if any live key-check or eFuse code
    survives — no `mkey_check`/`sdk_mkey_lock`/`sdk_mkey_lock_v2_cfun`/
    `key_check_demo`/`sdk_chip_key_verify_v2`, no `0x0200012E` stub, no writes
    to `0x01C80108-0x01C80110`, IRQ 123 reserved, no SDK key-blob bytes, no
    eFuse-SFR access, no `request_irq(123)` in our sources — while leaving
    the dormant `sdk_meky_check` in place. On a linked image it attributes
    each hit to its function, so the SDK's own `mkey_dummy_func` mailbox
    store passes and anything of ours fails, and it checks that the
    `late_initcall` group is exactly `[sdk_meky_check]`. It reads ELF itself
    (standard library only) and is covered by `tests/test_audit_link.py`;
  - a packaging gate, `tools/jieli/package_guard.py`: never ship any V1.2.x
    `uboot.boot`, `uboot_no_ota.boot`, `wl82loader.bin` or `ota.bin` — only
    V1.1.9's SPL is the FM-1's. It asserts the stock SPL hash `730e54f0…`
    and byte-identical `isd_config.ini`/`ota.bin`/`cfg`, and refuses any
    other SPL or loader in the tree (`tests/test_package_guard.py`);
  - the `boot_info` bridge from fm1-nes (Apache-2.0, in
    `firmware/third_party/fm1-nes/` with its licence and `UPSTREAM.md`),
    which copies the stock SPL's 6 hand-off words and zeroes words 6-22 so
    V1.2.1+'s wider `boot_info_init` reads defined zero, not stale RAM.
    Tested on the desktop (`tests/test_boot_compat.py`) and compiled for
    pi32v2, where it calls nothing but the SDK's own initializer; it has not
    run on a chip.

  `tools/jieli/compile-check.sh` and `tools/jieli/ac79-sdk-sparse.txt` now
  fetch and use V1.2.13 from Gitee (retrying its flaky SSL); the compile-only
  check was re-run against it on the build host (twice, the second time with
  the bridge and our sources in the audit). The V1.2.13 libc++ ships its
  own `math.h`, so the V1.1.9 run's one fix is no longer needed. No user-facing
  change. No vendor binary is in the repo.
- notes/2026-10-05-softkey-efuse.md: a desk-only investigation of the stock
  "soft key" SysEx and of the JieLi SDK's key and eFuse checks. The soft key
  only writes a marker to RAM and resets the chip into its ROM loader (no
  flash write), and its code path in FM-1_092 is identical to stock V15. The
  SDK's key check is present in every release and every stock image but does
  nothing on the FM-1, and nothing on the device writes eFuses; it recommends
  upgrading to SDK V1.2.13's libraries with safeguards. A separate draft,
  notes/2026-10-05-softkey-readonly-test-plan.md, is a read-only dump plan
  for the owner to review; nothing has been sent to any device.
- **Comb, an effect of its own.** The comb filter that was Filter's seventh
  Type is now its own effect, with the same knobs (Cutoff, Resonance, Drive,
  Mode, Morph, Mix, Level) and the same sound, sample for sample. Filter
  keeps six types and no longer carries the comb's 18 KB delay lines: it
  takes 656 bytes, so filters cost almost nothing on the RAM meter. Filter's
  Formant moved from Type 6 to 5. A Filter set to Comb maps onto Comb
  setting for setting (they share their parameter ids).
- **Frequencies and times turn in ratios.** Filter's and Comb's Cutoff,
  Echo's Time, Comp's and the Limiter's Release, Tilt's Pivot, Master Sat's
  Clean Lo and Clean Hi, the Isolator's crossovers, EQ's three frequencies,
  Gate's Hold, Decay, Key HP and Key LP and Sophie's Ring Time now move by the same musical step wherever they
  are: a click of the knob is about a semitone on a cutoff, their bars show
  the knob's position, their values show more decimals at the low end, and
  a sequencer lock steps through them evenly in ratio. Modulation moves them
  in octaves: a ±50 % LFO on Cutoff swings it about five octaves either way
  instead of pinning it at the ends, and NOTE at +100 % into Cutoff makes
  the filter follow the keyboard exactly, one octave per octave.
- **Engine API v3, for developers** (engines/README.md, "Engine API v3";
  `FM1_ENGINE_API_VERSION` is 3, so an engine built out of tree is
  rebuilt). Parameter flags widen to 16 bits with the new `FM1_PARAM_LOG`;
  `FM1_UNIT_DB` marks levels and gains in dB (Comp, Drive and the Limiter,
  and EQ, Tilt, Master Sat and Gate). Effects get an optional extension,
  `fm1_fx_ext_t` through `render_ext`: a key (side-chain) input, the tempo
  and beat position, and the sequencer's Start, Stop and beats at their
  exact frames, the same at any block size; both hosts pass it through
  `fm1_fx_render` (`fm1_fx_host.h`), and the key stays empty until the
  side-chain stage. Test Ext, a new test effect, marks what it hears with
  clicks. `fm1-render --tempo BPM` sets the effects' tempo without a
  sequencer; `--list` shows each engine's `fx_wants`. Every other engine and
  effect renders byte for byte as before. New tests: fm1-fx-ext-test and
  tests/test_engine_api_v3.py (the extension with a real sequencer at block
  sizes 1, 7, 13 and 64, the LOG law, NOTE keytracking, the app's knobs and
  bars), tests/test_engines_comb.py (the split, pinned against main), and
  two parity scenarios for the browser module.

- **Room, Hall, Gate and Plate's Freeze on the virtual FM-1:** the effect
  slots now offer twenty effects (ALGORITHM steps through Plate, Ensemble,
  Diffuse, PSX Verb, Crush, Fold, Drive, Echo, Filter, Comp, Limiter,
  DJ Filter, Tilt, Master Sat, Isolator, EQ, Room, Hall, Gate and Test
  Gain), and Plate gains a second page with Freeze.
  - Every new knob and switch is turned mid-note in the browser's parity
    scenarios: Room's and Hall's scenarios now move their knobs, and
    Hall's Freeze, while notes ring; a new scenario freezes Plate in front
    of Room; and another flips Plate's and Hall's Freeze every 4.4 ms.
  - A value on screen keeps one decimal when it is a small fraction of a
    wide range, so the Gate's 0.5 ms Attack reads 0.5, not 0.
  - 64 of 64 parity scenarios pass, identical to musl and to render.js
    (six of them turn effects' switches every 4.4 ms); 2,325 screens pass
    the layout check (136 new, ten of them the new effects' pages with a
    modulation cable on each parameter). The browser module grew from
    738 KB to 761 KB. The three new effects join the engine-SMOOTH
    driver's split and repeated-write checks. The modulation runtime's
    shared pool of parameter records grows from 160 to 180, so ten Gates
    and four Six-Ops can all take cables (the runtime is 832 bytes larger,
    23,200 in all). Chapter 6 of the manual has sections for Room and Gate and
    Plate's Freeze; chapters 12 and 13 list their memory and credits.
- **Gate**, a new effect: a noise gate that can also duck. Threshold,
  Attack, Hold, Decay and Range (down to silence) set how it opens and
  closes; Return keeps it from chattering on a sound that hovers at the
  threshold; Duck turns it over, so a loud key pulls the signal down to
  Range instead. Key HP and Key LP filter only what the gate listens to (so
  a kick's spill does not open a snare's gate), and Listen lets you hear
  that; Lockout stops a ringing drum re-opening it; Lookahead (0–5 ms)
  opens it just before the transient arrives, so attacks come through
  whole; Link picks how a stereo key is heard. Mode, Listen, Link and
  Lookahead change without a click, so the sequencer may lock them and
  modulation may move them. Range 0 and an open gate pass the sound bit
  for bit. The controls follow Drawmer's DS201 and DS301 gate manuals (as
  inspiration; our own code, MIT). For now it listens to its own input;
  keying it from another sound or from the sequencer is the side-chain
  stage still to come, and its hooks are in place. About 2 KB of memory at
  44.1 kHz, no maths library, and the same output, bit for bit, from the
  Mac, 32- and 64-bit Linux builds and WebAssembly. Documented in
  engines/README.md ("Gate"). Two parity scenarios are added.
- **Freeze** on the Plate reverb, a switch on its second page: it holds the
  tail at the level it had and ignores new input, while Mix still blends in
  what you play. It switches over 5 ms, so it does not click and can be
  locked on a step or driven by modulation. Decay and Damping wait until you
  release it. The hold is not endless: the highs fade over seconds and the
  body over minutes, and a quiet tail runs out sooner (about 25 s at
  −39 dBFS, nearly 3 minutes at −19 dBFS); engines/mi-fx.md says why and
  what would fix it. With Freeze off, Plate sounds exactly as before.
- **Hall**, a new effect: a stereo hall reverb written for this project, on
  an eight-line feedback delay network. Decay sets the reverb time from
  0.2 s to 20 s (2 s by default), Size the size of the hall, Damping how
  much faster the highs die away, and Mix the balance with the dry sound.
  A second page has Pre-delay (up to 150 ms), Diffusion (separate early
  reflections or a smooth wash), Mod (a slow, chorus-like movement that
  keeps long tails from ringing metallic) and Freeze, which holds the tail
  for minutes (it fades by about a decibel a minute) and lets nothing new
  in; a third has Width (stereo to mono)
  and Low Cut (keeps the bass out of the reverb). Freeze switches without
  a click, so it is ready for sequencer locks and modulation once those
  reach the effects. It uses 49 KB of memory,
  three quarters of Plate's, and about 2.6 times Plate's processing on a
  desktop. Every setting is stable, the tail always dies away to true
  silence when Freeze is off, and it sounds the same in the browser as on
  the desktop. Parameters and design in `engines/README.md`, a section in
  chapter 6 of the manual, tests in `tests/test_engines_hall.py` and
  `engines/test/hall_selftest.cc`, and a parity scenario for the virtual
  FM-1 that turns its knobs and Freeze while notes ring.
- **Room**, a new reverb effect: the reverb of Mutable Instruments Clouds with
  the diffuser Clouds runs before it, a smaller, denser room than Plate in
  40 KB (Plate takes 64 KB). Mix, Decay, Damping and Diffusion on the first
  page; Blur (smears the attack before it enters the room) and Width on the
  second. Decay reaches from a short room (under a second) to tails of 15 s
  and more. Every knob glides and can be modulated, Mix 0 passes the sound
  through untouched, and the output is the same at any block size and,
  with no libm and no fused multiply-adds, the same bits in the browser.
  For developers: the four Clouds files are vendored unmodified,
  `build/fm1-ref-room` renders the upstream classes for 60 reference tests
  (within half an LSB at 32 kHz and at 44,118 Hz), and `build/fm1-room-test`
  checks the glide, recovery, host rates and the libm-free maths. A parity
  scenario turns every knob while a chord rings through Room. Once a tail
  has gone, Room sweeps its diffuser's memory clean, so a silent Room does
  no subnormal arithmetic (left alone, all 2,048 of the diffuser's cells
  held a subnormal for good).
- **Modulation on the virtual FM-1's panel (docs/16 MG3), behind the lab
  switch:** add `?lab` (or `#lab`) to the page's address. The public page is
  unchanged: there ENV, LFO and EDIT still say they are not in the
  simulator yet.
  - Two LFOs, two envelopes and a random source (Chance) are ready from the
    start, and every note starts both envelopes again, even one played
    while another is held, whether it comes from the keys, MIDI in or the
    sequencer (a new source, RTRG, the note gate retriggered at each new
    note, feeds them; KEY in its place keeps them legato). Nothing moves the
    sound until you connect something.
  - LFO or ENV shows those modules a page at a time: their settings on the
    four knobs, SELECT through every module and page, ALGORITHM to put
    another of the sixteen kinds of module in a place (the second stage's
    Function to Filter too), or empty it. Changing a module back brings its
    connections back. SEL picks a module up so SELECT can move it.
  - The Filter module's Cutoff reads in Hz on its page (4.53 Hz in the
    middle of the knob, 0.05 Hz to 410 Hz), while the knob turns as before.
  - Modules are named by their kind and their place in the rack: LFO1,
    LFO2, ENV3, ENV4 and CHN5 to begin with. Chance, Calc, Compare and Coin
    are CHN, CLC, CMP and COI, so no two names are alike.
  - Hold LFO or ENV and turn a knob on the sound's page, an effect's page or
    a module's page: the LFO or envelope you looked at last now moves that
    setting, and the turn sets by how much. Turning again changes the same
    connection. With several sounds this reaches the sound you are on
    (SHIFT + PRESETS) and its two inserts, as well as the master effects.
  - EDIT lists all 32 connections. KNOB1 picks what moves, KNOB2 what is
    moved (from a list that starts at the sound you are on; ALGORITHM jumps
    between each sound, its inserts, the master effects, the host and each
    module), KNOB3 how much and KNOB4 an offset; ALGORITHM
    turns to a second page with a second source that scales the first, a
    curve, the polarity and on or off. SEL shows the chain a connection is
    part of.
  - A setting that something moves shows a gold diamond by its name, the
    range it moves over in gold on its bar, and where it is now in red.
  - For developers: `fm1-sim-render --lab --log-cmds` also logs the
    modulation as `fm1-render --mod` lines, so a session on the panel
    replays byte for byte; `--mod FILE` plays a modulation script, as
    `fm1-render --mod` does. `fm1-render --mod` now runs with the sound-unit
    flags too: `snd2:`, `snd2.fx1:` and the like name the other sound units
    and their inserts (the runtime's unit codes, `fm1_mod.h`), and
    `fm1_seq_host_dispatch_slots_ticks` runs the modulation over several
    sound units. The runtime is 23,200 bytes, and the lab's RAM meter counts
    it. Four new parity scenarios check the browser module with modulation
    running, two of them over several sounds (58 of 58 pass with the
    master-bus effects' own), and the layout check now covers 2,189
    screens. The browser module grew from 599 KB to about 738 KB.
- **DJ Filter, Tilt, Master Sat, Isolator and EQ on the virtual FM-1:**
  the master-bus effects of the 2026-10-02 effects note. The effect slots
  now offer seventeen effects (ALGORITHM steps through Plate, Ensemble,
  Diffuse, PSX Verb, Crush, Fold, Drive, Echo, Filter, Comp, Limiter,
  DJ Filter, Tilt, Master Sat, Isolator, EQ and Test Gain). Put them in
  the second slot, the end of the chain; with multi-sound (behind `?lab`)
  the two slots are the master bus of every sound.
  - Each has a parity scenario that turns its knobs, and its switch where
    it has one, while notes play; two more turn DJ Filter's Slope, Tilt's
    Curve, Master Sat's Shape and Isolator's Kill every 4.4 ms.
  - For developers: `tests/test_engines_fx_switches.py` turns those four
    switches every third block on a sine and on sharp onsets. 54 of 54
    parity scenarios pass, identical to musl and to render.js; 1,458
    screens pass the layout check (137 new). The browser module grew from
    573 KB to 599 KB. Each effect is under 400 bytes an instance, on
    64-bit and 32-bit builds alike. `tests/test_engines_fx_hostile.py`
    puts all five through the same hostile checks of the engine contracts
    (any block size and memory fill, seconds of garbage parameters and
    input, the pass-through settings bit for bit, every glide landing at
    8–384 kHz); it found Isolator's crossover glide stopping short of its
    target, fixed before release.
- **DJ Filter**, a new effect for the end of the chain (or the master bus,
  once there is one): one knob, Sweep, low-passes as it turns left of
  centre, from 20 kHz down to 60 Hz, and high-passes as it turns right, from
  20 Hz up to 8 kHz. Around the centre (Dead Zone, 0.05 by default) the
  sound passes untouched, bit for bit, and the filter costs nothing.
  Resonance peaks in the middle of the sweep and never at its ends; Slope
  chooses 12 or 24 dB per octave and crossfades between them; Mix blends in
  the dry sound; Range shortens the sweep for gentler moves. Sweeps are
  smooth whether turned by hand, locked or modulated, and crossing from one
  side to the other neither clicks nor thumps. Every parameter can be locked
  and modulated. For developers: `src/fx_djfilter.cc`, a trapezoidal SVF
  written here with libm-free maths (the same bits from Apple clang, GCC and
  Emscripten), 224 bytes an instance, and `fm1-djfilter-test`.
- **Tilt**, an effect that turns the whole sound darker or brighter with
  one knob, up to 9 dB either way about a pivot frequency you choose
  (200 Hz to 5 kHz). Two curves: *Shelf* turns quickly around the pivot,
  *Slope* more gently and evenly. A Level control makes up the volume.
  Flat, it passes the sound through untouched, bit for bit, so it can sit
  on the last slot as a master tone control. Every control, the curve
  included, glides when turned, locked or modulated, so sweeps have no
  clicks or zipper noise (engines/README.md, "Tilt"; manual chapter 6).
- **Master Sat**, gentle saturation for the master bus (effect id `sat`, after
  §6 of the 2026-10-02 effects note). Quiet passages pass unchanged; only
  the band between **Clean Lo** (20–300 Hz) and **Clean Hi** (1–20 kHz) is
  saturated, so the bass stays tight and the highs clear. **Drive** (0–18 dB)
  sets where the curve starts to bend without making the sound louder;
  **Glue** turns the mix down by up to 6 dB when the curve works hard, like a
  bus compressor; **Shape** picks a Smooth or a Dense curve (it crossfades,
  so it can be locked and modulated); **Asymmetry** adds even harmonics;
  **Level** trims the result. **Mix** starts at 0, an exact bypass, as every
  master effect does: turn it up to hear the effect. The curves use the
  coefficients of Airwindows PurestSaturation and TapeHack2 (Chris Johnson,
  MIT); the code is this project's own, with no maths library, and computes
  the same bits on the desktop and in the browser.
- **Isolator**, a three-band DJ kill EQ effect (engines/README.md, "Isolator").
  Low, Mid and High knobs cut each band to nothing at 0, leave it alone at
  three quarters of the way and boost it by 6 dB at the top; a Kill switch
  silences any combination of bands at once, and returns them to their
  knobs when released. The crossovers (80–400 Hz and 1.5–5 kHz, 250 Hz and
  2.5 kHz by default) are steep Linkwitz-Riley ones, so a kill is deep (the
  lows −64 dB at 40 Hz, the highs −80 dB at 15 kHz) and the bands add back
  up flat. Every control, Kill included, can be locked and modulated, and
  changes without clicks. At its defaults it passes the sound through
  untouched, bit for bit.
- **EQ**, a three-band parametric equaliser effect: a low shelf, a bell and a
  high shelf, each with its own frequency, gain (±15 dB) and Q on a page of
  its own, and an output Level. Its curves are those of the classic studio
  "cookbook" equaliser, measured to within 0.001 dB. At 0 dB a band does
  nothing at all, and with every gain at 0 dB the sound passes through bit
  for bit. Every knob is open to sequencer locks and modulation: frequency,
  gain and Q glide over a few milliseconds and the filters are built to be
  swept, so turning or modulating a band does not click. It computes the
  same samples in the browser as in a native build (engines/README.md,
  "EQ").
- Per-note sound changes, the groundwork for per-voice modulation: Macro,
  Macro Heavy, Six-Op FM and Shapes can now move one playing note's sound
  (its timbre, level, envelope times and the like, and its pitch) without
  touching the other notes. A note's changes last through its release and
  are cleared when the key is played again or its voice is reused. Nothing
  sounds different until something uses it; the envelopes and LFOs that
  will drive it come with the modulation work (docs/16, stage MG9). Sophie
  and the effects do not take per-note changes. For developers: the engine
  API's `set_param_note` and `POLY` flag, and `fm1-render
  --note-param-at` / `--note-pitch-at` (engines/README.md, "Per-note
  offsets").
- **Modulation, second stage (docs/16 MG2): thirteen more modules** for the
  modulation rack, in the engine and `fm1-render`; not yet playable in the
  simulator or on the FM-1.
  - **Function**: a rise-and-fall function generator in the spirit of
    Maths and Contour 1: one-shot, attack-release, cycling, gated cycling
    and a shaped slew, with end-of-rise and end-of-cycle triggers, hold and
    tempo sync.
  - **Bounce**: Mutable Instruments Peaks' bouncing ball, exactly as Peaks
    computes it, with a trigger at each bounce.
  - **Burst**: Peaks' ratchets, trigger delays and random repeats, exactly
    as Peaks makes them, plus accelerating ratchets and repeats that follow
    a clock.
  - **Register**: a looping random shift register after the Turing
    Machine, with a gate that flips the next bit and a pitch output in
    whole notes.
  - **Coin** (a random gate switch after Branches), **Divide** (two clock
    dividers, multipliers, Euclidean rhythms or chance gates, with swing
    and delay), **Slew** (six outputs fanned out in time), **Quantize**
    (Braids' 49 scales and ragas, exactly as Braids quantises), **Compare**
    (threshold, window and trend gates, placed to the sample), **Logic**
    (gates and flip-flops), **Calc** (arithmetic on two signals) and
    **Mix** (four inputs with gains).
  - **Filter**: a resonant low-, band- and high-pass filter for
    modulation signals. Turned up, a note or any gate makes it ring, a
    decaying wobble at its cutoff that can move any knob.
  - Every module repeats exactly for a given seed, at any block size, and
    the Peaks and Braids parts were checked output for output against the
    original code. Documented in `engines/mod/kinds.md`.
- **Modulation, first stage (docs/16 MG1):** the engine and `fm1-render` can
  now modulate sounds; not yet playable in the simulator or on the FM-1.
  - A rack of up to 8 modulation modules inside a matrix of 32 cables. Any
    module output can move a sound, effect or host parameter, or another
    module's knob, input or gate, so modules chain: a chain of four arrives
    in the same 0.7 ms step as a single cable, whatever order the rack is
    in. Feedback loops are allowed and run one step late.
  - Three modules: **LFO** (eight shapes, free, trig, hold, one-shot and
    half-cycle modes, and sync to the sequencer's tempo), **Envelope** (ADSR
    or AD after Mutable Instruments' Peaks, with loops; with no cable it
    follows the keys) and **Chance** (sample-and-hold, track-and-hold,
    smooth random and drift).
  - Sources from playing: velocity, note, a random value per note, the key
    gate and note trigger, and the sequencer's clock, beats, bars, start,
    transport and each track's gates and velocities.
  - A gate cable set below 100 % lets each trigger through with that
    chance, the same way every time for a given seed. Turning a cable's
    depth, plugging and unplugging a gate cable while a note is held, or
    replacing the module at its other end, never leaves an envelope stuck
    open.
  - Pitch (added to the pitch bend) and a tremolo gain can be modulated too.
  - A sequencer lock moves a parameter's centre while modulation keeps
    swinging round it, and Stop puts the centre back.
  - Every render without an active cable is byte for byte what it was, and
    the output is the same at any block size with cables active.
  - `fm1-render --mod FILE`, `--log-mod` and `--list-mod` (one sound unit:
    not with the multi-sound flags yet; `--param-at`, `--fx-param-at` and
    `--bend` move the bases), documented in
    `engines/mod/README.md`, tested in `tests/test_engines_mod_runtime.py`
    and `fm1-mod-core-test`. The JieLi compile check covers the modulation
    code too.
- notes/2026-10-05-community-repos.md: what Lunar learns from JieLi's current
  AC79 SDK on Gitee and from three FM-1 projects, Felucca (with its recovery
  tool FM-1-transporter), its fork SLOOP, and fm1-nes. Other open firmware
  already runs on FM-1s, installed and rolled back through the stock update
  path. Two independent code bases map the board: audio leaves over I2S to an
  external codec rather than the internal DAC, the encoders are read through
  the key matrix, and the display, matrix, MIDI and flash pins are named. A
  running app can enter the chip's ROM loader without a dongle (including a
  stock SysEx command that this project must not send before the dump-and-
  restore gate). It lists about 30 corrections to our docs and ten owner
  decisions.
- Parameter locks on the virtual FM-1's panel, still behind the lab switch
  (`?lab`; docs/15 stage S8).
  - Hold a step and turn SELECT past its two Step pages: the next pages
    are the sound's own, and a knob there locks its parameter on that
    step. The locked value shows in the parameter's own units, in gold,
    over the dim value it has on the other steps, and a dot after the bar
    marks a parameter with a lane (a track has eight). A step with locks
    gets a gold dot in the grid.
  - A lock goes to the sound the track plays, even when another sound is
    the one the keys play.
  - Parameters that cannot be locked (Macro's Model, Shapes' Shape) say
    so, and a ninth lane says "8 lanes used".
  - SHIFT and a knob clears that step's lock. OP5 (D#4) pressed while
    steps are held clears their locks; held, a knob clears that
    parameter's lane on the track.
  - Recording while playing, a knob writes its moves into the step that
    plays, and you hear them.
  - A knob on a parameter that has a lane now turns in 128 steps, the
    same steps a lock uses, and the lane's value between locks follows it
    at once. So what the knob shows is what plays, also after a stop.
  - For developers: `fm1_seq_value7` (the inverse of a lock's value) and
    the lane label writer join the shared bridge; a lane label writes a
    space in a parameter's name as `_` (`synth:Env_Pitch`), since a label
    is one word. Ten new gesture traces replay through `fm1-render` byte
    for byte, six of them taken from Movy's own automation tests; a new
    parity scenario plays locks from the panel; 1,321 screens pass the
    layout check (55 new), and the screens with the lab switch off are
    unchanged.
- Tracks on the virtual FM-1's panel, still behind the lab switch (`?lab`;
  docs/15 stage S6). There are eight tracks, all playing Sound 1 to begin
  with.
  - Hold SEQ and press white key 1 to 8 to work on that track, from any
    mode (you are back where you were when you let go of SEQ). In SEQ
    mode MONO and POLY (C#5, D#5) step to the previous and next track.
    The screen names the track, and says so when choosing it emptied what
    Capture held. The track's sound becomes the one the keys play.
  - OP6 (F#4) mutes and unmutes the track; hold it and white keys 1 to 8
    mute and unmute tracks 1 to 8, lit while they play. The tracks show
    at the top of the screen, a muted one as an outline. There is no solo
    (the owner's choice).
  - Hold SHIFT to see its shortcuts. SHIFT and white key 2 open the Track
    page (which sound the track plays, or MIDI out on a channel, its mute,
    and its lanes on a second page; moving a playing track elsewhere lets
    go of the note it holds, rather than leaving it sounding on the old
    sound), 3 the Clip page (speed from 1/8X to
    4X, length, transpose, quantize), 5, 7 or 9 the Set page (tempo,
    swing, the quantize new clips get, metronome). SELECT also walks on
    to these pages from the sound's.
  - A metronome click: SHIFT and white key 6, or the Set page, turn it on
    and off. SHIFT and white key 16 step the clip's quantize through 0,
    the default and 100 %.
  - For developers: the click is a new part of the shared sequencer
    bridge, so `fm1-render` plays it too, the same to the bit
    (`seq_clicks` in its summary). The app's event buffer grows from 256
    to 272 events, which holds the worst burst measured; the public
    page's RAM figure counts the 192 bytes, so a few chains read 1K more.
    Ten new gesture traces replay through `fm1-render` byte for byte, two
    new parity scenarios play tracks from the panel and the click (46 of
    46 pass, with multi-sound's), and 1,266 screens pass the layout check
    (69 new); the screens with the lab switch off are unchanged. With
    multi-sound, the browser module grew from 525 KB to 548 KB.
- Recording and Capture on the virtual FM-1's panel, still behind the lab
  switch (`?lab`; docs/15 stage S5). What you play on the keys (outside
  SEQ mode) or at MIDI IN now reaches the sequencer as well as the sound.
  - REC records on track 1: stopped, after a bar's count-in; playing, at
    once over a pattern, or from the next bar on an empty track. Press it
    again to stop. Its light is on while recording, blinks fast during the
    count-in, and blinks slowly while there is something to capture.
  - Step record: in SEQ mode, stopped, hold REC and play the white keys.
    Each note goes onto the step under the red frame, which moves on when
    you let go; keys held together make a chord. OP3 leaves a rest, or
    ties held keys into the next step; OP1 steps back. SHIFT and a white
    key move the frame there. An empty track grows to what you play.
    Notes at MIDI IN go in too.
  - Capture: SHIFT and REC keep what you just played. Playing, it lands
    where you heard it. Stopped, it reads your tempo, starts playing and
    shows the tempos it found: SELECT tries another, any other press keeps
    it. Over a pattern it is fitted to the set's tempo. A note captured
    just before the loop's end grows the pattern by a bar, as in Movy (the
    owner's choice).
  - For developers: recorded and captured notes are logged as `non` and
    `nof` lines, so every gesture trace that plays keys or MIDI IN replays
    through `fm1-render` byte for byte (11 new traces). Two new parity
    scenarios record and capture from the panel (41 of 41 pass). 1,055
    screens pass the layout check (39 new); the screens with the lab
    switch off are unchanged. The browser module grew from 516 KB to
    525 KB.
- Several sounds at once on the virtual FM-1, behind the lab switch
  (`?lab`; docs/15 §3.16, the owner's decision of 2026-10-02).
  - Up to four sounds play together, each with its own two insert effects
    and its own level into the mix; the two effect slots you had are now
    the master effects, after the sounds are mixed. Each sequencer track
    plays the sound its route names.
  - Hold SEL (SHIFT) and turn PRESETS to choose which sound you play and
    edit: the keys, MIDI IN, HOME, PRESETS and ALGORITHM then act on it,
    and the title shows it (`S2 Shapes`). PRESETS on Sounds 2–4 also
    offers Empty, to remove that sound. The page's Sound menu follows.
  - FX mode shows the chain of the sound you are on: its two inserts, a
    Mix page where KNOB1–4 set the four sounds' levels, then the two
    master effects. SEL and SELECT swap the two inserts, as they swap the
    master effects.
  - A RAM meter in the bottom bar shows how much of the FM-1's free memory
    the whole setup would take, and refuses any sound or effect that would
    not fit, with a popup saying by how much, whether you choose it on the
    panel or in the page's menus; turning PRESETS or ALGORITHM skips past
    such choices. What plays in the simulator fits the device.
  - Without the lab switch nothing changes: one sound and two effects,
    sounding exactly as before.
  - For developers: `fm1_app_unit_*` routes tracks to sound units (for
    stage S6), the route going in as a logged, replayable command;
    `fm1-render` takes `--sound`, `--insert`, `--level`, `--sound-note`,
    `--sound-param-at`, `--level-at` and `--slots`; three
    new parity scenarios play two and four sounds with inserts and the
    panel gestures; 142 new screens pass the layout check (its insert
    sweep runs every effect).
- notes/2026-10-02-filters-dynamics-options.md: research on classic filter
  designs, compressors, limiters, overdrives and saturators, and how they fit
  the effect slots, the voices and the modulation matrix. Most of the filter
  work already exists (effects pack 2), so it recommends integration first:
  split Comb out of Filter (its delay lines cost 18 KB per instance), add a
  logarithmic knob law so a Cutoff sweep or keytracking moves in octaves, then
  per-voice filters inside Macro and Shapes. It also flags that FM-1 projects
  elsewhere assume the chip has no floating-point unit while our compiler
  emits FPU code, which the dev kit has to settle, and lists 16 owner
  decisions.
- **Drive, Filter, Comp and Limiter on the virtual FM-1:** the effect
  slots now offer twelve effects (ALGORITHM steps through Plate,
  Ensemble, Diffuse, PSX Verb, Crush, Fold, Drive, Echo, Filter, Comp,
  Limiter and Test Gain).
  - Every effect's knobs are now checked turning mid-note in the browser,
    not only at their starting values: each new effect's parity scenarios
    turn its knobs and switches while notes play, and four new scenarios do
    the same for the older effects.
  - For developers: `fm1-render --fx-param-at T:K:NAME=VALUE` turns a
    parameter of the K-th effect during a render, as `--param-at` does for
    the sound; the app's native harness takes it too, and the scenarios'
    `fx_param_at` drives the browser module the same way. A test keeps
    every effect turned in some scenario.
  - 39 of 39 parity scenarios pass, identical to musl and to render.js
    (two of them turn every switch of the new effects every 4.4 ms);
    1,016 screens pass the layout check (102 new). The browser module grew
    from 482 KB to 516 KB.
- **Filter**, a new effect: seven classic filter types in one, every knob a
  modulation target. Type picks SVF (low-pass, band-pass, high-pass, notch),
  Ladder (24, 18, 12 or 6 dB per octave), Diode (a 303-style diode ladder),
  Sallen-Key (bright and aggressive, after the Korg-35 filter of the later
  MS-20), SK Mixed (a gritty mixed-input Sallen-Key, after the
  Steiner-Parker Synthacon's filter, with low-pass, band-pass and
  high-pass inputs), Comb (tuned by Cutoff, positive or negative, peaks or
  notches) or Formant (the vowels
  A-E-I-O-U for men, women and children). Cutoff runs 20 Hz to 18 kHz;
  Resonance goes up to self-oscillation, in tune with Cutoff, on all five
  analogue-style types; Drive saturates. On the second page, Mode (the
  response, slope, input or voice, blended between), Morph (stereo spread,
  comb polarity or the vowel), Mix and Level. Changing Type starts the new
  filter unheard and then crossfades to it, within 10 ms, so it never
  clicks, even changed on every step: the sequencer may lock it and
  modulation may step through the types. The types are named for their
  circuits, never for a maker. Silence stays silent at any setting. Our
  own code (MIT), after Zavalishin's *The Art of VA Filter Design*, Andrew
  Simper's SVF, Huovilainen's ladder, the
  Korg35, diode-ladder and Steiner-Parker circuits, Zölzer's universal comb
  and Peterson and Barney's vowel measurements; documented in
  engines/README.md ("Filter"). It uses about 18 KB of memory at 44.1 kHz
  (Comb's delay line) and no maths library, so the browser plays it sample
  for sample like the desktop build (checked against GCC with glibc and
  musl). Four new parity scenarios cover its seven types, and a section in
  chapter 6 of the manual describes it.
- **Drive**, a new effect: overdrive and saturation, written for this
  project. Type picks the curve: Soft (smooth, tanh-like), Tube (uneven,
  with a second harmonic at every level), Diode (a harder knee), Fuzz (a
  hard, lopsided clip with a built-in gate) or Tape (gentle, with loud highs
  saturating first and coming out softened); changing it crossfades instead
  of clicking. Drive (−12 to +36 dB), Tone (a tilt: darker to the left,
  thinner to the right, flat in the middle) and Mix on the first page; Bias
  (uneven clipping), Gate (quiet parts drop out, a sputtering fuzz), Level
  and Auto on the second. With Auto on, the default, Drive changes the
  character and not the loudness. Type and Auto can be locked and
  modulated without clicks. Its anti-aliasing keeps the harsh tones a
  plain digital clipper folds back below 5 kHz 21–29 dB lower. Silence stays
  silent at any setting. Parameters and design in `engines/README.md`, and
  a section in chapter 6 of the manual. Two new parity scenarios cover it.
- **Comp**, a new effect: a compressor, written for this project. Threshold
  (−60 to 0 dB), Ratio (1:1 to 20:1, and a limiter at the top of the
  knob), Attack and Release on the first page; Knee (soft or hard), Makeup,
  Mix (parallel compression) and Character on the second: Peak and RMS
  choose how it listens, Glue holds a part together with a slower, rounder
  response, Punch lets the front of each hit through. On a third page,
  Auto Rel makes the release follow the music (quick after short peaks,
  slow after long loud passages) and Auto Gain sets the makeup so that a
  full-scale sound stays at full scale, up to 24 dB of it, and never
  pushes anything past full scale, not even the start of a hit before the
  attack has caught up (it rounds that peak off along the compressor's
  curve instead). Both channels are compressed together. Silence stays
  silent, knob turns glide, and Character, Auto Rel and Auto Gain switch
  mid-note without a jump, so they can be locked and modulated. It
  computes the same bits on the desktop and in the browser's WebAssembly.
  Parameters and design in
  `engines/README.md`, a section in chapter 6 of the manual; a new parity
  scenario covers it. For developers,
  `include/fm1_comp.h` reads its gain reduction, for a later modulation
  source.
- **Limiter**, a new effect: a look-ahead brickwall limiter for the master
  or for one sound. Ceiling (−24 to 0 dB), Drive (−12 to +24 dB), Release
  (1 ms to 1 s) and Lookahead (0 to 5 ms) on the first page; Mode
  (Brickwall or Soft Clip), Link (how much the two channels share one gain)
  and Mix (blending the dry sound back in) on the second. In Brickwall mode
  nothing passes the ceiling, and anything under it comes through
  untouched, only delayed by the lookahead. Lookahead 0 adds no delay and
  catches peaks with a gentle soft clip instead; Soft Clip mode rounds
  peaks off for a louder, warmer sound. Turning Lookahead or switching Mode
  while it is limiting fades smoothly and never flattens a peak, even on
  every step, so both can be locked and modulated (in review, a change
  could briefly hard-clip peaks far over the ceiling, and a fast run of
  Lookahead changes could click; both fixed before release). It uses about
  11 KB of memory at 44.1 kHz. The firmware's own output limiter stays
  after every effect. Written for this project (MIT), after Geraint Luff's
  look-ahead limiter design; parameters and design in
  `engines/README.md`, tested in `tests/test_engines_limit.py`, and a
  section in chapter 6 of the manual. A new parity scenario plays it twice
  in one chain.
- notes/2026-10-02-delay-reverb-eq-gates-options.md: research on delays,
  reverbs, EQ, a DJ filter and tilt for the master bus, bus saturation, and a
  Drawmer DS201-style gate. It also designs side-chaining: the gate and the
  compressor each get a key input patched separately from their audio
  input, either audio (the sound itself, another sound or the master,
  through key filters) or a trigger from the modulation matrix, with gain
  reduction and gate state usable as modulation sources. Every pick is MIT,
  public domain or our own code. It lays out stages B1–B8 and 17 owner
  decisions.
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
- README: the owner's new opening — project goals (including the Orbital Dock
  community module marketplace and firmware builder), current status, and
  why it cannot be flashed yet.
- **New pictures of the virtual FM-1, and a manual brought up to date with
  it.**
  - The README's picture and the phone picture show the page as it is now:
    a chord over the demo pattern, with an LFO cabled to Timbre and the
    memory meter on the screen. They no longer show the old memory figure
    in KB, and REC no longer blinks in them for notes waiting for Capture.
    The rest of the screen pictures are retaken from the same build, and
    there are new ones of Drums, the sequencer's Track view and the
    modulation matrix.
  - The manual shows those three screens. It names Drums and the four
    Plaits-based engines wherever the rate rule applies, and lists Comb and
    Test Ext and the new `--tempo` option among the desktop tools' options.
    It explains that frequency and time knobs turn in ratios and that
    modulation moves them in octaves, and that the sequencer's locks reach
    only the sounds so far. Its memory table matches the build: Filter is
    under 1 KB, Comb 17 KB, the Limiter 11 KB. It credits the modulation
    modules and Comb, and the open FM-1 firmware projects whose reports it
    now uses.
- **The sequencer, four sounds at once and modulation are on the virtual
  FM-1's public page.** The lab switch is gone: the page no longer needs
  `?lab` in its address (an old `?lab` link opens the same page), and
  everything that was behind it works for everyone: the entries under
  *Added* above that say "behind the lab switch" now describe the public
  page.
  - SEQ, PLAY/STOP and REC work: SEQ mode with the 16 steps on the white
    keys, the step and lock pages, recording, step recording and Capture,
    eight tracks with mute and routing, and the Set, Clip and Track pages.
    The page starts with a one-bar demo pattern on track 1; press
    PLAY/STOP, or Space on the computer keyboard, to hear it.
  - SEL is SHIFT everywhere but in FX mode; SEL with PRESETS chooses which
    of the four sounds you play, and the Sound menu under the panel follows.
  - FX mode shows the current sound's two inserts, a Mix page with the four
    sounds' levels, and the two master effects. A memory meter in the
    screen's bottom bar replaces the memory figure, and anything that
    would not fit the FM-1 is refused, on every chain.
  - LFO, ENV and EDIT open the modulation pages: the rack, the gesture
    that makes a cable, the matrix and the chain.
  - SAVE and ARP are the only buttons that still say they are not in the
    simulator yet; SEL outside FX mode no longer says it works only there.
  - The user manual describes all of it: chapter 7 (the sequencer) for the
    simulator, a new chapter 8 (modulation), and four sounds, inserts and
    the memory meter in chapters 5 and 6. Chapters 8 to 13 are now 9 to 14.
    The manual's and the README's screen pictures were retaken.
  - For developers: `fm1_app_set_lab`, `fm1w_set_lab` and the harness's
    `--lab` are gone. `fm1_app_init` starts the modulation runtime with the
    default rack; the harness's sidecar always starts with `--slots`; the
    layout sweep is one set of 2,338 screens; the parity scenarios have no
    `lab` key, and `fx-turns-diffuse-psxverb` plays Macro, since the RAM
    meter refuses Shapes beside Diffuse and PSX Verb. The browser module is
    765,189 bytes (769,693 with the switch), and 66 of 66 parity scenarios
    pass.
- **Licences: the GPL switch** (owner, 2026-10-05; CLAUDE.md, docs/12 §6).
  GPL modules will sit behind one build switch, on by default everywhere
  while we test; while it is on, no firmware image that links JieLi's
  libraries may be shared, and the public simulator's module is offered
  under GPL terms. No GPL code is in the tree yet.
- **Knob turns and sequencer locks no longer click** (docs/15 stage S7b).
  When a continuous parameter changes while a sound plays, the engine now
  glides to the new value over 2.5 ms instead of jumping, so a lock under a
  held note, or a knob turned while playing, is smooth. This holds for every
  sound engine, for the Plate, Ensemble, Diffuse, Crush and PSX Verb
  effects and for Echo's Tone; Fold, Drive, Filter, Comp, Limiter and the
  rest of Echo already glided. A change while nothing sounds, or before an
  effect starts, still applies at once, so a lock on the step of a note
  that starts on its own plays from that note's first sample, and
  sequences of separate notes sound exactly as before. A note with its own
  per-note offset follows the glide with its offset on top; the offset
  itself does not glide. The glide is counted in each engine's own
  samples, so the sound is the same whatever the host's block size. On the
  virtual FM-1, nine of the 47 test scenarios sound different, all of them
  ones that turn a knob or play a lock while something sounds (the panel
  and multi-sound demos, the lock demo, and the effects' knob-turn demos);
  the rest are unchanged. Engines use 12 bytes more per parameter (Crush
  96 → 176 bytes, Echo 16 bytes more, each Schwung module 176 bytes more
  on 64-bit, 160 on 32-bit).
- **The docs now match what the FM-1 community firmware and JieLi's current
  SDK show** (from `notes/2026-10-05-community-repos.md`, crediting Felucca
  by hugelton, SLOOP by isod89, fm1-nes by Keitark, FM-1-transporter by
  kurogedelic and JieLi's AC79 SDK). No user-facing change; nothing was sent
  to any FM-1.
  - **A new safety trap** in CLAUDE.md and AGENTS.md: the stock SysEx
    `F0 22 24 35 7D F7` (the "soft key") reboots a running V15 into the
    chip's ROM loader. It is not the identity query, is one byte from the
    upgrade command, and must not be sent before the dump-and-restore gate;
    FM-1-transporter sends it by itself, so it is not to be run against the
    owner's unit. docs/03, docs/07, docs/09, docs/10 and DEVELOPERS.md's
    one-rule section say the same. The one rule itself is unchanged.
  - **The hardware tables** (CLAUDE.md, DEVELOPERS.md, docs/01, docs/05,
    docs/08, docs/14): audio leaves over I2S (ALNK0) to an external codec, not the
    internal DAC; the seven encoders are scanned in the key matrix, MASTER is
    a pot on PB6 and ADC 3 is the battery; the flash reads as Puya
    `0x856014`. docs/01 gains a pin map (§3.1) with each row's source and
    how it compares with our own photos, the two 74HC595s become matrix
    column drivers, and its open questions narrow.
  - **The app starts at `0x02000120`**, now checked against our V15 and
    FM-1_092 unpacks; docs/02's `0x020000A0` is corrected.
  - **The install path** (DEVELOPERS.md I0–I15): Felucca and SLOOP already
    install and roll back through the stock path with their own loader, so
    I13 gains their update-service, boot-guard and fail-open design; I1
    keeps the SDK at V1.1.9 because `system.a` gains key checks from
    V1.2.7, with a refusal check and blob hashes; I3 gains a sparse
    mask-ROM writer plan; I4 starts from the reported pin map; the "still
    open" list loses four answered questions.
  - **The second core:** the SDK has no core argument for tasks, but a
    `#C<n>` task-name prefix exists; docs/14 adds probes C6d–C6f.
  - **Status and sources:** docs/05's L1 and L2 rows, docs/04's entries for
    the four projects and the Gitee SDK, docs/07's recovery paths (three
    software entries into the ROM loader, the updater's DIP modes, the WL82
    USB ID), docs/10's third dongle report, docs/12 §6's licence notes (the
    SDK's FreeRTOS and GPL-2.0 headers), HANDOFF's facts and clone list,
    and `tools/jieli/ac79-sdk-sparse.txt`, the SDK sparse-checkout list.
- **Sophie's Pad can be locked** (the owner's decision). It picks which of
  Sophie's sixteen pads her other knobs edit, so a lock on it changes which
  pad the locks after it, on that step and later, edit. Nothing else about
  any engine changed: 708 renders before and after are byte-identical,
  apart from lanes whose labels write a space as `_`, which reach their
  parameter now.
- **Engine API v2: every parameter has a fixed id and says what it allows.**
  Each parameter of every sound engine and effect now carries an id that
  never changes, so a sequencer lock (and later a modulation route or a
  preset) keeps its target even when a parameter list is reordered or
  extended. Each also says whether it can be locked, whether it is read only
  when a note starts, whether it should glide when it changes, and whether
  it can be modulated, plus a unit and a short name for the coming
  modulation matrix. What you hear changes in one case only: a sequencer
  lane on a parameter whose change cuts every sounding note (Macro's and
  Macro Heavy's Model, Shapes' Shape) is now refused instead of applied;
  `fm1-render` counts the refusals. PSX Verb's Model, which empties
  the reverb, is marked the same for when effects can be locked. Six-Op
  FM's Patch and Sophie's Model stay lockable: they change the next notes
  only. Sophie's Pad stays lockable too (above). Lane names in saved sets
  stay as they were (`synth:Timbre`). Every other render is
  byte-identical, over 1,458 renders
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
- docs/02 §5 and `tools/check_msfa_table.py` had rows 4 and 6 of msfa's
  algorithm table the wrong way round: `0x41`, which the FM-1 carries, is
  Google's original (there since its first commit, 2012), and `0xC1`, which
  Felucca's port of Dexed's msfa carries, a later change. The FM-1's table is Google's, row for row; the tool
  now reports 32 of 32 rows for an FM-1 image.
- On the virtual FM-1, Sophie's pads followed Sound 1 rather than the
  current sound: with Sophie as Sound 2 the white keys played notes she
  ignores, and with Sophie as Sound 1 they played her pad notes on another
  current sound. The white keys now play her pads whenever she is the
  current sound.
- The layout check drew FX mode's routed-parameter screens on an empty
  insert instead of the effect under test; it now draws them on M1.
- The simulator page's help credits every source of the modulation
  modules, as the manual does: Braids and Music Thing Modular's Turing
  Machine (Tom Whitwell) were missing.
- For developers: `fm1-sim-render` frees what a run holds when it stops
  part way, on a refused `--unit-route`, `--seq-reset` or `--seq-import`,
  so CI's leak check sees only the refusal.
- Sophie made no sound from the virtual FM-1's keys: it only plays MIDI
  notes 36–51 (its 16 pads), below the keys' range at the default octave.
  With Sophie as the sound, the 16 white keys now play pads 1–16 at any
  octave, and the black keys play nothing. MIDI IN keeps the drum map.
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
