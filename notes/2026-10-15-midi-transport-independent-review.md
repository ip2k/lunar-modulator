# MIDI transport implementation review — 2026-10-15

This is a read-only source review of the transport changes at `6d971bf1`
and app FIFO follow-up `c1934edf`, as present in the inspected checkout at
`09fce750`. No source, test, firmware, or hardware state was changed by this
review.

## Source findings

- `engines/seq/seq_engine.c:2008-2053` implements internal-clock MIDI
  transport separately from the existing external-clock follower. Start
  releases an active/paused pass, clears `song_jump` and external-follow
  state, then calls `sq_play`; `sq_play` chooses the song top after the jump
  is cleared. Stop calls `sq_stop_at(..., 0)`, which flushes sounding gates,
  recording/capture, and automation while preserving song position, track
  playheads, master tick, and fractional accumulator. Continue is accepted
  only while `midi_paused`, restores playing and the previous clock-emission
  state, and does not emit Start.
- `fm1_seq_advance` increments wall-frame time while paused and returns before
  changing musical clock/tick state (`seq_engine.c:1908-1915`). This preserves
  input timestamps while freezing song time. The host regression compares
  the resumed note-event sequence against an uninterrupted reference after a
  pause, including scene progression and no Start event on Continue
  (`engines/test/seq_host_test.c:1021-1112`).
- `sim/web/src/fm1_app.c:3597-3608,3648-3685` flushes pending input in order,
  reserves a full event burst before applying transport, retains Stop under a
  saturated FIFO, and lets a newer local Play/Stop discard queued MIDI
  transport intent. `tests/native/app_midi_transport.c` exercises these
  FIFO cases and checks synchronized UI playing state.
- Native USB and UART paths dispatch FA/FB/FC before channel filtering
  (`firmware/native/app_probe.c:157-165,205-225`). The parser tests exercise
  realtime bytes interleaved with running-status channel messages on both
  paths. F8 clock input is intentionally ignored by the native app; it is not
  wired to the separate external-clock follower. That is a documented scope
  boundary, not evidence of internal-clock transport failure.

I found no concrete source-level defect in Start/Stop/Continue, pause timing,
release behavior, or FIFO ordering in the reviewed paths. Continue's lack of a
Start event is deliberate so downstream MIDI effects do not reset their
phase.

## Acceptance boundary and recommended next check

The tests are strong at the core, parser, and app-FIFO layers, but do not
provide end-to-end physical proof of musical position/resumption. Existing
telemetry records USB-message and UART-byte ingress, not sequencer playing
state, song position, tick phase, or per-event dispatch. The current
`notes/2026-10-15-native-midi-transport.md` reports a five-event physical
campaign (FC/FB/FA/FC/FB) whose capture was still active at its recorded
checkpoint; it does not establish the resulting transport behavior or audio.

When the coordinator finishes that already-authorized capture, correlate its
timestamped input transcript with the WAV and telemetry. A useful acceptance
check is: first FC releases active notes and holds song tick; FB resumes from
that position; FA restarts from the top; the second FC/FB pair pauses/resumes
again. Audio evidence can support that sequence but cannot establish exact
internal position by itself. If the capture remains ambiguous, the next
instrumentation should expose read-only transport state (playing, paused,
song position, master tick) in the diagnostic telemetry and rerun the same
bounded sequence. Do not infer success from ingress counters alone.

The prior passive capture in the same note reports substantial queue
starvation (`U=48741`, render maximum about 5.06 ms versus 1.45 ms per
64-frame block). Thus even a correct transport state trace would not amount to
acceptable real-time playback until the separate audio-performance issue is
resolved. SAVE remains disarmed; this review makes no installation, release,
or musical-acceptance claim.
