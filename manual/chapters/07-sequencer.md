# Sequencer

{{requires seq}}

Lunar Modulator's sequencer records and plays patterns of notes and
parameter changes. It follows the design of Movy, the sequencer megadake wrote
for the Ableton Move: tracks of clips, sixteen steps to a bar, parameter locks
on any step, conditions and probability, swing, non-destructive quantise,
scenes, a song mode and Capture, which keeps what you just played even if you
were not recording.

Today the sequencer runs in the desktop tools, where it is tested against
Movy's own code note for note. The controls described in this chapter are the
plan for the FM-1; they are not in the simulator yet.

{{seq-glance}}

## How a pattern is organised

{{status desktop planned}}

- A **track** plays one sound: the engine, or an instrument on a MIDI
  channel. The FM-1 build is planned with four to eight tracks.
- Each track has eight **clip** slots. A clip is a loop of up to sixteen bars
  holding notes and parameter locks; one clip per track plays at a time.
- A **step** is a sixteenth note. A bar has sixteen steps, and the sixteen
  white keys show one bar at a time.
- A **scene** is one clip slot across every track: launching scene 3
  launches slot 3 on each track. A **song** is a list of scenes played in
  order.

!!! outline "To be written"
    - A diagram: tracks down, slots across, the playing clip highlighted.
    - GRID mode and KEYS mode: in GRID mode the white keys are steps and
      the black keys functions; in KEYS mode the keys play notes as usual.
      How to switch between them.

## Steps and notes

{{status desktop planned}}

In GRID mode, tap a white key to put a note on that step or take it off.
The note is the last one you played, or the chord you are holding. Hold a
step and press keys to add or remove pitches on it; a step holds up to
twelve notes.

!!! outline "To be written"
    - Opening a step: hold it for 300 ms; the step page shows VEL, LEN,
      PROB and COND on [[KNOB1]] to [[KNOB4]], and INV on the second page
      ([[SELECT]]).
    - Length: hold one step and press a later one to stretch the note to it.
    - Nudge: moving a note up to a step early or late, in ticks.
    - Velocity and transpose of a held step, or of several held steps at
      once.
    - Clearing: [[role:CLEAR]] with a step clears its notes and locks.
    - The key lights in GRID mode: note, playhead, held, outside the loop.
    - On the desktop: the `tog`, `ltog`, `evel`, `elen`, `enudge` and `etrn`
      verbs (the table at the end of this chapter).

## Parameter locks

{{status desktop planned}}

A parameter lock gives one step its own value for a parameter: a brighter
note on step 5, a longer decay on step 13. Hold a step and turn
[[KNOB1]] to [[KNOB4]]: the value is stored on that step, for the parameter
on that knob. When the sequence plays, each lock sends its value as its step
starts, and the parameter keeps that value until another step changes it or
the sequence stops.

Each track has eight lock lanes, one per parameter that has locks. A lane
also has a base value, which steps without a lock of their own return to
when they have a note.

!!! outline "To be written"
    - Locks on steps without notes (lock-only steps), and how they latch.
    - Stop and release: the FM-1 returns each locked parameter to its base
      when you stop, so a sound never stays at a value no step asked for.
    - Clearing one lock, a step's locks, or a whole lane, with
      [[role:CLEAR]] and [[role:SHIFT]].
    - Locks on list parameters (Model, Shape, Patch): they step through the
      list in even bins.
    - Lock resolution: 128 values across a parameter's range.
    - What the screen shows: locked values in an accent colour, a dot on
      each parameter with a lane.

## Conditions and probability

{{status desktop planned}}

A step can play only some of the times its clip loops round, or only by
chance.

- **Condition** A:B plays the step on the A-th pass of every B: 1:2 plays
  every other time, 4:4 on the fourth of every four.
- **Probability** plays the step with a chance from 100 % down to 10 %.
- **Invert** turns a condition round: 1:2 inverted plays on the passes 1:2
  skips.

!!! outline "To be written"
    - The condition values the step page offers (36 A:B pairs up to 8) and
      the range scripts accept (A and B up to 64).
    - Conditions on one pitch of a chord against the whole step.
    - How probability and conditions combine.

## Swing and quantise

{{status desktop planned}}

**Swing** delays every second sixteenth: 50 % is straight, and 80 %, the
most, plays it half a step late.
**Quantise** pulls recorded notes towards the steps, from 0 % (as played) to
100 % (on the grid). It is non-destructive: the notes keep their played
timing, so you can change it later.

!!! outline "To be written"
    - Swing at other clip speeds.
    - The default quantise for new clips.

## Clips

{{status desktop planned}}

