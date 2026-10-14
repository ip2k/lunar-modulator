# Device38 expanded-image dual-read adapter (offline review)

## Scope and result

Added `tools/fm1_expanded_rom_backup.py` as a new, separate wrapper. It does not alter the older V8 fresh-ROM wrapper, the returned-ROM adapter, the fixed loader, its profile, or any historical pin. It admits one fresh passive ROM enumeration on USB topology `1-1` / bus 1 / `4c4a:8057`, binds the exact previously reviewed expanded-install proof artifact, pins the known expanded image SHA-256 `c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903`, and consumes the observed enumeration once. The current USB device number must equal the coordinator-observed `38` exactly; values such as `37`, `39`, or `038` are refused. This binds the offline adapter to the stated observation rather than accepting any positive device number.

The adapter pins the same three existing modules and hashes as the audited fresh ROM read path: fixed loader bridge `79bbe99c...db00afb`, returned-ROM inventory `afeefe7b...a52b4be`, and SG reader `28317ee5...d6ae57`. It also pins the fixed loader/profile through the bridge existing hashes, checks the 88-byte Linux SG header, and requires exactly 8,757 commands plus the established inventory digest `f99b6e73...9838017`. Its only admitted output is two full 1 MiB reads whose SHA-256 must each equal the exact target digest. It defines no write, reset, erase, retry, caller-supplied target SHA, or generic-loader option. On success it records those operation counts as zero and leaves `physical_recovery_verified` false.

The pinned installation evidence is `notes/2026-10-13-current-expanded-candidate/device36-physical-install.json` (SHA-256 `1798734ef5d8a0754cd17e039e7747a306e34177ebaabcdc591ad06f3a25e41c`). The adapter checks the evidence bytes and its target/full-readback/verification fields. This binds the adapter to the recorded earlier install candidate; it does not independently prove device38 current flash state. The new dual reads are the proposed state check. The evidence JSON itself is an offline verifier receipt with `hardware_operations=0`, and makes no boot, release, or recovery claim.

## Checks

- `python3 -m py_compile tools/fm1_expanded_rom_backup.py tests/test_expanded_rom_backup.py` passed on Hera.
- Focused Hera container pytest: 16 passed. Admission requires exact `devnum == "38"`; negative cases include `37`, `39`, and `038`. Mock-transport `run()` cases verify two exact 1 MiB outputs, short/mismatched dump refusal, transport-error close/no-retry logging, and one-use marker refusal. Pinned image: `lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`, `docker-batch.slice`, 4 CPUs, 8 GiB memory/swap, 512 PIDs, network disabled, read-only worktree and pytest dependency mounts.
- Tests cover exact-envelope acceptance using mocked source modules, wrong port/bus/PID/device-number/kind/adapter hash refusal, stale observation refusal, dependency source hashes, unchanged legacy V8 target pin, and mocked end-to-end `run()` outcomes.
- Hera system Python lacks pytest; the pinned offline image was used. All transport tests are mocks: actual sysfs discovery and SG reads are not exercised. No hardware APIs were invoked.

## Limits and next gate

This is an offline adapter candidate only. A Mac-owned reviewer must inspect the diff, the proof-artifact lineage, the exact fresh observation, loader/profile provenance, generated command transcript, dump hashes, and destination permissions before any authorized read campaign. This task did not access USB, send MIDI, load a RAM image, read flash, reset, or power-cycle. A matching dual read would establish byte identity with the fixed image, not successful boot, rollback, SPL recovery, or release acceptance. Device38 reported ROM enumeration and expected target SHA were coordinator-provided context, not independently observed here.
