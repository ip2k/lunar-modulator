# Ready resampler RAM placement trial

The trusted-ready resampler pop path now has an opt-in ELF placement attribute. With `FM1_HOT_DSP_RAM=1`, `fm1_resampler_pop_ready_` is outlined into `.ram_dsp`; default builds leave the helper's placement unchanged. The helper remains `static inline`, and deliberately has no `used` attribute, so a translation unit that only includes the header does not acquire an unused RAM copy. No FIR arithmetic or public API changed.

The change is commit `1624974067ec51cf56b443d789ba8568906be8f5`, pushed to `feature/2026-10-11@installable-firmware` and verified against the remote ref. The focused host tests passed:

```text
.venv/bin/python -m pytest -q tests/test_engines_resampler_ready_path.py
3 passed
```

The differential test compares the trusted-ready path to the checked API bit-for-bit in both default and `FM1_HOT_DSP_RAM=1` host builds. A two-translation-unit test confirms that the macro alone does not force an unused helper symbol into an including translation unit. Host Mach-O does not support the ELF section attribute, so actual section placement was checked in the native target link.

## Bounded Hera target link

The exact source commit was linked in an isolated Hera worktree at `/home/claude/.local/share/codex-worktrees/resampler-ram-placement-20261015`, branch `codex/2026-10-15-resampler-ram-placement`. The frozen output is `/home/claude/mvave-fm1/resampler-ram-placement-16249740/output`; its receipt is `frozen-build-input-receipt.json`, SHA-256 `07ccabad82fd875fe0a07d82160d3d335d9dae6e1dc6947b85b9001e4b2d5eb3`.

The runner was a private copy of the reviewed 16-shard bounded build workflow, SHA-256 `455d5e28790423f18fbaf6a04cbaf5f57097245bca6889997177fd62afd22f2b`. Inputs were the exact `1624974067ec51cf56b443d789ba8568906be8f5` source, pinned image `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`, profile `fd68a478ea594ab9c3a7f34a604e23f99614e707bb9840b8a91947b07e547738`, selection `bf8bf47385901432c277f27e3892f7e41c43d78204eed30323556855756db45c`, and the previously verified toolchain/header snapshots. All 16 catalogue shards and the link exited successfully; no shard was OOM-killed. Catalogue containers used `docker-batch.slice`, 2 CPUs, 2 GiB memory, 4 GiB total swap, no network, and read-only source/toolchain/header mounts. The link used the same isolated image and bounded workflow.

The final ELF has `.ram_dsp` at `0x1c00544..0x1c01e80`, size 6,460 bytes (`0x193c`). The linker reserves through `0x1c06000`, leaving 16,768 bytes in that section region. The ready-pop helper has four LTO-specialized copies in RAM:

| Entry | Address | Bytes | Caller |
| --- | ---: | ---: | --- |
| `.531` | `0x1c0067a` | 310 | XIP `0x0200730e` |
| `.789` | `0x1c007cc` | 306 | RAM `0x1c019b2` |
| `.2190` | `0x1c008fe` | 310 | XIP `0x020204f4` |
| `.4605` | `0x1c0107a` | 310 | XIP `0x02039a6c` |

Together the four bodies account for 1,236 bytes. The baseline link placed the single shared ready-pop body in XIP at `0x0200892e`; the new link has four RAM entries and calls each entry from the recorded sites. The generated verification lists the existing seven hot-DSP bodies and reports `.ram_dsp` extent ending at `0x1c01e80`; no linker region expansion was made.

Key output hashes: app `8d462a80161b60902cccc9a0c439c6d8ff7053333be7499e0b129a0ff206131d`, ELF `40416445889dbfeff37c0a8293a077e39a999ef654715c93aef6e6ed8b2cfd02`, disassembly `9ee05dfb2b4065c3afc023c14aef673d4412289999b64590b782d6833cdd2cb2`, verification `65303a8d08bcea2e0aca7c321c1f588a01150909b3e3dc0ee2db75193c57d3eb`, RAM disassembly `981ed3cd53b7f0e15d0c3de1b82c4863b470701d66d7a8ef2b4b31c5df3d6f61`.

This verifies target code placement and fit only. It does not prove the callees are wholly RAM-resident, flash-writer execution safety, device admission, or any real-time/audio improvement. The next useful step is a separately reviewed, source-pinned physical diagnostic build and controlled measurement if the coordinator selects this placement for a candidate; this build itself was never sent to a device.
