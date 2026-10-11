# Installable firmware continuation — 2026-10-11

## Objective and acceptance

Resume the owner's installable-image goal. The first acceptance endpoint is
awaiting owner clarification: a diagnostic image that boots, displays a probe
and retains recovery, or playable Lunar with controls, MIDI and audio. Both
need actual pi32v2 compile/link, stock-component/partition package guards,
reviewed concrete candidate and recovery plan, backups before flash mutation,
actual hardware boot/recovery acceptance, and required CI/review/integration.
A source component, checkpoint push or simulated display is not completion.

Branch `feature/2026-10-11@installable-firmware` starts from origin/main
`b335dc2c450473dc375163aec7fa679e1b099cc3`. Current managed checkout:
`/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
[verified] Implementation checkpoint `c95758b388c852b1ffd43d9746242eefbaf067d4`
was pushed to origin on this branch and matched the remote branch SHA. The
subsequent documentation checkpoint records these final verification receipts.
No PR was opened or main merge attempted.

## Bench state and missing hardware acceptance

[verified] Read-only SSH USB inventory as `claude@bench01.local` finds
`4c4a:8057` UBOOT, bus 3/device 18, and `/dev/sg0`/`/dev/sda`. No MIDI node.
The numeric/non-local hostname failed host-key verification; no host-key
configuration was altered. No device CDB, identity SysEx, soft key, loader
upload, erase or program was sent this session.

[reported: prior live-bringup note] The prior eight-byte loader callback read
completed and left the unit in UBOOT awaiting owner power-cycle/normal-screen
confirmation. The owner subsequently confirmed normal boot after a power-cycle (see the
Hera migration receipt below); this historical wait is closed. The source note is in the attached live-bringup checkout, branch
`chore/2026-10-10@fm1-live-bringup`, at
`notes/2026-10-10-fm1-live-bringup.md`. Its audited reader/wrapper tools and
private result paths must be recovered from that stream before use, not
silently substituted with generic loader commands. Full broken-app recovery
remains unverified. Existing inert/handover images have no app update service.

## Coherent implementation checkpoint

[verified: source inspection] Independent MIT `spi1_transport.c/.h` implements
software-only binding, explicit GPIO/mux/SPI setup, command/data CS/DC handling,
and a six-register native volatile backend. It uses no SDK/ROM calls or vendor
HAL. Primary WL82.h provides addresses/layout; recovered stock V15 provides
CON/BAUD/pin facts, as recorded in the October 9 prerequisites note. The SDK's
SPI demo labels CON bit 14 as clear-pending. GPIO output/direction/mux RMW
preserves unrelated bits and requires exclusive ownership/interrupt control.

[verified: host simulation] Pending-clear and completion waits each have a
finite register-read budget (1–65,536). Timeout disables SPI, raises CS and
latches failure with no automatic retry. Simulated cases cover stuck stale
completion, readiness on the last allowed read, command and data failures,
nested transaction rejection, delay failure, preserved unrelated GPIO/mux
bits, software-only factory/binding and full four-band pixel output.
[inferred; hardware verification pending] SPI disable before CS release is intended
to stop late clocks; pad behavior and this sequence remain unverified on device.
The poll bound is not milliseconds. No guessed clock, busy delay, PA2 write,
watchdog, exception handler, second-core release or recovery callback is added.

[verified: build source] The existing diagnostic script now compiles the backend
into a separate object and vendor disassembly without linking it into any
application variant. The source archive already includes `firmware/display/`.
It is deliberately not activated at startup until the platform prerequisites
and concrete recovery plan are reviewed.

## Verification and execution limits

[verified] Host `cc -std=c99 -Wall -Wextra -Werror` shared-library compilation
passes. Focused pytest run: 31 passed, 2 optional skips (private guarded stock
app not supplied, ignored vendor target artifact absent). A subsequent focused
run supplied the local private stock V15 app via `LUNAR_STOCK_APP`: all 14 panel
protocol tests passed, including its SHA-guarded stock setup-table comparison.
The target-artifact check remains unavailable. `bash -n` and
`git diff --check` pass. System Python lacks pytest; the existing original
checkout `.venv/bin/python` executes the tests successfully.

[verified] Aeon direct SSH to `claude@192.168.1.25` timed out. `aeon.local` did
not resolve. Standard SSH ProxyJump through bench01 reached the Pi but its
connection to aeon returned `No route to host`. No node was rebooted, woken,
reconfigured or modified to resolve this. Toolchain build remains unexecuted;
host C compilation does not verify pi32v2 ABI/code generation. The intended
reproduction once aeon is reachable is:

```sh
bash tools/jieli/link-diagnostic.sh claude@192.168.1.25 \
  /home/claude/mvave-fm1/sdk-v1213/toolchain/current \
  /home/claude/mvave-fm1/codex-installable-20261011 panel-protocol
