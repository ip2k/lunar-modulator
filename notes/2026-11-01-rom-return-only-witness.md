# Separately named return-only ROM candidate

The bounded offline source candidate at `firmware/rom-witness-return/` adds
one explicit `rts`, a fixed linker and separate builder/auditor. Original W01
source, manifests, tools and retained bytes remain unchanged [verified: scoped
Git comparison]. The prospective contract is two code bytes at `0x01c02000`
plus 510 zero padding bytes. No actual vendor output is claimed at the source
checkpoint; that job requires source review and separate allocation.

The focused host suite exercises the actual checker with synthetic fixtures:
extra/changed code, entry/machine/section/symbol/relocation faults, all 512
single-byte envelope mutations, size/padding faults and source/tool/manifest
tampering are refused. This is structural evidence, not native instruction
execution. The companion README records the fixed command recipe, provenance,
acceptance flags and cleanup lifecycle.

The source changes control flow through inherited RETS; it performs no
explicit unrelated register, stack, memory, IRQ, MMIO, clock, watchdog or core
operation. Bare return ABI, fetch coherence, ROM state, watchdog lease and any
eventual strict upload/response remain unqualified. No device, transport,
Pico firmware, default diagnostic or profile integration is part of this work.
No new protected analysis or downloads occurred. All hardware remains outside
this milestone.
