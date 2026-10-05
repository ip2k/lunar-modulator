# Sequencer

{{requires seq}}

Lunar Modulator's sequencer records and plays patterns of notes and
parameter changes. Its design follows Movy, the sequencer megadake wrote for
the Ableton Move: tracks of clips, sixteen steps to a bar, parameter locks on
any step, conditions and probability, swing, non-destructive quantise, scenes
and a song mode, and Capture, which keeps what you just played even when you
were not recording.

The sequencer runs today in the desktop tools, where it is tested note for
note against Movy's own code. On the FM-1 it is planned: this chapter
describes how you will play it there, with the keys, knobs and buttons, and
what it already does in the desktop tools. It is not in the browser simulator
yet.

!!! note "Reading this chapter"
    - Controls drawn with a dashed outline, such as [[role:SHIFT]] and
      [[role:CLEAR]], are sequencer functions that still have to be given a
      button on the FM-1. The index of controls lists them apart.
    - The gestures are the design for the FM-1. They follow Movy's,
      translated to the FM-1's piano keys and four parameter knobs, and may
      still change while the interface is built.
    - Steps, tracks, slots and scenes are numbered from 1 here, as the FM-1
      will show them. Scripts for the desktop tools count from 0
      ([Scripts on the desktop](#scripts-on-the-desktop)).

{{seq-glance}}

## How a pattern is organised

{{status desktop planned}}

Everything the sequencer holds is a **set**: the tempo, the swing, a song,
and every track with its clips.

- A **track** plays one sound: the sound engine, or an instrument on a MIDI
  channel. The FM-1 build is planned with four to eight tracks.
- Each track has eight **clip slots**. A **clip** is a loop of 1 to 256 steps,
  up to sixteen bars, holding notes, parameter locks and step conditions. One
  clip per track plays at a time.
- A **step** is a sixteenth note. Sixteen steps make a bar of 4/4.
- A **scene** is one slot number across every track: launching scene 3
  launches slot 3 on each track. A **song** is a list of scenes played in
  order.

| Example set | Slot 1 | Slot 2 | Slot 3 | Slot 4 | Slot 5 | Slot 6 | Slot 7 | Slot 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Track 1 | **plays** | clip | clip | | | | | |
| Track 2 | **plays** | clip | | | | | | |
| Track 3 | clip | **plays** | clip | | | | | |
| Track 4 | | | clip | | | | | |

In this set, tracks 1 and 2 play their first clip, track 3 its second, and
track 4 is silent. Launching scene 3 would start slot 3 on tracks 1, 3 and 4
at the next bar, and stop track 2, which has nothing in slot 3.

### GRID mode and KEYS mode

The FM-1's keyboard will have two jobs:

- In **KEYS mode** the keys play notes, as in [chapter 4](04-playing.md).
  The notes go to the selected track; they are what you record and what
  Capture hears.
- In **GRID mode** the 16 white keys are the 16 steps of one bar of the
  selected clip, numbered 1 to 16 from the left. The 11 black keys become
  functions: two of them, ◀ and ▶, move the view a bar earlier or later and
  nudge held steps, and two more keys or buttons, − and +, transpose held
  steps. In the loop and session views the white keys stand for bars, tracks
  or slots instead.

Which control switches between the two modes, and which black key carries
which function, is still to be decided with the rest of the FM-1's
interface. [[SEQ]], [[PLAY/STOP]] and [[REC]] are reserved for the
sequencer.

### What the screen shows

The sequencer's screens are planned as follows:

- A header with the track, the clip slot, the bar, the tempo, and PLAY, REC
  or EXT (following an external clock).
- A grid of four rows of 16 steps, four bars at a time. A step with notes is
  filled, a step with locks has a dot in its corner, a step with a condition
  or probability has a tick, and steps outside the loop are outlined.
- Four cells for the parameters on [[KNOB1]] to [[KNOB4]]. A locked value is
  shown in an accent colour, and a dot marks each parameter that has locks
  on this track.
- A strip at the bottom with an overview of the loop, or a short message.

The session view shows every track and slot at once
([Scenes and song](#scenes-and-song)).

### The key lights

The key lights on the FM-1 can probably only be on or off, so in GRID mode
the sequencer uses blinking to tell states apart:

| Key light | Meaning |
| --- | --- |
| On | The step has notes |
| Off | The step is empty, or outside the loop |
| Inverted: off on a step with notes, on on an empty one | The playhead is on this step |
| Slow blink | The step lies under the length of the note you are holding |
| Fast blink | Recording is writing to this step |

## Steps and notes

{{status desktop planned}}

### To put notes on a step

1. Select the track and its clip
   ([Tracks and routing](#tracks-and-routing), [Clips](#clips)).
2. In GRID mode, tap the step's white key. The key lights.

The step gets the notes you are holding on a keyboard at [[MIDI IN]]. If you
are holding none, it gets the note or chord you played last. A tap places up
to twelve notes, each one step long.

A step changes when you release its key, so a key you hold to edit the step
(below) never switches it on or off. Tap a step that has notes to remove
them; its parameter locks stay.

The first note in an empty slot makes a one-bar clip. A note in a later bar,
past the clip's end, lengthens the clip to the end of that bar.

!!! note "Editing a clip that is not playing"
    If you add notes to a clip that is not playing while the sequencer runs,
    that clip starts playing on its track at the next bar.

### To add or remove one note of a chord

1. Hold the step's white key.
2. Hold [[role:SHIFT]]. While it is down, the keys play pitches.
3. Press a key to add that pitch to the step, or to remove it if the step
   already has it.

You can also hold the step and play the pitch on a keyboard at [[MIDI IN]].
A pitch added this way takes the length of the notes already on the step.

### The step page

Hold a step for about 300 ms and the screen opens the step page, with the
step's own settings:

| Page | [[KNOB1]] | [[KNOB2]] | [[KNOB3]] | [[KNOB4]] |
| --- | --- | --- | --- | --- |
| 1 | VEL | LEN | PROB | COND |
| 2 | INV | | | |

Turn [[SELECT]] to change page.

| Setting | What it sets | Range |
| --- | --- | --- |
| VEL | The velocity of the step's notes | 1 to 127 |
| LEN | How long the step's notes last | From a tick up to the end of the loop |
| PROB | The chance that the step plays | 100 % down to 10 % |
| COND | On which passes of the clip the step plays | 36 conditions, 1:1 to 8:8 |
| INV | Turns the condition round | Off or on |

[Conditions and probability](#conditions-and-probability) explains PROB,
COND and INV. How [[KNOB1]] to [[KNOB4]] divide their work between the step
page and parameter locks while you hold a step is one of the details still
to be settled on the FM-1.

### To set the length of notes

- Hold the step and press a later step: the held step's notes now last
  until that step.
- Or set LEN on the step page.

A note never lasts past the next note of the same pitch, nor past the end of
the loop.

### To nudge notes

Hold one or more steps and press ◀ or ▶: their notes move 2 ticks earlier or
later. Hold [[role:SHIFT]] as well to move them 1 tick. A tick is 1/24 of a
step, and a note stays within one step of the step it belongs to.

!!! tip "Nudges and quantise"
    Quantise pulls nudged notes back towards the grid too. At 100 % a nudge
    has no effect; at 0 % you hear it in full
    ([Swing and quantise](#swing-and-quantise)).

### To change velocity or pitch

Hold one or more steps, then:

- turn VEL to set the velocity of every note on them;
- press the transpose functions, − or +, to move every note on them a
  semitone down or up.

### To clear steps

| To clear | Do this |
| --- | --- |
| A step's notes | Tap the step |
| A step's notes and locks | Hold [[role:CLEAR]] and press the step |
| A step's locks only | Hold the step and press [[role:CLEAR]] |

## Parameter locks

{{status desktop planned}}

A parameter lock gives one step its own value for one parameter: a brighter
note on step 5, a longer decay on step 13. You lock the sound engine's
parameters, as [chapter 5](05-sound-engines.md)'s tables list them; locks on
the effects' parameters are planned as well.

### To lock a parameter on a step

1. Turn [[SELECT]] to the page with the parameter, as you would to play it.
2. Hold the step's white key.
3. Turn the parameter's knob. The value is stored on that step.
4. Release the key.

You do not hear a lock while you set it on a held step; you hear it when the
step plays. Locks are made with one step held: with two or more steps held,
the knobs change the sound as usual.

A step does not need notes to carry a lock. A lock on an empty step changes
the sound under notes that are still ringing, and the value then holds until
a step with notes resets it (below).

Each track has eight lock lanes, so it can lock up to eight different
parameters at once. A parameter takes a lane the first time you lock it, and
gives it back when its last lock on the track, in any of its clips, is
cleared.

### How a lock plays

When the playhead reaches a step, each locked parameter on the track takes:

1. the step's lock, if it has one;
2. otherwise, if the step has notes, the parameter's base value;
3. otherwise, the value it already has.

A value is sent only when it changes, and a step's locks are sent just
before its notes, so each note starts with its locked sound. In this
example the parameter runs from 0 to 1 and its base value is 0.40:

| Step | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Notes | yes | | yes | | yes | | yes | |
| Lock | | | 0.80 | | | 0.20 | | |
| Value | 0.40 | 0.40 | **0.80** | 0.80 | 0.40 | **0.20** | 0.40 | 0.40 |

!!! note "Locks keep running"
    Locks follow the steps even when the track is muted or a condition keeps
    a step's notes silent, so the sound is ready when the notes come back.

### Base values

Each locked parameter has a base value, the value that steps with notes but
no lock return to. Turning a knob with no step held changes the parameter as
usual and makes the new value its base.

### When the sequencer stops

When you stop the sequencer, every locked parameter that was left at a
locked value goes back to its base value, after the notes have ended. The
same happens to a track that stops at the bar, and to a parameter when you
clear its last lock. A sound never stays at a value that no step asked for.

### To clear locks

| To clear | Do this |
| --- | --- |
| One lock | Hold the step, hold [[role:SHIFT]], and turn the parameter's knob |
| Every lock on a step | Hold the step and press [[role:CLEAR]] |
| Every lock of one parameter on the track | Hold [[role:CLEAR]] and turn the parameter's knob one detent |

### Values and list parameters

- A lock stores one of 128 values spread evenly across the parameter's
  range. On a frequency or a time (a cutoff, a delay, a release), they are
  spread evenly in ratio, as the knob turns, so each step is the same
  musical interval: from 20 Hz to 18 kHz, a little under a semitone a step.
- On a list parameter, such as Model, Shape, Patch or Pad, the 128 values
  are divided evenly between the entries.
- Parameters that disturb every sounding note when they change refuse
  locks: Macro's and Macro Heavy's Model, which cut the notes, and Shapes'
  Shape, which strikes them again. So does Sophie's Pad, which only chooses
  the pad her other knobs edit. A refused lock is simply not played; the
  desktop renderer counts them. A lock on Six-Op FM's Patch or on Sophie's
  Model changes the sound of that step's notes only, as those engines read
  it when a note starts.
- Continuous parameters are planned to glide to a locked value over 2 to
  3 ms, so a lock under a ringing note does not click.
- The sound engine itself cannot be locked. To change engine on a step, put
  the notes on another track.

## Conditions and probability

{{status desktop planned}}

A step can play only on some passes of its clip, or only by chance. Set both
on the step page.

### Conditions

A condition A:B plays the step on the A-th pass of every B passes of its
clip. Passes are counted for each track from 1, starting when its clip
starts: when you press Play, or when the clip is launched.

| Condition | Plays on passes |
| --- | --- |
| 1:1 | Every pass (the default) |
| 1:2 | 1, 3, 5, 7 … |
| 2:2 | 2, 4, 6, 8 … |
| 1:4 | 1, 5, 9, 13 … |
| 3:4 | 3, 7, 11, 15 … |
| 4:4 | 4, 8, 12, 16 … |

COND on the step page offers the 36 conditions with A and B up to 8 and A no
greater than B, from 1:1 to 8:8. Scripts accept A and B up to 64.

### Probability

PROB gives a step a chance to play each time it comes round, from 100 %
(always) down to 10 %. Scripts accept any value from 0 to 100 %.

The chance comes from a fixed random sequence that starts afresh when the
sequencer starts up, so the desktop tools render the same script the same
way every time.

### Invert

INV turns a condition round: the step plays on exactly the passes the
condition would skip. 1:4 inverted plays on passes 2, 3, 4, 6, 7, 8 and so
on.

### How they combine

- The condition comes first. The chance is tried only on the passes the
  condition lets through.
- All the notes on a step share one decision: a chord plays whole, or not
  at all.
- One note of a step can also have a condition and a chance of its own,
  which then decide for that note alone. The desktop tools set them with a
  pitch; the FM-1 is planned to offer them on drum tracks.

## Swing and quantise

{{status desktop planned}}

### Swing

Swing delays every second sixteenth note to give a pattern a shuffle. It is
set for the whole set, from 50 % (straight) to 80 %:

| Swing | Off-beat sixteenths play late by |
| --- | --- |
| 50 % | Nothing: straight |
| 60 % | 4 ticks, 1/6 of a step |
| 66 % | 6 ticks, 1/4 of a step |
| 70 % | 8 ticks, 1/3 of a step |
| 80 % | 12 ticks, half a step |

Swing follows the tempo, not the clip. In a clip playing at 2X it delays the
steps that land on the tempo's off-beat sixteenths, steps 3, 7, 11 and 15 of
each bar of the clip, so that the clip swings with the others. A clip at
half speed or slower is not swung, because none of its steps lands on an
off-beat sixteenth.

### Quantise

Quantise pulls recorded notes towards their steps, from 0 % (as played) to
100 % (exactly on the step). It is non-destructive: each note keeps the
timing you played, and quantise only changes where it sounds, so you can
change it again at any time.

- Each clip has its own quantise, on the clip page ([Clips](#clips)).
- New clips start with the set's default quantise, which is 0 % until you
  change it ([Transport and clock](#transport-and-clock)).
- Notes you place by tapping steps are already on the grid; quantise matters
  for notes you record, capture or nudge.

## Clips

{{status desktop planned}}

### To choose and launch a clip

In the session view, keys 1 to 8 launch slots 1 to 8 of the selected track
([Scenes and song](#scenes-and-song)).

- A launch takes effect at the next bar, so clips change in time.
- Launching a clip while the sequencer is stopped starts the sequencer.
  Tracks that were playing when you stopped start again with it.
- Launching an empty slot stops the track at the next bar.
- Launching a clip by hand ends a song that is playing.

### Length and the loop window

A new clip is one bar long. You can change its length on the clip page, from
1 to 256 steps, or set its loop window with [[role:LOOP]]:

1. Press [[role:LOOP]]. The white keys now stand for bars 1 to 16.
2. Press the first bar of the loop, then the last.

To loop a single bar, double-tap it instead. To make the loop longer or
shorter afterwards, hold [[role:LOOP]] and turn [[SELECT]].

A loop window starts at the beginning of a bar and is at least one bar long.
Notes outside it stay in the clip, silent, until the window includes them
again.

### The clip page

Press [[role:SHIFT]] and white key 3 to open the clip page:

| Setting | What it sets | Range |
| --- | --- | --- |
| SCALE | The clip's speed against the tempo: at 2X its steps are 32nd notes, at 1/2X eighth notes | 1/8X to 4X |
| Length | The clip's length | 1 to 256 steps |
| Transpose | Moves every note of the clip up or down without changing the stored notes; not on drum tracks | −36 to +36 semitones |
| Quantise | How far recorded notes are pulled to their steps | 0 to 100 % |

### Double Loop

Press [[role:SHIFT]] and white key 15 to double the clip's length and copy
its notes into the new half: a one-bar idea becomes two bars to develop.
Locks and conditions are not copied. A clip that would grow past sixteen
bars is left as it is.

### To copy steps and clips

1. Hold [[role:COPY]].
2. Press the step to copy.
3. Press each step to paste it to.

A copied step takes its notes and locks with it, but not its conditions.
Copying whole clips, which takes everything, and duplicating a clip into the
next empty slot are in the sequencer already; their controls on the FM-1 are
still to be assigned.

### To delete a clip

Tap [[role:CLEAR]] on its own: the chosen clip is deleted.

### Undo

[[role:UNDO]] takes back your last gesture, and [[role:SHIFT]] with
[[role:UNDO]] brings it back. A gesture is one action, such as a step tap or
one turn of a knob: a turn counts as finished when you leave the knob for
0.6 s. Undo is planned with the FM-1's interface; the desktop tools accept
its commands and ignore them.

## Scenes and song

{{status desktop planned}}

### The session view

[[role:SESSION]] shows every track and slot of the set at once, with the
clips that play and those that wait for the next bar.

- To select a track, hold [[role:SESSION]] and press the track's white key.
- In the session view, keys 1 to 8 launch the selected track's slots.

### To launch a scene

In the session view, hold [[role:LOOP]] and press one of the odd white keys:
keys 1, 3, 5 … 15 launch scenes 1 to 8.

The scene starts at the next bar. Every track with a clip in that slot
starts it, and every track without one stops. While the sequencer is
stopped, launching a scene starts it.

### Song

A song plays a list of scenes, one after the other.

- Start a song from a scene, then add the scenes to follow, in order. A song
  holds up to 64 entries. The FM-1's controls for building a song are still
  to be assigned; the desktop tools use the commands `song` and `songadd`.
- Each scene plays for as long as its longest clip, rounded up to whole
  bars. Add the same scene twice in a row to play it twice as long.
- The next scene is launched a bar ahead, so it starts exactly on time.
- After the last scene the song starts again from the first.
- A scene with no clips at all stops every track and ends the song there.
- [[PLAY/STOP]] starts a song from its first scene. Launching a clip by hand
  ends the song.

## Recording

{{status desktop planned}}

### To record

1. Select the track and the clip slot to record into.
2. Press [[REC]].
3. Play, in KEYS mode or from a keyboard at [[MIDI IN]].
4. Press [[REC]] again to stop recording. The sequencer keeps playing;
   [[PLAY/STOP]] stops both.

If the sequencer was stopped, it starts with a one-bar count-in: four
clicks, the first one accented. Recording begins on the bar after it.

### First take and overdub

- **Into an empty clip** (a first take) recording starts on the next bar.
  The clip grows a bar at a time for as long as you keep recording, up to
  sixteen bars. When you stop recording, it keeps every bar it has reached
  and loops.
- **Into a clip with notes** (an overdub) recording starts at once and adds
  to the notes there. The clip keeps its length.

### How played notes are placed

- Each note goes to the nearest step, swing included, and keeps the timing
  you played, so quantise can pull it in later.
- A note played up to half a step before recording starts lands on the first
  step.
- A note you hold across the end of the loop keeps growing, up to the length
  of the clip.
- A note you have just recorded does not play again until the loop comes
  round, so you never hear it twice.
- Up to 16 notes held at the same time are recorded.

### Turning knobs while recording

Turning a knob while you record locks the parameter on the step that is
playing, and you hear the change as you turn.

### Metronome

Press [[role:SHIFT]] and white key 6 to turn the metronome on or off. It
clicks on every beat and accents the first beat of each bar. On the FM-1 the
click is planned as a sound of its own; the desktop tools write the clicks
to the event log.

### Step recording

Hold [[REC]] while the sequencer is stopped to record step by step instead,
without the clock running. Step recording is planned with the FM-1's
interface.

## Capture

{{status desktop planned}}

Capture keeps listening while you are not recording. If you played something
you like, press Capture afterwards and it becomes a clip. Capture's control
on the FM-1 is still to be assigned.

!!! note "Capture in the desktop tools"
    `fm1-seq` and `fm1-render` run with Capture on and 256 events, as planned
    for the FM-1. In compat mode, which reproduces Movy exactly, they keep
    512 like Movy. `fm1-seq --capture 0` runs without it.

### What Capture keeps

- The notes you play on the keys or at [[MIDI IN]], for any track except one
  you are recording on, and not during a count-in.
- Your last phrase: up to eight bars at the current tempo and, in the FM-1
  build, up to 256 note events. Each note takes two, its start and its end,
  so that is about 128 notes.
- A pause longer than two bars starts a new phrase. At fast tempos the pause
  must still last more than 2 seconds, and at slow ones 8 seconds is always
  enough.
- While the sequencer plays, Capture keeps your latest pass of the loop:
  when you play again at a point you played on an earlier pass, it starts
  afresh from there.

!!! caution "Capture empties itself"
    Starting or stopping the sequencer empties Capture, and so do most
    edits: a step, a lock, a clip setting, a launch or a recording. Press
    Capture straight after the phrase you want to keep.

### To capture while stopped

1. With the sequencer stopped, play your phrase.
2. Press Capture.

**Into an empty clip**, Capture works out the tempo you played at, between
40 and 250 BPM, from three or more notes; with fewer it keeps the current
tempo. It sets the sequencer to that tempo, writes the notes into the clip,
rounded up to whole bars and at most sixteen, and starts playing it.

**Into a clip with notes**, or while the sequencer follows an external clock,
the tempo stays as it is and your phrase is fitted to it. Into a clip with
notes, the phrase is added into the clip's loop. The sequencer then starts
playing.

### Choosing a tempo

A phrase often fits more than one tempo, typically one and its half or
double. Capture then offers up to three, slowest first, with its best guess
chosen. Choose another to rewrite the clip at that tempo, and accept to
close the choice. Capture does not listen while the choice is open.

### To capture while playing

Press Capture while the sequencer plays and the notes go where you played
them in the loop, into the selected track's clip, which keeps playing. If
that clip is empty, Capture makes a new clip as long as your phrase in whole
bars, starting where in the bar you started, and launches it at the next
bar.

## Tracks and routing

{{status desktop planned}}

### To select a track

Hold [[role:SESSION]] and press the track's white key. What you play, record
and edit goes to the selected track.

### To mute or solo a track

- Hold [[role:MUTE]] and press the track's white key to mute it, or to
  unmute it.
- Hold [[role:MUTE]] and [[role:SHIFT]] and press the track's white key to
  solo it.

Muting a track ends its sounding notes at once. Its parameter locks keep
running ([Parameter locks](#parameter-locks)).

### Routing

Each track plays either the sound engine or an instrument on a USB-MIDI
channel from 1 to 16. Unless you route it, a track sends MIDI on its own
channel: track 1 on channel 1, track 2 on channel 2, and so on. A set keeps
its routing.

!!! note "Tracks that share the engine"
    The FM-1 runs one sound engine at a time. Tracks routed to it play the
    same sound, and if two of them lock the same parameter, each overwrites
    the other's value. The FM-1's default routing is still to be decided.

In the desktop tools, track 1 plays the engine when nothing else is routed;
MIDI-routed tracks are written to the event log rather than played
([Scripts on the desktop](#scripts-on-the-desktop)).

### Drum tracks

A track can be made a drum track. Its clips' transpose then does not apply,
so each note keeps its drum, and you can mute up to 16 single drum notes on
it, or solo one. Drum tracks are in the sequencer already; their controls on
the FM-1 are planned for later.

## Transport and clock

{{status desktop planned}}

### Play and stop

Press [[PLAY/STOP]] to start the sequencer. Play always starts from the
beginning: a song from its first scene, otherwise each track's chosen clip.

Press [[PLAY/STOP]] again to stop. Notes end, recording ends, locked
parameters return to their base values, and a song goes back to its start.
Each track keeps its chosen clip.

In scripts, a `play` while the sequencer plays restarts it from the
beginning.

### Tempo

The tempo runs from 20 to 300 BPM in steps of 0.01 BPM, and is 120 BPM when
the sequencer starts up. The tempo, the swing and the default quantise
belong to the set as a whole; on the FM-1 they are planned on the set
pages, which [[role:SHIFT]] with white key 5, 7 or 9 opens.

### MIDI clock out

While it plays, the sequencer sends MIDI clock: Start when it starts, 24
pulses per quarter note, and Stop when it stops. A restart sends Stop and
then Start, so devices that follow stay in time. On the FM-1 the
clock is planned on USB-MIDI; the desktop tools write it to the event log.

### Following an external clock

When MIDI clock arrives while the sequencer plays, the sequencer follows it:

- It waits for the next bar of the incoming clock, counted from its first
  pulse, then plays in step with it.
- It takes its tempo from the pulses, smoothing out small changes.
- It stops sending clock of its own while it follows.
- A MIDI Start restarts it from the beginning.
- If the pulses stop for half a second, or a MIDI Stop arrives, it carries
  on by itself at the last tempo, and sends Start to its own followers at
  the next bar.

In the desktop tools, a MIDI Start or Stop also starts or stops the
sequencer itself, but only while the set's `link` setting is on: `link 1` in
a script, or a set saved with it on. It is off otherwise. On the FM-1,
Continue and Song Position are planned as well
([chapter 8](08-midi.md#following-an-external-clock)).

## Memory

{{status desktop planned}}

The FM-1 has no room to spare, so the sequencer keeps its notes, locks and
step conditions in fixed pools that every clip of the set draws from, and
reserves all its memory when it starts. A full pool never corrupts a set: an
edit that does not fit is refused whole, never half done, and the FM-1's
screen is planned to say so.

{{seq-memory}}

| Pool | For each track | Notes |
| --- | --- | --- |
| Notes | 192 | One clip can hold up to 512 |
| Parameter locks | 192 | One clip can hold up to 1,024 |
| Step conditions and probabilities | 32 | One clip can hold up to 1,024 |

The pools are shared, so one busy clip can use what quieter tracks leave
free. Besides them the set has room for 64 notes sounding at once (when all
are in use, the oldest ends to make room), a song of 64 entries, and 16 notes
held at once while recording.

## Controls at a glance

{{status planned}}

The sequencer's gestures on the FM-1, as planned. GRID mode is assumed
unless the gesture says otherwise.

| Gesture | What it does | See |
| --- | --- | --- |
| Tap a white key | Puts notes on the step, or removes them | [Steps and notes](#steps-and-notes) |
| Hold a step for 300 ms | Opens the step page | [The step page](#the-step-page) |
| Hold a step, turn a knob | Locks the parameter on the step | [Parameter locks](#parameter-locks) |
| Hold a step, press a later step | Sets the length of the held step's notes | [Steps and notes](#steps-and-notes) |
| Hold a step and [[role:SHIFT]], press keys | Adds or removes pitches on the step | [Steps and notes](#steps-and-notes) |
| Hold steps, press ◀ or ▶ | Nudges their notes 2 ticks; with [[role:SHIFT]], 1 tick | [Steps and notes](#steps-and-notes) |
| Hold a step, [[role:SHIFT]], turn a knob | Clears that lock | [Parameter locks](#parameter-locks) |
| Hold a step, press [[role:CLEAR]] | Clears the step's locks | [Parameter locks](#parameter-locks) |
| Hold [[role:CLEAR]], press a step | Clears the step's notes and locks | [Steps and notes](#steps-and-notes) |
| Hold [[role:CLEAR]], turn a knob one detent | Clears that parameter's locks on the track | [Parameter locks](#parameter-locks) |
| Tap [[role:CLEAR]] | Deletes the chosen clip | [Clips](#clips) |
| Hold [[role:COPY]], press a step, then others | Copies the step to the others | [Clips](#clips) |
| [[role:LOOP]], then two bars | Sets the loop window | [Clips](#clips) |
| [[role:LOOP]] and [[SELECT]] | Makes the loop longer or shorter | [Clips](#clips) |
| [[role:SESSION]] | Shows every track and slot | [Scenes and song](#scenes-and-song) |
| Hold [[role:SESSION]], press a white key | Selects that track | [Tracks and routing](#tracks-and-routing) |
| Session view: keys 1 to 8 | Launch the selected track's slots | [Clips](#clips) |
| Session view: [[role:LOOP]] and an odd white key | Launches scenes 1 to 8 | [Scenes and song](#scenes-and-song) |
| Hold [[role:MUTE]], press a white key | Mutes or unmutes that track; add [[role:SHIFT]] to solo | [Tracks and routing](#tracks-and-routing) |
| [[role:SHIFT]] and white key 3 | Opens the clip page | [Clips](#clips) |
| [[role:SHIFT]] and white key 5, 7 or 9 | Opens the set pages | [Transport and clock](#transport-and-clock) |
| [[role:SHIFT]] and white key 6 | Turns the metronome on or off | [Recording](#recording) |
| [[role:SHIFT]] and white key 15 | Double Loop | [Clips](#clips) |
| [[role:SHIFT]] and white key 16 | The clip's quantise | [Swing and quantise](#swing-and-quantise) |
| [[role:UNDO]]; [[role:SHIFT]] and [[role:UNDO]] | Undo; redo | [Clips](#clips) |
| [[PLAY/STOP]] | Starts from the beginning, or stops | [Transport and clock](#transport-and-clock) |
| [[REC]] | Starts or stops recording; held while stopped, step recording | [Recording](#recording) |

## Scripts on the desktop

{{status desktop}}

The desktop tools drive the sequencer from a text script: one command per
line, each a time, a verb and its arguments. `fm1-seq` runs the sequencer on
its own and writes every event it produces; `fm1-render` plays the same
script through a sound engine into a WAV file.

### The script format

```text
#! rate=44118 block=64 tracks=4 end=264708
# A one-bar pattern on track 0 with a brighter second note, then play.
@0 bpm 12000
@0 tog 0 0 48 100; tog 0 4 55 90; tog 0 8 60 100; tog 0 12 55 90
@0 alabel 0 0 synth:Timbre; abaseq 0 0 40
@0 aset 0 0 4 110 1
@0 play
```

- The first line, `#!`, sets the sample rate (default 44,118 Hz), the block
  size in frames (default 128), the number of tracks (default 8) and, with
  `end`, how many frames to run. Without `end` the run stops just after the
  last command.
- Each command line starts with `@` and the frame at which it applies, in
  samples at the script's rate. Several commands can share a line,
  separated by `;`.
- Lines starting with `#` are comments.
- Tracks, steps, slots and scenes count from 0. Tempos are in hundredths of
  a BPM, and lock values run from 0 to 127.
- A line `@<frame> rt F8` delivers a MIDI clock pulse to the sequencer; `FA`,
  `FB` and `FC` are Start, Continue and Stop.

In the example, `tog` puts four notes on steps 0, 4, 8 and 12 of track 0.
`alabel` assigns lock lane 0 to the parameter Timbre, `abaseq` sets its base
value to 40 without sending it, and `aset` locks the value 110 on step 4,
quietly.

### To render a script and keep the set

```bash
engines/build/fm1-render --engine macro --cmd pattern.txt \
    --log-events pattern.jsonl --out pattern.wav
engines/build/fm1-seq --cmd pattern.txt --export pattern.movy1
engines/build/fm1-render --engine macro --seq pattern.movy1 \
    --seconds 8 --out set.wav
```

- The first line plays the script through Macro into `pattern.wav` and logs
  every event.
- The second runs it through the sequencer alone and saves the resulting
  set as text, in Movy's `movy1` format
  ([chapter 9](09-settings-and-storage.md#sequencer-sets)).
- The third loads that set and plays it from the beginning for eight
  seconds.

### Routing and the event log

- A lock lane's label names the engine parameter it drives: the part after
  the last `:`, such as `Timbre` in `synth:Timbre`, matched without regard
  to case. A label that names no parameter of the engine does nothing.
- With no routing given, track 0 plays the engine. `--route 1:engine` sends
  track 1 to the engine as well, and `--route 2:midi:3` sends track 2 to
  MIDI channel 3, which the event log records but nothing plays.
- The event log has one line per event, in JSON: the block, the frame, the
  tick, the kind (`on`, `off`, `cc`, `clock`, `start`, `stop` or `click`),
  the track and two values. A lock is logged as kind `cc`, controller 102
  plus its lane.
- `fm1-render`'s summary line reports `seq_refused`: edits that did not fit
  the sequencer's memory.

### Commands

{{seq-verbs}}
