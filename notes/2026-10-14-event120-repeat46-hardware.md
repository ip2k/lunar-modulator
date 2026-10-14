# Event Horizon repeat on ROM device 46

[verified] The coordinator passively identified FM1 USB path 1-1, bus 1,
device 46, VID:PID 4c4a:8057 on bench01. Newly reviewed device46 adapters
passed 21 focused tests on both Hera and the Mac. Source was staged in a new
root-owned mode-0700 directory, leaving previous consumed campaigns intact.

[verified] The fresh read campaign completed its exact 8,757-command inventory.
Both complete 1 MiB dumps matched installed target SHA-256
145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657.
No flash erase/program or reset command occurred in that read campaign.

[verified] An initial boot preflight rejected the coordinator's incorrectly
labelled snapshot before a device command or one-use marker was issued.
The coordinator corrected the label, obtained a fresh passive mapping of
the same connection, and passed the strict boot preflight.

[verified] Exactly one FC0C argument-1 request was submitted at Unix time
1792015946.9745731. Its SG completion was ambiguous (host 7, residual 16,
info 1); the adapter latched the failure without retry. A subsequent passive
lsusb showed native USB 1209:0001 as bus 1 device 47.

[verified] Private evidence remains on bench01 at
/home/claude/fm1-device46-event120-repeat-20261014. Read and boot markers are
consumed. Native enumeration establishes neither musical acceptance nor
independent recovery. Owner observations and passive timed return remain
pending. No second reset is authorized by this consumed evidence.
