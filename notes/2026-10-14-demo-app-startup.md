# Native demo full-app startup and pool characterization

Date: 2026-10-14
Exact source base: `c083ec72a2170e6a9a0026f73e606c123c214ed1`
Worker branch: `codex/2026-10-14-demo-app-startup-c083` (Hera; uncommitted worker-owned files; no push from Hera)

## Result

This is a host-native diagnostic characterization of all four legacy examples and all four replacement showcase assets materialized at the exact base above. It runs each checked-in JSON project through the native `fm1-state pack` tool and feeds the packed bytes to a host-linked harness that initializes the real `fm1_app_t`, its eight-track sequencer, real `lunar_instance_pool`, and `lunar_project_start` constructor/import path.

All eight cases passed their characterization assertions. “Passed” means the observed state matched the startup/refusal checks described below; it does not mean every project is eligible to preload. Six projects are refused. No pool or sequencer capacity was changed.

## Capacity and source-path basis

- `sim/web/src/fm1_app.h:265-266` fixes the app at `FM1_APP_SEQ_TRACKS=8` and `FM1_APP_SEQ_BYTES=32768`. The harness calls `fm1_seq_size(&app.seq_lim)` and fails if it exceeds this real app arena. Every case observed 31,944 bytes, within 32,768.
- `firmware/native/app_probe.c:61-67` defines the pre-existing 192,000-byte native instance-pool default. The harness copies that amount into its host pool; it does not increase it.
- `firmware/native/project_start.c:138-145` shows the full startup continues through modulation preparation/staging/adoption after candidate units and sequence have staged. `firmware/native/project_engines.c:49-59` reserves all candidate engine instances before constructors and reports `FM1_STATE_RAM` if an allocation cannot be made. `firmware/native/project_seq.c:53-56` explicitly refuses sequence importer end/loss flags.
- The test resolves the native module catalogue and asserts exactly 55 production modules (all selected IDs with `test-` entries removed). The engine binary and app harness are rebuilt in a fresh temporary build root for the test session.
- Existing sequence-only evidence is in `notes/2026-10-14-demo-sequence-import.md`. This full-app result adds engine/unit/modulation staging observations; it is still host-native evidence.

## Per-project measurements

Hashes are SHA-256. The “pool live” field is the state after `lunar_project_start` returns. Refusal cases verify no candidate unit remains active and the instance pool is fully released.

| Project | Source SHA-256 | Packed SHA-256 | Result | Allocation evidence | Sequencer |
|---|---|---|---|---|---|
| Afterglow Relay | `56098c13c658450c4013f91583cf04dafa6062b30c1c240446401a4201741a62` | `b26fccb44bbf044fc0054991eaefc311c641748099385f624a16ca7b1ec78624` | startup success, report 0; 9 active units | 12 attempts, 0 failures; peak 169,244 bytes / 10 allocations; final live 168,508 / 9; largest request 49,888 | 8 tracks; 31,944 / 32,768 bytes |
| Event Horizon | `5b92ad3d8e6448855b9cde032a935437331620819becbb206212f32845414897` | `0ca335f967cbb469d29132406c0d7ff86972a7cce418dcbdbbbff79668cda56f` | refused, report 5: candidate engines cannot coexist with live allocations | 10 attempts, 1 failure; request 65,744; peak 155,884 / 7; final live 0 / 0; 0 active units | 8 tracks; 31,944 / 32,768 bytes |
| Packet Bloom | `7d755fd777f1b0534c2518717e4bded475872db57f9596fe410d75606765e349` | `230c98a06a101ce1675ccbeadc934fb44886ac51287b91acdf5eee3fc4187512` | startup success, report 0; 9 active units | 12 attempts, 0 failures; peak 169,244 / 10; final live 168,508 / 9; largest request 49,888 | 8 tracks; 31,944 / 32,768 bytes |
| Neon Transit | `e19152d0747d6d2a69cc61eaabeed6d083f89fbecdfa7e1d85ba7f9911f6e251` | `cb180adf8d7f7b2e8b1cd8c14daaf309446fbf0bea58b4abc8682c9f10b661f2` | refused, report 5: candidate engines cannot coexist with live allocations | 10 attempts, 1 failure; request 65,744; peak 155,948 / 7; final live 0 / 0; 0 active units | 8 tracks; 31,944 / 32,768 bytes |
| Afterglow Relay Showcase | `53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f` | `4992a4cdb17163b40426b54f3bcfd478abf0d7b35572ed3b856ec8b02b081988` | refused, report 5: candidate engines cannot coexist with live allocations | 10 attempts, 1 failure; request 65,744; peak 155,948 / 7; final live 0 / 0; 0 active units | 8 tracks; 31,944 / 32,768 bytes |
| Event Horizon Showcase | `0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c` | `3bd6347eaf8e01a7e89b474a2627cd23b2a0b241d935fd5438decd89b8cd7e12` | refused, report 8: project sequence importer refused content or observed loss | 1 attempt (31,944-byte sequencer arena), 0 pool allocation failures; pool returned to 0 / 0; 0 active units | 8 tracks; 31,944 / 32,768 bytes |
| Packet Bloom Showcase | `eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731` | `11ca03e383dfc98e437ae63efbec786b2b31be304ed568bbc110c86800e9b3df` | refused, report 8: project sequence importer refused content or observed loss | 1 attempt (31,944-byte sequencer arena), 0 pool allocation failures; pool returned to 0 / 0; 0 active units | 8 tracks; 31,944 / 32,768 bytes |
| Satellite Hearts | `090996484a125f5bde3fe4fb0a6dc3284cf7a260d6c6603298206921e78ed5d6` | `04de81e9459baeb1e45fab771ac09fed1ceef69a2563cabd521692a42fbc1278` | refused, report 5: candidate engines cannot coexist with live allocations | 5 attempts, 1 failure; request 207,728; peak 31,944 / 2; final live 0 / 0; 0 active units | 8 tracks; 31,944 / 32,768 bytes |

