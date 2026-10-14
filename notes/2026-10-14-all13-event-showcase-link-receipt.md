# All-13 Event Horizon Showcase target-link receipt

This text-only receipt transfers the checked offline link evidence into the isolated implementation worktree; it does not change or promote the target artifact. Artifact root: `/home/claude/mvave-fm1/all13-event-showcase-link-v1/`.

- Selection request file SHA-256: `3d84b13fbe6d5bb37c1cfc2edae50c739d65e8c926d3cf52dc22fbede9db70d3`.
- Canonical selected request SHA-256 recorded in the selector receipt: `0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a`. This is the canonical request serialization digest and is expected to differ from the raw JSON file digest above.
- Staged source profile (`prepared/staged/profile.json`) raw-file SHA-256: `5b52c80822c1ffc6ff602212c91f865d6632150eccd05f8eb4723c201a5d5274`.
- Prepared manifest (`prepared/prepared/profile.json`) digest used by the builder: `b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46` (the `embedded_content.prepared_sha256` value in `target-link/build/verification.json`).
- The selection contains all 13 production sound modules plus the listed effects/MIDI/modulation and one `replacement-showcase-candidate-event-horizon` project at startup index 0. The prepared profile packs one 4,345-byte project payload (SHA-256 `b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163`). This establishes linked bytes and selected metadata only; it does not establish playback semantics.
- `verification.json` SHA-256: `b7e57d935d54f54e74bff8c20f5dd898d670621cde4f37297cf45a676c103483`. Its `flash_layout` is `expanded-d9000`, `flash_write_range` is `empty`, `embedded_content.sequence_semantics_verified` and `native_playback_verified` are false, and startup project `runtime_verified`, `stack_margin_verified`, and `hardware_tested` are false.
- Link map `lunar-app-probe.map` reports `.pool` size `0x66aa0` = 420,512 bytes. The primary `.pool` contribution is `0x5e9a0` = 387,488 bytes; `.pool.wavetable` adds `0x8100` = 33,024 bytes (`braids::wt_waves`). Separately, verification's `instance_pool_bytes` is 216,064 bytes for the instance arena, not the entire linker `.pool`.
- `firmware/native/app.ld` places `.pool` in the combined RAM window (432 KiB, `0x01c08000` onward), with `_pool_end <= _guard0`; map has `_pool_start=0x01c0cc50`, `_pool_end=0x01c736f0`, and the linker assertion passed. The section is `NOLOAD`; its presence/size in the ELF/map is not proof that startup clears it or that runtime capacity/timing is admitted.

The existing target artifact used a task-local wrapper to inject the real production SAVE service define; the production builder did not yet expose that option. The wrapper is not part of this branch's implementation. The new builder flag links the existing production service while preserving its zero-initialized/unbound I/O and `storage_admitted=0` gates; this receipt itself does not claim a rebuild with that new option.

Scope limits: offline ELF/link-map evidence only. No device, USB/MIDI, flash, install, boot, audio playback, SAVE write, storage admission, or default-project claim.
