# Credits and licences

Lunar Modulator stands on other people's work. This chapter names it, and the
terms it is used under.

## Sound engines and effects

- **Mutable Instruments**, code by **Emilie Gillet**, MIT licence. Macro,
  Macro Heavy and Six-Op FM are built from the engines of Plaits; Shapes from
  the macro-oscillator of Braids; Plate from the reverb of Rings, its Freeze
  after the one in Elements; Room from the reverb and diffuser of Clouds;
  Ensemble and Diffuse from Plaits' ensemble and diffuser. Their code is included
  unmodified; the wrappers that make it polyphonic and fit it to the FM-1
  are this project's own, and Macro Heavy's speech model adapts one of
  Plaits' classes. Lunar Modulator is not affiliated with or endorsed by
  Mutable Instruments, and as Mutable Instruments asks of work derived from
  its code, the engines carry names of their own.
- **Six-Op FM's patches** are the three banks distributed with Plaits' code.
  Their origin is not stated there. In public builds, the twenty-three
  patches whose stored names are trademarks or a person's name are shown
  under descriptive names of this project's own.
- **msfa**, the FM synthesizer core of Google's Music Synthesizer for
  Android, by **Raph Levien** for **Google**, Apache License 2.0: FM6's
  envelopes, LFO, operators, algorithms and tables. Its code is included
  unmodified, its tables computed ahead of time as its own code computes
  them; the voice built from it, its amplitude modulation, the feedback
  loops of algorithms 4 and 6 and its controls are this project's own.
  FM6 reads voices in the format of Yamaha's DX7 and is not affiliated
  with or endorsed by Yamaha.
- **FM6's name** is borrowed, with thanks, from the FM engine of
  **Felucca** by **hugelton** (Hügelton Instruments), open firmware for the
  FM-1; Felucca's Apache-2.0 port of the same core checks FM6 in the tests
  (below).
- **FM6's built-in voices** are this project's own, written for it and
  under the MIT licence.
- **Sophie** by **Matt Estela**, MIT licence, included unmodified.
- **Drums**: its kicks, toms, snares and hi-hats are Plaits' drum models by
  **Emilie Gillet** (Mutable Instruments, MIT licence), included unmodified,
  which model the circuits of Roland's TR-808 and, in their synthetic kick
  and snare, borrow from the TR-909's. Its rim shot, clap, cowbell and
  cymbals are this project's own code, with three small pieces of Plaits'
  hi-hat in the cowbell and cymbals (its swing VCA curve, its oscillators'
  ratios and its clocked noise): the cowbell and cymbals follow the circuit
  models of **Kurt James Werner, Jonathan Abel and Julius O. Smith** ("More
  cowbell", AES 137th Convention, 2014; "The TR-808 cymbal", ICMC/SMC
  2014, CC BY 3.0), and the clap and rim shot published descriptions of the
  TR-808's circuits, among them **Baratatronix**'s. No code or text is
  taken from the papers or the descriptions. The two kits are inspired by those drum machines; Roland's
  names appear here only as credit.
- **PSX Verb** by **Charles Vestal**, MIT licence, included unmodified.
- **Schwung**, Charles Vestal's host for modules on the Ableton Move, MIT
  licence. Lunar Modulator includes Schwung's plugin interface unmodified,
  with a compatibility layer of its own, so that Schwung modules such as
  Sophie and PSX Verb build from their own source. Schwung's licence notes
  that it began as a fork of Move Anything by Bobby Digitales.
- **Crush** is this project's own code. Pairing a sample-rate reducer with a
  bit reducer follows **DaisySP**'s Decimator and Bitcrush, by
  **Electro-Smith**, MIT licence; none of DaisySP's code is used.
- **Fold** is this project's own code, after the wavefolders of Serge and
  Buchla synthesizers and the folding in Mutable Instruments' Warps and
  Plaits by **Emilie Gillet**; its anti-aliasing follows the method of
  **Parker, Zavalishin and Le Bivic** (DAFx-16). No code is taken from any
  of them.
- **Drive** is this project's own code: its curves are written here, its
  tape emphasis follows tape's record and replay equalisation, and its
  anti-aliasing follows the method of **Parker, Zavalishin and Le Bivic**
  (DAFx-16). No code is taken from anyone.
- **Echo** is this project's own code. Its ping-pong layout is the textbook
  one, after **Udo Zölzer**'s *DAFX*, and its 16-bit delay memory follows
  **Emilie Gillet**'s effects engine in Rings and Clouds; none of their code
  is used.
