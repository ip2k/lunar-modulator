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

[verified] The offline analyzer now validates and preserves schema-3 clock
snapshots as raw startup observations, separate from diagnostic counter deltas
and schema-2 render windows. It accepts clock-only logs without manufacturing
performance data, rejects malformed fields/schema/uint32 values, and leaves
CPU frequency uninterpreted. Analyzer plus recorder regression: 44 tests pass.

[verified] Hera completed a fresh frozen build from exact source
5c4502ee552f51e40fe54527dc8fe2dea58dd300. App size 853,324 bytes,
SHA-256 `072f82f37a5b2a8005127fae551f92f4094e96faf283ab925a71d8297bd66820`;
frozen receipt `78e3b7d6c00da6f55798fa955909e8b7821fd132cbc19abb7f7b3f29f6c553f6`.
The existing generic build validator passed; container exit0/noOOM. Handoff:
Hera:/home/claude/.local/share/codex-coordination/handoffs/lunar--clock-snapshot-build-20261015.md.
Source confirms the three volatile reads; inlined target accesses were not
reliably mapped in disassembly. No physical clock observation or performance
improvement has been established.

## Fresh ROM71 campaign started

[verified] The private coordinator passed file-only preflight on bench01 and
started its one-use cycle at
`/home/claude/fm1-clock-5c4502ee-20261015/rom71-clock-cycle`. Fresh paired
reads passed and installation began. Candidate full-image SHA-256 is
`9e864776ac931840e2859dd218a95d446c50b43ec57376b0191cf34e585459bf`;
210 sectors differ from the previously verified current image. The reviewed
policy allows 211 sectors; these counts have different meanings. Candidate
receipt SHA-256 is
`789aad6e856d77d7552f172eda7781efc194919f84e41fb8c2dac92628bf0292`.

Final runner SHA-256 is
`19aa367b750fce60866607eeef1add810cd71daf6fb627f2e6054fa9a90f4971`;
passive capture helper SHA-256 is
`04f905716d5baf2a8e0e3b667c223f8c2fbc5a4267a66a76c1fc97980c4b4d39`.
Runtime manifest SHA-256 is
`044a87ed21a249eaa76ca6c0b60dbcac18e064f69fe14dfccb2ab9432f3444b4`.
The initial file-only preflight rejected a mismatched boot-adapter pin before
any live operation; the corrected pin matches both the reviewed hot-DSP
adapter and the deployed file. Eight focused coordinator tests passed.

Installation completion, readback, boot, clock observation and audio results
remain pending at this checkpoint. Do not rerun this consumed cycle or retry
an ambiguous reset. Inspect its durable journal and capture first.
