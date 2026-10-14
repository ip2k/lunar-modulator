# Event Horizon device42 repeat hardware check

[verified] Mac coordinator reviewed the device42 adapters and corrected the boot verifier to read `fm1_event120_device42_rom_backup.py` rather than the historical device40 filename. Focused offline tests passed 13/13. Existing tests did not exercise that filename dependency; the real guarded preflight did.

[verified] Fresh bus1/device42 ROM reads completed 8,757 reviewed commands and two complete 1 MiB dumps, both SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. No flash erase/program or reset occurred during reads. Private evidence remains on bench01 at `/home/claude/fm1-device42-event120-repeat-20261014` (mode0700); no vendor bytes are committed.

[verified] One FC0C argument1 request was submitted at Unix time1792010528.4383206. Its completion was ambiguous (host7, resid16), so no retry occurred. A subsequent passive `lsusb` showed native USB bus1/device43 `1209:0001`. This establishes native enumeration following the request, not successful playback or complete functionality. Owner watched observation is pending; previous Event Horizon boot observations were missed.

[verified] The bench Pico replied to MicroPython `os.uname()` with `Raspberry Pi Pico 2 W with RP2350`, release1.29.0. This identifies the board, not its GPIO wiring or recovery ability. Its USB connection alone does not carry the GPIO-generated USB_KEY to the FM1. Hera is preparing a board-specific build; no Pico flash has occurred yet.
