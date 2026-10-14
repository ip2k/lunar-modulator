# Installed FM-1 performance source review

## Scope and source identity

[verified] This is a read-only source review on commit `66196f54f3295cfdec14a2924c767235bbd5cc2c` (`codex/2026-10-14-trio-pulse-d7000-corrected`) with the installed application source cross-check at `359a46e6b17b3b6eed3242a2b2256bf0b1d8c3e9`. The installed-image correction identifies the physical app as the D9000, singleton Event Horizon build from `359a46e6`, not the later D7000 companion-SET candidates. No firmware code was changed, no target build or run occurred, and no device operation occurred.

[verified] The relevant loop and audio-queue files are identical at the installed source and review source: `firmware/native/audio_queue.h` SHA-256 `95e071a351921fc976197a02f69b26aa35d58649e58c4b3791e3c0b37db421cc`; `firmware/third_party/dinghy/src/lcd.c` SHA-256 `b69f0c3d6a5b61c883a35b50ddd6582811bd620a45268543e923fb8849caaac4`. `platform.c` differs only by UART1 initialization in this comparison. `app_probe.c` adds UART/MIDI diagnostics, companion-set handling and timing instrumentation in the later source, while retaining the same refill, draw and strip-transfer cadence. This isolates the scheduling observations below from those later features.

The retained notes reviewed were `notes/2026-10-14-realtime-event120-target.md` and `notes/2026-10-14-installed-app-provenance-correction.md`. The first explicitly says its 846,000-byte instrumented D7000 link was not installed or listened to; its R/D/U fields therefore do not supply performance measurements for the installed D9000 app.

## Audio cadence and queue bounds

[verified] `firmware/native/audio_queue.h:11-18` sets 64 frames per block and eight blocks. At the engine rate passed by `app_probe.c:239` (`44118.0f`) that is 512 frames, or about 11.61 ms of queued audio. `platform.c:63-65` sets the I2S half-buffer to 256 frames; `platform.c:230-253` consumes that half in the audio interrupt. `app_audio` dequeues four 64-frame blocks per 256-frame callback (`app_probe.c:111-120`). A half callback recurs about every 5.80 ms at this rate.

[verified] `refill_audio` renders 64-frame blocks until the eight-block queue is full, with a per-call maximum of eight render calls (`app_probe.c:122-135`). The outer loop calls it before and after platform polling, after MIDI/input/save work, and after drawing (`app_probe.c:291-305,344-379`). A full queue can therefore leave up to roughly 11.61 ms of pre-note samples queued when a note event is handled. This is a bounded latency contribution, not enough evidence by itself to explain the owner's report of severe sluggishness.

[verified] On an empty queue, `lunar_audio_pop` emits silence and increments the consumer-owned underrun counter without advancing the read index (`audio_queue.h:49-63`). The later readout's `R` records the maximum duration of one 64-frame engine render; `U` is a cumulative missing-block count. Neither value was captured from the installed app. The instrumented target note explicitly says R excludes the full callback and U is not a measure of audible severity.

[verified] The source does not show a direct 44.1 kHz engine-rate mismatch. `app_probe.c` initializes the engine at 44,118 Hz, matching the 44,117.6 Hz I2S rate described in `firmware/third_party/dinghy/src/usb.c:64-72`. USB advertises 44,100 Hz and is explicitly asynchronous; its ring adjusts for the small host/I2S clock difference. The `FS 44100` constant is for USB audio, not the engine sample-rate argument. This 18 Hz difference is deliberate in the source comments and is only about 0.041%; these are source-derived nominal values, not a new physical sample-rate measurement.

## Main-loop and TFT work

[verified] Every outer-loop pass runs `platform_poll`, which feeds the watchdog, retries USB, polls OTA service and reads/filters the master ADC (`platform.c:257-287); it then processes key/button/encoder input and up to 32 USB MIDI events, refills audio and conditionally redraws the app at a 33 ms interval (`app_probe.c:296-379). These are bounded source-level work items, but their execution durations are not measured by the current installed-image evidence.

[verified] `display_strip` runs on every outer-loop pass. When a previous DMA transfer is still active it returns; when complete it converts 240×16 framebuffer pixels into RGB565 byte order and starts a 7,680-byte DMA strip (`app_probe.c:137-149`, `lcd.c:4-7,89-95`). The configured SPI baud divisor is 4, documented as 12 MHz (`lcd.c:9-10,127`). At that rate, one strip's pixel payload alone takes 5.12 ms, and a full 240-row traversal takes 15 strips or at least 76.8 ms (about 13 complete traversals per second), excluding command/setup and CPU conversion. DMA overlaps main-loop work while the strip is in flight, so this is a bus-limited upper bound, not a measured frame rate. The app can redraw at 30 Hz while the visible framebuffer is transferred as a rolling strip scan; that cadence is a concrete candidate for the reported slow VU meter.

[verified] The strip path does not synchronously wait while the DMA status bit says busy: it returns before converting or launching the next strip. Once the status is complete, `lcd_sync` waits/clears before touching the DMA source. The code therefore supports a slower/rasterized display explanation, but source inspection alone does not establish that TFT work starves audio rendering.

## Input-path qualification

[verified] The installed `359a46e6` `app_probe.c` polls `midi_get` for USB MIDI; `platform.c` has `FELUCCA_UART 0` and no UART1 startup hook. The later `66196f54` source adds a separate `LUNAR_UART1_MIDI` initialization and poll path. Consequently, an external K6 MIDI OUT connected to the FM-1 DIN input is not a valid note-latency stimulus for the installed `359a46e6` image. This does not prove the owner used that path for the sluggish-note observation; it means the next capture must bind the tested input path to the installed image's actual MIDI source.

## Conclusion and next measurement

[verified] The source review found no demonstrated callback deadline defect or engine-rate unit error. It did find a bounded 11.61 ms queue horizon and a display scan whose theoretical payload floor is 76.8 ms per full-screen traversal. The latter can plausibly explain some meter lag; neither establishes the cause of the reported audio problem. The installed build lacks the later R/D/U instrumentation, and the instrumented build in the retained note is a different, uninstalled configuration.

The useful next evidence is a coordinator-owned watched run of one exact, identified candidate with matching input routing and analogue capture. Its telemetry should separately record: maximum 64-frame render duration, maximum contiguous refill duration, queue occupancy/minimum depth and underrun delta, audio-ISR duration, `platform_poll` duration, TFT conversion/wait duration and full strip-sweep time. Preserve the current R/D/U fields but do not treat D (which times app draw/footer) as including `display_strip` or the rest of the loop. Compare R with the 64-frame period of about 1.45 ms and check whether U increases; the four-block callback and queue headroom still require end-to-end observation. No threshold should be used as a hardware acceptance claim without the capture.

Rarefaction was available only against the Mac's active checkout, whose HEAD is not this assigned Hera worktree, so I did not retarget the shared semantic index. The exact-source review used the isolated Hera checkout and direct line inspection. No Rarefaction/Serena result is claimed for this commit.
