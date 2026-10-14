# Native NOR HAL candidate audit — 2026-10-14

Scope: identify reusable physical NOR operations in the pinned SDK-free
Dinghy/Felucca runtime and the already-reviewed fixed RAM loader. This is a
source and retained-link audit only. No bench, USB, loader execution, NOR
operation, or production edit occurred. The diagnostic-image and physical
recovery goal remains the controlling milestone; this audit does not admit an
application NOR writer.

## Finding

`firmware/third_party/dinghy/hal/fm1_flash.h` contains an independently visible
SPI NOR implementation, including JEDEC ID (`0x9F`), addressed 4 KiB sector
erase (`0x20`) and page program (`0x02`). It is the only application-side
candidate found in this checkout. However, it is GPL-3.0-only, permits the
legacy Felucca store/global regions and OTA-staging ranges, and has a
synchronous global-IRQ-off contract; it does not
meet Lunar's project-save I/O contract as written. More decisively, the current
retained SAVE-scheduler ELF does not contain usable erase/program operations:
its linked `fl_erase4k_ram` and `fl_prog_ram` symbols are each four bytes and
disassemble to `r0 = -1; rts`. They fail closed before touching hardware.
Therefore the current all13 application cannot use this driver to write NOR.

The reviewed fixed RAM loader has a second NOR implementation, but it is
loader-private machine code, not an application driver or source-level API.
Its relevant methods are traced in
`notes/2026-10-11-fixed-loader-nor-write-review.md`: read `0x01c04e1a`, ioctl
`0x01c0505a`, erase primitive `0x01c04ffa`, and page-program primitive
`0x01c04e50`. The note proves narrow command paths and also documents that
write return/completion is not trustworthy without independent readback.
Do not reuse or link this loader implementation into Lunar.

## Dinghy source and linked evidence

In `firmware/third_party/dinghy/hal/fm1_flash.h`:

| Operation | Source path | Relevant behavior |
| --- | --- | --- |
| JEDEC read | `fl_jedec_ram()` (around line 146), via `fl_enter`, `fl_cs`, `fl_tx`, `fl_rx`, `fl_exit` | Leaves XIP, issues `0x9F`, reads three bytes, then restores XIP. Platform startup accepts only `0x856014` (`firmware/third_party/dinghy/src/platform.c`, around line 329). |
| Sector erase | `fl_erase4k_ram()` (around line 166), called by XIP-side `fl_erase4k()` (around line 231) | Requires aligned `0x1000` range accepted by `FL_RANGE_OK`; sends WREN `0x06`, checks WEL, sends `0x20` and 3-byte address, invalidates cache, polls WIP with a 500,000 µs limit. |
| Page program | `fl_prog_ram()` (around line 183), called page-by-page by XIP-side `fl_write()` (around line 239) | Requires 1–256 bytes wholly within one 256-byte page and an accepted `FL_RANGE_OK` range; sends WREN, checks WEL, sends `0x02`, address and payload, invalidates cache, polls WIP with a 10,000 µs limit. |
| Read | `fl_read_ram()` (around line 202), used by `st_read()` in `src/platform.c` around lines 74–86 | Uses fast-read `0x0B`, address and dummy byte, then reads into caller buffer. The source has no address-range check in this entry point. |

The header's own contract requires every instruction executed while SFC/XIP is
off to be in `.ram_text`, with no calls, `.rodata` or XIP helpers, and requires
callers to enter with interrupts disabled. The linker scripts place this
section at `0x01c00000` (`firmware/third_party/dinghy/app.ld` and
`firmware/native/app.ld`); `fm1_cstart()` copies `_rt_load` to `_rt_start.._rt_end`
before ordinary application startup (`src/platform.c` around lines 286–290).
The current retained ELF confirms `.ram_text` at `0x01c00000`, size `0x468`
(1,128 bytes), load address `0x020d28dc` (`build/native-save-scheduler-20261014/save-scheduler-link-v1/sections.txt`
and `save-retained.map`, around line 4418). Its retained JEDEC and read
disassembly is inline and uses immediate SFR addresses; no called helper or
external rodata was observed in those routines. This is static-link evidence,
not target execution or proof that an operation is safe on every NOR variant.

The same current map lists `fl_erase4k_ram` at `0x01c00000`, size 4, and
`fl_prog_ram` at `0x01c0014e`, size 4. The linked disassembly at those addresses
is only `r0 = -1; rts`. The source-level bodies are consequently not evidence
that the retained application has an enabled physical writer. Keep the
current `FL_RANGE_OK` fail-closed build behavior until an explicit reviewed
storage profile and complete write-admission gate exist.

### XIP-off, interrupt and watchdog behavior

