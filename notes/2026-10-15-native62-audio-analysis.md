# Native62 MIDI/audio capture analysis — 2026-10-15

This is an offline signal review of the private 150-second native62 capture. It measures whether distinct C4/E4/G4 stimulus windows coincide with output energy and whether the measured spectrum is near each expected fundamental. It does not establish subjective sound quality, end-to-end MIDI delivery per note, exact latency, or full-song acceptance.

## Evidence and method

The private Hera files were independently hashed before analysis:

- `audio.wav`: SHA-256 `7636d91740a834aba1ca2bc4bc750cc05833257c6dbc9b6eca9cd185a255dd1a`.
- `capture.jsonl`: SHA-256 `3641b5d2050a4c9930ad24654c6ffcb9e37fe1bfbea382fe9c2e135370b2129d`.
- `events.jsonl`: SHA-256 `1fb722bb6de54ef3b8e4b0e8361736bb7964eb30ab457db61bb6ec3770a50b9f`.
- Existing whole-file analysis: `analysis.json`, SHA-256 `647ec0a14e6b6d591db0fd246a54dc9f0d6189306e171e45e692a9d9e77738c5`.

The WAV is PCM S32_LE, six channels, 48 kHz, 7,200,000 frames (150 seconds). The analysis read the original audio read-only in a network-disabled `docker-batch.slice` container, limited to 2 CPUs, 2 GiB memory/swap and 64 pids, image ID `sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`. The private per-stimulus output is `segment-rerun/results.json`, SHA-256 `f9eae669c508e17c330453779129e398106255679a3e612cca4a5e30617e2579`.

For each stimulus, the capture helper's note-start wall timestamp was mapped to WAV time by subtracting `audio_capture_ready.wall_time`. It sampled 100 ms RMS windows and scanned a 0.5-second Hann-windowed segment over a ±10 Hz range at 0.5 Hz increments around the equal-tempered fundamental. The helper-ready timestamp is not a measured ALSA first-sample timestamp, so the mapping is approximate; the frequency grid is not a precision tuning measurement.

## Measurements

Idle stereo output during seconds 8–14 measured −65.74 to −66.18 dBFS on channel 1 and −65.37 to −65.76 dBFS on channel 2. During the active portions (+0.3 to +2.0 seconds from each approximate WAV onset), all six windows had mean RMS between −23.3 and −22.9 dBFS on channel 1 and −23.1 to −22.9 dBFS on channel 2. Their 100 ms minima stayed between −24.7 and −21.9 dBFS, with no silent 100 ms gap during the 2-second holds. Energy decayed close to the idle floor by about +2.3 seconds. No clipped samples were reported in the WAV analysis.

| Input block | MIDI note | Approximate WAV onset | Fundamental scan, ch. 1 / ch. 2 | Component level, ch. 1 / ch. 2 |
|---|---:|---:|---:|---:|
| KA6/TRS | 60 (C4) | 17.679 s | 260.63 / 260.63 Hz | −27.32 / −27.16 dBFS |
| KA6/TRS | 64 (E4) | 21.679 s | 328.63 / 328.63 Hz | −26.74 / −26.57 dBFS |
| KA6/TRS | 67 (G4) | 25.679 s | 391.50 / 391.50 Hz | −25.18 / −25.01 dBFS |
| FM1 USB | 60 (C4) | 40.680 s | 260.63 / 260.63 Hz | −27.41 / −27.24 dBFS |
| FM1 USB | 64 (E4) | 44.680 s | 328.63 / 328.63 Hz | −26.66 / −26.50 dBFS |
| FM1 USB | 67 (G4) | 48.680 s | 391.50 / 391.50 Hz | −25.42 / −25.25 dBFS |

Each channel also showed approximately −102 dBFS in channels 3 and 4 and digital silence in channels 5 and 6 during these windows. Repeated runs of each pitch match at the 0.5 Hz scan resolution; component-level differences are under 0.3 dB. The peaks lie within about 1 Hz of nominal C4/E4/G4. Given the short-window/grid method, that supports presence near the requested pitch but does not establish precise tuning.

The approximate WAV onsets are about 0.2 seconds after the logged note-start wall timestamps. This is not a trustworthy latency figure: the helper's `audio_capture_ready` timestamp does not identify the actual first captured sample, and clock/stream alignment bounds were not measured.

## Interpretation and limits

The capture contains strong, sustained, pitch-consistent output in all six stimulus windows: three notes sent to the KA6/TRS path, followed by the same three notes sent to the FM1 USB MIDI output. This is consistent with both blocks producing audio and the repeats being similar. The capture alone cannot assign causality to an input path with certainty because the same pitches were played in both blocks and the host helper explicitly records `output_device_acceptance:false` and `target_consumption_proven:false`. Parent-reported native62 telemetry totals six accepted note-ons, six USB MIDI messages and 18 UART bytes across the run; those aggregate totals corroborate ingress but are not per-note/per-port audio attribution.

The result is objective evidence of captured output energy and approximate pitch during the six test windows. It is not perceptual listening acceptance, proof of the intended audio route/quality, a measured latency pass, or evidence of sustained/full-song performance. Next useful evidence is time-aligned telemetry or a capture with non-overlapping isolated port stimuli and a measured audio-stream start marker; listening remains a separate owner acceptance step.
