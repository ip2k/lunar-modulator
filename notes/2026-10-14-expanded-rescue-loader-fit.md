# Expanded D7000 rescue-loader fit: bounded target build

**Result:** [verified] The retained Dinghy/Felucca loader was rebuilt with an app write ceiling at `0xD7000` and a two-sector stage `[0xD7000,0xD9000)`. Its target image is 8,232 bytes in RAM and its wrapped OTA stage is 6,954 bytes. With an 80-byte SPL record at `0xD8F00`, this leaves 982 bytes before the record and 176 bytes after it. This is a size/layout experiment only. It does not establish flash ownership, interrupted-write recovery, package acceptance, or hardware installation.

## Exact source and build

The measured source was the retained source snapshot at `/home/claude/mvave-fm1/native-baseline-20261012`, which has no Git metadata. It is the Dinghy/Felucca-derived loader identified by the prior source audit and hashes below; it is not represented as the exact current project source or an upstream commit. The four-file target-only adaptation is saved at [target-adaptation.patch](2026-10-14-expanded-rescue-loader-fit/target-adaptation.patch), SHA-256 `8336f2fc652eaa6eff21275a912d149b94b24576807bd6e51c27f057da628de6`.

Original source snapshot hashes:

- `firmware/loader/ldr_core.c`: `389aa2e09e74fdac184221edd9b8b7d76eb59ec3dabd11008cbb06081f9fe1de`
- `firmware/loader/loader.c`: `d1a68016bde7c5f1ecdd2613f1f9ef55cd5822e65a0c6e3394fb9249f1d0fdea`
- `firmware/loader/loader.ld`: `4acae8c9a16cf9a70f53a546f9175b5a86d2bc5cb6bce39513a2ff3c4fdba4ae`
- `firmware/loader/crt0_ldr.S`: `bd4149b97520d1dcc271f730c5a046b0dbf97909e48e968e0ba18304ffc37841`
- `firmware/src/ota.c`: `ffc981586704b41f62c763248037d1fe373c84c3566c0486de795296f9841855`
- `firmware/hal/fm1_flash.h`: `ee9700389d8bf842606b7210e52e125c085a44fbb5d30301cf189d823c4d5e90`
- `tools/build.py`: `0b91f74c77d4b747675bd99a2475d56adbacc3e30295c57a6e311ed83123cadd`
- `tools/lz4blk.py`: `bede501ca8774ba6942b35ad2c43823e9f48f13d0fb001ef9b73cdaf41460e16`

The private candidate source and build outputs are retained at `/home/claude/.local/share/codex-coordination/receipts/lunar-expanded-rescue-loader-fit-20261014/`. The patch changes four bounds only in this private source copy: app writes end before `0xD7000`; loader record scanning/clearing is limited to `[0xD7000,0xD9000)`; package-side stage uses two 4 KiB sectors with record at `OTA_AREA + OTA_AREA_LEN - 0x100 = 0xD8F00`; the flash-driver write guard accepts only the app and stage ranges. It removes the candidate's prior broad record-delete scan over `[0x93000,0xFC000)`. No repository production source was changed.

The bounded networkless container used `lunar-jieli-check:bookworm` (`sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`), `docker-batch.slice`, one CPU, 2 GiB memory/swap, 256 PID cap, and a read-only JieLi toolchain mount. The clang binary SHA-256 is `42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`; the linker SHA-256 is `fd61aff15616bb6f6b58fd2e9ede7af741c7bf05facb3e0cb3d3c9817c268fd9`.

From the copied candidate source tree inside that container, the build invocation was:

```sh
python3 -c 'import os,runpy; os.environ["JIELI_TOOLCHAIN"]="/opt/jieli"; os.environ["JIELI_DOCKER"]="0"; x=runpy.run_path("tools/build.py"); x["build_loader"]()'
```

The successful build reported `loader: image 8232 B at 0x1c0a800, bss end 0x1c0f400` and `loader: ota.bin 6954 B`. Artifact hashes:

