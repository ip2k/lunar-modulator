# Fixed return-r01 Pico transport, source milestone

This separately named, offline-only Pico 2 W variant is a candidate for the
512-byte ROM-return r01 payload at `0x01c02000`. It is excluded from the
ordinary FM-1-transporter build and does not change its recovery client,
V15-only shim, or W01 experiment. This source milestone does not authorize a
Pico build or physical use.

The pinned source is kurogedelic's FM-1-transporter at
`a7fb5e8ac692c528f8ed29e325911a3f4b8111d6` with tracked patches 0001,
0002 and `0003-fixed-return-r01-rom-mode.patch`, in that order. The upstream
submodule, Pico SDK, TinyUSB checkout and immutable container image are
independent inputs to the later offline recipe. The build manifest records
the fixed payload source commit `306eca49bf504ecc96426597a6b58e36144d6785`,
512-byte SHA-256 `898b7737d69e351e54b406aebda27652c04413344d19dfb698a8642e33b698f9`,
and CRC32 `E6FACC35`. The final UF2 SHA is deliberately unset until an
independently reviewed build produces it; the compile-time
`rr01-pico-v1` marker cannot attest the flashed image.

The strict variant requires the target D+ to remain low for a continuous
50 ms electrical observation at Pico startup, then
runs one cold USB_KEY handoff and accepts only one exact ROM VID/PID and
36-byte INQUIRY identity. Its CDC data interface accepts three fixed lines:
`rr01-ready`, `rr01-upload` plus exactly 512 plaintext bytes, and
`rr01-call`. The upload claim precedes the first payload byte. Only the
specified FB06 memory write and, after a completed upload, one consumed
FB08 call are reachable. The FB06 CDB checks the complete fixed envelope,
including the actual ROM ciphertext CRC16 `C360` (wire bytes `60 C3`).
The existing BOT completion patch checks exact CBW, data and CSW lengths,
tag, status and residue; `cmd_exec` checks exact 16-byte response and echo.
All faults, detach, extra input and repeat commands are terminal. No loader,
soft key, rekey, readback, status, keepalive or automatic retry is exposed
by this variant. The strict USB descriptors identify the product as
`Lunar fixed ROM return-r01` and CDC interface 02 as
`Return-r01 fixed data`; USB reset interface and 1200-baud BOOTSEL callback
are absent. Those strings are mode correlation, not device attestation.

The host's later one-shot receipt must fsync `upload_attempted` before any
upload byte and `jump_intent_consumed` before any `rr01-call` byte. Timeout,
disconnect, ERR and missing or malformed response are inconclusive and
permanently spent. A matching complete call reply is bounded evidence of
the ROM command returning only when cold-ROM, wiring and UF2 provenance are
established separately. It is no ABI, execution-duration, or hardware
qualification proof.
The low D+ observation is a cold-entry precondition, not proof that the
FM-1 was actually powered off or that the later mount came from mask ROM.

Synchronous BOT waits can run callbacks while core 0 receives CDC bytes. The
strict path rechecks the same live mount after each required descriptor,
INQUIRY, upload and call boundary. The strict protocol serializes phase,
request and reply publication with a Pico SDK critical section; it never
holds that lock across BOT, TinyUSB I/O, waiting or formatting. Core 0 owns
CDC connectivity and copies TX bytes out of the protected ring before
writing them to TinyUSB. The strict target compiles a no-op log source and
does not wait for or emit an interactive console log, avoiding the inherited
volatile cross-core log queue. A causal old-source fixture showed that an
extra line arriving inside FB06 or FB08 previously produced an OK reply
followed by a terminal error; the corrected fixture requires only the
terminal refusal. A pthread fake-critical-section case also exercises the
two cores' in-flight overlap. Upload and call claims pair the live protocol
check with the audited core-1 host-state claim under that short lock. A
separate CDC-write callback test verifies that discarding a queued reply
cannot advance a stale TX ring tail. Bytes already accepted by TinyUSB
cannot be retracted; host timeout or a later terminal reply is inconclusive.
These checks bound late success after a detected in-flight fault.

On terminal state the strict core-1 task stops calling TinyUSB's host task,
and transfer/probe hooks recheck the sticky state before later stages. An
already submitted transfer may still complete or time out, and PIO/USB
electrical signaling is not proven silent. The later actual target build
must retain its ELF, map, disassembly, symbols, compile commands, cache and
UF2 in one owned output for independent inspection before stage cleanup.

Offline verification for this source milestone materializes the actual
pinned upstream C, applies all three tracked patches, and compiles the
patched protocol and exact host allowlist functions with fake TinyUSB/BOT
dependencies. The focused suite includes success, bad/extra/partial payload,
single-attempt refusal, CDC disconnect, wrong mount generation, exact and
corrupt INQUIRY, generic commands and pipelining. It compiles the actual
ROM cipher and CRC functions to check the fixed FB06 wire CRC. Full Pico
link, image/resource inspection and device behavior remain later gates.
