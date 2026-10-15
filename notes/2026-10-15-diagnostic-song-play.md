# Explicit unattended song diagnostic

[verified: host tests] `--diagnostic-song-play` is opt-in and restricted to a prepared project startup in the 120-second song diagnostic with telemetry and without the Trio pulse. The generated receipt identifies the one-shot action and its two-second readiness delay. The main loop consumes that action once after the initial audio refill and presses/releases normal PLAY only if playback is stopped. An external Stop after the attempt is therefore respected. The independent boot-origin recovery deadline is unchanged; time spent initializing or in a chooser reduces available playback time.

[verified: host tests] Compiled C tests exercise the delay boundary, unsigned timer wrap, null state and no repeated action; builder tests reject unsupported modes and missing prerequisites. Target link and physical song timing/audio acceptance remain pending. Normal firmware does not automatically start playback through this diagnostic switch.

Source-navigation limitation: Rarefaction and Serena both currently resolve the primary checkout rather than this authoritative installable-firmware worktree. Serena's symbol query returned file-not-found. File inspection and host compilation were used; neither index provides ABI or target-build proof.
