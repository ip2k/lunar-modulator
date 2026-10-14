# Event Horizon 120-second expanded candidate

This is an offline-only raw-image construction and receipt-correspondence result. No device, USB, MIDI, flash, power, or reboot operation was performed. The output is not installable, admitted for hardware use, or a physical-write plan.

## Runtime and linked image

The native link used the explicit `song-diagnostic` runtime: `probe_return_to_rom_seconds=120`, with `release_accepted=false`. This is a ROM-return deadline, not the song duration; the selected Event Horizon song is about 108.8 seconds. The default remains the 20-second diagnostic mode, and continuous mode is not accepted. The selection has one project, `replacement-showcase-candidate-event-horizon`, at startup index 0. SAVE is linked but remains disarmed/unadmitted. The linked app is 862,272 bytes against an 868,836-byte app budget (6,564 bytes remaining); app SHA-256 `264a35311828d7269aca10f8f8c65e5429ead5df23162a9d781d1f36e5e4980d`. ELF SHA-256 `5448341601f024a4e5a2141aee2f758debb7d8a0af7676271a40e0a55ec454f9`. Preserved exact link artifacts are under `/home/claude/mvave-fm1/song-runtime-link-20261014/link-v2/`. Source worktree commit was verified as `0c2a7172a2cc6490437d073653d0d5bd72c611c1` with clean status in `lunar-song-runtime-link`; its runtime/link result is recorded in `notes/2026-10-14-song-diagnostic-runtime.md`.

The exact prepared selection request SHA-256 is `0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a`; prepared profile SHA-256 is `b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46`. The profile selection is the exact input for the build; an older 20-second image receipt was not reused.

The controller now accepts `diagnostic` and `song-diagnostic` as explicit bounded modes, defaults to `diagnostic`, and binds the selected runtime configuration and ROM-return interval into the generated image receipt. Mismatched runtime receipts and continuous mode are rejected. Both modes remain explicitly unadmitted and non-installable.

## Raw candidate and manifest

Using the retained pair of identical 1 MiB raw backups and their fixed-loader read-only provenance, the candidate generator validated the recorded FM-1_092 profile, protected raw ranges, exact reference components, and the flattened ELF against `app.bin`. The vendor pi32v2 `objdump` was used for the SDK-free link audit. The current candidate image is retained privately, outside Git, at `/home/claude/.local/share/codex-private/event120-expanded-candidate-20261014/candidate/target.bin` (1,048,576 bytes; SHA-256 `0eaa6bd5501c64bb6f1e76c5e089dcd543816de35434d5cf4ed1170ba01df8c7`). Candidate receipt SHA-256 `76d733b8cb1f2e8edf760c5e51aab282b02bd091f3c80cae827c34c604542b79`.

The current image receipt SHA-256 is `f370af5bfeea0eade0a78f159eb02e22da2e9c77afe4a560b6fd6ce22a9eabea`. The expanded transport manifest SHA-256 is `c7a8edf11674b6ac9b90c38b833d5f70a683f73d23702f9379cee3c8aee718ed`; it records 1 MiB target geometry, startup index 0, exact selection/profile/request correspondence, and the unchanged protected ranges. It explicitly states `hardware_admitted=false`, `physical_writer_ready=false`, `settings_migration_verified=false`, `recovery_verified=false`, `installable=false`, and `device_io_performed=false`.

Inputs came from existing historical private backups in `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1/`; this construction does not refresh or extend their physical admission. The fixed-loader provenance was selected because that retained manifest identifies a fixed-loader backup. The result preserves raw unknown and reserved content according to the verified profile; it does not assert that any reserved VM/USR/BTIF range is available for reuse. Physical ownership, migration, recovery, and rollback remain unresolved gates.

## Verification

- `python -m py_compile tools/native/build_demo_image.py tests/test_native_demo_image_controller.py` passed on Hera.
- `git diff --check` passed.
- `/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/pytest -q tests/test_native_demo_image_controller.py` passed: 24 tests. Tests ran in a detached local worktree of the exact pushed source because the chosen Hera system/container interpreters do not have pytest installed.
- The candidate generator and transport manifest were run offline on Hera against the preserved exact app/ELF, backups, references, prepared selection, and generated receipts. Both regenerated receipts bind to the hashes recorded above.
- No fresh firmware build was run for this task; this task reused the preserved exact target-link output. No package, install, or hardware acceptance is claimed.

## Next dependency

Before any physical use, the owner/coordinator must review a concrete recovery transaction, settings migration and rollback plan, and request a new physically observed admission under the existing hardware policy. The emitted sector ordering and raw candidate do not confer write authorization.
