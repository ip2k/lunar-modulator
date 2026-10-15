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
running-status interleaving and ignored clock messages. The separate real-app FIFO regression also passes, including Stop retention
at saturation, held command order, local panel supersession and both running
and stopped UI synchronization. No target link or physical transport result
is claimed. SAVE remains disarmed; installable-release acceptance is open.

[verified] Hera completed all16 bounded catalogue shards at source
6d971bf1c53e78fb6b1abc3f058ef7467840e77e:167 unique objects, all exits zero,
no OOM, object hashes checked. The frozen Event Horizon+SET diagnostic linked
and passed native audit: app849276bytes of860644, SHA256
46842613d95445ba1088b276f7cc6d0e57b4a9b25b0b284e56552012a8603809.
All13 sound engines/54 modules, telemetry, one-shot autoplay and TRS MIDI are
linked. Private evidence is on Hera at
`/home/claude/mvave-fm1/song-midi-link-6d971bf-20261015`.
Independent read-only receipt review found no EH+SET policy mismatch. This
remains a private diagnostic build, not hardware-admitted/installable firmware.

[verified] Offline candidate reconstruction on bench01 produced target SHA256
0903762167a1dd9877c190e3b67e6657cfe4c5f7227af65d327456f73f8ba4fe;
209 sectors differ from the last installed diagnostic. `_check_build` accepted
its exact EH+SET frozen receipts before candidate construction. No new device
command was issued at this stage. The completed-install gate rejected an old
source hash for the policy expanded in c66d28b9. Independent review confirmed
that update preserves the Trio branch and strictly binds the EH+SET branch.
Updated both adapter and boot dependency hashes, including the adapter hash
in the boot gate. All 33 policy/adapter/boot tests pass; a new test checks every
real boot dependency hash and rejects a tampered policy copy. No safety check
was removed. The pending ROM63 campaign remains one-use, with fresh paired
reads required before writes and SAVE disarmed.
