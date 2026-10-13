# Stock return and identity after completed-trace restore

[verified] All 80 reset/provenance model checks passed across 16 Hera containers,
with zero failures, errors, skips or OOM. Receipt: `reset-verification-v3.json`.
These checks used actual private evidence with modeled transport; they are not
physical device operations.

[verified] The separately bound, consumed `physical-stock-reset-003` packet
submitted exactly one FC0C reset CBW in bench-side USBmon. The child exited 1:
the post-ioctl USB-binding check found the old sysfs entry absent. SG completion
and reset causation therefore remain unproven. The same physical USB port next
enumerated normal `4c4a:c755`, bus 1/device 11/path `1-1`. No reset was retried.

[verified] Normal USB appeared before the ALSA MIDI endpoint. The wrapper stopped
without sending an identity query. Once the endpoint existed, a separately
frozen identity-only successor sent one fixed 10-byte read-only query and matched
the known `FM-1_092` reply exactly. It performed no reset or flash operation.
The owner was not asked to power cycle. Raw replies and complete capture packets
remain private under ignored build paths; public hashes and acceptance limits
are in `physical-stock-return-verification.json`.

[verified] The canonical wrapper now passively waits up to 10 seconds for one
same-port MIDI endpoint, checking capture liveness and unchanged USB binding.
It sends no additional reset or identity query while waiting. All 57 wrapper
model checks passed in 16 Hera containers, including delayed endpoint, timeout,
changed device, ended capture and duplicate endpoint cases. Receipt:
`wrapper-verification-v3.json`. This revised wrapper was not used in the completed
physical reset; that attempt used template `8beb87f1…` and remains consumed.

[verified] This demonstrates normal stock USB and stock application identity
after the verified stock restore. It does not demonstrate Lunar display output,
SG reset completion, reset causation or recovery from a physical interrupted or
corrupted firmware write. Those acceptance gates remain open.
