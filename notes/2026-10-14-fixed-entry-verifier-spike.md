# Fixed-entry verifier spike (offline only)

**Status.** Bounded target ABI/link feasibility succeeded. This is a research spike, not production firmware, an accepted image, a recovery guarantee, or a device test. The retained stock SPL/header contract for a mutable application body is still unverified.

## Geometry correction

The current API profile is 862,296 bytes. Against the candidate 860,644-byte app budget (the 868,836-byte expanded profile less the proposed 8,192-byte rescue reservation), it exceeds the budget by 1,652 bytes. Separately, the measured both-wavetable-compressed profile is 844,284 bytes and the prior image metadata records its end at raw 0xD3018, leaving 16,360 bytes of arithmetic headroom against that same candidate budget. That is a measured candidate that fits the arithmetic comparison; the API profile and the both-compressed profile are distinct configurations. Neither establishes layout ownership, rescue-loader fit, frozen-header acceptance, or physical admission. See notes/2026-10-14-wavetable-fullsong-fit.md.

## Spike result

The isolated linker script maps the app entry to XIP 0x02000120/raw 0x4120. It reserves XIP [0x02000120, 0x02001000), corresponding to raw application bytes 0x4120..0x5000 (0xEE0 = 3,808 bytes), for the immutable entry and verifier. The mutable image begins exactly at XIP 0x02001000/raw 0x5000 and is linker-bounded by XIP 0x020D3000/raw 0xD7000. No production files or generated platform sources were changed.

The two pi32v2 variants have identical linked immutable application prefixes, independently recomputed manifests, and different mutable bytes. A separate 0x120-byte deliberately invalid synthetic header sentinel plus that 0xEE0-byte prefix forms a 4,096-byte synthetic sector; it is only an equality fixture and does not model a valid FM-1 header. In the map, .immutable_entry ends at 0x0200021C (252 bytes from app entry), .mutable begins at 0x02001000, the manifest is at 0x02001088, and the mutable end is 0x02001094. Linker assertions for entry address, immutable boundary, mutable origin, and D7000 candidate bound pass.

The target disassembly preserves Dinghy's _start first instruction pair (goto, rts), then saves startup state and installs _ustack_top/_sstack_top before calling lunar_validate_mutable. The branch to fm1_cstart is after the verifier returns success; failure reaches a CLI loop. The sample fm1_cstart itself is an inert loop. The CRC reader only dereferences the bounded mutable range and its manifest after the fixed start/end checks. This demonstrates a target compiler/linker arrangement for the prototype. It does not prove stock SPL descriptor compatibility, C runtime initialization behavior for a real app, target boot behavior, power-loss resilience, timing, or actual SRAM/stack headroom.

## Checks and reproducibility

Host validation: pytest -q tests/test_fixed_entry_verifier_spike.py passed (4 tests) in Hera's /home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv. Tests exercise two distinct accepted records, body corruption, malformed magic/length/version, oversized extents, truncation, and source-level ordering/boundary assertions.

Target build: tests/native/fixed_entry_verifier_spike/build.sh ran in an offline Docker container with --cgroup-parent=docker-batch.slice --cpus=2 --memory=3g --memory-swap=3g --network=none, image lunar-jieli-check:bookworm digest sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc. Toolchain binaries:
- clang SHA-256 42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c
- pi32v2 ld SHA-256 fd61aff15616bb6f6b58fd2e9ede7af741c7bf05facb3e0cb3d3c9817c268fd9
- pi32v2 objcopy SHA-256 a941eab0dd62d51da635be7834fc34d4765dbf421d00599f3a5081d42d416502
- pi32v2 objdump SHA-256 cffc304e1a9be5dac22984a6ad48e81ef82b17166fd8864c251cf635c9663b73

Both output ELFs are 3,956 bytes; the body CRC input is 136 bytes and the 12-byte manifest follows. A app/ELF/map/disassembly SHA-256 values are 2159c9c5f8df1362aa41748e66f9828a43bbeef74b8286edd959c89572f65256, da030a8dce46794dd44c4a7412fa889eaac8bfc644415704840c10f16a405c36, 8d70223898be81730a77a2c834cf9ea92e2a86d41d4abfd66b141d1082b058d9, d84561302d2254b0d51283a36a2eabae50bbb8e821a43902f26c909c4dcad00c. B app SHA-256 is 1ce011286618cf38519d6f189058adb92921bf4f49902d8d0d92b65e95d5282d. Both application prefixes are 8a58291146f71997ec5ca427b1d5e0aea5d169a166e69461122d867a2a827041; A/B mutable SHA-256 values are a3e466cfe2887f8b403b029a7d6a1d8d313a6dc9e27c44b8a1269ad0dae5af11 and 32f5aba28ad6eee9fe28cacbde145b6b95afbcc738d02062aca3ac62fc79b405. The synthetic 4 KiB sector SHA-256 is e4f2a249368120c1cf41b5bf26ba0b180b7af9264ba03633d41c97fe36545c7c.

The retained target artifacts are under Hera /tmp/lunar-fixed-entry-verifier-out-v6/ (A/B ELF, map, disassembly, binary and JSON). They are scratch build evidence, not repo inputs. The current commit base was 359a46e6b17b3b6eed3242a2b2256bf0b1d8c3e9; record SHA-256s of all changed source/test files in the task handoff after commit.

## Integrity choice and limits

The prototype reuses the polynomial/init convention in tracked Dinghy OTA's CRC16 as a small corruption-detection probe. CRC16 is not authentication; anyone who can modify body bytes can update this manifest. A shipping selector would need a separately reviewed trust policy and a cryptographic authenticator/signature if it must reject malicious replacements. MCUboot's maintained image design documents image hashes and signature validation as a reference model: [image design](https://github.com/mcu-tools/mcuboot/blob/main/docs/design.md), [signed images](https://github.com/mcu-tools/mcuboot/blob/main/docs/signed_images.md). Those references do not make MCUboot directly compatible with JieLi's boot chain, and no new library was added.

The decisive next gate is to establish, from exact stock SPL source/disassembly and retained package construction rules, whether an immutable first-sector entry at this offset can coexist with the stock header/descriptor, and whether a body/manifest boundary can be represented without changing SPL-consumed bytes. Then size the real verifier (including its chosen authenticator), prove C startup/data dependencies and stack cost, and test its behavior in a faithful offline boot model. Until those pass, this is feasibility evidence only; initial USB_KEY recovery and watched hardware acceptance remain separate.
