# Exact-source demo project packing validation

**Result:** the native `fm1-state` collector and binary writer successfully packed and re-read all four materialized demo projects separately and in the requested ordered four-project profile, against the exact source revision `e435edadad48641e9e08c0023b71b80b5692cd44`. The collector was freshly built with the GPL-enabled `FM1_MODULES=all` catalogue (58 IDs: 14 sound engines, 26 audio effects, 2 MIDI effects, and 16 modulation kinds, including three test-only modules). For the matched production link input, a separate 55-ID profile excludes `test-sine`, `test-gain`, and `test-ext`; it retains every production engine/effect and all production modulation modules. All project dependencies were present. This validates these packed build inputs only; it does not establish a target link, linked-image fit, firmware installability, user approval of the compositions, or device/perceptual acceptance.

## Reproducibility and provenance

- Hera isolated checkout: `/home/claude/.local/share/codex-worktrees/lunar-demo-packed-validation`, branch `chore/2026-10-14@demo-packed-validation`, HEAD `e435edadad48641e9e08c0023b71b80b5692cd44`.
- Inputs came from committed `engines/state/examples/{afterglow-relay,event-horizon,packet-bloom,neon-transit}.lunar` at that revision. Controller/test additions were copied into the isolated checkout later; no tracked engine, codec, project, or catalogue source was changed.
- Container image: `lunar-recovery-pytest:20261011`, immutable run image identity is unverified. The earlier recorded digest was malformed and no retained container inspection substantiates it. The later mutable-tag inspection returned `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`; that later observation does not identify the earlier run image. Build ran on Hera with `--network none`, `docker-batch.slice`, project/session labels, 1 CPU, 2048 MiB memory and matching swap cap.
- Compiler: `c++ (Debian 12.2.0-14+deb12u1) 12.2.0`.
- A fresh output directory was used, so no preexisting object files participated. Command:

  ```sh
  make --no-print-directory -C /src/engines \
    BUILD=/out/fm1-state-build FM1_GPL_MODS=1 FM1_MODULES=all \
    /out/fm1-state-build/fm1-state
  /out/fm1-state-build/fm1-state meta > /out/fm1-state-meta.json
  ```

  The build exited successfully. Compiler warnings appeared (including an existing possible `snprintf` truncation warning in `engines/host/state_tool.c`); warnings were not promoted to errors. Binary SHA-256: `7a3cf4155c6642bd14fb69de25e2c1415b423ce9fa193006a3ef70f55d55fb77`. Metadata output SHA-256: `cda87a7d44517a0e60a9f2013717c46c72abf23ec20b3711e633e7e1f0b5278a`.
- All profiles were passed to `tools/native/prepare_image_profile.py`, which runs `fm1-state pack`, reads packed records, compares unit/module dependencies to the selected module registry, and records source/packed hashes. The implementation is at `tools/native/prepare_image_profile.py:50-120`; the ordered selection controller is `tools/native/prepare_demo_selection.py:22-75`. The state tool's documented native check/pack/records operations are `engines/state/README.md:28-37`.

## Results

Packed SHA-256 values are for the actual `.bin` bytes emitted by the freshly built state tool. Source and packed bytes and profile receipt hashes are preserved in [`2026-10-14-demo-packed-validation/receipt.json`](2026-10-14-demo-packed-validation/receipt.json).

| Project | Packed bytes | Packed SHA-256 | Resolved project dependencies | `fm1-state check` |
| --- | ---: | --- | --- | --- |
| Afterglow Relay | 8,888 | `b26fccb44bbf044fc0054991eaefc311c641748099385f624a16ca7b1ec78624` | `arp`, `chance`, `drive`, `drums`, `dx7`, `env`, `filter`, `hall`, `lfo`, `limit`, `macro`, `warble` | OK; 10 units, 5 modules, 4 cables, 1 DX7 voice; host RAM estimate 195,360 / 387,924 B |
| Event Horizon | 10,136 | `0ca335f967cbb469d29132406c0d7ff86972a7cce418dcbdbbbff79668cda56f` | `arp`, `chance`, `crush`, `drums`, `dx7`, `echo`, `env`, `filter`, `hall`, `lfo`, `limit`, `macro` | OK; 10 units, 5 modules, 4 cables, 1 DX7 voice; host RAM estimate 244,576 / 387,924 B |
| Packet Bloom | 9,528 | `230c98a06a101ce1675ccbeadc934fb44886ac51287b91acdf5eee3fc4187512` | `arp`, `chance`, `drive`, `drums`, `dx7`, `env`, `filter`, `hall`, `lfo`, `limit`, `macro`, `warble` | OK; 10 units, 5 modules, 4 cables, 1 DX7 voice; host RAM estimate 195,360 / 387,924 B |
| Neon Transit | 9,624 | `cb180adf8d7f7b2e8b1cd8c14daaf309446fbf0bea58b4abc8682c9f10b661f2` | `arp`, `chance`, `drive`, `drums`, `dx7`, `echo`, `env`, `filter`, `hall`, `lfo`, `limit`, `macro` | OK; 10 units, 5 modules, 4 cables, 1 DX7 voice; host RAM estimate 244,640 / 387,924 B |
| **Combined, in order Afterglow → Event Horizon → Packet Bloom → Neon Transit** | **38,176** | individual packed hashes above, in this order | union of the project dependencies above | All four passed individually; combined preparation read all four packed records in order |

The all-58 registry smoke-pack outputs are under `out/demo-packed-validation-v1/prepared-*`; the production-only all-four ordered selection is `out/demo-packed-validation-v1/production-prepared-combined`, with four files `content-00.bin` through `content-03.bin`. The matched production Afterglow input is `out/demo-packed-validation-v1/production-prepared-afterglow-relay`. The latter selects the 55 production module IDs (including all 13 non-test sound engines, production audio/MIDI effects, and production modulation modules); three test-only IDs are excluded. Its selected project requires only the resolved dependency subset above. Its profile SHA-256 is `173d4a377a36da99d53fe23b0ba7963c9c41355eea2ce8e9730a77410a4f4fb9`; generated module-header SHA-256 is `eef6dabe417ebdb03c5ab510f7b4a3733aed331bf656ae26e7535f87276e861e`.

The native selection controller’s three new cases passed along with the existing image-profile, integrity, and staging tests: **43 tests passed** in the recorded image tag (immutable run identity unverified) using the existing Hera pytest environment at `/tmp/check-venv/bin/python`. They cover reverse project order and startup index 2, refusal when project dependencies are omitted (without a success receipt), and refusal of client-supplied catalogue paths. The returned receipt explicitly leaves `installable`, `native_link_verified`, `native_ram_verified`, and `hardware_tested` false.

## Limits and next dependency

The reported `fm1-state check` RAM figure validates a desktop collector estimate for the project representation; it is not evidence of a target firmware link or runtime RAM. Packed project byte sizes are not a whole image size: module code, metadata, app framing and every other container section still need to be measured together. This result does not certify the demos as musically approved or hardware accepted. `sequence_semantics_verified` remains false in the pack receipts. No hardware, USB/MIDI, flash, power or reboot operation was performed.

The next useful step is a same-source/same-55-production-module native link comparison using `production-prepared-afterglow-relay` as the exact packed input, with compiler optimization/profile recorded and all chunk/framing costs included. Then retain normal packed-content, link and target-RAM gates; hardware and musical acceptance remain separate owner gates.

Semantic index tools were not pointed at this Hera worktree because the active shared Serena/Rarefaction project selection could not be confirmed without changing another session's root. The task instructions' safe file-inspection fallback was used; the exact compile, pack, records, dependency scan and tests provide direct execution evidence.
