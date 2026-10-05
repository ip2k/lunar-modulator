# Effects

After the sound engine, the sound passes through two effect slots, then the
limiter, then [[MASTER]]. Each slot holds one effect or nothing. Every engine
but Macro Heavy's string machine plays in mono; the effects are where the
sound gains its stereo width.

{{engine-summary audio_fx}}

## The effect chain

{{status sim desktop planned}}

The simulator starts with Plate in the first slot and the second slot empty.
An effect processes everything before it: the engine, then the first slot,
then the second. A reverb after a chorus sounds different from a chorus after
a reverb.

**To see the chain:** press [[FX]]. The screen lists both slots and shows the
chosen slot's parameters on [[KNOB1]] to [[KNOB4]]. Press [[FX]] again, or
[[HOME]], to return to the sound.

**To choose a slot:** turn [[SELECT]]. It moves through the first slot's
pages, then the second slot's. The bottom bar shows where you are, such as
*1/2 FX2*: page 1 of 2, second slot.

**To put an effect in the chosen slot:** turn [[ALGORITHM]]. It steps through
*Empty slot*, Plate, Ensemble, Diffuse, PSX Verb, Crush, Fold, Echo, Tilt,
Master Sat, EQ and Test Gain, and round again. In the simulator you can also
use the **Effect 1** and **Effect 2** lists under the panel.

**To empty a slot:** turn [[ALGORITHM]] to *Empty slot*, one step before
Plate, or choose *(none)* in the list.

**To swap the two slots:** press [[SEL]] to pick up the chosen slot (its arrow
turns into an asterisk and [[SEL]] lights), turn [[SELECT]] to move it to the
other position, and press [[SEL]] again to put it down. The effects move with
their settings.

- An effect you put in a slot starts with its default settings, and the old
  effect's tail stops at once.
- The same effect can sit in both slots, each with its own settings.
- Changing the sound engine keeps both effects and their settings.

