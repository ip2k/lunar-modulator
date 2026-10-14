# Event Horizon Trio live-note path

## Scope and source identity

[verified] This is an offline source review of the installed image source commit `43a5a8d77721e58011a00cec782cb64df73a9f86`, using the retained Event Horizon project profile at `engines/state/examples/replacement-showcases/event-horizon-showcase.lunar` (SHA-256 `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f`). The relevant app, project startup, MIDI filter, MFX host, HAL and ADC files are unchanged through `76dcf4afe53b0f784cb4b916e7dd978eb687dfb7`; the only relevant-path diff is the diagnostic footer addition in `firmware/native/app_probe.c`. This note does not use a new build or any device interaction. The shared Rarefaction/Serena project selectors point to the Mac authority, so I used direct inspection of the exact Hera Git tree instead of retargeting either shared server.

## Finding

[verified] In the profile, sound index 2 is `trio`, selected by `session.current: 2`. Its sound level is 70/100, its Trio `Volume` is 0.62, both inserts are null, and its only MIDI effect is `arp` with `on: false` (profile lines 9–14, 291–345). The master Hall mix is 0.05 and the limiter has zero drive; the modulation rack has no cables (lines 402–429, 446–519). These settings contain no intentional zero-level or modulation route for the selected sound.

[verified] Project startup restores the sound levels/current sound and applies the project MFX on/off flags (`firmware/native/project_boot.c:115–124`, `firmware/native/project_start.c:70–95,198–262`). `fm1_mfx_active()` returns false unless a slot has both an effect and `on` set (`engines/seq/mfx_host.c:40–52`). `fm1_mfx_live_note()` therefore returns false for this Trio; `play_on()` then calls the sound engine's `note_on` directly (`sim/web/src/fm1_app.c:1520–1543`). This route does not depend on transport running. `fm1_app_note_on()` calls `play_on()` for the selected sound before the sequencer UI handling (`sim/web/src/fm1_app.c:1613–1623`). With the saved profile, the Trio arp cannot capture or delay live notes while transport is stopped.

[verified] The native USB-MIDI poll accepts note-on/off messages matching `app.settings.midi_in_channel`, then dispatches them to `fm1_app_note_on/off` (`firmware/native/app_probe.c:141–167`; `firmware/native/midi_input.h:6–18`). The fresh app initializes the settings structure to zero and no project profile field changes `midi_in_channel` (`sim/web/src/fm1_app.c:627–671`, `firmware/native/project_start.c:70–95`); zero is the filter's omni-channel setting. Thus the startup profile does not intentionally filter the incoming channel. This does not prove that the USB MIDI endpoint delivered the test event or that the running binary's parser received it.

[verified] The HAL's explicit total-output multiplier is `master_q12`; on ALNK0 it multiplies each rendered sample before clipping (`firmware/third_party/dinghy/src/platform.c:221–251`). The main loop polls MASTER ADC channel 4 and sets that multiplier to `(adc²)>>8` (`platform.c:255–284`; `firmware/third_party/dinghy/hal/fm1_adc.h:3–8,29–44`). ADC zero can silence all output. The app's own default `gain` and `master` are 1.0 (`sim/web/src/fm1_app.c:657–660`); the project Trio level is 0.70 and engine volume 0.62. [reported] The owner has reported a high MASTER position; the actual ADC sample and computed `master_q12` were not captured, so an ADC/pot fault or unexpected zero sample is not excluded.

## Practical interpretation and next diagnostic

[verified] Source/configuration makes the Trio arp and stopped transport poor explanations for live notes being consumed. A zero master ADC sample is a source-supported whole-output mute path, but current knob position alone does not verify the ADC value. The profile's Trio has nonzero levels, no inserts, no modulation cables, and an off arp.

[inferred] The smallest discriminating capture is to record, for the same USB note-on/off attempt, (1) decoded USB MIDI event count/channel/status at `incoming_midi`, (2) app-level note-on count plus selected sound/MFX active state, (3) pre-master rendered peak/RMS, and (4) sampled MASTER ADC and `master_q12`. If the app note counter remains zero, inspect USB event delivery/channel configuration; if it increments but pre-master audio is silent, inspect engine note/voice allocation; if pre-master audio exists but post-master is silent, inspect ADC/master scaling. These observations separate transport receipt, synth output, and analog gain without changing the show or its levels.

## Limits

[verified] This is source/profile evidence only. It does not demonstrate USB event receipt, audible output, measured ADC position, or physical audio quality. The root's separate host observation that a USB note test caused no analogue-energy delta is not itself proof that the note reached `incoming_midi`. No firmware behavior or project content was changed, and no device commands were run.