- `loader.elf`: `4cf9c339f2f8bd51efc01d245f6835747d0735147b4aa6aa3442a55c53f1993b`
- `loader.bin`: `6274059785faf34349196421574007bd92d62adc77d7ca9a2d9a7cdfca9c8575`
- wrapped `ota.bin`: `31d2d2110ac98cd2fcec813b3ff98c5d64686612807511769d05330c69fc8694`

The 6,954-byte wrapper includes the 32-byte outer header, 32-byte inner header, and compressed blocks. `ota_stage()` checks its 6,922-byte body against `OTA_AREA_LEN - 0x200 = 7,680`, leaving 758 bytes under that body limit. In the 8,192-byte stage, the 80-byte record occupies `[0xD8F00,0xD8F50)`; total unoccupied space is 1,158 bytes: 982 before and 176 after the record. The target loader has an 11,216-byte NOLOAD `.bss` (end `0x1C0F400`); this is RAM, not staged bytes, and was not evaluated against a running-device stack budget.

## Bounds and practical fit

`LDR_APP_HI` is end-exclusive. The candidate writes app sectors from `0x4000` to `0xD6FFF`; it reads and CRC-checks later bytes in the served `flash.bin` but does not write them. The stage writer erases `[0xD7000,0xD9000)`, verifies the body, writes the stage header last, and publishes the record at `0xD8F00`. Its record-drop scan checks the two sector-tail positions in this range. The adapted next-app cleanup clears only these two stage sectors.

This does not fit the current complete full-song image layout unchanged. The app payload ends at `0xD6978`, 1,672 bytes before the stage; aligned tool/config records extend to `0xD7674`, so 1,652 bytes of metadata overlap the stage. With this stage reservation, the preserved-layout app budget is 860,644 bytes and the current 862,296-byte app is 1,652 bytes over. A separately reviewed method to preserve/relocate those records or another owned extent is required; they cannot be treated as disposable. The comparison uses the actual private worker artifact `/home/claude/.local/share/codex-coordination/receipts/lunar-real-installer-worker-20261014/app.bin` (862,296 bytes, SHA-256 `7175f6d1e97563b07350e0bccb10a9820104eb47a4fc67212797c68651fbd575`) and the exact retained profile geometry recorded in `notes/2026-10-14-rescue-tail-fit-measurement.md`; it is not a newly built D7000-layout image.

The patch avoids the old broad cleanup scan across `[0x93000,0xFC000)`, including documented user-data/global extents `[0x97000,0xE0000)` and `[0xFC000,0xFF000)`. This does not grant ownership of D7000–D9000, which currently overlaps metadata.

## Recovery limits

Although the staged loader and record fit, power-loss recovery remains unresolved. The stock SPL skips its trailing-record scan when the ordinary app header passes its CRC. This loader writes app sectors starting at `0x4000` while the old header remains valid, so a power cut during payload writes can leave SPL choosing an incomplete app instead of the staged record. The candidate adds no header invalidation; reviewed evidence does not establish safe NOR/SFC torn-program behavior for invalidation. Body readback and record-last publication do not close this boot-selection gap.

Other open gates are source revision/provenance, app-header transaction ordering, physical program behavior, metadata layout, actual SPL treatment of this record/payload location, end-to-end packer/controller adaptation, runtime RAM/stack budget, and owner-reviewed recovery/backup gates. No device, USB, MIDI, flash, reset, or power command was issued. No package was admitted and no physical extent is claimed.

## Checks and next dependency

- [verified] Input hashes and target-only patch are recorded above.
- [verified] Bounded networkless pi32v2 `build_loader()` succeeded; output hashes are listed.
- [verified] Candidate erase/program and cleanup bounds are limited to the app and two-sector stage; the old broad record-cleanup loop was narrowed.
- Not run: host fake-NOR cutpoint tests, full image/controller packaging, SPL integration at this address, hardware or recovery acceptance.

Next, resolve the complete app/tool/config extent conflict, then evaluate this exact adapter against the measured SPL selection/cutpoint model. Keep admission false until those checks and owner-reviewed physical gates establish a recovery invariant. Do not treat this fit result as authorization to erase or repurpose D7000–D9000.
