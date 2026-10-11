# Offline entry guard and display/recovery composition

2026-10-11. Lunar Modulator, personal and non-commercial. The endpoint remains
an installable diagnostic image that boots, shows the display probe and retains
recovery. These independently authored MIT components are offline prerequisites;
neither is an installation candidate or a hardware activation permit.

## Entry prerequisite

[verified: Hera linked bytes and vendor listing] The separate `entry-guard`
profile contains nine instructions, 26 bytes. It preserves incoming r0, masks
local ordinary interrupts, checks cnum exactly zero, then compares r0 to
0x01c7fe08 without dereferencing it. Accepted and rejected outcomes enter
different CLI/self-branch loops. No calls, returns, RAM/MMIO accesses, stores,
SP/SSP changes, core1 policy, vector installation or board output are present.

Its linker allocates only `.entry`, with one RX PT_LOAD mapping exactly the
26-byte entry at 0x02000120. ELF headers are excluded from that mapping. The
strict audit binds the flat bytes, ELF, complete vendor rows, branch targets,
symbols and generic SDK-free receipt to the same artifacts, recomputing that
receipt rather than trusting its supplied pass summary. Existing package and
raw-image profile allowlists exclude this guard. `hardware_ready=false`.

[verified: independent review] The first review identified unchecked load
mapping and stale/swapped receipt provenance. Both were fixed and independently
rechecked against the saved Hera artifact. A later review identified accepted
noncanonical ELF header fields and mismatched old log/new XML test receipts;
the final fix pins the actual vendor header/section geometry and rejects each
independent header mutation even with recomputed receipts. Final independent
review found no residual issue in this audit scope. The fresh coherent log/XML
report 178 passing focused checks, zero failures/errors/skips, in 7.392 seconds.

The flat SHA-256 is
`851d39f06a992af8f8835e1e7b8791447f9eb8d60760abd5e6799bcb55e4e202`.
The linked ELF SHA-256 is
`7d462ec547761e131f2092ffcd6cea7d33f9ae9c97455ab1600a91988dd9f965`.
An independently linked CLI-to-STI mutation fails the strict byte audit.
Existing inert, handover and panel-protocol target builds also pass their
separate audits. These are compilation/artifact results, not device execution.

| Saved entry evidence | SHA-256 |
| --- | --- |
| tools/jieli/entry_guard_audit.py | `ab078ae42ed44f1fb5cbb1317bd0d7c6ee26a1e5b0be0b27e1d8d8c86bbd7dfa` |
| tests/test_entry_guard_audit.py | `fe5932ee80c4cc500bd8023536e1d94fcfeeec38e423367ef44752d552acbac7` |
| build/jieli-entry-guard/focused-tests.log | `d1c008a9acf6b21075741e7a550156ee9f5ad9e1bfb1fa589336b68bdb4a4f1d` |
| build/jieli-entry-guard/focused-tests.xml | `e6561fd174bd87b34d76651872b78898337f250bb265dd612024e8bde4312b56` |
| build/entry-guard-independent-review.md | `bd40e27d107b7cc6412bc49e94cc17ff8bcb97252b11478df4ca274f048d2494` |

## Actual component composition

[verified: source and host execution] `firmware/bringup/bringup.c` directly
joins the existing panel probe and recovery requester. Bind invokes no callbacks
and validates caller-owned, initialized references, required callbacks, recovery
state/poll bounds and dwell 0–1000 ms. Run latches its attempt before effects,
revalidates its inputs, invokes the panel probe, and dwells through the same bus
only after successful display. It ends the bus before one recovery request,
including after display, transfer or timer failure. Malformed inputs write no
marker. A used controller cannot be rebound or replayed.

Display, dwell, request invocation and transmission have separate result fields.
COMPLETE denotes finished orchestration even on a failed operation; transmitted
does not establish reset, enumeration or usable recovery. References and callback
contexts must remain alive and exclusively owned. Arbitrary dangling pointers,
concurrent mutation or resetting used storage are outside this C contract.

[verified: Hera host tests] The new integration tests compile the actual panel,
SPI1, TIMER4, recovery and controller C together with warnings as errors. Actual
SPI1 wait callbacks invoke actual TIMER4 delay; a finite register simulator
injects setup/pixel completion loss and stuck-clear failures, timer failures
before display and during dwell, mailbox corruption and timeout on each P33
reset-request byte. Tests check the complete pixel count, cleanup ordering,
marker persistence, bounds, invalid-interface suppression and non-replay.
The new module passes 55 tests; combined component regression passes 117 with
one optional private-stock fixture skip. Independent source review found no
blocking issue. It did not rerun those tests; root's full-suite regression is
a separate evidence layer.

[verified: pinned target compiler] `compile-bringup-in-container.sh` compiles
all five C components with JieLi 20250324.1. A relocatable aggregate resolves
the controller's exact panel/recovery dependencies with no unresolved runtime
helper. It creates no boot ELF, flat boot image or package, and remains outside
all diagnostic link/staging profiles. Native compilation does not prove ABI,
startup state, clock rates, peripheral ownership or device behavior.

