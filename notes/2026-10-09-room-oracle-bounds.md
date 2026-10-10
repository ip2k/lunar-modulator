# Room reference frame-count bounds

The `fm1-ref-room` audit finding was real: `--rate inf` and `--seconds inf`
passed the old positive-value checks, then generated-input mode converted
their product to `uint32_t` before sizing its frame vector. An oversized finite
request could exceed the same conversion range or produce a WAV whose RIFF
length and byte-rate fields overflowed.

The CLI now rejects non-finite/non-positive rate and duration values, rates
that cannot be represented in the WAV sample-rate and byte-rate fields, and
frame counts beyond the WAV/`uint32_t` limits before converting or allocating.
The synthesis classes and processing path are unchanged. Tests cover infinite
and NaN rates/durations, a finite but unrepresentable rate, finite oversized
and overflowing frame requests, plus a valid 32-frame, 8 kHz render.

Validation ran on aeon in `lunar-asan:ubuntu-24.04` with the documented
`docker-batch.slice` parent and 4 GB memory and swap ceilings. The two focused
pytest cases passed. The container exposes `c++` but not `g++`, so the test
used `CXX=c++`; Rarefaction could not index the isolated worktree's target
symbol, and Serena provided the source navigation.
