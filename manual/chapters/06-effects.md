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
*Empty slot*, Plate, Ensemble, Diffuse, PSX Verb and Test Gain, and round
again. In the simulator you can also use the **Effect 1** and **Effect 2**
lists under the panel.

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
cent of the originals'.

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
