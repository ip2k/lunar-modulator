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
*Empty slot*, Plate, Ensemble, Diffuse, PSX Verb, Crush, Fold, Drive, Echo,
Filter, Comp, Limiter, Room, Hall and Test Gain, and round again. In the
simulator you can also use the **Effect 1** and **Effect 2** lists under the
panel.

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
    cent of the originals'. Crush, Fold, Drive, Echo, Filter, Comp, Limiter
    and Hall, written for Lunar Modulator, work out their frequencies and
    times from the output's rate, so they need no correction.

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

## Drive

{{status sim desktop planned}}

Overdrive and saturation, written for Lunar Modulator: the sound is turned
up into a curve that flattens its peaks, from a gentle warmth to a buzzing
fuzz. Each channel is shaped on its own.

- **Type** chooses the curve. Changing it fades from one to the next in a
  few milliseconds, so it does not click, even when the sequencer or a
  modulation source changes it on every step.
    - **Soft:** smooth, rounded saturation, the most even-tempered.
    - **Tube:** lopsided, so it adds a warm second harmonic even when barely
      driven, and squashes one side of the wave before the other.
    - **Diode:** clean up to a point, then a firmer knee, like the clipping
      diodes in an overdrive pedal.
    - **Fuzz:** a hard clip with corners, lopsided and with a little gate of
      its own, so decaying notes break up and sputter.
    - **Tape:** gentle, with more headroom; loud high notes and bright
      sounds saturate first and come out softened.
- **Drive** sets how hard the sound is driven, from −12 dB at the left
  (nearly clean) to +36 dB at the right. Louder notes are driven harder, so
  velocity and the engine's envelope change the tone.
- **Tone** tilts the driven sound: in the middle it is left alone, to the
  left the highs are cut (darker, less fizz), to the right the lows (thinner,
  brighter).
- **Mix** fades from the dry sound at the left to the driven sound alone at
  the right, the default. In between, the dry sound keeps its punch under
  the drive.
- **Bias**, on page 2, makes the clipping uneven, which adds a hollow,
  reedy colour; in the middle the curve is used as it is.
- **Gate**, on page 2, makes the quietest part of each wave drop out, from
  nothing at the left to a lot at the right: a crackle on every Type, and
  on Fuzz the starved, sputtering sound of a fuzz with a dying battery. More
  Drive lets more of the sound through.
- **Level**, on page 2, sets how loud the driven sound is, from −24 to +12 dB.
- **Auto**, on page 2, is on by default: it keeps the driven sound about as
  loud as the dry sound whatever Drive and Type are, so turning Drive
  changes the character and not the volume. Turn it off to let Drive make
  the sound louder too, as on a pedal.

Silence stays silent at any setting, and the knobs glide over a few
milliseconds, so turning them does not click. Drive is built to keep the
harsh, unrelated tones of a digital clipper low, and it has no tail: when
the sound stops, so does the effect.

!!! tip "Starting points"
    - **Warm bass:** Tube, Drive about +12 dB, Tone a little left of the
      middle.
    - **Lead:** Diode, Drive +24 dB, Tone about 0.4, then a little Echo.
    - **Broken fuzz:** Fuzz, Drive +24 dB, Gate about 0.4, Bias a little off
      the middle, and play notes that decay.
    - **Tape glue:** Tape, Drive about +18 dB, Mix about 0.6, on chords.

{{engine-table drive}}

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

## Filter

{{status sim desktop planned}}

A filter with seven characters in one, written for Lunar Modulator. It takes
away part of the sound's spectrum, the highs, the lows or a band, and as
Resonance rises it rings at the cutoff, up to a whistle of its own. Each
channel is filtered on its own, so Morph can pull them apart.

