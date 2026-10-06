# Settings and storage

This chapter covers the global page, where Lunar Modulator shows what
applies to the whole instrument, and how sounds and sequencer sets are kept.

!!! warning "Nothing is stored on the FM-1"
    Lunar Modulator writes nothing to an FM-1's memory, and will not until
    the one rule is met ([chapter 1](01-welcome-and-safety.md#the-one-rule)).
    The sounds, patterns and settings your FM-1 holds now stay as they are.

## The global page

{{status sim planned}}

### To open the global page

Press [[GLO]]. Press [[GLO]] again, or [[HOME]], to leave it. The bottom bar
reads *1/1 Globe* while the page is open.

### What it shows

| Line | What it means |
| --- | --- |
| Rate | The sample rate the firmware runs at, such as 44118 Hz |
| Block | How many samples the firmware computes at a time: 64 |
| RAM | Two figures in kilobytes: the memory the sounds, effects, sequencer and modulation take (the sequencer about 36K of it and modulation about 23K, playing or not), then the 379K the FM-1 has free for them. The memory meter in the bottom bar shows the same as a share ([chapter 6](06-effects.md#memory)) |
| Voices | How many notes the current sound's engine plays at once |
| M1, M2 | The effect in each master slot by its name, such as *Plate*, spelled out where the line has room (*Compressor* for Comp), or `--` for an empty slot |
| Octave | The keyboard's octave, from −3 to +3 ([chapter 4](04-playing.md#octave-and-transpose)) |
| Transpose | The transpose in semitones, from −12 to +12 |

The knobs change nothing on this page.

!!! tip "Will it fit on the FM-1?"
    The simulator refuses any sound or effect that would take the first
    figure past the second, so whatever it plays would fit on the FM-1. To
    make room, choose a smaller engine or effect, or empty a sound or a slot
    ([chapter 6](06-effects.md#memory)).

### Settings on the FM-1

On the FM-1, the global page is planned to hold the settings that apply to
the whole instrument. Which ones is not decided yet. The questions still
open include the MIDI channel the sound engine listens on, the pitch bend
range, and, should the FM-1's keys turn out not to sense how hard they are
played, a fixed velocity.

## Sounds

{{status planned}}

A sound is everything you hear from the keys: the sound engine with its
parameters, and its two insert effects with theirs; the two master effects
and the modulation rack belong to the whole instrument.

In the simulator, nothing is kept. Each engine starts at its defaults when
you choose it with [[PRESETS]], and closing or reloading the page starts the
simulator afresh, with the demo pattern on the sequencer. Choosing another
engine also ends every note sounding on that sound.

Saving and recalling sounds is planned for the FM-1, with [[SAVE]], and has
not been designed in detail yet. As with sequencer sets, nothing will be
written to the FM-1's flash memory before the one rule has been met.

## Sequencer sets

{{status desktop planned}}

A set is everything the sequencer holds ([chapter 7](07-sequencer.md#how-a-pattern-is-organised)).

### What a set keeps

| Kept | Not kept |
| --- | --- |
| The tempo, the swing and the external-clock `link` setting ([chapter 9](09-midi.md#following-an-external-clock)) | Whether the sequencer was playing |
| The song | The playhead's position |
| Each track's chosen clip, its mute, its muted or soloed drum notes, and its routing | How many times each clip has looped, which conditions count |
| Each track's lock lanes, with their parameters and base values | The random sequence behind probability |
| Every clip: its length, loop window, speed, transpose and quantise | Which tracks are drum tracks |
| Every note, lock, condition and probability | The default quantise for new clips |

### In the desktop tools

The desktop tools save and load sets as text in Movy's `movy1` format, a
plain text file you can read, keep under version control or share:

```bash
engines/build/fm1-seq --cmd pattern.txt --export pattern.movy1     # save the set a script builds
engines/build/fm1-seq --seq pattern.movy1 --export copy.movy1      # load a set and save it again
engines/build/fm1-render --engine macro --seq pattern.movy1 --seconds 8 --out set.wav
```

Movy reads these files too, and Lunar Modulator reads Movy's. The
differences:

- Lunar Modulator adds a line for each track you route away from its
  default, which Movy ignores.
- It keeps what it loads within its own ranges, clip speeds of 1/8X to 4X
  among them.
- It leaves out what does not fit its memory: notes and locks beyond its
  pools, and tracks beyond the number it was started with.

### On the FM-1

The FM-1 build is planned to keep sets in three stages:

1. **In memory.** The set lives in the instrument's working memory and is
   lost when you switch off.
2. **On a computer.** You save a set to a computer and load it back over
   USB-MIDI, as system exclusive messages carrying the same `movy1` text.
   A full set is about 90 KB and is sent in parts.
3. **In flash memory, last.** Sets will be written to an area of their own,
   apart from the areas M-VAVE's firmware uses, only when you save. Each set
   is kept twice, so a power cut while saving cannot lose both copies.

The third stage waits for the one rule
([chapter 11](11-updating-and-recovery.md#the-one-rule-again)).

## Backing up

{{status planned}}

### Your work

Planned: one export that saves every sound and every set to a computer, and
an import that brings them back. Until sounds and sets can be stored on the
FM-1 itself, saving a set to a computer is the backup.

### Your FM-1's own sounds and patterns

The patches, patterns and settings that M-VAVE's firmware keeps in the FM-1's
flash memory stay in their own areas. Lunar Modulator is planned never to
write there.

- Reading them would need their formats, which only a complete copy of the
  FM-1's memory can show.
- That copy is exactly what the one rule asks for first: a full read-out of
  the FM-1's memory, kept safe, before anything is written
  ([chapter 11](11-updating-and-recovery.md#the-recovery-dongle)).

!!! tip "Keep your own copies"
    If you use a patch editor or librarian with M-VAVE's firmware, keep your
    banks on your computer as well. The FM-1 accepts voices and banks over
    MIDI but does not send its stored banks back.
