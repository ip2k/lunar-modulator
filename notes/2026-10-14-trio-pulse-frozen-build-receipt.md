# Frozen Trio-pulse D7000 diagnostic build

A clean source archive at corrected commit `66196f54f3295cfdec14a2924c767235bbd5cc2c` was rebuilt with frozen source, toolchain, catalogue, and prepared-profile snapshots in a bounded offline Docker container. The linked app and ELF match the earlier corrected build byte-for-byte. This records reproducible build evidence; it does not admit the artifact for installation or storage use.

The tracked helper is `tools/native/run_frozen_trio_diagnostic_build.py`; focused tests are in `tests/test_native_frozen_trio_diagnostic_build.py`. It snapshots all source/toolchain/catalogue/prepared inputs, records canonical per-entry manifests, verifies copied trees before execution, checks source and mounted snapshot stability after the build, inspects the container configuration before start, and retains the actual output hashes. The original source checkout is checked for tracked modifications and only these two task-owned untracked files are allowed. The source mount itself is produced by `git archive` from the exact pinned commit.

## Build receipt

Private evidence is retained under `/home/claude/.local/share/codex-private/trio-pulse-frozen-build-20261014/run-5/` (mode 0700). The frozen input receipt is `frozen-build-input-receipt.json`, raw SHA-256 `136dad341994bee22919e115a04951ad983935729023bbc6b648c7b9b29c3ce2`, mode 0600. It binds the source Git commit/tree, canonical source manifest, original and copied toolchain/catalogue/prepared tree manifests, image ID and inspected image digest, the full Docker create command, inspected network/cgroup/CPU/memory/swap/PID/mount/rootfs/user configuration, and all build-output hashes. No `image.json` or `build_tuple.json` was emitted; the coordinator should pin this receipt externally.

Manifest files, all mode 0600, use canonical JSON `{schema:1,objects:[...]}` with per-path types/modes, file lengths and SHA-256, and symlink targets. The exact raw manifest digests are:

- source archive: `source-tree-manifest.json`, `171fc9abe30ccc4774aad9602fb48e5aa6ab720b369113b1abb646e7ce36e36d`
- full toolchain: `toolchain-tree-manifest.json`, `9323ff1af9ad0cad41cd884d41281ac7cba52ef137f919c28b313e106d08b650`
- selected catalogue snapshot: `catalogue-tree-manifest.json`, `03b1e4351de71848659de2219a2bcbeb170ceca8c59a76a970b7db07e64a989d`
- prepared profile tree: `prepared-tree-manifest.json`, `36fa154dd0c46863d3d83878d7f45ab7a2abc9b97440cf54325a0828f13f7414`

Source and copied snapshot digests matched before the run and were rechecked after it. The catalogue and toolchain source trees were also rehashed after the run and matched their initial digests. Source commit tree is `483e0fa782650c2158eae979f1830960c5f86a96`; prepared `profile.json` SHA is `d4b8a9c6c4945fa8b94940cd9c826f46000d18351e000090faca7b800a79ad29`. The Docker image ID is `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.

Build outputs are under `writable-output/build/`:

- `artifact/app.bin`: 807,320 bytes, SHA-256 `3de52e9bddd24c19fbabaa3cc7cec97ea78ef0a2397debfc009befb1f8b9b6bc`
- `lunar-app-probe.elf`: 935,992 bytes, SHA-256 `a07fbd8e966873c154bfc4f62fc1d9b608004e7d1c56640f59a762959d324e6e`
- `verification.json`: SHA-256 `ef342a86db9352558a59c3be3e260f8d372d9dc5efd85cfb3dd888ecd4dfac97`
- `artifact/artifact.json`: SHA-256 `b3e2778fb3c764f4f8629a080aec7c2b172e8d7cafb0ada5820c35d17c2208cf`
- `artifact/disassembly.txt`: SHA-256 `18025345332b64239be825c6df198c21c82825e07594b184c1e9b8afdab7ef24`

The build used all 13 engines and the 54-module EH+SET controlled profile, with no embedded project or set asset, expanded D7000 layout, UART1 TRS MIDI, and one diagnostic Trio pulse. It linked the SAVE service but the receipt and verification state both retain `save_service_armed=false`, `storage_admitted=false`, `hardware_admitted=false`, `hardware_tested=false`, and `installable=false`. Layout and SDK-free key audit passed. No hardware, USB/MIDI, flash, package publication, or installation operation occurred.

## Container and command

The container used the pinned image, `docker-batch.slice`, network `none`, quota 400000/period 100000 (4 CPUs), 4 GiB memory and equal swap, PID limit 256, read-only rootfs, dropped all capabilities, no-new-privileges, UID 1001, a read-only source/toolchain/catalogue/prepared mount set, and one writable private output mount. The inspected container ID was `5d29c79346b870f5481c2317077f5922f70268492d395a0ce566e3490a01f36b`. The complete `docker create` argument vector is retained in the frozen receipt.

Inside the container the build command was:

```text
python3 tools/native/build_application_probe.py --toolchain /toolchain --catalogue /catalogue --build /out/build --prepared-profile /prepared --expected-profile-sha256 d4b8a9c6c4945fa8b94940cd9c826f46000d18351e000090faca7b800a79ad29 --firmware-identity FM-1_500 --runtime-mode song-diagnostic --stack-watermark --flash-layout expanded-d7000 --link-project-save-service --shapes-voices 8 --indexed-tft --compressed-wavetables --enable-trs-midi --diagnostic-trio-pulse
```

The build output log is `writable-output/build/container.log`; the host runner console JSON is adjacent at `run-5.console.json`. Earlier wrapper attempts failed before producing a receipt: initial container workdir was unset, the prepared input was mounted as a file rather than the required directory, then the builder's output directory was precreated. These were runner integration issues; the successful run above used `/workspace`, the full prepared directory, and a writable parent directory so the builder created `/out/build`.

## Validation and limits

The frozen source app/ELF SHA-256 values exactly equal the previous corrected app/ELF values. `audit_link` reported zero failures and zero pending checks; verification records the expanded-d7000 layout and `installable=false`. The helper's focused test suite passed 5 tests using `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/python -m pytest -q tests/test_native_frozen_trio_diagnostic_build.py`; `py_compile` passed.

This links the corrected content-free Trio diagnostic. It is not the installed image, not an installable package, and not physical audio/MIDI validation. The generated record has no build tuple/image sidecar, so the next worker must bind the exact frozen receipt and manifests as external coordinator-pinned evidence. The private stock baseline used by the earlier candidate is the retained original092 reference pair at `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1/{stockA.bin,stockB.bin,manifest.json,identity.json,reference/}`; this is historical reference material, not a fresh device read pair.
