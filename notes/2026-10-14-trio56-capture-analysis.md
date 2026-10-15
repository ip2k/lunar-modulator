# Trio capture: early C4-like signal analysis

## Result

[verified] The private capture contains substantial, tonal audio before the later injected note windows. The two analyzed output channels rise far above their later noise floor during roughly 1–5.5 seconds. In particular, the 3.4–5.4 second segment has a strong narrow peak at 262.75 Hz in a 0.25 Hz Goertzel scan; C4 is 261.63 Hz. Autocorrelation at a 183-sample lag (262.30 Hz) is consistent with that estimate. In 100 ms windows around 3.4–5.4 seconds, energy at the C4 bin dominates the adjacent B3/D4 bins. This is consistent with a sustained C4-like note, not only a startup click or brief transient.

[verified] The one-second channel-1/channel-2 RMS values are 0.0793/0.0808 at 3–4 s, 0.1139/0.1160 at 4–5 s, and 0.0757/0.0772 at 5–6 s. They return to 0.00070/0.00075 at 6–7 s. The 0–1 s window is 0.00061/0.00066 RMS; the first large rise is in 1–2 s (0.0495/0.0511 RMS), so the signal is not a continuous startup noise floor. No clipped samples were found in the recorded channels.

[verified] At the reported later test windows, the recording is near its floor: channel 1/2 RMS is 0.00050/0.00053 at 16 s, 0.00050/0.00053 at 20 s, 0.00050/0.00053 at 24 s, and about 0.00048–0.00051/0.00050–0.00054 for 57–68 s. The analysis sidecar has no timestamp annotations. Therefore this capture does not show a measurable response at the reported later TRS and USB note injections.

[inferred] The early waveform is compatible with a synthesized C4-like tone and is much stronger and more periodic than the later baseline. Audio analysis alone cannot identify which device generated it, prove the MIDI event was accepted, or establish musical/playback acceptance. The 1–3 s activity also includes a lower-level interval; do not describe all of 1–5.5 s as one uninterrupted note.

## Inputs and method

[verified] Private input WAV: `/home/claude/.local/share/codex-private/trio56-capture.wav`, SHA-256 `0ca618c0f183bc78deba5fe86db26c9b77e2386e8a47b4098792ad0a3b88af05`, 172,800,044 bytes. It is PCM, 6 channels, 48,000 Hz, signed 32-bit, 7,200,000 frames (150 s). Private analysis sidecar SHA-256: `8526496737be8fda73538ffa93d9461e9f785a9c2f4d9b6a66fc4df4f9426d62`; its annotations array is empty.

[verified] Recomputed one-second statistics with `tools/native/analyze_ka6_wav.py` using the pinned validation Python environment. A separate standard-library streaming check examined 100 ms windows and used Goertzel comparisons at B3/C4/D4/A5. A focused 3.4–5.4 s Goertzel scan searched 240–280 Hz in 0.25 Hz increments; normalized autocorrelation was also checked around the corresponding period. No media or sample data is stored in this repository note; the WAV and generated analysis remain in the private directory.

## Limits and next check

[reported] The supplied run context places later TRS events around 16–24 s and USB events around 58–67 s. The sidecar contains no stimulus markers, so these associations are not independently verified from the audio file.

[inferred] Capture timing offset and an unrelated external source remain possible explanations for early audio. To attribute the early C4-like signal, compare against a no-note capture and align a hardware-generated capture marker or recorded stimulus timestamps; then separately evaluate the later event windows. This analysis is acoustic evidence only, not device MIDI-acceptance or owner listening evidence.