A clip runs from 1 to 256 steps, with a loop window that can start anywhere
in it. Each clip has its own speed, from an eighth of the tempo to four
times it, and its own transpose of up to three octaves either way.

!!! outline "To be written"
    - Choosing a clip slot, launching it on the next bar, and stopping a
      track.
    - Setting the length and the loop window with [[role:LOOP]]: the white
      keys become bars.
    - Double Loop: doubling a clip's length with its content.
    - Copying and pasting steps and clips with [[role:COPY]], duplicating a
      clip into the next free slot.
    - Undo with [[role:UNDO]] (planned with the FM-1's interface; the
      desktop tools accept the undo commands and ignore them for now).

## Scenes and song

{{status desktop planned}}

Launching a scene starts the same slot on every track at the next bar. A
song plays a list of scenes, each for as long as its longest clip, and arms
the next one a bar before it is due.

!!! outline "To be written"
    - Building a song: start it from a scene, then add scenes in order.
    - [[role:SESSION]]: the overview of all tracks and slots on the screen.
    - What happens when the song reaches an empty scene.

## Recording

{{status desktop planned}}

Press [[REC]] to record what you play. When the sequencer is stopped, a
one-bar count-in comes first. While it plays, recording into a clip that
already has notes starts at once and adds to them (overdub); into an empty
clip it starts on the next bar. A first take into an empty clip grows bar by
bar for as long as you keep playing, up to sixteen bars.

!!! outline "To be written"
    - Step recording: hold [[REC]] while stopped.
    - How played notes are placed: onto the nearest step, keeping their
      timing for quantise to work on.
    - Turning a knob while recording: locks on the current step.
    - The metronome.

## Capture

{{status desktop planned}}

Capture keeps listening while the sequencer is not recording. If you played
something you like, press Capture afterwards and it becomes a clip: the
sequencer finds the tempo from what you played, offers a few likely tempos to
choose from (up to three), and places the notes on the grid. The FM-1
build keeps the last 256 events for it, about 128 notes.

!!! outline "To be written"
    - The tempo choice: candidates, and how to accept one.
    - Capture while the sequencer plays: the notes fit the running tempo.
    - Which track Capture listens to; clearing what it holds.
    - The control that triggers Capture, once assigned.

## Tracks and routing

{{status desktop planned}}

Each track plays either the sound engine or an instrument on a USB-MIDI
channel from 1 to 16. Unless you route it, a track sends MIDI on its own
channel: track 1 on channel 1, track 2 on channel 2, and so on. The desktop
renderer sends track 1 to the engine when nothing else is routed.

!!! outline "To be written"
    - Choosing a track: [[role:SESSION]] and a white key.
    - Mute and solo with [[role:MUTE]] and [[role:SHIFT]].
    - Drum tracks: transpose off, and muting or soloing single drum notes.
    - The FM-1's default routing, once decided, and which tracks reach the
      engine when several do (one engine slot today).
    - In the desktop renderer: `--route T:engine` and `--route T:midi:CH`;
      MIDI-routed tracks are logged, not played.

## Transport and clock

{{status desktop planned}}

[[PLAY/STOP]] starts and stops the sequencer. Play always starts from the
beginning: the song from its first scene if there is one, otherwise each
track's chosen clip. The tempo runs from 20 to 300 BPM. The sequencer sends
MIDI clock at 24 pulses per quarter note with Start and Stop, and can follow
an external clock instead.

!!! outline "To be written"
    - Setting the tempo; tap tempo if planned.
    - Following external clock: what Start, Continue and Stop do.
    - Stopping: notes end, and locked parameters return to their base.

## Memory

{{status desktop planned}}

{{seq-memory}}

!!! outline "To be written"
    - What fills up first (notes, locks, gates) and the message the screen
      shows when an edit does not fit: the edit is refused whole, never
      half done.

## Scripts on the desktop

{{status desktop}}

The desktop tools drive the sequencer from a text script: one command per
line, each a verb and its arguments, at a given time. `fm1-seq` runs the
sequencer alone and writes every event it produces; `fm1-render` plays the
same script through a sound engine into a WAV file.

```bash
engines/build/fm1-render --engine macro --cmd song.txt --log-events song.jsonl --out song.wav
engines/build/fm1-render --engine macro --seq set.movy1 --seconds 8 --out set.wav
```

Tracks and steps are numbered from 0 in scripts. A lock lane's label names
the engine parameter it drives, such as `synth:Timbre`.

{{seq-verbs}}

!!! outline "To be written"
    - The script format: `@<frame> <verb> <arguments>`, with an example
      that builds a one-bar pattern with a lock and plays it.
    - Saving and loading sets in Movy's `movy1` text format.