- **Type** chooses the filter. Changing it starts the new one quietly in
  the background, then fades over to it, all within about 10 milliseconds,
  so it does not click, even when the sequencer or a modulation source
  changes it on every step.
    - **SVF:** a clean state-variable filter. Mode picks low-pass, band-pass,
      high-pass or notch.
    - **Ladder:** the classic four-stage ladder, the default: round and
      thick, and its bass holds as Resonance rises. Mode picks how steep it
      is, from 24 dB per octave down to 6.
    - **Diode:** a diode ladder in the style of the TB-303: rubbery and
      squelchy at high Resonance. Mode as for Ladder.
    - **Sallen-Key:** a Sallen-Key filter, after the Korg-35 filter of the
      later MS-20: bright and aggressive, it screams as Resonance rises.
      Mode picks low-pass, band-pass, high-pass or notch.
    - **SK Mixed:** a mixed-input Sallen-Key, after the Steiner-Parker
      Synthacon's filter: gritty and uneven. Mode picks which input the
      sound goes into: low-pass, band-pass, high-pass, or a notch.
    - **Comb:** a short echo tuned by Cutoff, which makes metallic,
      flanger-like peaks or notches at the multiples of that pitch. Mode
      goes from peaks at the left to notches at the right; Morph sets their
      polarity: at the left they sit on Cutoff's harmonics, at the right
      the sound turns hollow and an octave lower.
    - **Formant:** the vowels A, E, I, O and U, as a voice shapes them.
      Morph sweeps through the vowels; Mode picks the voice, a man's at the
      left, a woman's in the middle, a child's at the right; Cutoff shifts
      the vowels up or down; Resonance makes them narrower and more vocal.
- **Cutoff** sets where the filter works, from 20 Hz to 18 kHz; the default
  is 2 kHz. When a filter rings on its own, it rings at this pitch.
- **Resonance** emphasises the sound around Cutoff. Near the right, from
  about 0.93, SVF, Ladder, Diode, Sallen-Key and SK Mixed whistle on their
  own, in tune with Cutoff (SK Mixed a little flat). On Comb it sets how
  long the echo rings; on Formant, how narrow the vowels are.
- **Drive** pushes the sound into the filter's saturation: quiet sounds come
  up to 12 dB louder, loud ones thicken and grit.
- **Mode**, on page 2, changes the response as each Type above describes.
  It turns smoothly: between two positions you hear a blend of both.
- **Morph**, on page 2, spreads the two channels for SVF, Ladder, Diode,
  Sallen-Key and SK Mixed: at the right, the left channel's cutoff is up to
  an octave lower and the right's an octave higher. On Comb and Formant it
  does what their entries above say.
- **Mix**, on page 2, fades from the dry sound at the left to the filtered
  sound alone at the right, the default.
- **Level**, on page 2, sets the filtered sound's level, up to twice
  (6 dB) at the right.

Silence stays silent at any setting, even with a filter ringing, and the
knobs glide over a few milliseconds, so turning them does not click.

!!! tip "Starting points"
    - **Acid bass:** Diode, Cutoff about 400 Hz, Resonance about 0.8, Drive
      about 0.5, low notes, and turn Cutoff while they play.
    - **Talking pad:** Formant, Resonance about 0.6, and sweep Morph slowly.
    - **Screaming lead:** Sallen-Key, Resonance about 0.9, Drive about 0.3.
    - **Metallic ring:** Comb, Cutoff on the note you play, Resonance about
      0.8.
    - **Wide sweep:** Ladder, Morph about 0.3, and sweep Cutoff.

{{engine-table filter}}

## Comp

{{status sim desktop planned}}

A compressor, written for Lunar Modulator. When the sound gets louder than a
threshold, Comp turns it down, so loud and quiet notes sit closer together:
drums hit harder and hang together, chords sustain evenly, a bass line
stays steady. Both channels are turned down together, so the stereo picture
does not move.

- **Threshold** sets the level above which Comp starts to work, from −60 dB
  at the left to 0 dB, full scale, at the right. The lower it is, the more
  of the sound is compressed.
- **Ratio** sets how hard. At 4, the default, every 4 dB that the sound
  rises past the threshold comes out as 1 dB. It goes from 1 (no
  compression) to 20, and at 21, the far right, nothing gets past the
  threshold at all: Comp becomes a limiter.
- **Attack** sets how quickly Comp reacts, from at once at 0 to 100
  milliseconds. A slower attack lets the start of each note or hit through
  before the sound is turned down, which keeps it punchy.