- **Filter** is this project's own code: zero-delay-feedback filters after
  **Vadim Zavalishin**'s *The Art of VA Filter Design*, **Andrew Simper**'s
  (Cytomic) state-variable filter, **Antti Huovilainen**'s ladder model
  (DAFx-04) and the diode-ladder circuit; its Sallen-Key type is after the
  Korg-35 filter of the later MS-20, and its SK Mixed type after the
  Steiner-Parker Synthacon's filter (their makers' names appear here only
  as credit); its non-linear solver follows a method **Teemu Voipio**
  published, and its vowels are the measurements of **Peterson and
  Barney** (1952). No code is taken from any of them.
- **Comb** is this project's own code: **Udo Zölzer**'s universal comb
  (*DAFX*), with Filter's saturating loop. It was one of Filter's types
  until October 2026. No code is taken from anyone.
- **Comp** is this project's own code, after the compressor design of
  **Giannoulis, Massberg and Reiss** (*Journal of the Audio Engineering
  Society*, 2012). No code is taken from anyone.
- **Limiter** is this project's own code, after **Geraint Luff**'s
  look-ahead limiter design (Signalsmith Audio, 2022). No code is taken from
  the article or from Signalsmith's library. Its Round mode ports the loop of
  **Airwindows** ClipOnly2, by **Chris Johnson**, MIT licence ("Copyright
  (c) 2016 airwindows, Airwindows uses the MIT license"; the licence is in
  the source tree with the effect).
- **DJ Filter** is this project's own code: the state-variable filter of
  **Andrew Simper** (Cytomic) and **Vadim Zavalishin**, in the form of
  stmlib's by **Emilie Gillet** (MIT licence). No code is taken from anyone.
- **Tilt** is this project's own code. A tilt built from first-order
  sections follows **Airwindows**' ToneSlant (MIT licence) and the
  spectral tilt of the **Faust** libraries; none of their code is used.
- **Master Sat** is this project's own code. Its two curves use the
  coefficients of **Airwindows** PurestSaturation and TapeHack2, by **Chris
  Johnson**, MIT licence ("Copyright (c) 2018 Chris Johnson"; the licence's
  notice is in the effect's source), and its Glue follows the idea of
  Airwindows Compresaturator, whose code is not used.
- **Isolator** is this project's own code. Its three bands are split as in
  the **Faust** libraries' three-band Linkwitz-Riley crossover, with
  **Andrew Simper**'s (Cytomic) and **Vadim Zavalishin**'s state-variable
  filter; none of their code is used.
- **EQ** is this project's own code. Each band is the state-variable filter
  in the form **Andrew Simper** (Cytomic) published, whose maths is in the
  public domain, and its curves are checked against **Robert
  Bristow-Johnson**'s Audio EQ Cookbook. No code is taken from either.
- **Hall** is this project's own code. It is a feedback delay network after
  **Jean-Marc Jot** and **Antoine Chaigne** (1991); its structure follows
  schwung-work's Voidspace and **Geraint Luff**'s Signalsmith basics library
  (both MIT), its input diffusion **Manfred Schroeder**'s all-passes with
  **Jon Dattorro**'s coefficients, and its 16-bit delay memory **Emilie
  Gillet**'s effects engine in Rings and Clouds; none of their code is used.
- **Gate** is this project's own code. Its controls follow the operator
  manuals of **Drawmer**'s DS201 and DS301 noise gates (the maker's name
  appears here only as credit); its key filters are **Vadim Zavalishin**'s
  state-variable filter. No circuit or code is taken from anyone.
- **Squash** ports three **Airwindows** plug-ins by **Chris Johnson**, MIT
  licence ("Copyright (c) 2016 airwindows, Airwindows uses the MIT
  license"): its Snap type is Pop3, Mu is Pressure4 and Split is
  ButterComp2, rewritten in single precision for the FM-1, with their noise
  taken out and the few changes the effect's notes list.
- **Transient** is this project's own code, on the classic two-follower
  principle of transient designers, as noted from **legsmechanical**'s Bus
  Driver (MIT licence). No code or measurement is taken from it.

Each engine's and effect's credits are also built into the firmware, and are
printed under its table in chapters [5](05-sound-engines.md) and
[6](06-effects.md).

## The sequencer

- **Movy** by **megadake**, MIT licence. Lunar Modulator's sequencer is a new
  implementation, written in C, of the behaviour of Movy's sequencer core,
  and its design follows Movy's. Movy's own core, run unmodified on a
  computer, is used to check Lunar Modulator's, event for event.

## Modulation

- The rack's modules are this project's own code, after published designs,
  chiefly those of **Mutable Instruments**' Peaks and Braids by **Emilie
  Gillet** (MIT licence). Three are ports of that code: Bounce from Peaks'
  bouncing ball, Burst from Peaks' pulse shaper and randomizer, and
  Quantize from Braids' quantizer and its scales.
- The LFO's shapes follow **Schwung**'s LFO by **Charles Vestal** and
  Peaks; the envelope follows Peaks' multistage envelope; Chance follows
  **DaisySP**'s sample and hold (**Electro-Smith**, Paul Batchelor) and
  **Music Thing Modular**'s Workshop System Computer card 106 (**Matt
  Allison**); Register follows **Tom Whitwell**'s Turing Machine (Music
  Thing Modular), **Chris Johnson**'s card 20 and **Phazerville**'s
  Turing code (**Patrick Dowling**). Divide, Burst, Compare, Logic, Calc,
  Slew and Mix follow Phazerville's applets (**Jason Justian** and
  others), and the Resonator **Andrew Simper**'s (Cytomic) state-variable filter.
  No code is taken from any of them but the three ports above.
