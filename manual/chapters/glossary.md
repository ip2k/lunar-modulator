# Glossary

Base value
:   The value a locked parameter returns to on steps that have notes but no
    lock of their own. Turning a knob with no step held sets it
    ([chapter 7](07-sequencer.md#base-values)).

Block
:   The small piece of sound the firmware computes at a time: 64 samples,
    1.45 ms at 44,118 Hz.

BPM
:   Beats, here quarter notes, per minute: the sequencer's tempo, from 20 to
    300.

Capture
:   The sequencer's record-after: it keeps the last phrase you played while
    not recording, so you can turn it into a clip afterwards
    ([chapter 7](07-sequencer.md#capture)).

Clip
:   A loop of notes, locks and conditions on one track, from 1 to 256 steps
    long. Each track has eight clip slots and plays one clip at a time.

Condition
:   A rule, written A:B, that plays a step only on the A-th pass of every B
    passes of its clip.

Count-in
:   The bar of clicks the sequencer plays before it records, when you start
    recording with the sequencer stopped.

Desktop tools
:   `fm1-render` and `fm1-seq`, programs that run Lunar Modulator's engines,
    effects and sequencer on a computer and write the result to files.

Drum track
:   A sequencer track whose clips are not transposed, so each note keeps its
    drum, and whose single drum notes can be muted or soloed.

Encoder
:   A knob that turns without end, in steps you can feel. Seven of the FM-1's
    knobs are encoders; [[MASTER]] is not.

Engine
:   The part of the firmware that makes the notes: Macro, Shapes, Six-Op FM
    and the others in [chapter 5](05-sound-engines.md).

Event log
:   A file in which the desktop tools record everything the sequencer does,
    one line per note, lock or clock message.

Firmware
:   The software built into an instrument that makes it work.

First take
:   A recording into an empty clip. It starts on a bar, and the clip grows a
    bar at a time while you record.

Flash
:   The memory that keeps the firmware and saved data when the power is off.

FM synthesis
:   Making sound by letting oscillators (operators) change each other's
    frequency, which gives bright, bell-like and metallic tones.

GRID mode
:   The planned way of using the FM-1's keyboard for the sequencer: the 16
    white keys are the steps of a bar and the black keys are functions.

Identity
:   The model name and number an FM-1 reports about its firmware, such as
    `FM-1_015`. More reliable than a file name
    ([chapter 10](10-updating-and-recovery.md#the-firmware-your-fm-1-has-now)).

KEYS mode
:   The FM-1's keyboard playing notes, as it always does outside the
    sequencer.

Lane
:   One of the eight places a track keeps the locks of one parameter. A
    track can lock up to eight parameters at once.

Limiter
:   The last stage of the sound path, which keeps the output below full
    scale.

Lock
:   See *parameter lock*.

Loop window
:   The part of a clip that plays, starting at the beginning of a bar. Notes
    outside it are kept, silent.

Low-pass gate
:   A combined filter and amplifier that closes as a note dies away, so the
    sound gets quieter and darker together, as acoustic instruments do.

Metronome
:   The sequencer's click on every beat, with an accent on the first beat of
    each bar.

MIDI
:   The standard way instruments and computers exchange notes, controller
    movements and clock.

MIDI clock
:   Timing pulses, 24 to a quarter note, with Start and Stop messages, that
    keep instruments playing in time with each other.

movy1
:   The plain text format in which the sequencer saves a set. It comes from
    Movy, and both read each other's files.

Nudge
:   Moving a note a little earlier or later than its step, in ticks, up to a
    step either way.

One rule
:   Nothing is installed on, or written to, an FM-1 until a complete copy of
    its memory has been read out and written back, byte for byte, on that
    unit ([chapter 1](01-welcome-and-safety.md#the-one-rule)).

Operator
:   In FM synthesis, one oscillator with its own envelope. Six-Op FM and FM6
    have six.

Overdub
:   Recording into a clip that already has notes, adding to them.

Parameter
:   One adjustable setting of an engine or effect, such as Timbre or Decay.

Parameter lock
:   A value for one parameter stored on one step of a clip, which the
    parameter takes when that step plays.

Pass
:   One time round a clip's loop. Conditions count passes.

Playhead
:   The step the sequencer is playing on a track.

Potentiometer
:   A knob with end stops whose position is its value, such as [[MASTER]].

Probability
:   The chance that a step plays each time it comes round: on the step page,
    from 100 % down to 10 %.

Quantise
:   Pulling recorded notes towards their steps. Lunar Modulator's is
    non-destructive: notes keep their played timing.

Recovery dongle
:   A small device between a computer and the FM-1's USB-C socket that
    starts the processor's recovery mode
    ([chapter 10](10-updating-and-recovery.md#the-recovery-dongle)).

Recovery mode
:   A mode built into the FM-1 processor's read-only memory, in which a
    computer can read and write the flash whatever it holds.

Role
:   In this manual, a sequencer function that still has to be given a
    button on the FM-1, drawn with a dashed outline, such as
    <kbd class="ctl role">SHIFT</kbd>.

Routing
:   Where a sequencer track sends its notes: the sound engine, or a
    USB-MIDI channel.

Sample rate
:   How many samples of sound the firmware computes each second. Lunar
    Modulator's is 44,118 Hz.

Scene
:   One clip slot across all tracks, launched together.

Session view
:   The planned sequencer screen that shows every track and clip slot at
    once.

Set
:   Everything the sequencer holds: tempo, swing, song, tracks and their
    clips.

Simulator
:   The browser version of Lunar Modulator: the firmware's engines and
    effects behind a drawing of the FM-1's panel.

Song
:   A list of scenes played in order.

Step
:   One sixteenth note of a bar in the sequencer; 16 steps make a bar.

Step page
:   The screen that shows a held step's own settings: velocity, length,
    probability, condition and invert.

Swing
:   Delaying every second sixteenth to give a pattern a shuffle.

System exclusive
:   MIDI messages that carry data of a manufacturer's or project's own, such
    as a whole sequencer set.

Tick
:   The sequencer's smallest step of time: 1/24 of a step, or 96 to a quarter
    note.

Track
:   One line of the sequencer, playing one sound: the engine or a MIDI
    channel.

Transpose
:   Moving notes up or down by semitones without changing which keys you
    play.

USB-MIDI
:   MIDI carried over a USB cable, as the FM-1 exchanges it with a computer.

Velocity
:   How hard a note is played, from 1 to 127.

Voice
:   One sounding note. An engine's voice count is how many notes it can play
    at once.
