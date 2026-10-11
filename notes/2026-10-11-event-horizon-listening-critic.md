# Event Horizon: owner listening revision and independent source review

## Owner brief

[reported] The owner heard the previous Event Horizon and found its main synth too similar to Afterglow, Hall too wet, S3 busy/shrill, the hook unclear and the intro uninteresting. Requested direction: S3 **Trio / Saw x3** with a note-triggered envelope opening the filter; S4 **Acid Bass / Square**, with longer sustain/release; drums approximately 60% of the earlier level, hats quieter still. This listening feedback supersedes prior paper scores as musical acceptance. No sixth numeric review round is started.

[verified] Official YouTube oEmbed returned these titles for the supplied references on 2026-10-11:

- [Disclosure — You & Me (Flume Remix)](https://www.youtube.com/watch?v=OUkkaqSNduU), Flume channel.
- [San Holo — Light](https://www.youtube.com/watch?v=ULHeRdgeT54), Trap Nation channel.
- [The Chainsmokers — Closer ft. Halsey](https://www.youtube.com/watch?v=PT2_F-1esPk), ChainsmokersVEVO.
- [Louis The Child — It's Strange feat. K.Flay](https://www.youtube.com/watch?v=rhrqbcufZXo), Ultra Records.

[verified] These are metadata identifications, not auditory analysis. Three direct web opens failed; the fourth exposed a title but no usable audio. No audio perception is available here. Do not infer arrangement, instrumentation or a successful auditory match from video metadata. Use original notes/assets and retain the owner's reference intent in the audition brief.

## Engine behavior checked before composition

[verified] `engines/src/felucca_shim.cc:199` exposes Trio Wave `Saw x3`, oscillator intervals, Detune, filter Mode/Cutoff/Resonance, Env Amt and an actual per-voice Attack/Decay/Sustain/Release envelope. Positive Env Amt opens the filter according to that envelope. The wrapper maps percentage to a signed -64..63 amount; `engines/src/felucca_bridge.c:237` adds `(env * fenv) >> 7` to that voice's cutoff. This is per-note behavior, not a shared global filter sweep. Note-on starts/retriggers the voice; note-off releases it. The same internal ADSR also controls amplitude, so a slower filter attack changes articulation too.

[verified] Trio adds an extra envelope-driven filter accent when velocity exceeds 110 (`felucca_bridge.c:238`). Keep this deliberate, particularly when the owner's complaint is shrill peaks. Default Int 2 is 0 and Int 3 is -12 semitones; selecting Saw x3 alone does not imply three unison oscillators. Choose intervals explicitly and inspect the resulting chord pitches/tails.

[inferred] Start with the built-in per-note envelope when its amplitude/filter coupling suits the phrase. If independent filter timing is necessary, inspect an external Envelope routed per voice to `snd3.Cutoff`, with the appropriate sound-specific note gate and `voice:true`; do not substitute a globally retriggered rack envelope for independent chord-voice articulation. Shorter/sparser chord figures and a lower base cutoff can address density and brightness directly; merely changing the oscillator label cannot.

[verified] `engines/src/acid_bass.cc:116` exposes **no Sustain or Release controls**. Its Decay parameter maps to the filter-envelope decay, 200–2000 ms. Vendored `engines/third_party/fm1-x0x/dsp/bass303.c:281` fixes the gated amplitude RC decay at 1230 ms and post-gate release RC constants at 1 ms normal / 50 ms accented. These are exponential constants, not times to silence. Note-off sets gate low. Longer sequencer gates can extend held sound, but cannot create a user-selected post-note-off release. Increasing Decay must not be described as implementing amplitude sustain/release.

[verified] Acid Bass is monophonic. Overlapping held notes trigger slide/legato; releasing the current note can return to the latest held key. Velocity >=100 selects accent. A chord-shaped lead clip is therefore not a polyphonic Square lead: explicitly author one melodic line and inspect overlaps. Requested longer release remains a genuine capability gap pending an engine change or an explicitly described approximation. An echo tail is a repeated effect tail, not an amplitude release.

## Review targets and handoff

[inferred] The rewrite needs a foreground motif stated early enough to identify the song, a clear division between Trio chord punctuation and Acid melody, and a drop return whose contour can be recognized without relying on wet effects. Check actual notes, chord qualities, rhythm/gates, register, envelope behavior, automation and scene repeats. “60% drums” should name the changed gain layer and preserve backbeat hierarchy; lowering hats separately must not accidentally suppress the kick/snare identity.

[verified] These findings were sent to writer `/root/remaining_work` and parent `/root` before the draft freeze. Writer owns assets; critic owns this report. Frozen rewrite and exact runtime evidence are pending after the Afterglow runtime check. Every new asset must retain its own source identity and fresh native/Wasm/browser evidence. Musical approval remains the owner's audition.

[verified] Semantic navigation was checked without retargeting shared tools: Rarefaction selects the primary checkout and warns of missing compile database; its bounded Acid Bass position query returned no useful references, despite the registry/function-pointer caller visible in source. Serena returned the actual `Instance::NoteOff` implementation, including final-key `bass303_note_off`. Both are shared primary-root views, not proof of writer-worktree state. Relevant source inspection supplies the fallback; no shared session was activated or restarted.