The four report-5 failures prove the pool allocator rejects the current candidate and cleans up its live allocations; they do not prove the projects fit a larger or target-native pool. The report-8 showcase cases fail at sequence import before any engine pool allocations. The C harness reports `modulation_active` from `fm1_app_init`; that flag describes the app’s initialized default modulation object even after a project refusal and is not evidence that project modulation was adopted.

## Build and test receipt

- Test source SHA-256: `e3a7a4dfb15b467f64d916900ededc4bd2844bef43ffa5825e45a73104e20ff4`.
- C harness SHA-256: `4141aebe6b1733c0025bec6d6b1fc8255ca629ba3b78e877298f153580bc5a96`.
- Command: `docker run --rm --network none --cgroup-parent=docker-batch.slice --cpus=4 --memory=4g --memory-swap=4g --label lan.project=lunar-modulator --label lan.session=collector_sequence_bound-20261014-appstartup-status -v "$PWD:/work:ro" -w /work lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d /tmp/check-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_native_demo_app_startup.py`
- Result: `8 passed`, exit 0, 28.856 seconds. This run asserted exact legacy outcomes and bounded replacement success/refusal behavior; replacement assertions were tightened afterward. The subsequent retained rerun passed all eight exact outcomes; see `2026-10-14-demo-app-startup-rerun.md` and its JSON receipt. The container was ephemeral (`--rm`); the command pins the image by digest, uses no network, four CPUs and 4 GiB memory/swap, and mounts the exact c083 source read-only. No container ID/inspect record was retained for this last run.
- The full app test compile emitted existing warnings in state_tool `snprintf`, `editor_meta.cc` initializer fields, Acid Bass enum comparisons, `seq_engine.c` possibly uninitialized scene, and simulator sequence-view `snprintf`; no warning was treated as an acceptance pass.
- The generated engine and harness binaries lived only in the ephemeral container's pytest temporary directory and were removed with the container.

## Limits and next dependency

This is host-native allocation-path evidence only. It does not establish pi32v2 allocation sizes/alignment, total target startup RAM, stack use, audio scheduling/playback, listening acceptance, hardware startup, shipment, or default eligibility. Host pointer widths and allocator behavior differ from the target. Do not promote a project to the default from this evidence. In particular, the two replacement sequence import refusals need source-level loss analysis and, if warranted, a separate content/importer task; capacity growth is not an appropriate response. The four allocation-refused showcase/legacy projects need target-specific allocation and startup-RAM measurements before choosing a capacity remedy; host allocations alone do not establish target capacity failure.

## Owned artifacts and handoff

Only these files are owned here:
- `tests/native/demo_app_startup.c`
- `tests/test_native_demo_app_startup.py`
- `notes/2026-10-14-demo-app-startup.md`

The coordinator reviewed these worker artifacts and the tightened eight-case rerun for checkpointing on the installable-firmware branch. Hera has no GitHub write credential; GitHub backup is performed and verified by the coordinator. No hardware commands were issued.
