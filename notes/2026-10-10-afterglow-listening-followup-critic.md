# Afterglow listening follow-up: source diagnosis

This is a focused instrument, effect and groove review following owner listening feedback, **not a sixth musical scoring round**. The five-round scores remain unchanged. Baseline project: `3e6eaa5fea7a38822b60a2a742af4b932856b8cc`. No by-ear listening by this critic is claimed.

[reported] The owner describes the baseline as shrill/discordant, excessively reverberant and mechanically repetitive, with an unwanted older keyboard character; lowering Hall Mix to 0.05 during playback sounded substantially better to the owner. That observation is the listening evidence; the following are independently inspected source mechanisms, not measured perceptual causality.

## Sound-generation findings

- [verified] Chord slot 3 uses Macro VA Pair with Harmonics 0.35, Timbre 0.38, Morph 0.5, Decay 0.68, no insert filter. `engines/third_party/mutable/plaits/dsp/engine/virtual_analog_engine.h:36` selects `VA_VARIANT 2`; `engines/src/mi_macro.cc` consumes the engine’s main `out` signal. `ComputeDetuning(0.35)` yields approximately −7.2564 semitones for its saw oscillator. Every written chord tone therefore includes an additional pitch that is neither unison nor an octave. [inferred] MIDI chord correctness alone cannot establish the resulting harmony; this is a credible source of the reported discordance.
- [verified] Envelope module 3 routes to chord Timbre at amount 40. The modulation range rule permits a full envelope to add 0.4, taking base 0.38 to 0.78. Variant 2 introduces square-oscillator hard sync above Timbre 0.5; its sync offset formula `(Timbre − .5)^2 * 4 * 48` reaches approximately 15.05 semitones at 0.78. This parameter does not simply move a low-pass cutoff. [inferred] An explicit filter envelope is a more controllable route to warm chord motion.
- [verified] Baseline Hall is master-wide: Mix 0.20, Decay 0.68, Size 0.76. The DX7 lead and all percussion also reach it. [inferred] Start the revision at the owner-tested Mix 0.05, then assess shorter decay/size with the owner; adding less reverb alone does not repair oscillator tuning.
- [verified] The baseline drum slot uses Punch with Kit Decay 0.42 and inherited per-pad parameters: snare MIDI 38 Tune +3, Decay 0.58; closed hat MIDI 42 Tune +7, Decay 0.70. `engines/src/drums.cc` ignores note-offs and lets hits ring for their pad decay. Four-tick hat events do not imply four-tick sounding hats. [inferred] Revoice individual pads as well as selecting a kit; shorten/darken the hat through its actual pad parameters rather than event gates.

## Groove findings

[verified] Ordinary chill bars put kicks at steps 0/8, snares 4/12 and hats 2/6/10/14, with recurring hat velocities 72/53. `sq_swing_delay` in `engines/seq/seq_clip.c` applies delay only to odd real sixteenth anchors at normal clip scale. These ordinary drum steps are all even, so swing 56 does not change their timing. Quantize 0 preserves explicit tick deviation, while playback still adds anchor swing; the fifth serialized event field is the step anchor. Odd-step pickups receive swing, so explicit offsets must account for it rather than adding the desired total lateness twice.

[inferred] A focused revision should compose a stable two- or four-bar drum phrase, retain a recognizable backbeat, use a restrained low-velocity ghost or anticipatory kick, vary selected hats and leave purposeful gaps. A small explicit late snare offset can create a consistent pocket. Variation should support the bass and phrase endings; random timing or a fill on every bar is not required. At 92 BPM/96 PPQN, one tick is about 6.79 ms, so even a two-tick offset is meaningful.

## Review responsibility and next checkpoint

[verified] Earlier reviews inspected written pitches, gates, routing and stored sound parameters but did not trace this patch’s model-specific oscillator transfer functions. They therefore missed this audible-harmony risk. This follow-up corrects that coverage gap and does not retrospectively claim listening acceptance.

[verified] Shared Rarefaction/Serena roots remain subject to the concurrent-session restriction documented in the critic ledger; no shared server was retargeted. Source paths and exact saved project are the authority for this bounded follow-up. The existing approved music skills remain advisory. No asset or engine code was edited by the critic.

Pending: writer’s frozen focused Afterglow revision. Inspect emitted instrument parameters, actual effect/route state, drum pad settings and rendered firing ticks; check the other three assets remain outside the revision. Runtime receipts and owner listening remain separate from source acceptance.