- **Release** sets how quickly the sound comes back up once it gets
  quieter, from 10 milliseconds to 2 seconds. Short releases pump with the
  rhythm; long ones hold the level steady.
- **Knee**, on page 2, softens the threshold. At 0 the compression starts
  all at once; the higher the knee, the more gently it eases in, over that
  many dB around the threshold.
- **Makeup**, on page 2, turns the result up, or down, by up to 24 dB, to
  win back the level the compression took.
- **Mix**, on page 2, blends the untouched sound back in. At the right, the
  default, you hear only the compressed sound; in between is parallel
  compression, where the dry sound's hits ride on the compressed sound's
  body.
- **Character**, on page 2, chooses how Comp listens and reacts:
    - **Peak** reacts to every peak: precise, for taming hits and for
      limiting.
    - **RMS** reacts to the average loudness, which is gentler and closer
      to how loud the sound seems.
    - **Glue** listens like RMS, but more slowly, lets go more smoothly and
      has a softer knee: for holding chords or a whole part together.
    - **Punch** reacts to peaks but eases into each one, so the front of
      every hit gets through before Comp clamps down.
- **Auto Rel**, on page 3, makes the release follow the music. After a
  short peak the sound comes back quickly; after a long loud passage,
  slowly. Short hits leave no holes and long notes do not pump.
- **Auto Gain**, on page 3, sets the makeup for you, so that a sound at
  full scale stays at full scale however Threshold, Ratio and Knee are set,
  up to 24 dB of it: past that, at very low thresholds and high ratios,
  the sound comes out quieter. It never pushes a sound past full scale:
  even the start of a hit, before Attack has caught up, is turned down
  just as far as the compression would turn it down once settled, so a
  sound that does not pass full scale on the way in does not pass it on
  the way out. Where it has to do that it rounds the peaks of the wave
  off, a little like a soft clip, so with a slow Attack the starts of
  notes can sound slightly grittier; a shorter Attack, or the Limiter for
  a clean ceiling, avoids it. Makeup then adds to it or takes from it; with
  Makeup above 0 the output can pass full scale by that much.

Silence stays silent at any setting, and the knobs glide over a few
milliseconds, so turning them does not click; changing Character, Auto Rel
or Auto Gain while Comp is working does not jump either, so the sequencer
and modulation sources can change them on every step.

!!! tip "Starting points"
    - **Tighter drums:** Peak, Threshold about −20, Ratio 4, Attack about
      10, Release about 100, Auto Gain on.
    - **Smooth pad:** Glue, Threshold about −24, Ratio 2 to 3, Attack about
      30, Release about 400, Auto Rel on.
    - **Parallel punch:** Punch, Threshold about −35, Ratio 8, Mix about
      0.5, then Makeup to taste.
    - **Brick wall:** Peak, Ratio 21, Attack 0, Release about 50, the
      threshold just under the loudest peaks.

Comp listens only to the sound passing through it. Making one sound duck
under another (a sidechain) may come later.

{{engine-table comp}}

## Limiter

{{status sim desktop planned}}

A look-ahead brickwall limiter, written for Lunar Modulator, for the whole
sound (in the second slot) or to tame one effect's peaks. It sees peaks a
few milliseconds before they arrive and turns the sound down just in time,
so nothing passes its ceiling, and it leaves anything quieter untouched.

- **Ceiling** is the most the output reaches, from −24 dB at the left to
  0 dB, full scale, at the right; the default is −1 dB.
- **Drive** turns the sound up into the limiter, by up to 24 dB, for a
  louder, denser sound; to the left of 0 it turns the sound down.
- **Release** sets how quickly the sound comes back up after a peak, from
  1 millisecond to 1 second; the default is 100 milliseconds. Short releases
  are louder but can pump or distort low notes; long ones are smoother.
- **Lookahead** sets how far ahead the limiter looks, from 0 to
  5 milliseconds; the default is 2. The sound is delayed by as much. At 0
  there is no delay, and the limiter catches the front of each peak with a
  gentle soft clip instead.
