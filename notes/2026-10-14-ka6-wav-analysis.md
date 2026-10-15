# KA6 capture analyzer

[verified] `tools/native/analyze_ka6_wav.py` is a standard-library, streaming analyzer for the expected six-channel, 48 kHz, signed 32-bit PCM KA6 capture. It accepts ordinary PCM and WAVE_FORMAT_EXTENSIBLE with the PCM subtype, requires 32 valid bits, checks RIFF/chunk bounds and frame alignment, and rejects other formats. It reads sample data in bounded 4096-frame chunks and reports channel 1/2 frame count, normalized RMS, absolute peak, signed-32-bit peak magnitude and exact full-scale rail sample count. Other channels are retained only in the source WAV; no stats are reported for them.

[verified] Output includes RIFF format metadata, total frame count/duration, and capture-relative windows of one second (48,000 frames) plus a final shorter window. Optional `--annotations events.jsonl` accepts JSONL entries with `kind` `boot` or `stimulus`, nonnegative `t_seconds`, and optional text `label`. It marks whether each timestamp falls within the capture and explicitly labels the entry as timing annotation only; it does not establish that MIDI reached the instrument. Optional `--baseline before.wav` reports channel RMS/peak/clipping deltas for same-index windows shared by the captures; unmatched trailing windows are omitted.

[verified] Example once the coordinator provides a capture:

```sh
python3 tools/native/analyze_ka6_wav.py capture.wav \
  --annotations capture-events.jsonl \
  --baseline pre-install.wav \
  --output capture-analysis.json
```

[verified] Validation on Hera: `python3 -m unittest tests.test_ka6_wav_analysis -v` (6 tests passed); `python3 tools/native/analyze_ka6_wav.py --help`; `git diff --check`. Synthetic tests cover ordinary and extensible PCM, clipping and one-second boundaries, invalid channel/rate/bit-depth/subtype, partial frames/truncated RIFF, annotation validation, and baseline window comparison.

[verified] No owner recording was available to this task, so the analyzer has not been run on a real KA6 capture. It does not decode MIDI, infer note acceptance, detect analog input routing, or establish that a capture was synchronized to device boot beyond the supplied relative timestamp annotations. The expected six-channel format must be confirmed from the actual recorder output; a different legitimate format is rejected pending an explicit change to the contract.
