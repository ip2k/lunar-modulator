# Native staging of the full-song demo projects

Date: 2026-10-14
Source checkout: `/home/claude/.local/share/codex-repos/native-demo-sequences-20261014` on Hera
Exact source base: `56826d5f8a0191ae1cf080a822f4228343b0cc2e`
Worker branch: `codex/2026-10-14-native-demo-sequences`

## Result

The four materialized legacy example projects pack with the native `fm1-state`
tool and pass the native `lunar_project_seq_stage` path with all eight
production sequencer tracks enabled. The staged sequencer's canonical Movy1
export matches a direct import of that same source project's `set` text. The
probe found eight named scenes and the expected complete arrangement lengths;
it reported no importer refusal, dropped events, gate eviction, or Movy faults.
All four source projects contain zero trigger events, so the observed zero
trigger count is source data rather than evidence of lost events.

| Project | Source SHA-256 | Packed bytes | Packed SHA-256 | Bars | Song entries | Scenes / tracks | Notes / locks / triggers |
|---|---|---:|---|---:|---:|---|---|
| Afterglow Relay | `56098c13c658450c4013f91583cf04dafa6062b30c1c240446401a4201741a62` | 8,888 | `b26fccb44bbf044fc0054991eaefc311c641748099385f624a16ca7b1ec78624` | 76 | 8 | 8 / 8 | 1,096 / 416 / 0 |
| Event Horizon | `5b92ad3d8e6448855b9cde032a935437331620819becbb206212f32845414897` | 10,136 | `0ca335f967cbb469d29132406c0d7ff86972a7cce418dcbdbbbff79668cda56f` | 116 | 8 | 8 / 8 | 1,217 / 416 / 0 |
| Packet Bloom | `7d755fd777f1b0534c2518717e4bded475872db57f9596fe410d75606765e349` | 9,528 | `230c98a06a101ce1675ccbeadc934fb44886ac51287b91acdf5eee3fc4187512` | 88 | 8 | 8 / 8 | 1,125 / 384 / 0 |
| Neon Transit | `e19152d0747d6d2a69cc61eaabeed6d083f89fbecdfa7e1d85ba7f9911f6e251` | 9,624 | `cb180adf8d7f7b2e8b1cd8c14daaf309446fbf0bea58b4abc8682c9f10b661f2` | 104 | 8 | 8 / 8 | 1,236 / 448 / 0 |

## Method and receipt

`tests/test_native_demo_sequences.py` resolves the current native catalogue,
filters `test-*` entries, asserts the 55 production modules, and makes a fresh
GPL-enabled `fm1-state` build with those modules. It links the probe against
the resulting production registry objects and the actual native project and
sequencer staging sources. The probe packs each checked-in `.lunar` source,
stages that packed file through `lunar_project_seq_stage`, checks the stage
report/loss counters, compares a canonical staged export with direct source
sequence import, and checks the declared song length, scene names, tracks,
note/lock counts, and fault/refusal/drop counters. It requests
`fm1_seq_limits_default(&limits, 8)`, matching `FM1_APP_SEQ_TRACKS` in
`sim/web/src/fm1_app.h`; the app initializes its sequencer with that constant
in `sim/web/src/fm1_app.c`.

Execution used Hera's existing pinned image
`lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.
For the final hash-capturing run, Docker reported container
`001aa5a3da16604d5c1c56d5892cf09531326f29d2bc1c3cd35128e76d96bbea`, that
same image digest, network `none`, 8 CPUs, 8 GiB memory/swap, source mounted
read-only at `/work`, and labels `lan.project=lunar-modulator`,
`lan.session=collector_sequence_bound-20261014`. The command was
`/tmp/check-venv/bin/python -m pytest -s -q -p no:cacheprovider tests/test_native_demo_sequences.py`.
It completed with **4 passed**. The environment reported Debian GCC/G++
12.2.0, Python 3.11.2, pytest 9.1.1. Compiler emitted pre-existing warnings
in `state_tool.c`, `editor_meta.cc`, `acid_bass.cc`, and `seq_engine.c`; the
native test completed successfully despite them.

## Limits and acceptance boundary

This verifies source projects through the native packed-project sequence
staging path. It does not run the full firmware startup/session constructor,
prove pi32v2 allocation or total startup RAM fit, test playback/timing/audio,
approve the compositions musically, validate the build UI, or claim a
hardware-tested or shipped default. The `FM1_APP_SEQ_BYTES` arena capacity is
32,768 bytes, but this probe allocates host memory from `fm1_seq_size()`; no
claim is made here that the complete firmware startup fits device RAM.

Rarefaction and Serena project-index checks were not used for this isolated
Hera checkout because shared-session project roots must not be redirected;
the check used bounded source inspection and direct native compilation.

## Handoff

The test and C probe are new files owned by this task. They remain uncommitted
and unpushed for coordinator review. Next useful dependency is a bounded
full-app startup/import RAM test using the actual 8-track app configuration
and real project/session/module/effect constructors; it must distinguish
sequencer-stage success from total startup allocation proof. Hardware and
listening acceptance remain separate owner gates.
