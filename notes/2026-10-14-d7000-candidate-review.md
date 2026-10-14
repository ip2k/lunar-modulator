# D7000 offline candidate constructor review

Review date: 2026-10-14. Reviewed exact source base `c9b90db89c2ccec3191dc24b3d43e349f17bffd6` in isolated Hera worktree `codex/2026-10-14-d7000-candidate-review`. Scope was the D7000 geometry/profile and candidate constructor only; no implementation files were changed.

## Result

No blocking defect found in the bounded D7000 layout handling. The constructor selects an explicit named `expanded-d7000` profile, caps the app and aligned configuration records at `0xD7000`, compares the raw target tail beginning at `0xD7000` byte-for-byte with the supplied baseline, and emits protected ranges covering the D7000-D9000 two-sector stage and all bytes above it. Unknown layout names are rejected by both the geometry and link-budget paths. The pre-existing D9000 layout remains the default in `expanded_candidate.construct`, `expanded_flash_profile` helpers, `probe_artifact.flatten`, and CLI arguments; the new profile is opt-in.

The maximum geometry is internally consistent: raw app origin `0x4120`; D7000 limit `0xD7000`; reserve `384 + 2940 = 3324` bytes; maximum aligned app `860644` bytes ends at `0xD6304`; the 383-byte tool aligns to `0xD6304..0xD6483`; the 2937-byte cfg and final four-byte alignment end exactly at `0xD7000`. The limit is 4-KiB-sector aligned, so its final application sector starts at `0xD6000`; the preserved stage is exactly `0x2000` bytes (`0xD7000..0xD9000`). This is a link/geometry bound, not proof that a particular image, loader, transaction, or hardware recovery path is admitted.

Construction starts from a decoded copy of the checked baseline, erases only `[APP_BASE, limit)` in that decoded candidate, restores the pinned directory gap and configuration tool/cfg records at the computed locations, repairs record CRC/lengths, then SFC-encodes the changed region and appends the original raw bytes from `limit` to flash end. The independent validator verifies the full raw prefix and tail, app/tool/config content, records, CRCs, deterministic padding, and unchanged reserved descriptors. Candidate construction further binds the two matching baseline dumps/manifest/identity, reconstructed ELF-to-app equality, complete SDK-free link audit, allowed sectors, and protected ranges. The receipt explicitly leaves physical writer, hardware approval, settings migration, OTA/package, and installation gates false.

## Checks

Ran both focused test files in the pinned network-isolated Hera pytest container (`lunar-recovery-pytest`, digest `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`), with 4 CPUs, 8 GiB memory/swap, `docker-batch.slice`, read-only worktree/dependencies, network disabled:

```text
python3 -m pytest -q -p no:cacheprovider --basetemp=/tmp/lunar-pytest \
  tests/test_expanded_flash_profile.py tests/test_expanded_native_candidate.py
60 passed
```

Coverage includes synthetic boundary app sizes, maximum and over-limit size, bad and unknown baseline/profile inputs, unknown flash profiles, altered D7000/D8000/D8FFF tail bytes, protected bytes, CRC/record/config/padding changes, target-provenance binding, unsupported app-only-at-D9000 rejection, and checks that physical/installability flags stay false. No private flash image or vendor payload was opened or copied for this review.

Relevant implementation hashes at reviewed HEAD:

- `tools/native/flash_layout.py`: `bece11cdbb35b0742fb1c8800afd73e2d1cac458f9e2fb102e8d3d7a408b5f25`
- `tools/jieli/expanded_flash_profile.py`: `8af9cff5705d401d91bb80073259827dbb1997dd2de267e3a9cae9b70db871d9`
- `tools/native/expanded_candidate.py`: `0e2277e2d5604e3923f1ed48618c978d15ab6a27b89e9a63ac20e743e109b447`
- `tools/native/probe_artifact.py`: `ff0685ef518df2937acf99438a28ba70926948912a32dd02a8730d6c6b451e46`
- focused tests: `tests/test_expanded_flash_profile.py` `9ded584bb3cb764d2c4dcd73bb586f333df678a8f5f8c4aa714ae4f917f73ee9`; `tests/test_expanded_native_candidate.py` `5e134aefe421dad0830eb758ce840c99540fcbf5ffe877fa29dec1aa39d16a4a`

## Limits and next gate

This review does not prove frozen-SPL acceptance of a new D7000 layout, NOR interrupted-program behavior, recovery-loader code fit/runtime, settings migration, an install transaction, or hardware acceptance. The tests use synthetic flash/ELF fixtures. The D7000 candidate must remain non-installable until the separately reviewed loader/recovery and physical-admission gates are completed. No hardware or device commands were issued.
