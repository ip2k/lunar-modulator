# Expanded D7000 link reservation profile

Date: 2026-10-14. Branch: `codex/2026-10-14-d7000-link-reservation`.
Base: `da6b59439d132ad5676063201e0a13eef461e88f`.

## Change

Added the explicit `expanded-d7000` option to the native linker-layout profiles. It sets the same linker XIP length mechanism as existing profiles, with an application byte budget of **860,644 bytes**:

`0xD7000 - 0x4120 - (384 + 2940) = 860,644`.

The calculation keeps the existing 3,324-byte cfg/tool metadata allowance before the proposed stage. The profile constants name a two-sector range `[0xD7000, 0xD9000)` (8,192 bytes). The dynamic `FLASH_LAYOUTS` choices make the profile available to `build_application_probe.py` and `probe_artifact.py`; their default remains `protected`. Existing `expanded-d9000` behavior is unchanged.

The focused test checks profile exposure, default behavior, exact linker length, exact budget fill, a one-byte overflow, and the stage size. This is a link-budget guard only. It does not change the raw candidate builder, transaction plans, flash ranges, app-header logic, or any hardware-admission flags.

## Evidence and limits

The retained Shapes-8/Event Horizon target receipt reports an 845,036-byte app, which is 15,608 bytes below this profile's budget arithmetically. That ELF was linked with `expanded-d9000`, not this new profile; no D7000-profile target link was run here. The existing current all-55-module Event Horizon diagnostic app is 862,296 bytes, 1,652 bytes over this budget. Existing evidence also reports a 6,954-byte wrapped loader and an 80-byte record within the proposed 8,192-byte stage, leaving 1,158 nominal bytes. These comparisons establish only arithmetic fit.

The current package/candidate path remains pinned to `expanded-d9000`. Existing retained metadata reaches `0xD7674`, overlapping the proposed `0xD7000..0xD9000` stage, and flash ownership, metadata relocation, SPL selection, interruption safety, loader provenance/integration, RAM/stack fit, runtime recovery, and device acceptance remain unresolved. No physical extent is admitted. No USB, MIDI, flash, power, or reboot operation was performed.

## Check

Focused command on Hera passed: `tests/test_native_probe_artifact.py`  **42 passed** in the pinned `lunar-preload-tests:20261014` container (SHA-256 `1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`), network disabled, 2 CPUs, 3 GiB memory and equal swap, `docker-batch.slice`, task label `codex.task=d7000-link-reservation`. Hera's system interpreter lacks `rg`; bounded source searches used `grep`.

Next dependency: have the coordinator review this link-only contract, then run the exact D7000-profile target build through the current image/profile controller only after that path can explicitly select and receipt-bind the profile. Keep physical admission false until all separate storage, recovery and hardware gates pass.