The source snapshots SFC/SPI state, disables SFC XIP, moves the pins to SPI0,
performs the transaction and restores XIP. It does not save/restore the prior
interrupt mask: `irq_save()` always executes `cli` and returns zero;
`irq_restore()` always executes `sti`. Each erase holds global interrupts off
for the full WIP poll, up to 500 ms; each program holds them off for the full
poll, up to 10 ms. Calls from `st_read()` likewise disable global interrupts
around each read chunk (up to 256 bytes). This blocks unrelated interrupt
service for each transaction; it is not the interrupt-friendly asynchronous
I/O promised by `firmware/native/project_save_service.h` around lines 24–28.

The HAL does not feed the watchdog from RAM. Dinghy arms it with `0x0D` during
startup (`src/platform.c` around line 313); the timer comment maps `0x0A` to 1 s
and `0x0F` to 32 s, with main/OTA idle-loop feeds (`hal/fm1_sys.h` and
`src/platform.c`). The OTA loop feeds while waiting for transport, but the
synchronous erase/program routines do not call that idle hook. One sector
erase's 500 ms polling bound is shorter than the configured nominal watchdog
interval, but a caller sequence that remains in synchronous save work longer
than the remaining interval can reset before returning to the main-loop feed.
No target timing or reset behavior is established here. A future adapter must
bound each indivisible erase, preserve the caller's IRQ state, provide a
documented watchdog-feed strategy between operations (or prove a tighter
whole-transaction bound), and return to the scheduler between erase/program
units. It must not feed or call an XIP helper while XIP is unavailable unless
that call chain is separately placed and audited in RAM.

Error handling is mixed. Erase/program reject invalid range/alignment,
unsupported SFC modes and missing WEL, and report WIP timeout as `-4`.
However, `fl_tx()`/`fl_rx()` discard the result of `fl_spi_wait()`, so SPI
peripheral timeouts do not propagate as operation errors. The read path returns
success after data transfer and has no range check. `fl_wait_ready()` measures
time with TIMER4 and has a maximum, but its status-byte transfer can itself
silently time out. No source-level result alone should be treated as proof of
completed programming; require bounded readback and compare against expected
bytes, then verify the complete protected region.

## Loader-private implementation boundary

The fixed loader audit is based on an exact private encrypted/decoded
candidate and vendor-disassembler listing; see `notes/2026-10-11-fixed-loader-nor-write-review.md`
for hashes, addresses and trace limits. That review establishes narrow FB01
erase and aligned FB04 program paths under stated state assumptions, but says
the loader has no application partition policy, does not validate the FB04 CRC
in the traced handler, ignores write results and has no reliable post-write
completion signal. Its internal methods are machine code within the loader
image and depend on loader-owned handles, dispatch tables, USB callbacks and
initialization. The current checkout does not contain those loader sources as
an application HAL. The RAM recovery probe in `firmware/ram-recovery/` is a
separate MIT reset request experiment; its source explicitly does not access
NOR. None of these recovery paths can substitute for an app NOR driver.

## License and provenance

`firmware/third_party/dinghy/UPSTREAM.md` pins the unmodified Dinghy source to
`zvenson/dinghy` commit `d44df7db09b98ccad2f1233b8f83f5f09c04829e`,
GPL-3.0-only, and requires its license and source notices to remain. The
separate `engines/third_party/felucca/UPSTREAM.md` covers three GPL-3.0-only
engine sources and does not provide a flash driver. This audit finds no
permissively licensed application NOR implementation in the pinned Dinghy
runtime. Any reuse must retain the GPL profile boundaries already recorded in
the repository; a small independent adapter does not remove the linked HAL's
license obligations.

## Recommended bounded next step and gate

For eventual application persistence, first write an explicit physical profile
that is limited to Lunar's admitted project-storage extents and uses the
existing transaction/journal policy. In a separate change, adapt the Dinghy
transport sequence only after reviewing its upstream license and registering
the profile's allowed ranges. Keep all RAM-executed code, constants and
interrupt masking auditable as one linker-checked call graph; preserve/restore
the exact IRQ state; propagate SPI transfer errors; reject all unrecognized
JEDEC IDs and unsupported SFC modes; use bounded status polling; and return
from each sector/page unit so the save service can feed the watchdog and keep
its scheduler contract. Preserve existing audio-stop, one-way generation
consumption, no-implicit-retry, journal commit-last and protected-region rules.

Before any hardware admission, require a fresh image/link receipt proving the
full transitive XIP-off call graph and RAM constants, a fail-closed source and
artifact range audit, fault-injected transaction tests, repeated link/map size
and RAM-residency checks, and independent review of a concrete image plus
recovery plan. Physical acceptance then requires the already-authorized staged
backup/restore plan and explicit owner-governed device steps; this offline
audit grants no new hardware operation.

## Evidence limits

Static source and retained-ELF evidence is from the worktree's current save
link; loader evidence is from the prior exact-image offline review. No target
was run. The physical in-package NOR's exact part variant, protection bits,
power-loss behavior, and XIP-off timing remain unverified. Rarefaction selected
the primary checkout instead of this worktree, so source navigation here used
bounded file and link-artifact inspection; no semantic-tool coverage is
claimed. Serena selected the worktree, but no source edit depended on semantic
tool output.