- **Mode**, on page 2, chooses how peaks are handled:
    - **Brickwall** turns them down, so nothing passes the ceiling and
      nothing below it is changed.
    - **Soft Clip** lets them run into a curve that rounds them off just
      under the ceiling: louder and warmer, with some added harmonics.
- **Link**, on page 2, at the right, the default, turns both channels down
  together, so the stereo picture holds. At the left each channel is limited
  on its own: louder, but a peak on one side can shift the picture.
- **Mix**, on page 2, blends the untouched sound back in (parallel
  limiting). Below the right end, the output can pass the ceiling.

Turning Lookahead fades from the old delay to the new, and switching Mode
fades too, so neither clicks, even when the sequencer or a modulation
source changes them on every step; the ceiling holds throughout. The other
knobs glide over a few milliseconds.

!!! tip "Starting points"
    - **Safety on the whole sound:** in the second slot, Ceiling −1 dB, the
      rest at their defaults.
    - **Louder:** Drive +6 to +9 dB, Release about 60 milliseconds.
    - **Warm and loud:** Soft Clip, Drive about +6 dB, Lookahead 0.

The limiter at the very end of the chain ([below](#the-limiter)) stays in
place. With Ceiling at −0.2 dB or lower and nothing louder after it, it has
nothing left to do.

{{engine-table limit}}

## Hall

{{status sim desktop planned}}

A stereo hall reverb, written for Lunar Modulator: a large, smooth space
whose tail can ring from a fraction of a second to twenty seconds, or be
frozen and held. It takes 49 KB of memory, three quarters of Plate's.

- **Decay** sets how long the reverb rings, from 0.2 seconds at the left to
  20 seconds at the right; the default, 2 seconds, is a concert hall. Size
  does not change it.
- **Size** sets how large the hall is: at the left a small room whose first
  reflections come quickly, at the right a large hall. Turning it while the
  reverb rings bends the pitch of the tail.
- **Damping** makes the high frequencies die away faster than the low ones,
  as they do in a real room: at the left the tail stays bright, at the
  right it turns dark quickly.
- **Mix** fades from the dry sound to the reverb. The dry sound stays at
  full level up to the middle and the reverb is at full level from the
  middle on.
- **Pre-delay**, on page 2, waits up to 150 milliseconds before the reverb
  starts, which keeps the attack of a note clear of it; the default is 20.
- **Diffusion**, on page 2, at the left lets the first reflections through
  as separate echoes; at the right they blur into a smooth wash.
- **Mod**, on page 2, gently moves the reverb's internal delays, like a
  slow chorus. It keeps long tails from sounding metallic; turn it down for
  a stiller, purer tail. It sounds the same every time you play.
- **Freeze**, on page 2, holds the reverb as it is, for as long as it stays
  on, and lets nothing new in: play over a frozen chord. Off lets it fade
  away. It switches without a click, so once the sequencer and modulation
  reach the effects, they will be able to turn it on and off in time.
- **Width**, on page 3, narrows the reverb from wide stereo at the right to
  mono at the left.
- **Low Cut**, on page 3, keeps the bass out of the reverb, so a bass line
  or a kick stays tight while everything else rings.

!!! tip "Starting points"
    - **Concert hall:** the defaults.
    - **Big, dark ambience:** Decay about 0.8, Size at the right, Damping
      about 0.7, Mod about 0.5, Mix about 0.5.
    - **Small, bright room:** Decay about 0.2, Size at the left, Damping
      low, Diffusion at the right.
    - **Drone pad:** play a chord, turn Freeze on, then play over it.

{{engine-table hall}}

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

For a ceiling of your own, lookahead or a softer clip, put the
[Limiter](#limiter) effect in a slot.

[[MASTER]] comes after the limiter and only turns the result down. The level
meter in the screen's top bar shows the output before [[MASTER]], and turns
red when the limiter is close to working.

!!! tip "When you can hear the limiter"
    Dense chords at a high engine Volume can make the limiter duck: the
    whole sound dips as new notes come in and swells back. If the level meter
    turns red often, lower the engine's Volume, not [[MASTER]].

{{engine-others audio_fx}}
