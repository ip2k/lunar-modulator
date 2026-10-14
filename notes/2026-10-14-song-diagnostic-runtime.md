# Bounded full-song diagnostic runtime — 2026-10-14

The Event Horizon Showcase candidate lasts 108.8 seconds in the native host
renderer. The default twenty-second device probe cannot establish complete-song
playback. Added an explicitly selected `--runtime-mode song-diagnostic` to the
private application builder, returning to mask-ROM recovery after 120 seconds.
The ordinary diagnostic remains the default; continuous mode remains explicit.
No mode establishes hardware or release admission.

The application now measures its recovery deadline using the existing `fm1_ms`
clock. A single subtraction on the high-resolution 32-bit counter cannot span
two minutes at the target tick rate. Unsigned millisecond subtraction handles a
counter wrap during either bounded diagnostic. The watchdog, USB recovery and
boot-failure guards are unchanged. The browser controller continues to accept
only its fixed twenty-second diagnostic recipe and rejects a 120-second receipt.

Verification [verified]: 70 actual host-C timer/configuration tests passed on
Hera, covering default/20/120/continuous, deadline boundaries and counter wrap.
23 controller receipt tests passed, including rejection of the longer runtime.
Container: `lunar-recovery-pytest:20261011`, immutable image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
network disabled, docker-batch.slice, 2 CPUs, 2 GiB memory and equal swap cap,
read-only input at `/home/claude/mvave-fm1/song-runtime-review-20261014`.
The timer run emitted only a read-only pytest-cache warning; the controller run
disabled cache and was warning-free. Target code generation/link and physical
timekeeping/recovery remain unverified for this new mode. No hardware commands
were issued.

Serena's overview located the actual worktree timer function. Rarefaction's
shared primary-checkout root rejected the external worktree path; file inspection
was used without changing another worker's active root. Host-C tests do not
validate the pi32v2 ABI or target interrupt timekeeping.

Next: link the exact full-song candidate with this explicit runtime, inspect its
target audits and flash/RAM budget, then prepare a fresh reviewed hardware
campaign. Owner watched playback/listening and recovery remain required.