In the desktop tools, `--fx` adds effects in the order you give them, and
each `--fx-param` sets a parameter of the effect before it
([chapter 2](02-getting-started.md#the-desktop-tools)). There you can chain
more than two.

!!! note "Memory"
    The engine and both effects have to fit in the FM-1's memory. The
    simulator measures them against about 379 KB, the room M-VAVE's firmware
    leaves free on the FM-1, as an estimate of what Lunar Modulator will have
    there ([chapter 12](12-specifications.md)). The bottom bar of the screen
    shows how much the current chain takes, and turns red when it is more.
    Most combinations fit; Shapes with PSX Verb and Plate together does not.
    The simulator plays such a chain anyway, so that you can hear it.

!!! note "Rates"
    The effects run at the output's rate. They were written for rates of
    about 48,000 samples a second, so at the FM-1's 44,118 their delays come
    out about 9 % longer, a slightly larger room, and their slow modulation
    about 8 % slower. Their decay times are corrected, and stay within a few per
    cent of the originals'. Crush, Fold, Echo, Tilt, Master Sat and EQ,
    written for Lunar Modulator, work out their frequencies and times from
    the output's rate, so they need no correction.

## Plate

{{status sim desktop planned}}

A plate reverb, from Mutable Instruments Rings: a dense, smooth tail that sits
behind the sound. It takes the sum of both channels in and returns a stereo
tail.

- **Mix** fades from the dry sound at the left to the reverb alone at the
  right.
- **Decay** sets how long the tail lasts.
- **Damping** darkens the tail as it decays: the higher, the darker.
- **Diffusion** smears the echoes into a smooth wash; lower values leave
  more distinct reflections. The default, 0.5, is the setting Rings itself
  uses.

!!! tip "Starting points"
    - **A small room:** Decay low, Mix about 0.2.
    - **A long plate for pads:** Decay high, Damping low, Mix about 0.4.
    - **A dark wash:** Decay high, Damping high, Mix towards the right.

{{engine-table plate}}

## Ensemble

{{status sim desktop planned}}

The ensemble from Plaits' string machine: a rich, swirling chorus that turns
one voice into many. It mixes three moving copies of the sound, swept by a
slow and a fast modulation.

- **Mix** blends in the effect. The dry sound never drops below half, so even
  at the right the original is still there.
- **Depth** sets how far the copies drift.
- **Width** spreads the effect across the stereo field. At the left both sides
  are the same, as in the original module; turn it up to widen a mono engine.

Ensemble has no tail: when the sound stops, so does the effect.

!!! tip "Strings and pads"
    Put Ensemble before Plate for string-machine pads, and keep Depth low for
    a subtle thickening of single notes.

{{engine-table ensemble}}

## Diffuse

{{status sim desktop planned}}

The diffuser from Plaits' particle model: a short, grainy reverb that blurs
attacks. It takes the sum of both channels in and returns a stereo result.

- **Mix** fades from the dry sound at the left to the effect alone at the
  right.
- **Time** sets how long the blur lasts.
- **Tone** darkens the effect: at the left only the lows remain, and at the
  right almost nothing is filtered. The default lets through everything up to about
  9.5 kHz.
- **Width** spreads the effect across the stereo field. At the left both sides
  are the same.

!!! tip "Softening attacks"
    Use Diffuse on percussion such as Sophie or Macro Heavy's drums, and in
    front of Plate to soften the start of each note before the long tail.

{{engine-table diffuse}}

## PSX Verb

{{status sim desktop planned}}

A reverb modelled on the sound chip of a well-known 1990s games console, by
Charles Vestal, from the Schwung community. Its six models range from a small
room to a hall and Space Echo.

- **Model** chooses the room: *Room*, *Studio S*, *Studio M*, *Studio L*,
  *Hall* or *Space Echo*. The default is Hall.
- **Decay** sets the length of the tail. In the middle it matches the
  original chip; to the left it is shorter, to the right longer.
- **Mix** fades from the dry sound at the left to the reverb alone at the
  right.
- **Level** sets how loud the reverb itself is.
- **Input**, on page 2, sets how hard the reverb is driven.

!!! note "Choosing the model"
    In FX mode, [[ALGORITHM]] changes the effect in the slot, not PSX Verb's
    model. To change the model, turn [[KNOB1]] on page 1.

PSX Verb takes about 131 KB of memory, the most of any effect.

{{engine-table sw-psxverb}}

## Crush

{{status sim desktop planned}}

A bitcrusher and sample-rate reducer, for the grit of early samplers and game
consoles. It holds each sample for a while and rounds it to a coarse step, so
the sound loses its top end in a shower of aliasing and its quiet detail in
buzz. Both channels are held at the same moments.

- **Bits** sets how fine the steps are, from 16, all but untouched, down to
  1. It turns smoothly between whole numbers, so it can sweep. Silence stays
  silent at any setting, but at very low Bits quiet sounds fall under the
  first step and drop out: at 1 bit only full-scale sound comes through.
- **Rate** sets how often a new sample is taken, from 100 times a second at
  the left to every sample at the right; the default is about 9,600. The
  scale is even in pitch, so each step of the knob sounds alike.
- **Jitter** makes each hold a little longer or shorter at random, which
  roughens the tone and smears the aliasing into noise. At the left every
  hold is the same length. The randomness repeats exactly each time the
  effect starts.
- **Mix** fades from the dry sound at the left to the crushed sound alone at
  the right, the default.
- **Tone**, on page 2, darkens the crushed sound: at the right nothing is
  filtered, at the left only the lows below about 150 Hz remain.
- **Level**, on page 2, sets how loud the crushed sound is, up to twice its
  level.

!!! tip "Starting points"
    - **Old sampler:** Bits 12, Rate about 0.8, Tone about 0.8.
    - **Broken game console:** Bits 4, Rate about 0.5, Jitter a little.
    - **Radio static:** Bits 2 to 3, Rate low, Jitter high, Mix about 0.5.
    - Turn the engine up rather than Level when low Bits makes a quiet
      sound vanish: the steps are fixed against full scale.

{{engine-table crush}}

## Fold

{{status sim desktop planned}}

A wavefolder, written for Lunar Modulator, after the folders of Serge and
Buchla synthesizers. It turns the sound up into a fold point and folds
whatever passes it back on itself, again and again, so a plain wave grows
bright, hollow, ringing overtones that move as the level changes. Each
channel is folded on its own.

- **Fold** sets how hard the sound is driven into the folds, from not at all
  at the left (a sound within full scale passes unfolded) to sixteen times
  at the right. The louder the note, the more it folds, so velocity and the
  engine's envelope shape the tone.
- **Symmetry** shifts the sound before it is folded. In the middle the folds
  are even; away from it they are lopsided and add a hollow, reedy colour,
  and at either end a quiet sound is folded on one side only.
- **Shape** chooses the fold: at the left sharp corners, bright and buzzy; at
  the right rounded ones, softer; in between a blend.
- **Mix** fades from the dry sound at the left to the folded sound alone at
  the right, the default.
- **Tone**, on page 2, darkens the folded sound, from about 200 Hz at the
  left to almost nothing filtered at the right.
- **Level**, on page 2, sets how loud the folded sound is.

Silence stays silent at any setting, and the knobs glide over a few
milliseconds, so turning them does not click. Fold is built to keep the harsh,
unrelated tones of a digital folder low, and it has no tail: when the sound
stops, so does the effect.

!!! tip "Starting points"
    - **West-coast lead:** a sine from Shapes or Macro, Fold about 0.6, Shape
      about 0.5, and play with velocity.
    - **Reedy bass:** Fold about 0.4, Symmetry about 0.4, Tone about 0.6.
    - **Movement:** put Ensemble or Echo after Fold, and sweep Fold slowly by
      hand while a note holds.

{{engine-table fold}}

## Echo

{{status sim desktop planned}}

A stereo echo, written for Lunar Modulator, whose repeats can bounce from one
side to the other. Up to about a third of a second the echoes are clean
copies; longer ones grow darker with each repeat, like those of an old
analogue echo pedal, so that the effect keeps to 64 KB of memory however long
the time.

- **Time** sets the delay, from 10 milliseconds at the left to one second at
  the right; the default is 300. Turning it while echoes sound bends their
  pitch, like changing a tape echo's speed.
- **Feedback** sets how many times the sound repeats, from a single echo at
  the left to a long, slowly fading trail at the right. It never runs away.
- **Ping-pong** at the right, the default, sends the repeats left, right,
  left; at the left each side echoes on its own side.
- **Mix** fades from the dry sound to the echoes. The dry sound stays at full
  level up to the middle and the echoes are at full level from the middle
  on, so the middle has both at full level.
- **Tone**, on page 2, darkens each repeat a little more than the one before:
  at the left the trail turns dull quickly, at the right it stays bright.
- **Wow**, on page 2, adds a slow wobble to the delay, like a worn tape; it
  sounds the same every time you play.
- **Level**, on page 2, sets how much of the sound goes into the echo. Turn
  it down to let the echoes ring on while what you play next stays dry.

!!! tip "Starting points"
    - **Slapback:** Time about 100, Feedback low, Ping-pong at the left, Mix
      about 0.3.
    - **Wide bounce:** Time about 300, Feedback about 0.5, Ping-pong at the
      right.
    - **Dub trail:** Time about 600, Feedback high, Tone about 0.3, Wow about
      0.3.

Echo does not yet follow the sequencer's tempo; set Time by ear.

{{engine-table echo}}

## Tilt

{{status desktop planned}}

A tilt equaliser, written for Lunar Modulator: one knob turns the whole sound
darker or brighter. Turned right, the highs rise and the lows fall by the
same amount; turned left, the reverse. One frequency, the pivot, keeps its
level, so the sound changes colour without getting much louder or quieter.
It suits the end of the chain, the second slot, where it shapes everything
before it.

- **Tilt** sets how far, up to 9 dB either way. In the middle, the default,
  the sound passes through untouched.
- **Pivot** sets the frequency that stays put, from 200 Hz to 5 kHz; the
  default is 1 kHz. Lower it to brighten or darken mostly the body of the
  sound, raise it to work mostly on the air at the top.
- **Curve** chooses the shape. *Shelf*, the default, turns quickly around
  the pivot and then levels off, like the treble and bass controls of an
  amplifier turned in opposite directions. *Slope* turns more gently and
  evenly across the whole range, for a subtler change of colour.
- **Level** sets the output level, from −24 dB to +12 dB, to make up for
  what a strong tilt adds or takes away.

Every control, Curve included, moves smoothly when you turn it, so Tilt
can be swept or modulated without clicks.

!!! tip "Starting points"
    - **Warm up a bright mix:** Tilt about −3, Curve Slope.
    - **Lift a dull pad:** Tilt about +4, Pivot about 2 kHz.
    - **Telephone-thin, for a break:** Tilt at the right, Pivot about
      3 kHz, Level down a few dB.

{{engine-table tilt}}

## Master Sat

{{status sim desktop planned}}

Gentle saturation for the whole mix, written for Lunar Modulator: the warmth
and density of a signal pushed a little too hard through analogue gear,
meant to be left on. Quiet passages pass through unchanged and only the loud
parts are rounded off. The bass and the top end can be kept out of it, so
the low end stays tight and the highs stay clear. It starts with **Mix** at
the left, where it changes nothing at all: turn Mix up to hear it.

- **Drive** sets how early the sound starts to bend, from barely, only the
  loudest peaks, at the left to well into it at the right. It does not make
  the sound louder: quiet notes keep their level.
- **Clean Lo** keeps the bass below it out of the saturation, from 20 Hz to
  300 Hz. Higher settings keep the kick and the bass line clean and stop them
  from muddying everything else, and Glue does not react to them.
- **Glue** turns the whole sound down a little when the saturation works
  hard, up to about 6 dB, and lets it back up over a fraction of a second,
  like a bus compressor. It holds a mix together and keeps loud passages from
  turning harsh. At the left it does nothing.
- **Mix** fades from the dry sound at the left, the default, to the
  saturated sound alone at the right.
- **Shape**, on page 2, chooses the curve: Smooth, the default, bends
  gradually; Dense bends sooner and holds the peaks lower, for a thicker,
  more compressed sound. Changing it fades from one to the other in a few
  milliseconds, so it can be switched while playing.
- **Asymmetry**, on page 2, makes one side of the wave bend before the
  other, which adds a warmer, rounder colour of even harmonics. In the
  middle, the default, both sides bend alike.
- **Clean Hi**, on page 2, keeps the highs above it out of the saturation,
  from 1 kHz to 20 kHz; the default is 6 kHz. Lower settings keep cymbals
  and the top of the sound crisp; at the right almost everything is
  saturated.
- **Level**, on page 2, sets how loud the saturated sound is, from 12 dB
  down to 12 dB up.

Silence stays silent at any setting, and the knobs glide over a few
milliseconds, so turning them does not click. Master Sat is built to keep
the harsh, unrelated tones of digital distortion very low at moderate
settings; with Drive near the right, Clean Hi is what keeps them down.

!!! tip "Starting points"
    - **Warmth:** Mix at the right, Drive about 6, Glue about 0.25.
    - **Glue a mix together:** Drive about 9, Glue about 0.6, Clean Lo about
      120, Clean Hi about 5,000.
    - **Driven and dense:** Shape Dense, Drive about 14, Asymmetry about 0.4,
      and Level up a little to make up for Glue.
    - Master Sat belongs last, or just before a reverb, in the second slot.

{{engine-table sat}}

## EQ

{{status sim desktop planned}}

A three-band equaliser, written for Lunar Modulator: a low shelf, a bell in
the middle and a high shelf, one page each, then an output level. Use it to
shape one sound, or in the second slot as a tone control for everything
before it. The bands run one after the other, on both channels alike.

- **Low Freq**, **Low Gain** and **Low Q** shape the bass. Low Gain raises or
  lowers everything below Low Freq, by up to 15 dB either way; at Low Freq
  itself the change is half as much. Low Q sets how sharply the shelf turns:
  at 0.71, the default, as steeply as it can without overshooting; higher,
  a bump and a dip appear either side of Low Freq; lower, the change spreads
  over a wider range.
- **Mid Freq**, **Mid Gain** and **Mid Q**, on page 2, boost or cut a band
  around Mid Freq, anywhere from 20 Hz to 18 kHz. Mid Gain is the change at
  Mid Freq itself. Mid Q sets the width, from wide at the left to narrow at
  the right; a cut is as narrow as a boost.
- **High Freq**, **High Gain** and **High Q**, on page 3, do for the treble,
  above High Freq (1 to 18 kHz), what the Low knobs do for the bass.
- **Level**, on page 3, raises or lowers the result by up to 15 dB, to make
  up for boosts and cuts.

With every Gain and Level at 0, the default, EQ leaves the sound exactly as it
is. The knobs glide over a few milliseconds and the bands are built to be
swept, so turning a knob does not click, even quickly. EQ has no tail beyond
the ring of a narrow band.

!!! tip "Starting points"
    - **Warmth:** Low Freq about 120, Low Gain about +4.
    - **Presence:** Mid Freq about 3,000, Mid Gain about +4, Mid Q about 1.
    - **Air:** High Freq about 10,000, High Gain about +5.
    - **Find a ring:** Mid Gain at +15 and Mid Q near 10, sweep Mid Freq until
      the ring jumps out, then turn Mid Gain down to about −10.

{{engine-table eq}}

## Test Gain

{{status sim desktop}}

Test Gain multiplies the sound by **Gain**, from silence at 0 through
unchanged at 1 to twice the level, 6 dB up, at 2. It exists to test the effect chain and
the limiter.

{{engine-table test-gain}}

## The limiter

{{status sim desktop planned}}

Last in the chain, the limiter keeps the output just below full scale, so a
twelve-note chord cannot clip however its notes add up.

- A single voice passes untouched.
- When the sum gets louder than 0.98 of full scale, about 0.2 dB below it,
  the limiter turns it down at once, and lets it recover over about a tenth
  of a second.
- It also protects your ears and equipment from faults: a sample that is not
  a number becomes silence, and a wildly large one is clamped and holds the
  output down briefly instead of passing through.

[[MASTER]] comes after the limiter and only turns the result down. The level
meter in the screen's top bar shows the output before [[MASTER]], and turns
red when the limiter is close to working.

!!! tip "When you can hear the limiter"
    Dense chords at a high engine Volume can make the limiter duck: the
    whole sound dips as new notes come in and swells back. If the level meter
    turns red often, lower the engine's Volume, not [[MASTER]].

{{engine-others audio_fx}}
