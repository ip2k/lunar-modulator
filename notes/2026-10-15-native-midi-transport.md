# Native MIDI transport — 2026-10-15

[verified] Native USB and UART MIDI share the app transport dispatch before
channel filtering. FA Start rewinds and starts at internal tempo; FC Stop
releases sequencer gates and pauses musical time; FB Continue resumes the
paused transport without resetting MIDI-effect phase. F8 clock following is
not enabled by this change; the existing external-clock API remains separate.

[verified] Transport reserves a complete stop-event burst before mutation.
The app holds up to eight pending transport bytes when the audio event buffer
has insufficient room. Stop replaces the newest queued intent if saturated;
Start/Continue report BUSY. A newer local Play/Stop clears older queued MIDI.
The queue is cleared when its sequencer is dropped. Musical ticks freeze while
paused; wall-frame time continues for live input timestamps.

[verified] Root independently ran 172 tests across test_seq_render.py,
test_seq_song.py, test_native_midi_ingress_integration.py,
test_native_midi_stream.py and test_native_midi_uart_stream.py. They cover
pause/resume timing, scene progression, no Start event on Continue, paused
replacement-source rejection, USB/UART routing before channel filtering,
running-status interleaving and ignored clock messages. App FIFO pressure/UI
regression is pending separately. No target link or physical transport result
is claimed. SAVE remains disarmed; installable-release acceptance is open.
