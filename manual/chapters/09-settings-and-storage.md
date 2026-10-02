# Settings and storage

This chapter covers the global page, where settings that apply to everything
live, and how sounds and patterns are kept.

## The global page

{{status sim planned}}

Press [[GLO]] to open the global page, and press it again to leave. In the
simulator it shows:

- the sample rate and block size the firmware runs at;
- how much memory the current engine and effects take, against the memory
  the FM-1 has free for them (about 379 KB);
- the engine's number of voices;
- the octave and transpose.

The memory figure tells you whether a combination would fit on the FM-1:
the simulator can run combinations the device could not.

!!! outline "To be written"
    - Settings planned for the page: MIDI channel, pitch bend range, velocity
      curve or fixed velocity, tuning, the screen's brightness.
    - How a setting is changed: [[SELECT]] to the page, a knob for the value.

## Saving sounds

{{status planned}}

!!! outline "To be written"
    - What a sound is: the engine, its parameters and the two effects.
    - [[SAVE]]: storing a sound in a slot, naming it, recalling it with
      [[PRESETS]].
    - Not in the simulator yet: it starts with every engine at its defaults
      each time.

## Saving patterns

{{status desktop planned}}

!!! outline "To be written"
    - The desktop tools save and load sequencer sets as text, in Movy's
      `movy1` format.
    - On the FM-1, patterns are planned to live in memory first, with export
      and import over USB (system exclusive), and in flash last, in their own
      area with two copies so a power cut while saving cannot lose both.
    - Nothing is written to the FM-1's flash until the one rule is met
      (chapter 1).

## Backing up

{{status planned}}

!!! outline "To be written"
    - Exporting every sound and pattern to a computer, and importing them.
    - What the stock firmware's patches and patterns become: they stay in
      their own areas, untouched, and can be read only after a full backup
      of the device exists (chapter 10).
