# Playing

This chapter covers playing notes: the keys, how hard you play them, pitch
bend, the octave and transpose controls, and notes that arrive over MIDI.

## Keys and voices

{{status sim desktop planned}}

Each key plays one note for as long as you hold it. How many notes can sound
at once depends on the engine: twelve for most, eight for Six-Op FM and four
for Macro Heavy (chapter 5 lists each). When you play more notes than the
engine has voices, a new note takes over a voice that is already sounding.

!!! outline "To be written"
    - Which voice a new note takes when all are busy, per engine family
      (Plaits-based, Braids-based, Schwung modules), as the engine notes in
      `engines/` describe it.
    - Releasing notes: the engine's own release or decay, and [[MASTER]]'s
      place after the limiter.
    - Holding many notes: the bus limiter keeps the sum below full scale
      (chapter 6).

## Velocity

{{status sim desktop planned}}

Every note carries a velocity from 1 to 127, from how hard the key was
played. In the simulator, press lower on a key to play louder; a MIDI
keyboard sends its own velocity.

!!! outline "To be written"
    - What velocity changes in each engine: level, brightness or both.
    - On the FM-1: whether its keys sense velocity at all, once measured;
      a fixed velocity setting if they do not (chapter 9).

## Octave and transpose

{{status sim planned}}

At the middle octave the keys play F3 to G5. Press [[OCT-]] or [[OCT+]] to
move the keyboard down or up an octave, as far as three octaves either way.
Press both together to return to the middle octave and cancel any
transpose.

To transpose by semitones, hold [[OCT-]] or [[OCT+]] and turn
[[ALGORITHM]]: up to 12 semitones either way. The note a key plays is
53 + its position + 12 × the octave + the transpose, counting the lowest key
as position 0.

!!! outline "To be written"
    - The light in [[OCT-]] and [[OCT+]]: off at the middle octave, then
      slow, fast and steady for one, two and three octaves away.
    - A worked example: octave +1 and transpose −2 turns the lowest key from
      F3 into D♯4.
    - What the screen shows while you change octave or transpose.

## Pitch bend

{{status sim desktop planned}}

Pitch bend from a MIDI keyboard bends every sounding note by up to
two semitones up or down in the simulator. The desktop renderer accepts
bends of up to 48 semitones each way.

!!! outline "To be written"
    - A bend range setting (chapter 9) and its default.
    - How each engine follows a bend: all of them glide the pitch of
      sounding notes; engines with internal pitch (Shapes' physical models)
      may differ.
    - On the FM-1: no bend wheel; bend arrives over MIDI only, unless a
      control is assigned to it.

## Playing from MIDI

{{status sim planned}}

Notes, velocity and pitch bend from a MIDI keyboard play the engine as the
FM-1's own keys do; notes from both mix. CC 7 sets the volume and CC 123
releases every note. Chapter 8 has the full list.

!!! outline "To be written"
    - MIDI channels: which channel the engine listens on (Omni in the
      simulator), and how sequencer tracks are routed (chapter 7).
    - On the FM-1: MIDI over USB and the 3.5 mm input; Bluetooth MIDI is a
      later question.
