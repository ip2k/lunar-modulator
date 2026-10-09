# Warble effect implementation checkpoint — 2026-10-09

Warble is a new, compact, original wow/flutter audio effect in
`engines/src/fx_warble.cc`, licensed MIT with no third-party DSP code or
runtime dependency. CHOMPI's Warble informed the effect choice only; no
CHOMPI/DaisySP implementation was copied. The earlier comparative research is
in `notes/2026-10-09-effects-expansion-research.md`, and the project-specific
CHOMPI review is `notes/2026-10-01-chompi-evaluation.md`.

The three continuous controls are Wow (0–1, default 0.35), Flutter (0–1,
default 0.25), and Mix (0–1, default 0.5). Independent deterministic LFO
phases run at 0.35 Hz and 6.5 Hz, modulating a shared stereo read head around a
12 ms base delay by up to ±3 ms and ±0.45 ms. A per-instance interleaved
16-bit ring stores 4,096 stereo frames (16,384 bytes); the full instance is
16,464 bytes on this desktop ABI. Times scale from the host sample rate, which
the implementation accepts from 8 to 192 kHz. Wow and Flutter glide over
approximately 20 ms, Mix over 5 ms, and setting controls before the first
render applies immediately. At Mix zero the original input bits are returned
unchanged while guarded samples continue filling the ring. Destroying and
recreating the instance clears history and returns both LFO phases to zero.

The build catalogue, proposed default module list, engine registry, editor
effect group and user-facing effect lists now include Warble. Tests pin its
stable editor group and metadata, compare Mix-zero WAV output bit-for-bit with
unity gain, require audible full-wet modulation, and exercise host contracts:
unsupported rates, bounded instance size, delay time across sample rates,
repeatability under different render block sizes, exact dry bypass, smooth
live parameter changes and finite/bounded output for hostile samples and
parameter values.

Validation to date: `make -C engines build/fm1-warble-selftest` and
`engines/build/fm1-warble-selftest` pass all seven focused C++ checks; `git diff
--check` is clean. The full native renderer/Python integration tests and the
combined Wasm/parity/page build remain pending. No JieLi target build, FM-1
traffic, install or hardware audio test was performed. The Wasm artifact must
be regenerated together with the other in-flight engine/module changes before
it is treated as a combined product build.
