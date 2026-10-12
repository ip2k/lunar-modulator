# Live MIDI effect clock during pause

The independent editor review found a paused live-arp regression on baseline
`bdc7ca81` [verified]. Native pause freezes the sequencer's fractional accumulator,
but the host kept deriving every block's MIDI effect ticks from that unchanged
fraction. A held live keyboard key could stall or run at audio-block frequency,
depending on where the owner paused.

The host now carries its existing MIDI effect accumulator independently whenever
the sequencer is not playing, at the sequencer's current BPM [verified]. While
playing, native-grid ticks still come from the sequencer, and their endpoint
fraction seeds the live clock for a subsequent pause. External/compat playback
also carries the independent BPM fraction. No extra allocation or state field is
introduced. The sequencer reports zero grid increment while paused, matching its
frozen advance behavior. Live keyboard arps remain audible; the sequencer's
position and resume fraction are unchanged.

`engines/test/mfx_pause_test.c` drives the actual native sequencer host, MIDI effect
host, arp engine wrapper and arp core [verified]. It covers fractions 10%, 50%,
90% and 99.6% of a tick, blocks of 31/64/127 frames, 120 BPM and a change to 90 BPM
while paused. Each case requires the held live key to keep exact straight 1/16
spacing, the released clip key to stay absent, the expected number of live notes,
frozen sequencer master tick/fraction/clip position/rendered time, and retained
fraction with advancing time after resume. Its initial baseline run failed on
the stalled low-fraction live note count; all 24 cases pass with the repair.

Validation [verified]:
- Isolated Hera source stage
  `/home/claude/mvave-fm1/paused-mfx-clock-20261012`:
  test_seq_mfx_pause, test_seq_transport, test_sim_arp, test_seq_render and
  test_seq_ui: 244 passed, six existing optional skips.
- Hera container `lunar-recovery-pytest:20261011`, bounded to four CPUs/4 GiB:
  24-case native harness passes with ASan+UBSan and leak detection.
- Same isolated container: 24-case harness passes with `-m32` and GPL disabled.
- `git diff --check`: clean.

Rarefaction status and Serena initial instructions/current config were inspected.
Both selected `/Users/likwid/Developer/mvave-fm1-firmware`, rather than this isolated
checkout. Their shared active project was preserved; source inspection and actual
native builds provided this subtask's evidence. No semantic correctness claim is
made from their mismatched indexes.

Handoff: integrate the repair commit into the parent editor stream, rebuild the
actual browser-linked Wasm, run combined browser/review/CI gates, then finish the
parent's authorized merge/live acceptance. No hardware write occurred; native
coverage alone does not establish browser, deployment or listening acceptance.
