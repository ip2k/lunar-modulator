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
confirmation. This confirmation remains requested before further device
traffic. The source note is in the attached live-bringup checkout, branch
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

1. Receive the owner's endpoint clarification and normal-boot confirmation.
2. Restore access to the existing LAN target build; compile/review the SPI object,
   especially 32-bit MMIO accesses, pending polling, and unresolved symbols.
3. Establish independent clock/timer, watchdog, core/exception and PA2 contracts;
   integrate a visible startup candidate only when these are supported by evidence.
4. Close the route back to USB update mode, then prepare the exact private image
   and recovery proposal under existing package/partition safeguards. Preserve
   stock SPL/OTA/cfg and fresh compared backups before any flash operation.
5. Run the hardware acceptance and required review/CI/integration. Keep the
   installable-image objective active through these steps.
