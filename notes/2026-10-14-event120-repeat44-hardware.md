# Event Horizon repeat from ROM device 44

[verified] The Mac coordinator passively identified bench01 USB path 1-1,
bus 1 device 44, 4c4a:8057, then ran the reviewed device44 read adapter.
Two complete 1,048,576-byte reads independently matched installed target
SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`.
The completed inventory contains 8,757 commands, zero flash erase/program
operations and zero reset operations. Commands receipt SHA-256:
`45a46828af1f9064d2836abb6b7baa17b676a18ea1bec05859862dee49624040`.

[verified] After a fresh same-connection passive snapshot and boot preflight,
one FC0C arg1 request was submitted at Unix time 1792013192.138558.
Its SG completion was ambiguous (host 7, residual 16, info 1); it was not
retried. A subsequent passive enumeration showed native USB device 45,
1209:0001. This establishes application USB startup, not screen/audio/control
acceptance. The owner was asked to watch the two-minute Event Horizon test,
press PLAY and report music, controls, glitches and diagnostic footer values.
That acceptance and the passive timed return to ROM are pending.

Private receipts and dumps remain on bench01 under the root-owned mode-0700
directory `/home/claude/fm1-device44-event120-repeat-20261014/`.
Both read and boot authorization markers are consumed; never reuse them.
No flash write occurred in this repeat. The Pico2W remains enumerated as
device 38; its separately observed FAULT status and pending GPIO wiring
confirmation do not establish app-independent FM1 recovery.