```

[verified] Serena session `5fc0d026` was activated on this absolute worktree;
`find_symbol` locates `lunar_panel_probe` at source lines 38–63, but references
returned empty despite the known `protocol_capture.c` call. Treat empty results
as incomplete indexing, not no callers. Rarefaction status selects the original
checkout, not this worktree; worktree selection is rejected because it is
outside its configured workspace. Bare-name fallback searched only 200 files
and exact position in the original checkout is absent. No other session's
server/root was changed. File inspection and host compiler checks are used;
Rarefaction needs a connection rooted at this checkout before it can navigate
new files. Serena also locates the Python stale-completion test and its exact
body at lines 183–192; C transport diagnostics return empty, with index
completeness unproven. Neither tool validates device ABI/MMIO.

## Next dependent work

1. Receive the owner's endpoint clarification. Normal-boot confirmation is
   complete; use Hera for every further build while aeon is under maintenance.
2. Target build access and initial object review are now complete (see resumed
   verification below); continue the independent platform-contract work.
3. Establish independent clock/timer, watchdog, core/exception and PA2 contracts;
   integrate a visible startup candidate only when these are supported by evidence.
4. Close the route back to USB update mode, then prepare the exact private image
   and recovery proposal under existing package/partition safeguards. Preserve
   stock SPL/OTA/cfg and fresh compared backups before any flash operation.
5. Run the hardware acceptance and required review/CI/integration. Keep the
   installable-image objective active through these steps.

## Resumed target verification after LAN recovery

[verified: live SSH, October 11] Aeon is reachable as `claude@192.168.1.25`;
its existing pinned toolchain and `lunar-jieli-check:bookworm` image are ready.
Hera is reachable as `claude@192.168.1.48`, with Docker 29.9.0, 64 logical CPUs
and approximately 119 GiB available memory at inspection. Its batch slice is
configured. These small builds ran on aeon in existing bounded containers
(4 CPUs/4 GiB each); no infrastructure or service configuration was changed.

[verified: vendor compile/disassembly] The first target SPI object exposed an
unresolved `memcpy` from callback-structure assignment despite freestanding,
no-builtin flags. Explicit field copies remove that dependency. The build now
saves the vendor symbol table and rejects named undefined SPI-object symbols.
Rebuilt vendor disassembly shows direct word MMIO loads/stores, finite polling
branches and explicit callback copies; no external helper remains. This is
code-generation evidence, not device or electrical acceptance.

[verified: target compile/link/audit] All three variants compile and link with
zero unresolved application symbols and pass `audit_link` (0 fail, 0 pending).
Local ignored artifacts are under `build/`; remote sources/artifacts remain at
`/home/claude/mvave-fm1/codex-installable{,-inert,-handover}-20261011` on aeon.
The SPI transport is still a separate object, never activated or linked into
these RAM-only variants. Their reports still say device execution unverified,
package not created. Image SHA-256 receipts:

| Artifact folder | Flash bytes | Reserved RAM bytes | SHA-256 |
| --- | ---: | ---: | --- |
| jieli-diagnostic | 200 | 4144 | `5566edb6742aebb695a4ed2ab0e9d979ebadb615190bb030c55f59f2258fee08` |
| jieli-handover | 288 | 8352 | `0991eae9c0fc77bf4ed80f73b2d643972d70bb9151b3b0da29a2a68d41a1b19c` |
| jieli-panel-protocol | 1212 | 8400 | `ebbe370cf135d0e1dd2ad16a04b47cf67bcdfbfaa4c837b960d946a5fc86cbcb` |

[verified: tests] After the field-copy change, the focused SPI/protocol/capture
suite passes all 33 tests with both private stock and target-artifact fixtures;
no skips remain. Shell syntax and whitespace checks pass.

[verified: tooling limit] The subsequent Serena diagnostic request resolved
against the original checkout and failed with missing `spi1_transport.c`.
Selection has changed since the earlier successful worktree queries; no shared
project was switched back because another session may be using it. Target
compiler, vendor disassembly and explicit source inspection provide current
verification; the earlier empty diagnostics are not treated as current coverage.

[verified: read-only bench inventory] Bench01 still sees bus 3/device 18
`4c4a:8057` UBOOT. Owner power-cycle/normal-screen confirmation and milestone
clarification remain pending. No device protocol command or flash mutation was
sent. The installable-image objective remains unfinished; restored build access
does not close startup, calibrated delay/clock, watchdog, core/exception, PA2,
or recovery-route contracts.

## Hera build migration and normal boot — owner steering, October 11

[reported: owner] Power-cycle restored the normal FM-1 screen. [verified:
read-only USB inventory] Bench01 now enumerates `4c4a:c755` FM-1 on bus 3,
device 19, with `/dev/snd/midiC2D0`. The prior post-callback power-cycle gate
is closed. No identity query, soft key, loader command or flash write was sent.

Owner requires builds on Hera while aeon is under maintenance, and authorizes
many parallel containers when useful. No builds were launched on aeon during
this migration. A read-only asset inventory attempt on aeon timed out; two
stalled Hera NFS-path inventory SSH sessions were cancelled without modifying
NFS, Docker or other services. All new build assets use Hera's local `/home`.

[verified] Downloaded the repository-pinned archive directly from the vendor:
`https://jl-update.oss-cn-shenzhen.aliyuncs.com/jieli-linux-toolchains-20250805.1.tar.xz`.
SHA-256 `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`
matches `tools/jieli/compile-check.sh`. Despite the archive's filename, its
internal directory is `jieli-linux-toolchains-20250324.1` and clang reports
4.0.1. Never infer the compiler revision from the archive name. The vendor's
latest short link currently redirects to 20260730.1; that archive was not used.

