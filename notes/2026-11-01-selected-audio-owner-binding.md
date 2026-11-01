# Selected audio-only main-owner binding — 2026-11-01

WIP from `6ece5032bb4a2e7f3856350c89015725f727a473`. This opt-in source
slice moves selected-app input application and rendering from ALNK IRQ to
main. Timer5 publishes accepted scanner events; ALNK copies already-converted
PCM or zero into its free half. It retains the complete offline PROJECT closure
and the single existing app/owner/input/producer storage.

The old/default profiles remain selected separately. The HAL initializer is
factored into prepare/start/final-PC6 helpers but its original wrapper retains
both waits and register order. The new profile prepares with DMA/IRQs off,
prefills both actual DMA halves and two producer slots, publishes readiness,
starts DMA, enables IRQs, and services the5ms final-PC6 tail in main without a
post-start busy delay. Display is explicitly disabled; no fake SPI completion.

The return policy retains immutable zero real qualification and refuses before
functional startup. FRONTEND_READY is the same numeric phase as legacy
LCD_READY; only the profile-specific completion description changes. No target
build, physical qualification, RAM execution, DMA/cache/deadline or release
acceptance claim. XIP text plus BSS does not fit in total SRAM; the separate
512-byte ROM witness remains the physical prerequisite, not this image.

Implementation and focused host tests are still in progress at this checkpoint.
No host or target result is claimed. Private source plan and exact base manifest:
`scratch/devkit-20261023/audit-20261101/native-owner-target-binding-plan/` in the
performance worktree. Source is in its own branch/worktree; Hera task claim
`lunar--selected-audio-owner-binding-20261101`; no job running yet.

Rarefaction is fixed to primary and refuses sibling-checkout traversal. Serena
absolute-path symbol overview matched the owner source without changing its
shared selection. Exact checkout reads provide the fallback; no target ABI
claim comes from semantic tools.
