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

## Completed physical clock capture

[verified] The transaction journal completed, with full-image readback SHA-256
`9e864776ac931840e2859dd218a95d446c50b43ec57376b0191cf34e585459bf`.
Its record hash is
`c033bb2c8d91b76b3b931768a4c1a107e87726d273125519a9c37132d7bf71b1`.
The sole reset returned an ambiguous SG response (host7, residual16); no retry
was sent. Independently, capture observed native USB device72 and the device
subsequently returned to ROM73 after its timed diagnostic. Audio180s and
telemetry110s completed with exit0. Boot campaign SHA-256:
`998c24a95e05de3b43ef93806cdb2f27e0b5f8e957653ab3474e00956995197d`.

[verified] All 11 schema-3 reports replay the same startup sample: CLK_CON0
449 (`0x1c1`), CLK_CON2 6 (`0x6`), SYS_DIV66048 (`0x10200`), uptime0.
There are55 diagnostic and56 render-profile frames (122 valid total). Events
SHA-256 `7d1916940bca089725852d49a13ba7224ca2ed52810abe31abcbac3ccae1221c`;
raw SysEx `14ee22e523ff7e705b2e3ff85c61ddccba136a3ce45ecca37f778e3ef0080b31`;
recorder receipt `f99a0ffe72ad2a986d5fecb8cc43f599502d14447fc92ec2b15c98b5361371d1`.
Over107.957 device seconds, production averaged259.2143 blocks/s versus
689.34375 required; underruns averaged430.1250/s. Maximum render116558 ticks
(4856.58us with the existing24ticks/us conversion), budget1450.66us.
User/system observed minimum stack margins5884/7724 bytes,105 samples, are
not worst-case proof. Audio performance remains failed; SAVE stays disarmed.

[verified: source] Native audio initialization clears only CLK_CON2[11:8],
preserving its low nibble6. The reviewed post-install reset primitive is a
core soft reset, which does not establish that the stock SPL reran. The exact
stock SPL's documented requested-rate branches do not assign low nibble6.
[inferred] Loader-era clock inheritance is a plausible explanation needing
further tracing or a cold-boot comparison; these words do not measure CPU MHz.
The owner has been asked for an optional cold power-cycle comparison; offline
work continues without treating elapsed time as a response.

Private local analysis/evidence: `scratch/clock-snapshot-result/physical/`.
Pinned static branch audit: `scratch/stock-spl-clock-branch-map.md`; Hera
handoff `lunar--stock-spl-clock-decode-20261015.md` SHA-256
`887e201cc8c4f79a6d09df55eebe05df5f4a00aa31491a953e227fc0e006cd36`.

## Supplemental PLL evidence preparation

[verified: pinned SDK IR inspection] CLK_CON2 low-nibble case 6 is a valid
SDK bookkeeping branch. Its calculation also reads 0x119a0, 0x119a8 and
0x119ac. The exact integer operation order and evidence hashes are retained
in private `scratch/clock-case6-ir-extraction.md`; this does not measure CPU
frequency or prove that native startup ran the SDK initializer.

[verified: source] The same bounded diagnostic opt-in now samples those three
raw words once at startup and repeats them in a separate schema-4 frame.
Schema 3 remains byte-compatible. Both use whole-frame queue admission;
schema 4 first becomes due at five seconds, then every ten seconds after a
successful enqueue. Queue pressure may delay the report. An independent
review caught and corrected an unsigned initial-deadline underflow before
any target build. Host tests exercise the actual scheduling function at
startup, either side of the deadline, and queue-full deferral, as well as
strict schema-4 encoding/decoding and recorder/analyzer preservation.

No register writes, frequency inference, target observation or audio
improvement is established by this supplemental source change. The next
frozen build must include current limiter/sixop optimizations. A fresh
candidate constructor must require exact schema-3/4 verification metadata;
the generic flash build checker alone does not require clock diagnostics.
ROM71's consumed campaign must not be reused.