[verified] Created the existing repository-defined Debian bookworm build image
on Hera; its image ID is
`sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.
Hera toolchain path is `/home/claude/mvave-fm1/sdk-v1213/toolchain/current`.
Three independent containers (each 4 CPUs, 4 GiB, in `docker-batch.slice`)
built inert, handover and panel-protocol variants concurrently. All links and
SDK-free audits pass. Every `diagnostic.bin` matches the aeon SHA-256 receipt
above; every SPI object matches
`2ff0a511e6820a8391f7c97714bd8ba6ff4f6ce41fc65eac200be4c05f64ac1c`.
The ignored comparison receipt is `build/hera-migration/aeon-hashes.json`.
The current local `build/jieli-*` artifacts were retrieved from Hera.

For each profile `inert`, `handover` or `panel-protocol`, use:

```sh
bash tools/jieli/link-diagnostic.sh claude@192.168.1.48 \
  /home/claude/mvave-fm1/sdk-v1213/toolchain/current \
  /home/claude/mvave-fm1/installable-PROFILE-20261011 PROFILE
```

Replace both `PROFILE` occurrences with that profile. These separate remote
work directories avoid concurrent-output races. No installable package or
hardware diagnostic execution is implied by the successful builds. The owner
endpoint question is pending; all remaining startup/recovery contracts above
still apply. Do not fall back to aeon builds while its maintenance is active.
