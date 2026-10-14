# Shapes8 wavetable profile at the expanded transport boundary

This change recognizes the independently measured Shapes8 profile alongside the existing Shapes12 profile. The builder continues to default to compressed-required-banks-flash-plaits-v1; callers must explicitly select compressed-required-banks-ram-plaits-braids-shapes8-v1. No package admission or device I/O is enabled.

The named Shapes8 profile pins the actual 8-voice link Plaits and Braids table records, including symbol, width, raw and packed byte counts, raw/packed/source hashes, and FNV values. It requires both macro and shapes, indexed TFT, compressed tables, and flash_plaits_wavetables=false. The checker recomputes the expected instance pool from 192,000 base bytes + 57,088 indexed-storage credit - 50,688 Plaits bytes - 33,024 Braids bytes = 165,376. The existing Shapes12/flash-Plaits branch remains the default and retains its previous Braids validation.

expanded_transport_manifest.build_manifest now re-runs this profile validation against the linked image receipt and its selected modules, then records the verified profile in the private offline manifest. Tampered profile, row, voice-count, or pool metadata is rejected. All hardware, physical-writer, settings-migration, recovery, and installable flags remain false.

## Concrete link and candidate evidence

The source link used was /home/claude/mvave-fm1/shapes8-target-fit-20261014/link, with verification JSON SHA-256 d448735e1d75f04d959f6da9233108ac9bb8e7fb62124e12b494dc8bd94965f8. Its app is 845,036 bytes, SHA-256 5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573; ELF SHA-256 is db9d800022a4e73e672b049ee1aa350a01858a4baad58ef50eebe732e6d03134. The map places the 50,688-byte Plaits table and 33,024-byte Braids table contiguously in .pool. The link is the bounded 120-second song-diagnostic build, 55 modules, singleton Event Horizon startup index 0. Singleton runtime_hook_linked=false is expected.

The retained matching private expanded candidate was independently rebound into /home/claude/.local/share/codex-private/shapes8-event120-expanded-candidate-20261014/. Candidate target SHA-256: 145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657. The generated image receipt SHA-256 is b7c34d28a02029b23849d75b2a9a2acbcd3464fcf888be8abbfbfb8d66dbd9a4; transport manifest SHA-256 is 3c891dac59234a92dc58e66a8bfa7d779a4ccf20c82f057c98a463f16a3bec40. The manifest describes 213 changed sectors within the expanded app area and orders the app directory sector last. It remains an offline plan only; it does not establish safe power-loss recovery or current-device identity/backup freshness.

## Validation

On Hera, /home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q tests/test_native_demo_image_controller.py tests/test_expanded_transport_manifest.py passed (focused suites; exit 0). The cases cover the existing default profile, explicit Shapes8 profile, fixed row metadata and pool, and rejection of altered voices, module set, table identity, pool, runtime, or transport receipt.

No hardware commands were run. This does not verify physical SRAM headroom, audio behavior, playback, migration, rollback, install admission, or recovery under power loss. The next dependency is coordinator review/integration, followed by the separate physical acceptance gates; this branch must not be described as installable.
