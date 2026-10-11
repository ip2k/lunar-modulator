# Private SDK diagnostic

This C-only, GPL-engines-off profile uses the pinned AC79 V1.2.13 SDK and
its normal dual-core runtime. It preserves vendor startup, exception handlers
and the dormant key check, with the Apache fm1-nes stock-SPL boot_info bridge.
It is an experimental private build, not a released or hardware-qualified image.
No vendor binaries belong in this directory or in Git.

`tools/jieli/build-sdk-diagnostic.py` verifies every byte in the separately staged
SDK against the pinned inventory, builds into a separate output directory using
vendor toolchain 20250324.1, then runs the key-link and native-image audits.
It never packages or invokes a download tool. Heavy builds run on Hera with
source, SDK and toolchain mounted read-only.

The board exposes no demo devices and uses Keitark's unchanged Apache stock-
derived FM-1_010 power configuration. Actual FM-1_092 rail settings and panel
clock assumptions remain physical acceptance limits. `app_main` starts a
worker and returns so SDK timers and events continue. The worker records SDK
clocks, paints four bounded RGB565 bands through Lunar's SPI1 transport, waits
twenty seconds, then makes one reviewed RAM-marker/P33 reset request.

P33 access uses the SDK atomic cross-core lock and preserves nested local IRQ
masking. The lock acquisition itself is unbounded if another core stops while
holding it. Polling inside the transport is finite and has no OS calls. A
transmitted request does not prove reset or USB recovery. Stage 6 identifies
lock acquisition, stage 7 transmitted reset, stage 8 request failure; these are
RAM observations, not hardware acceptance.

The generated link script removes VM/BTIF cfg registrations while retaining
the read-only file cfg callbacks. Native audits pin startup/init registries,
stack and recovery-marker allocation, exact flattening, zero undefined symbols
and the owner's FM-1_092 application capacity (691744 bytes). Closed SDK storage
functions still exist through VFS tables; their reachable initialization paths
require independent instruction review, rather than assuming discarded cfg
registrations alone prove no automatic writes.

The installation adapter must retain stock SPL, OTA, cfg, loader configuration
and partitions. Keep hardware blocked until the concrete candidate and recovery
plan pass the parent review gates. Cold boot, visible output, UBOOT enumeration
and restored stock readback are separate physical checks.

Evidence and exact local/Hera artifact pins are saved in
`build/startup-resolution-goal.md` (private ignored build evidence).