| Saved composition evidence | SHA-256 |
| --- | --- |
| firmware/bringup/bringup.c | `c5e13b2b2ad7f831e27568d362611bfbe40e2c2104632e22dda8b153428d94d6` |
| tests/test_bringup.py | `123e3aa082d5fd2c96e9eda1f89d946f97ccd58e6b2fe17083bfee20cf5a4582` |
| tools/jieli/compile-bringup-in-container.sh | `3710b8cea30f5ac6b74a7923e21db8e8bdff2309969b5f14db888da1e1cc12d3` |
| build/bringup-evidence/tests.log | `c5849a55f25af807bcc7ed98f71b1c474c54bdf0a3e43af252b28d8ef539e70c` |
| build/bringup-evidence/native.log | `1e6b50d662be018505b2c2d080c71aa52826a3daf211c0941a0347b1da5c9f1f` |
| build/bringup-evidence/native/bringup-components.o | `ca431ad053cb6fba315520d513c378247f5fca9a6aa970753b9cf0d020239a1b` |
| build/bringup-independent-review.md | `b7a25782796bb6804c473bd7cb59ee92a07d621375fc843eedebeba62b6c709a` |

The ignored build handoffs/reviews contain detailed source pins and commands;
their essential implementation, findings and acceptance limits are preserved
here so Git backup does not depend on ignored artifacts. All heavy execution
used Hera, bounded containers and cached tools; aeon was untouched.

## Combined sixteen-container regression

[verified: frozen archive, Hera execution and root receipt review] Exact source
`38a7d53cd101c03bd5319c0f202b8f4dfc5bbc57` collected 5,851 unique Python
nodes across 131 modules. The sixteen concurrent chunks contained 365–367
tests. JUnit aggregation reconciles every collected ID exactly once, with
5,813 passes, 36 skips and two expected failures, with zero failures/errors or
unexpected passes. JUnit groups the 38 skips/expected failures together; those
nodes and reasons are identical to the preceding `b397ca90` run. Each container
exited 0 without OOM; elapsed shard times were 30.778–128.526 seconds.

All containers used the pinned Python3.11.2 image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
four CPUs, 4GiB, `docker-batch.slice`, no network and fresh isolated source
copies. Root verified 152 evidence-manifest entries, matched all 1,598 remote
source files to the frozen Git archive, and reproduced the exact aggregate.
All sixteen container IDs were removed; the final live task-label query
returned none. Independent read-only review recomputed the allocation,
collection identities, archive/source hashes, per-shard XML/log/receipt agreement,
all Docker resource/exit/removal records and the 152-entry manifest; no blocking
finding remained. The later CI snapshot and root handoff are separate additions
covered by a supplemental manifest, preserving the original Hera manifest.
Final read-only documentation review independently parsed all sixteen XML
files, confirmed the two sequencer-oracle undo expected failures and checked
the source/profile pins and unfinished milestone boundaries; it found no
blocking documentation issue. Root owns the final live CI snapshot.
These are host/Linux regression results, separate from target code generation,
cross-platform CI and physical execution.

Local receipts are ignored `build/recovery-python-shards-entry-bringup/`;
remote receipts are
`/home/claude/mvave-fm1/recovery-python-shards-entry-bringup-20261011-38a7d53c/`.

| Combined regression evidence | SHA-256 |
| --- | --- |
| Source archive | `4486853d7f06495d7480ac8c6bf62a48409546b4cd5352f5bba8270914f0e271` |
| plan.json | `c87afed22a5d019bedc0e106c0bfbcdee68f174762ff215d639559da75c33db1` |
| aggregate.json | `4ff89ed2b3d2d0606329a387321ddbae73cd44bf6cdf6e9ca3c725c35955bb20` |
| runtime.json | `0eb40ea59fd28b4d74947d7a16aacbae0dbd12a36bd7d7d1a492ee4fc2f0b771` |
| evidence-sha256.txt | `b27ce2dba1820a18fa65e6c31bd2c043b089b77f80e08c6c55331f7c74a41dfd` |
| Receipt archive | `b06c597727dcbd8be26ad033ebe413d7fc8ab35ef7d502150b27f855eb1ccd08` |
| build/shard-entry-bringup-independent-review.md | `9eed9029fa7d830330e3cf12c938e715e4d9057c349a954af38bd5f7e065c445` |
| build/final-receipt-doc-review.md | `e1b4d504b779b5427d051ccec062974cd8aa3a31e4ce7792502d3a96e661beaf` |

Exact-source [CI run38179739714](https://github.com/ip2k/lunar-modulator/actions/runs/38179739714)
was dispatched and remains in progress at this receipt checkpoint. No PR or
merge was performed; the agreed installable-image milestone remains unfinished.

## Remaining endpoint and source-navigation limits

The [native startup contract](2026-10-11-native-startup-contract.md) still gates
activation: no finite acknowledged secondary-core hold, masked exception
delivery specification or safe privilege/SSP/protection transition was found.
Clock/power, watchdog, PA2, peripheral/mailbox ownership and recovery from the
actual application context also remain open. The separately successful
[UBOOT return](2026-10-11-fm1-core-reset-bench.md) restores bench access, but
does not close these application-entry or broken-app recovery gates. No flash
operation occurred in this component work. Preserve fresh matching backups,
stock SPL/OTA/cfg/layout guards and concrete image/recovery review before any
future installation.

Rarefaction and Serena still select the original checkout during concurrent
work; their shared selection was not changed. Rarefaction rejects this absolute
worktree path. Serena's bounded absolute find_symbol returned the actual
controller and panel bodies, matching source, but its reference query rejected
the worktree caller as outside the configured workspace. This is partial symbol
navigation, not complete worktree reference coverage or target ABI verification.
Exact source, real host C tests and pinned vendor compilation supply the checked
evidence. The whole-flash simulator remains a protocol/NOR model, not a pi32v2
CPU emulator.
