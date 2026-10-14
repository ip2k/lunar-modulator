# Expanded rescue host-fixture bounds

## Result

The portable fake-NOR core fixture now runs unchanged at its prior `[0x4000, 0xD9000)` app bound and at the proposed `[0x4000, 0xD7000)` bound. The second profile proves only that this test derivative refuses app writes beginning at `0xD7000`, and that a full fixture transaction preserves the suffix beginning there. Arithmetic checks record a proposed two-sector `[0xD7000, 0xD9000)` stage, an 80-byte record at `0xD8F00`, and a 6,954-byte loader body ending at `0xD8B2A`; the loader ends 982 bytes before the record. The proposed stage ends at the measured VM start `0xD9000` in the expanded layout. These are geometry/model checks, not evidence that those bytes are owned, writable, or accepted by the stock SPL.

The failure cases now initialize the fake-NOR old app directory to a CRC-valid value, then assert that an erase failure at `0x5000` and first-page-program failure leave that header CRC-valid while app-body data is erased/partial. This exposes an important limitation of the tested transaction: payload failure happens before its directory-sector write, so the old-valid-header gap remains in the model. A CRC-valid header plus incomplete body is not a safe rollback proof; the fixture does not implement SPL selection or establish that SPL checks this app-body manifest. It is intentionally a counterexample-bearing portable-core test, not a recovery simulator.

## Source correspondence and limits

The tracked `firmware/third_party/dinghy` code is not the same loader as the expanded fake-NOR fixture. Dinghy's current app updater stages its image at `OTA_AREA=0xE0000`, length `0x5000`, with record at `0xE4F00`; `ota_stage()` erases that configured range, writes and verifies the body, and publishes its header last. The flash profile's default OTA window is also E0000..E5000. Neither tracked file implements the proposed D7000 stage or its D8F00 record. Hashes at this base:

- `firmware/third_party/dinghy/src/ota.c`: `ffc981586704b41f62c763248037d1fe373c84c3566c0486de795296f9841855`
- `firmware/third_party/dinghy/hal/fm1_flash.h`: `ee9700389d8bf842606b7210e52e125c085a44fbb5d30301cf189d823c4d5e90`
- test-only `firmware/third_party/felucca-expanded-offline/ldr_core.c`: `bfd254398b982c70ea9d73412c6072e1741a9f1ee2c35f53867ac05983d765e8`
- test-only fake-NOR harness: `26048928f137f3f41ff3cb53bf0e3f2c0d45b4cd204b540d84a066715079f770`
- pytest wrapper: `43af74297c3bd5484710f47d2ffe38e567d8b0657dbec8abf6d36494b506da30`

The `felucca-expanded-offline` probe is a host-only, GPL-3.0-only derivative of Felucca's portable loader core. Its fixture and source intentionally reject non-test builds. It models a synthetic package, a 1 MiB byte-array NOR, sector erase, page program, source mutation, readback and retry. It does not model USB transport, the stock SPL scan/branch, mask ROM, real flash behavior, electrical power cuts, or physical bank ownership. In particular, the “valid header while body is partial” result is a property of these synthetic writes and the fixture's CRC predicate, not a measured torn-write property of the FM-1.

This task makes no hardware admission, capacity ownership claim, installability claim, or rollback guarantee. It does not change Dinghy production code or platform OTA bounds. Serena/Rarefaction were not pointed at this Hera worktree: the active semantic roots were the Mac checkout, so exact source/fixture review used the isolated Hera files and their callers/tests instead.

## Reproduction

From the repository root, the wrapper compiles and runs two profiles with host `cc`, C99, `-O2 -Wall -Wextra -Werror`:

```sh
python -m pytest -q tests/test_expanded_loader_offline.py
```

The checked invocation used the existing Hera pytest environment at `/home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest` because Hera's system Python has no pytest module. Result: `2 passed`. Both generated C binaries independently printed `offline core test passed`; the D7000 variant additionally printed `ok` for the boundary, two-sector geometry, loader/record arithmetic, and protected suffix checks. `git diff --check` passed. No production target build or device operation was performed.

## Next dependency

Before adapting a real stage/update path, resolve the old-valid-app-header boot gap. A later design investigation should prove, from exact stock SPL predicates and the approved expanded boot architecture, that immutable first-sector bootstrap code can validate the mutable app body and choose a separately persisted rescue payload on invalid/missing manifests. This requires retaining and verifying any manifest/digest and rescue object under a proven SPL/loader-readable contract. It does not solve power loss during initial migration/first installation, establish D7000 ownership, or justify changing the current OTA stage. Those require independent offline proofs and later owner-controlled recovery acceptance.
