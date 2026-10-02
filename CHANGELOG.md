# Changelog

All notable changes to this project are recorded here, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. The project
has no releases yet; work before this file existed (research phase, bench
session 1, the `USB_KEY` dongle, the 2026-09-08 desk review) is in the git
history.

## [Unreleased]

### Added
- The sequencer core, `fm1_seq` (docs/13 stage M1): a C99, heap-free port of
  Movy's sequencer with every planned fix on by default and an exact Movy
  mode for tests. It has 4–8 tracks, each routed to the engine or to USB-MIDI
  on its own channel (14,984 B at 4 tracks, 28,808 B at 8). `fm1-render`
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
- docs/13 records the owner's choice of 7-bit locks with smoothing, and of
  Capture as an optional feature. docs/11 corrects its claim that Clouds'
  spectral mode needs its own FFT.
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
