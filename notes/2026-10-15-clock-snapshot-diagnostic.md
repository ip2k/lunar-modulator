# Raw clock snapshot diagnostic

[verified: source/host tests] `--diagnostic-clock-snapshot` adds an opt-in schema-3
USB-MIDI report to bounded native diagnostics with explicit telemetry. It takes
one volatile read each of CLK_CON0 (0x1000c), CLK_CON2 (0x10014), and SYS_DIV
(0x10008), in that order, at `app_main` entry after platform initialization.
The snapshot includes that entry's uptime. Reports repeat the immutable sample
about every ten seconds when ten USB-MIDI packets fit; they defer other reports
for that main-loop iteration and never block audio awaiting queue space. Default
builds contain no snapshot call or state. No clock/PLL/voltage writes are added.

[verified: offline SDK/SPL inspection] The pinned V1.2.13 SDK initialization uses
ordinary volatile configuration loads at CLK_CON2 and SYS_DIV; its mutable source
setter also loads CLK_CON0. Calling SDK `clk_get()` would return cached clock
information rather than establish the inherited native runtime configuration.
The exact stock SPL sets the PLL source on its common continuation, but static
code does not prove the branch taken on the device. SDK active and disabled PLL
selector declarations disagree. Therefore the new report preserves raw words
and deliberately makes **no MHz claim**.

Evidence handoff on Hera:
`/home/claude/.local/share/codex-coordination/handoffs/lunar--clock-getter-reads-20261015.md`,
SHA-256 `dc230b2e2bac4b70cb21e1edb511d760ed19268e0f96fda2b61b245df8f3a997`.
SDK commit e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d; cpu.a SHA-256
fe18129bfee7758074c486b2d33b2ed59a8c365600362d982992677c47821b2a;
WL82.h SHA-256 6f5a44f39282f66203d837a1c74c9d8197d2856547356fce8ed0d191318ff645.
The archive member was inspected as LLVM IR; it was not a native machine-code
object and no pi32v2 disassembly of that member is claimed.

[verified: host] The diagnostic/decoder/builder/recorder/analyzer suite passed
56 tests before the additional dedicated recorder test, which passed with its
12 recorder peers. The independent focused review passed 33 tests and found
no blocker (private `scratch/clock-snapshot-review.md`). The C harness checks
exactly three loads, immutable replay, canonical 32-bit SysEx encoding, packet
termination, invalid index behavior and mixed schema 1/2/3 capture. Decoder
rejects truncated and noncanonical numeric fields. Recorder emits a separate
`clock_snapshot_frame` event/count and opens no MIDI output. Build policy
rejects continuous-runtime or implicit-telemetry admission.

No target build, register observation, clock frequency, audio improvement or
hardware acceptance is established by this source/host result. A frozen build
and a separately reviewed fresh diagnostic cycle remain required. The earlier
f524e019 hot-DSP candidate does not contain this option or protocol.