- Some modules follow only the published behaviour of other instruments,
  whose makers' names appear here only as credit: Function after Make
  Noise's Maths, Joranalogue's Contour 1, Serge's DUSG and Befaco's
  Rampage; Coin after Mutable Instruments' Branches and Marbles; the LFO's
  modes after Elektron's instruments; Slew, Compare and Logic after Expert
  Sleepers' disting and Mannequins' Just Friends. No code of theirs is
  used.

`fm1-render --list-mod` prints each module's credits in full.

## Research this project builds on

- **aroum**: the first analysis of the FM-1's updater, and teardown photos.
- **AL-255**: a disassembly of the FM-1's firmware, its update protocol, and a
  safety review whose rules this project follows.
- **Echomatter**: showed that the FM-1's own update method accepts a rebuilt
  firmware package with a new version number, and rolled it back again.
- **kagaimiq**: documentation and tools for JieLi chips, including the
  recovery mode the dongle uses.
- **czietz** and **masanaohayashi**: reports of reaching that recovery mode on
  FM-1s with a small USB dongle, and czietz's tool for it.
- **probonopd**: notes on a sibling keyboard built on the same platform.
- **benny-sparra**: an editor and librarian for the FM-1, and observations of
  its MIDI.
- **Baud Girl**, whose third-party FM-1 firmware showed how firmware reaches
  users through the FM-1's own update method.
- **hugelton** (Felucca), **isod89** (SLOOP), **Keitark** (fm1-nes) and
  **kurogedelic** (FM-1-transporter): open firmware and tools that run on
  FM-1s. Their reports of how the board reads its keys and knobs, where its
  audio goes and how its recovery mode is reached inform this project's
  plans.
- **Google's music-synthesizer-for-android** and the **Dexed** family, whose
  FM engine M-VAVE's firmware is built on.

The project's research notes credit each source in detail.

## The simulator, the art and the manual

- **Audiowide** by Brian J. Bonislawsky (Astigmatic), SIL Open Font License
  1.1, for the name, the headings and the cover. The font file is included
  unmodified, with its licence.
- **IBM Plex Sans** and **IBM Plex Mono**, designed by Mike Abbink with Bold
  Monday for IBM, SIL Open Font License 1.1, set the printed manual. On the
  web the manual uses them where they are installed, and your system's own
  typeface otherwise.
- **Rosé Pine**, by mvllow and the Rosé Pine contributors, MIT licence: this
  manual is in the Dawn palette, and the simulator and the art in Moon.
- The simulator's screen font, the panel drawings, the banner and the boot
  screen are this project's own. The panel drawings follow M-VAVE's published
  dimensions and measurements of a unit.
- The manual is built with **Python-Markdown** and **WeasyPrint**, both under
  the BSD licence.

## Licences

Lunar Modulator's own code, and this manual, are under the MIT licence. Code
from other projects keeps its own licence, which the repository records
beside it with a note of where it came from. Everything listed in this
chapter that ships with the simulator or the desktop tools is under the MIT
licence, or, for msfa, the Apache License 2.0, or, for the fonts, the SIL
Open Font License 1.1. The repository's tests also use **Felucca**'s
`fm6_core.c` by **Leo Kuroshita** (Hügelton Instruments), an Apache-2.0 port
of the same FM core, to check FM6 against; it is in no build of the
firmware or the simulator.

## Trademarks

M-VAVE, Cuvave and FM-1 are the marks of their owners. Lunar Modulator uses
"FM-1" only to say which instrument it is written for, and is not made,
endorsed or supported by M-VAVE or Cuvave. The names of Mutable Instruments'
modules identify where code came from. Names such as Ableton Move and DX7
describe origins and compatibility only, and Roland, TR-808 and TR-909 the
machines that inspired Drums. All other trademarks belong to their owners.
