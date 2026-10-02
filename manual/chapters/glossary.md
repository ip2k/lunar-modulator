# Glossary

Base value
:   The value a locked parameter returns to on steps that have a note but no
    lock of their own (chapter 7).

Block
:   The small piece of sound the firmware computes at a time: 64 samples,
    1.45 ms at 44,118 Hz.

BPM
:   Beats, here quarter notes, per minute: the sequencer's tempo.

Capture
:   The sequencer's retroactive recording: it keeps what you played while
    not recording, so you can turn it into a clip afterwards.

Clip
:   A loop of notes and locks on one track, up to sixteen bars long. Each
    track has eight clip slots.

Condition
:   A rule that plays a step only on some passes of its clip, written A:B:
    the A-th pass of every B.

Desktop tools
:   `fm1-render` and `fm1-seq`, programs that run Lunar Modulator's engines,
    effects and sequencer on a computer and write the result to a file.

Encoder
:   A knob that turns without end, in steps. Seven of the FM-1's knobs are
    encoders; [[MASTER]] is not.

Engine
:   The part of the firmware that makes the notes: Macro, Shapes, Six-Op FM
    and the others in chapter 5.

Firmware
:   The software built into an instrument that makes it work.

Flash
:   The memory that keeps the firmware and saved data when the power is off.

FM synthesis
:   Making sound by letting oscillators (operators) change each other's
    frequency, which gives bright, bell-like and metallic tones.

Limiter
:   The last stage of the sound path, which keeps the output below full
    scale.

Lock
:   See *parameter lock*.

Low-pass gate
:   A combined filter and amplifier that closes as a note dies away, so the
    sound gets quieter and darker together, as acoustic instruments do.

MIDI
:   The standard way instruments and computers exchange notes, controller
    movements and clock.

Operator
:   In FM synthesis, one oscillator with its own envelope. Six-Op FM has six.

Parameter
:   One adjustable setting of an engine or effect, such as Timbre or Decay.

Parameter lock
:   A value for one parameter stored on one step of a sequence, which the
    parameter takes when that step plays.

Probability
:   The chance, from 10 % to 100 %, that a step plays each time it comes
    round.

Quantise
:   Moving recorded notes towards the grid of steps. Lunar Modulator's is
    non-destructive: notes keep their played timing.

Scene
:   One clip slot across all tracks, launched together.

Simulator
:   The browser version of Lunar Modulator: the firmware's engines and
    effects behind a drawing of the FM-1's panel.

Song
:   A list of scenes played in order.

Step
:   One sixteenth of a bar in the sequencer.

Swing
:   Delaying every second sixteenth to give a pattern a shuffle.

Track
:   One line of the sequencer, playing one sound: the engine or a MIDI
    channel.

Voice
:   One sounding note. An engine's voice count is how many notes it can play
    at once.
