# Explicit FM-1_500 diagnostic target link

This is private target-link evidence only. It does not establish a package, updater acceptance, installability, hardware acceptance, or release admission.

## Outcome

The canonical builder now accepts exactly one known RAM-section call in the final disassembly: fl_jedec_ram -> fl_jedec_checked_ram, with the call annotation address matching the linked .ram_text symbol address. It rejects missing/empty disassembly, missing required symbols, unattributed/malformed or indirect calls, any other caller/target, and mismatched linked addresses. This replaces the previous blanket no-calls-in-RAM-text check, which rejected the existing checked JEDEC helper call even though its target was in RAM. The existing analysis-only NOR closure tool was adjusted to patch the new gate rather than the removed blanket check.

The Dinghy inventory now pins hal/fm1_flash.h's current local bytes while retaining its upstream-original SHA and reason in local_modifications. This avoids describing the ICFG/deadline adapter as unmodified upstream code. build_probe.check_pins validates that distinction.

## Reproducible target link

Source worktree: /home/claude/worktrees/lunar-native-identity-target, branch codex/2026-10-14-native-identity-target, base ae124fd9894066b4e5f654683b36f37c6f82dbc6 plus this branch's changes.

The command ran in lunar-jieli-check:bookworm@sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc; network disabled, 4 CPUs, 8 GiB memory, 16 GiB memory+swap, 256 pids, read-only container root, dropped capabilities, no-new-privileges, /tmp tmpfs, cgroup parent docker-batch.slice, task labels lan.project=lunar-modulator, lan.session=native-identity-rerun2, codex.task=native-identity-target. Source, SDK, catalogue, and prepared profile were read-only mounts; output was a separate scratch mount.

Exact builder arguments: --firmware-identity FM-1_500 --runtime-mode song-diagnostic --stack-watermark --flash-layout expanded-d7000 --prepared-profile /home/claude/mvave-fm1/d7000-target-link-20261014/selection/prepared --expected-profile-sha256 bfe627dc60ca5552dfd2f749611105989f7fcfb3c8637840225b377c38ac6972 --link-project-loader --link-project-save-service --startup-project-index 0 --shapes-voices 8 --indexed-tft --compressed-wavetables. Toolchain: /home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1. Catalogue: /home/claude/mvave-fm1/native-identity-target-20261014/catalogue. The command exited 0 and audit_link reported PASS (0 fail, 0 pending, linked).

The prepared profile SHA-256 is bfe627dc60ca5552dfd2f749611105989f7fcfb3c8637840225b377c38ac6972; its packed project is 5,100 bytes, SHA-256 ecb00a5363695e3275891bcb1fa0ab44d9b23d7108c1b9ddac35230d81f24a32. The fresh Shapes8 catalogue was built from the same selected all-13 catalogue/toolchain inputs and had 167 objects, 0 failures.

Output in /home/claude/mvave-fm1/native-identity-target-20261014/canonical-rerun2/out/build:

- app: 845,272 bytes, SHA-256 27600a10bae2ec177699ae2a1e3794b739e6085f61d088c47307db7a0eb515e4 (15,372 bytes below the 860,644-byte expanded-D7000 app budget)
- target ELF SHA-256: 335c448e67919e2bc52e7421164033ddd505956016531897aebe73f15772a4d1
- map SHA-256: 10e1748b96d4407e97ed51990c46e2d43348ba8bb629c011c8829b4172435fbc
- verification receipt SHA-256: eca3d6d0f2575af44712a6fc6ce32f4b104dd0b6202b7c58df53a0729c79f3ea
- final RAM call audit SHA-256: 96d5eed3853201e9706a4fd90362c0d990bb598e8939643f6208997b59890936; exactly the fl_jedec_ram -> fl_jedec_checked_ram call at 0x01c0018a, target 0x01c00004
- app contains FM-1_500\0 at offset 838,860 and recovery identity FM-1_000\0 at offset 838,851

Receipt states the identity is explicit, but package identity, updater acceptance, and hardware identity are unverified. The app is not installable; hardware candidate/tested are false. SAVE service is linked but flash_io_bound, runtime_verified, save_service_armed, and storage_admitted are false. Startup index 0 is linked as a diagnostic request, but its runtime hook, runtime verification, and stack margin verification are false. Embedded content native_playback_verified and sequence_semantics_verified are false. No package or updater image was emitted.

## Checks

- python3 -m py_compile on the helper, builder, pin checker, analysis tool, and focused test module: passed.
- python3 -m unittest tests.test_native_nor_writer_closure -v: 12 passed.
- git diff --check: passed.
- Canonical constrained target build and linked audit_link: passed as above.

These checks validate exact linked metadata and the structural RAM-call allowlist. They do not validate target execution, interrupt timing, NOR writer closure while XIP is unavailable, watchdog recovery, save/restore behavior, device identity, musical acceptance, or owner/hardware approval.
