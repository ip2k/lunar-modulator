# Event Horizon audio scheduling and meter path audit

**Scope.** Source-only audit at commit `31955c14cf7dedefb3dcc62c0de89186084a40c3` in the authoritative worktree. No source or device state was changed. This extends the earlier [`2026-10-14-event120-runtime-cost-review.md`](2026-10-14-event120-runtime-cost-review.md) with the producer/consumer cadence and a display-timing blind spot. It is not a performance result.

## Timing contract and what the counters mean

- The app is initialized at 44,118 Hz (`firmware/native/app_probe.c:273`), TIMER4 uses 24 MHz and `FM1_TICKS_PER_US` is 24 (`firmware/third_party/dinghy/hal/fm1_time.h:3-16`). One 64-frame block is 1.45066 ms; a 256-frame half-buffer is 5.80262 ms; eight queued blocks represent at most 11.6053 ms of already-rendered audio.
- `refill_audio` renders one 64-frame `fm1_app_render` call per queued block and tracks only the maximum duration of that individual call (`app_probe.c:125-138`). `render_ticks_max / 24` is therefore a high-water duration for one render call, not loop latency, queue depth, note latency, or callback duration.
- `fm1_alnk0_irq` consumes four 64-frame blocks for each 256-frame half-buffer (`firmware/third_party/dinghy/src/platform.c:230-253`; `app_probe.c:101-120`). If the ring is empty, `lunar_audio_pop` emits 64 frames of zero and increments `underruns` once without advancing `read` (`firmware/native/audio_queue.h:47-63`). A rising underrun delta is direct evidence of missed supply; an `R` duration greater than 1.45 ms is a pressure signal but is not itself a dropout because queued blocks provide slack.
- `draw_ticks_max` covers `fm1_app_draw` plus the diagnostic footer work inside the timed interval (`app_probe.c:396-423`). It does **not** cover `display_strip`, which runs afterward (`app_probe.c:140-152,425-426`). `display_strip` checks/waits for an in-flight transfer, converts 3,840 pixels to the DMA buffer, and starts a 240x16 strip blit. Consequently a low `D` cannot rule out main-loop time spent on strip conversion/transfer scheduling.
- The 30 Hz draw cadence is an upper bound set by the `fm1_ms - last_draw >= 33` gate (`app_probe.c:396-399`), subject to how quickly the loop reaches it. The 240-row screen is sent in 16-row strips, one strip per main-loop pass (`app_probe.c:140-152`); a complete 15-strip refresh rate depends on loop/transfer cadence and is not measured by `D`.

## Event Horizon work per block

The checked-in Event Horizon example has four configured sound slots (drums, macro VA+Filter, macro VA Pair, DX7) and two master effects (Hall, limiter); its serialized focus is Trio, but focus does not select a render mask. The matched target review records the four active slots and empty instrument insert pairs in more detail (`2026-10-14-event120-runtime-cost-review.md`, Findings). The project is a four-part mix, not thirteen simultaneous engines: thirteen is the catalogue of buildable engines.

When a SET is attached, `render_sounds` calls `seq_flush`, advances the host by each produced block, and dispatches slots/ticks (`sim/web/src/fm1_app.c:3429-3457`). It then handles each nonempty sound slot, its configured inserts, level and mix (`fm1_app.c:3458-3479`). `fm1_app_render` subsequently executes configured master effects, the limiter, per-sample peak/scope tracking, app gain, sequencer/UI sync and LED updates (`fm1_app.c:3482-3551`). The set’s events add note/parameter dispatch when transport is playing, but the attached sequence host and four configured render paths remain active when PLAY is stopped. Thus event density alone cannot explain sluggishness reported before PLAY; conversely, the stopped set is not equivalent to a Trio-only render.

This establishes a plausible producer-load contrast, not per-engine cost or deadline failure. A slot can render silence/no active voices yet still incur its render and mixing path; actual polyphonic cost depends on active notes/engine internals. The serialized `Voice Mode: Poly` values and the engines’ maximum-voice metadata are not evidence that every maximum voice is active. Count actual simultaneous notes only from the selected SET/capture, not from the catalogue or voice cap.

## Meter and note-response implications

- The output peak is collected after the master effects/limiter but before `a->gain` is applied (`fm1_app.c:3502-3513`). This can make the display meter disagree with speaker loudness at reduced app master gain; it does not explain a delayed meter response by itself.
- `fm1_app_draw` updates the meter as `max(peak, prior_meter * 0.6)` once per draw and clears `peak` (`fm1_app.c:4492-4503`). At an ideal 33 ms cadence, the decay half-life is about 45 ms. That source-defined decay is short; multi-second visual sluggishness would point to draw/strip/main-loop progress, not this decay constant alone.
- MIDI is polled after a refill and other loop work (`app_probe.c:348-388`), then the next refill turns the accepted note into rendered blocks. If the queue was full immediately before note arrival, those stale blocks could add up to about 11.6 ms before the newly rendered note reaches output. The current telemetry does not sample queue depth at MIDI receipt, so this bound is architectural, not an observed latency.

## Ranked hypotheses and smallest discriminating follow-up

1. **Full-app render pressure.** EH has four active engines, the sequence-host dispatch, mix, Hall, limiter and output bookkeeping on every 64-frame render. Compare per-window `R` and underrun deltas with the same setup, first no-key/PLAY-stopped, then a held note, then PLAY. If `R` approaches/exceeds 1.45 ms and underruns rise, add per-slot timing or a matched one-effect-at-a-time diagnostic to localize cost before optimizing.
2. **Main-loop/display delay missed by current `D`.** Measure a separate maximum for the `display_strip` conversion/submit path and an audio-queue low-water mark (or producer-gap maximum). This is the most direct way to distinguish slow screen refresh from app drawing when `D` and underruns look healthy. Keep transfer wait and pixel conversion separately measurable if the combined value is high.
3. **Queue latency, not slow note dispatch.** Record queue depth when the note is accepted and time from acceptance to the next produced block; current `U` only reports empty blocks and cannot distinguish a note waiting behind already-rendered audio.
4. **Meter loudness semantics.** If the complaint is meter amplitude rather than response time, compare the pre-gain meter to post-gain output; current code intentionally measures before the app master gain.

No one of these hypotheses is confirmed by this audit. Existing Trio-only telemetry and prior Event Horizon static review are not substitutes for a matched fullsong capture. The upcoming hardware telemetry task owns that acceptance evidence; this note only identifies what the current source counters can and cannot resolve.

## Validation and limits

- Read the current app loop, ring buffer, HAL audio half callback, TFT strip transfer and meter update source at the exact commit named above. Manually checked calculations: `64/44118`, `256/44118`, `512/44118`, and `ln(0.5)/ln(0.6) * 33 ms`.
- Rarefaction was pointed at the primary checkout, not this authoritative worktree, so it was not used for claims. Serena was selected on the authoritative worktree; its bounded app/render symbol lookup succeeded, while one helper lookup returned no symbol. File inspection supplied the exact call paths and line references. No target build, waveform analysis, timing measurement, install or device command was run.
