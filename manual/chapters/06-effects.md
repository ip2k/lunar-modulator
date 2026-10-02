# Effects

After the sound engine, the sound passes through two effect slots and then
the firmware's limiter. Each slot holds one effect, or nothing. Press [[FX]]
to see the chain: [[SELECT]] chooses a slot, [[ALGORITHM]] the effect in it,
and the knobs its parameters. To swap the order of the two slots, press
[[SEL]], move the slot with [[SELECT]], and press [[SEL]] again.

{{engine-summary audio_fx}}

## The effect chain

{{status sim desktop planned}}

The simulator starts with Plate in the first slot and the second slot empty.
An effect processes everything before it: the engine, then the first slot,
then the second. A reverb after a chorus sounds different from a chorus after
a reverb.

!!! outline "To be written"
    - Emptying a slot, and how a chain is kept when you change the engine.
    - Memory: the engine and the two effects share the RAM the FM-1 has free
      (about 379 KB); the global page shows how much a chain takes. Large
      combinations (Shapes with PSX Verb and Plate) may not fit on the
      device.
    - Effects in the desktop renderer: `--fx ID --fx-param NAME=VALUE`, in
      chain order.

## Plate

{{status sim desktop planned}}

A plate reverb from Mutable Instruments Rings: a dense, smooth tail that sits
behind the sound.

- **Mix** fades from the dry sound to the reverb alone.
- **Decay** sets how long the tail lasts.
- **Damping** darkens the tail as it decays.
- **Diffusion** smears the echoes into a smooth wash; lower values leave
  more distinct reflections.

!!! outline "To be written"
    - Starting points: a short room (Decay low, Mix 0.2), a long plate for
      pads, a dark ambient wash.

{{engine-table plate}}

## Ensemble

{{status sim desktop planned}}

The ensemble from Plaits' string machine: a rich, swirling chorus that turns
one voice into many.

- **Mix** blends in the effect; the dry sound never drops below half.
- **Depth** sets how far the copies drift.
- **Width** spreads them across the stereo field.

!!! outline "To be written"
    - Tips: Ensemble before Plate for string pads; low Depth for a subtle
      thickening of single notes.

{{engine-table ensemble}}

## Diffuse

{{status sim desktop planned}}

The diffuser from Plaits' particle model: a short, grainy reverb that
blurs attacks.

- **Mix** fades from the dry sound to the effect alone.
- **Time** sets how long the blur lasts.
- **Tone** darkens the effect.
- **Width** spreads it across the stereo field.

!!! outline "To be written"
    - Tips: Diffuse on percussion (Sophie, Macro Heavy's drums), and as a
      softener before Plate.

{{engine-table diffuse}}

## PSX Verb

{{status sim desktop planned}}

A reverb modelled on the sound chip of a well-known 1990s games console, by
Charles Vestal, from the Schwung community. Its six models range from a
small room to a space echo.

- **Model** chooses the room; [[ALGORITHM]] steps through the models when
  the slot is selected.
- **Decay**, **Mix** and **Level** set the tail, the blend and the output.
- **Input**, on the second page, sets how hard the reverb is driven.

!!! outline "To be written"
    - What each model sounds like, and where it suits.
    - Memory: PSX Verb takes about 131 KB, the most of any effect.

{{engine-table sw-psxverb}}

## The limiter

{{status sim desktop planned}}

Last in the chain, the limiter keeps the output below full scale, so a
twelve-note chord cannot clip the output however the notes add up. A single
voice passes untouched. When the sum gets too loud, the limiter turns it
down at once and lets it recover over about a tenth of a second.

The limiter also protects your ears and equipment from faults: a sample that
is not a number becomes silence, and a wildly large one holds the output down
briefly instead of passing through. [[MASTER]] comes after the limiter and
only turns the result down.

!!! outline "To be written"
    - When you can hear the limiter working (dense chords at full Volume)
      and what to do about it: lower the engine's Volume, not [[MASTER]].

{{engine-others audio_fx}}
