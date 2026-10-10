# RAM-only panel protocol target link

2026-10-09. Personal MIT stream `chore/2026-10-09@panel-protocol-link`,
based on main `cafd77e0`. No hardware traffic, peripheral writes, package,
release or device execution. This is the next bounded offline preparation
after the [handover link](2026-10-09-handover-preparation.md) and
[display prerequisites](2026-10-09-lcd-runtime-prerequisites.md).

## Result and evidence

[verified] The explicit `panel-protocol` link variant compiles the existing
display protocol and a new independently authored RAM sink into the handover
application. Startup still preserves incoming r0, initializes bounded
data/BSS and SP/SSP guards, snapshots only the recognized boot pointer, and
never returns. Only status 1 invokes the sink. No SDK, ROM or MMIO backend is
linked; callback waits record requests without waiting. This deliberately
does not fulfill the hardware transport's minimum-delay contract.

[verified] State `lunar_panel_protocol` contains a tagged FNV-1a transcript,
command/data/end counts and requested waits. The sink checks active transaction
and counter bounds before accepting events. A host run matches the separately
exercised mock-transport transcript: 22 commands, 115254 data bytes, 22 ends,
two wait requests totaling 220 ms, no active transaction or protocol error.
Canaries and repeated invocation establish bounded destination writes and
fresh reset; malformed callback sequences exercise rejection.

[verified] Fresh vendor target link on aeon, capped at four CPUs/4 GiB in
`docker-batch.slice`, passes the unchanged SDK-free audit with zero failures
or pending checks. Explicit handover layout validates 1212 flash bytes,
4 data bytes, 160 BSS bytes and 8400 reserved RAM bytes within the 16 KiB
budget. SP/SSP each retain 4096 bytes and a 16-byte guard. The entry remains
`0x02000120`. Vendor decode shows the guarded capture call, indirect callback
calls and inline integer multiply; no unresolved libc/libm/SDK provider.
This is compiler/link evidence, not observed callback execution on pi32v2.

[verified] Fresh default inert and handover builds retain their prior flat
SHA-256 values (`5566edb6…` and `0991eae9…`). The report's default inert profile
and actual staging function both reject this variant's SSP section before
stock access or output creation. SDK audit defaults and package guards are
unchanged. Focused LAN pytest: **97 passed, 2 skipped** in 0.62 seconds,
including the actual target artifact layout/staging rejection. The two skips
require optional stock binaries; no new stock validation is claimed.
Earlier test attempts failed because the bounded LAN export omitted existing
staging/docs dependencies; completing the export resolved them without
changing the acceptance tests. The link image lacked pytest, so host C tests
ran in the cached Python 3.13 Bookworm image with pytest installed transiently.

[verified] CI head `7385bee7`, run `38026499766`, macOS job
`114138347580` stopped during Python 3.12 / pytest collection: the new test
used `from test_panel_probe` although the repository's tests are a package.
The earlier partial LAN export omitted `tests/__init__.py`, masking this
import error. A complete tracked-tree export reproduced the same failure
with `PYTHONPATH` unset. Qualifying the import as `tests.test_panel_probe`
restores root collection: **5207 tests collected** on bounded LAN Python
3.12. Focused protocol, capture, layout, memory and audit checks then report
**80 passed, 1 optional stock-dependent skip**, including the actual linked
artifact layout and default staging rejection. No target source, linked
artifact or acceptance gate changed; fresh CI is required for the new head.

Full sizes, hashes and byte-column comparison count are in the
[receipt](data/2026-10-09-panel-protocol-link.json). Vendor artifacts remain
ignored in `build/jieli-panel-protocol/`; LAN source/output:
`/home/claude/mvave-fm1/panel-protocol-link-20261009/{src,out}`.

```sh
bash tools/jieli/link-diagnostic.sh claude@192.168.1.25 \
  /home/claude/mvave-fm1/sdk-v1213/toolchain/current \
  /home/claude/mvave-fm1/panel-protocol-link-20261009 panel-protocol
```

## Remaining application and hardware gates

This closes a component-to-target-link gap only. Low RAM still overlaps the
loaded stock SPL and is not proven private; the code remains non-returning
with no calls into overwritten SPL. Boot input/header validity, exception
vectors, IRQ/current-core/secondary-core ownership, final watchdog state and
budget, clock/power and inherited XIP/cache/SFC remain unknown or incomplete.
There is no transport to observe the RAM result, no calibrated delay, bounded
SPI/GPIO backend, externally visible LCD output, installable application,
running instrument or passing owner device test. Full-image/broken-app
recovery remains distinct from the earlier bounded restore proof.

Next work must establish those startup/board contracts before implementing
a hardware transport; successful static linking cannot justify a device
experiment. Preserve the stock SPL and guarded package policy. No GPL
implementation was copied; the existing V15 protocol facts retain their
credited evidence in the prior display note.

Serena inspected the exact isolated firmware project and capture symbols.
Rarefaction's configured original checkout lacked the newer handover source
and had no compilation database; its fallback cannot establish target ABI.
File inspection and the pinned vendor link/disassembly supply this evidence.
