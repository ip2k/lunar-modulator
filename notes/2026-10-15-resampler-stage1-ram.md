# Opt-in stage-1 resampler RAM placement

The opt-in `FM1_HOT_DSP_RAM` ELF profile now places the trusted stage-1 FIR helper `fm1_resampler_intermediate_` in `.ram_dsp`, alongside the existing ready-pop path. This addresses the remaining XIP call path identified in the exact `20f9ae8f` ELF. The normal profile and non-ELF builds keep the helper's existing placement. No FIR arithmetic, coefficient data, sample rate, or public API changed.

The helper remains `static inline` and is only outlined with `noinline, section(".ram_dsp")` when it is referenced. No `used` attribute was added, so including the header without using the helper does not retain an extra RAM copy.

Focused checks:

```text
.venv/bin/python -m pytest -q -o addopts= \
  tests/test_resampler_stage1_placement.py \
  tests/test_engines_resampler_ready_path.py \
  tests/test_resampler_table_placement.py
7 passed
```

The new ELF32 test compiles an active caller with Clang and verifies the emitted helper section with the repository ELF parser. It also compiles an unused translation unit with the hot-DSP define under `-Wall -Wextra -Werror`, and checks default ELF placement remains outside `.ram_dsp`. The existing ready-path differential test verifies the checked and trusted APIs still match bit-for-bit in default and hot-DSP host builds.

Exact-source Hera build from commit `0556c5037713fb26f07e6428064dc0f7aa3c21c0` completed all 16 catalogue shards and the link with exit code 0. The frozen build-input receipt is at `/home/claude/mvave-fm1/resampler-stage1-ram-0556c503-20261015/output/frozen-build-input-receipt.json` (SHA-256 `984ae800b4a953a713fb51ecc7962cc12e8720b831abe6d486463ed54dc9b447`). The target ELF contains five LTO-specialized stage-1 helper copies in `.ram_dsp`: four are 414 bytes and one is 484 bytes, for 2,140 bytes total. Each is called by a corresponding RAM `fm1_resampler_pop_ready_` copy. `ram-dsp.txt` SHA-256 is `e61895647c13af7c43c85af8a2a74d186db44cbd85ba3720c8e25f62faeb50de` and `disassembly.txt` SHA-256 is `bde4e3f9b445d220a4f5fdece57e3b743d4c250fe6506dadec7049093fb59b3b`.

The full `.ram_dsp` section occupies 11,916 bytes at `0x01c00544..0x01c033d0`, leaving 11,312 bytes before the existing `0x01c06000` limit. The app is 853,736 bytes against the 860,644-byte budget, leaving 6,908 bytes. The matching app SHA-256 is `540a06213eb5bf5832683266eb0ee596891c96b6fd93023ce31fb1047b5b89d9`; ELF SHA-256 is `f2d7705dbcd56b64b2c38909e109a3f6bdf940625c7b4841dca6e921e220ab53`.

The build report continues to mark `all_callees_in_ram`, flash-write execution verification, hardware testing, installability, storage admission, and runtime-performance proof false. This confirms target placement and fit only; it does not demonstrate a realtime or audio improvement. No device was accessed.
