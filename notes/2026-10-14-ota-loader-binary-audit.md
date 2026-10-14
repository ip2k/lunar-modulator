# Static audit of retained FM-1_092 OTA loader

Date: 2026-10-14. Bounded offline review of the exact `ota.bin` retained from the stock FM-1_092 package, to see whether its binary supplies a provable app-size/address acceptance bound for the private FM-1_500 D7000 candidate. No binary was executed. No USB, MIDI, flash, power, reboot, device, package-install, or writer operation occurred.

## Result

The retained file is structurally decodable and the vendor `pi32v2` disassembler recognizes the target ISA. This review did **not** establish an attributable loader check for the candidate’s app extent, load address, maximum package size, or exact flash write end. In particular, it did not prove or disprove acceptance of the 845,272-byte FM-1_500 candidate. Keep stock-loader acceptance and installability unverified.

The file contains strings such as `flash.bin`, `app_dir_head`, `uboot.boot`, and `isd_config.ini`, consistent with handling update/package records. The flat disassembly also has dynamic record-processing and checksum-looking branches. With no symbols/section boundaries and data embedded in the image, the reviewed slices are not enough to assign those routines a complete call graph or assert that a specific branch validates an app address or length. No `0xD7000`, `0xD9000`, or `0x93000` literal was found in the vendor objdump text; this is only an observation about literal encodings in this build, not evidence those bounds are absent from computed checks.

## Exact inputs and reproducible decode/disassembly

Input: `/home/claude/mvave-fm1/native-ota-candidate-16-20261012/source/inputs/stock/ota.bin`, 19,969 bytes, SHA-256 `ef1f2db89b011fa53e71df363f0122de0ea896618c53fb53e8da676322004541`.

Its nested compressed payload declares 23,324 output bytes at RAM address `0x01C0A800`. Six block headers declare compressed/output sizes `3213/4096`, `3544/4096`, `3575/4096`, `3616/4096`, `3467/4096`, and `2442/2844`; the encoded blocks consume the file exactly. Decode used the existing `tools/lz4blk.py` from `/home/claude/mvave-fm1/native-baseline-20261012/`, carrying the previous output tail as the LZ4 dictionary between blocks. The resulting bytes were 23,324 bytes with SHA-256 `42798ffc24f385302f07865216726fbdd0bfeff1339bdd909edcc93f3b1bb53c`, matching the previously documented decoded-loader hash. The header field `9c5695b2` does not equal ordinary zlib CRC-32 of the full decoded image (`c6100027`); this task did not identify its checksum algorithm/coverage.

The blob was wrapped as a single `.incbin` assembly object and disassembled, without execution:

```sh
D=/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1/common/bin
"$D/clang" -target pi32v2 -mcpu=r3 -mfprev1 -ffreestanding -fno-builtin -c /tmp/ota_blob.S -o /tmp/ota_blob.o
"$D/objdump" -d /tmp/ota_blob.o > /tmp/ota_blob.dis
```

The assembly wrapper object SHA-256 was `7e76d01764d5af560f730fa0af052e37fea9016ee007fcf600967a08b2594261`; disassembly text SHA-256 was `996e0bb32aa8e3eabee4b46737d90e5b08eee1dd1a26f67867699f47ecb6f389`. The tool reports LLVM 4.0.1 and `ELF32-pi32v2`; `file` calls the object architecture unknown, so vendor objdump—not generic host disassembly—is the ISA source used. The flat image has no original ELF symbols, sections, or relocation map. Linear disassembly therefore includes data and is not a complete function inventory.

The review observed a startup entry at blob offset `0`, address-like RAM references based on `0x01C0A800`, package-related strings in the image, and routines that process fixed-size records/checksums. It did not reconstruct all callers or prove these routines govern app installation. The upstream AL-255 OTA protocol report and repo history describe successful stock updates and the specific FM-1_092 moved-layout install, but are not source for this exact proprietary loader or a reproducible loader emulator.

## Acceptance implications

The strongest retained evidence remains the documented successful FM-1_092 stock-path update, including its 691,744-byte app and `PRCT` end at `0xD9000`. This proves that one package/layout traversed the stock path; it does not prove the loaders general maximum or the larger 845,272-byte candidates acceptance. The V15 `0x93000` limit remains a bound of the V15 model/open Dinghy lineage, not a proved universal bound for this proprietary loader.

Keep `installable`, `updater_acceptance_verified`, release admission, and hardware acceptance false. Do not infer acceptance from the update strings, the `0xF0000000` terminal success marker, package CRC validity, or the absence of a named maximum literal.

A useful next acceptance experiment, if separately authorized on the Mac with the established backup/recovery plan, is to test the exact immutable candidate through the current app’s verifier and stock update path while capturing: exact package/app SHA, step-1 decision, loader requests and progress, reported and independently measured erase/program extents, terminal status, post-reboot identity, save/settings state, and recovery behavior. A paired known-good 092 package should establish the observation path. No such experiment was run here.

Prior context: `notes/2026-10-14-package500-loader-review.md` and `notes/2026-10-14-expanded-ota-feasibility.md`. Those notes’ statement that no full stock-loader disassembly was available is superseded only in the narrow sense that the retained 092 blob was decoded and passed through the vendor disassembler; the acceptance conclusion remains unresolved.
