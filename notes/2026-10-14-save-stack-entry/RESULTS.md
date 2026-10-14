# Retained SAVE entry-frame inspection — 2026-10-14

[verified] The vendor pi32v2 objdump disassembly of retained ELF
`ed067d2233d8b2b7994a3d8a0740a5a9b3ddfa6ec5acf06b990e0b49365cb9ab`
was generated on Hera in a pinned, network-disabled, bounded container.
The local ELF hash matches the retained link receipt. Private disassembly:
`build/native-save-scheduler-20261014/linked-disassembly.txt`; its digest and
the exact two-instruction entry sequences are in `receipt.json`.

| Function | Saved registers | Local reservation | Fixed entry bytes |
| --- | ---: | ---: | ---: |
| native_project_save_poll | 20 | 428 | 448 |
| lunar_project_save_app | 52 | 336 | 388 |
| fm1_app_state_collect_project | 52 | 3140 | 3192 |
| fm1_state_bin_write | 52 | 80 | 132 |
| lunar_project_save_write | 52 | 8 | 60 |

These are individual fixed entry reservations, not a complete stack bound.
The collector alone consumes 3192 bytes before nested calls. Inlining differs
between retained wrappers and the actual main-loop root. Callback dispatch,
sequencer/modulation collection, validators, flash drivers, interrupts, dynamic
reservations and the entry caller must be included before stack admission.
The receipt deliberately leaves complete-call-chain, interrupt and runtime
stack verification false. No physical operation was sent.

[inferred] The framebuffer lease solves the large compact writer workspace,
but does not remove collector or callback stack requirements. Physical SAVE
still needs a full linked call-chain review plus watched runtime high-water
checks under dense projects; the installed diagnostic cannot supply SAVE
acceptance because its physical storage binding is closed.
