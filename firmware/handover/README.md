# RAM-only stock handover preparation

Independently authored MIT, SDK-free variant alongside the unchanged inert
diagnostic. This prepares a bounded startup contract; it supplies no board
output, update service or evidence of device execution.

Entry uses the stock app address, CLI, its own SP and SSP reservations, then
calls C without modifying incoming r0. C initializes only its bounded low
RAM data/BSS, retains the argument, and dereferences it only when it matches
the statically established stock SPL pointer `0x01c7fe08`. It snapshots six
words, zeros the remaining seventeen slots, initializes SP/SSP guard bytes
and spins checking them. The separately copied 32-byte SPL header is not
read, copied or relocated; any pointer to it in the six words is preserved
as an opaque value. There is no SDK consumer of the snapshot.

Status 1 means cookie checks matched, 2 a cookie mismatch, 3 an SP/SSP guard
mismatch, 4 an unexpected incoming argument (no dereference). State is
`lunar_handover` in the ELF. No debugger or device transport currently
observes this RAM state, so this is still an inert link artifact.

```sh
bash tools/jieli/link-diagnostic.sh claude@192.168.1.25 \
  /home/claude/mvave-fm1/sdk-v1213/toolchain/current \
  /home/claude/mvave-fm1/codex-handover-preparation-20261009 handover
```

Artifacts are ignored under `build/jieli-handover/`. The explicit `handover`
layout profile validates both 4 KiB stacks, both 16-byte guards, unique
required sections, NOBITS reservations and exact ELF/flat load bytes. The
default inert profile remains strict and rejects this extra allocated SSP
section; current staging/replacement tools do not accept this variant.

The low RAM link budget overlaps loaded SPL RAM and is not proven private.
The variant never returns or calls overwritten SPL code. Its own SSP does
not establish exception vectors or secondary-core ownership. Inherited
XIP/cache/SFC, clock/power, final watchdog and IRQ/core/exception state
remain unknown or incomplete. The boot-info snapshot is not an SDK ABI
bridge, and no peripheral or MMIO is touched.

See [target evidence and continuation](../../notes/2026-10-09-handover-preparation.md).
