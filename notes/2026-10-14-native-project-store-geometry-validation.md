# Native project-store geometry and interrupted-operation validation

## Result

The existing low-level native journal test now exercises 102,400-byte slots and 49,152-byte (48 KiB) slots using a checked-in valid compact state body. It successfully completed 60 pytest cases (30 mutation-site shards at each geometry). Each shard injects both a partial mutation followed by callback failure and a complete physical operation followed by a lost-acknowledgement error. It scans both slots afterward and requires the real compact-state decoder to validate the selected record. In all cases the previously committed active slot remains byte-identical.

For this 1,620-byte body, a successful third save has 34 mutation callbacks with 102,400-byte slots (25 sector erases, seven body page programs, header and commit-marker programs) and 21 callbacks with 49,152-byte slots (12 erases plus the same nine programs). The 30 shards partition those callback ordinals. The injected failure in the final, complete commit-marker program is the one lost-acknowledgement case where scan correctly selects slot 0 generation 2: all commit bytes and the state body are present and the native validator accepts them. Every partial callback failure, and every earlier lost acknowledgement, recovers slot 1 generation 1. The generic compact import limit remains 98,304 bytes.

This validates the journal API and decoder against the two emulated slot sizes. It does not validate physical flash extents, power-loss behavior of the chip/driver, or full `lunar_project_save` two-pass preflight. The store API erases the inactive slot in `lunar_project_begin` before `lunar_project_write` can refuse an oversized body; this test checks that no additional mutation occurs after that refusal and that the prior active generation remains recoverable. An invalid non-sector-aligned geometry is refused before erase. Do not treat this lower-level test as proof that native SAVE preflights before erase.

## Test implementation and source evidence

- `tests/test_native_project_store.py` lines 8–11 parameterize the 102,400- and 49,152-byte geometries and 30 shards; lines 14–30 compile the real `project_store.h` implementation with the state parser and sanitizers; lines 34–39 run the matrix against `tin-kit.sound.lunarb`.
- `tests/native/project_store.c` loads and independently parses that fixture (lines 120–132), establishes valid generations 0 and 1 and snapshots them (147–156), counts all callbacks in a successful third save (158–163), then injects both failure modes over every callback ordinal (165–190). The erase/program callbacks perform a half-sector or half-page physical prefix before failure in mode 1 and complete the operation before returning failure in mode 2 (51–77). Recovery requires an exact expected slot/generation/body length plus a decoder call (103–118), and checks that the prior active slot is unchanged (181–188).
- The actual journal contract is in `firmware/native/project_store.h`: constants are a 32-byte header, 4,096-byte erase sector and 98,304-byte generic body maximum (lines 10–12); scan checks header/CRC/hash and invokes the supplied state validator before accepting a slot (47–71); begin erases the whole inactive slot before the caller writes (73–84); write rejects a body that exceeds slot capacity (87–99); commit writes header then the four-byte commit marker (101–116).

The successful Hera runs used `lunar-recovery-pytest:20261011` with immutable digest `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`, 1 CPU, 2 GiB memory and equal swap limit, `docker-batch.slice`, networking disabled, and task labels `lan.project=lunar-modulator`, `lan.session=installable-firmware`. The pinned image has pytest but no xdist plugin. The full matrix passed serially, then passed again in 30 parallel containers, each selecting one shard across both geometries (two pytest cases per container). Each container remained under the one-CPU/2-GiB limits.

## Exact run receipts

- Passing run: container `lunar-store-geometry-20261014-f`, exited 0. Log: `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/project-store-geometry-20261014/logs/native-project-store-geometry-f.log`, SHA-256 `1699ad0acb61f99bcc7e0ca3996118445e652bd13adfcc4577d443e939bca5ea`. Pytest output: 60 passed, `RUN_EXIT=0`.
- Parallel matrix: 30 containers `lunar-store-geometry-20261014-p00` through `...-p29`, each exited 0 and each log contains two passing pytest cases (`..`). Per-shard logs and `SHA256SUMS` are under `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/project-store-geometry-20261014/logs/parallel/`; the result manifest SHA-256 is `93fb7417a3c2f9a483e428acd4423722165c91dc7669bc53e33ec3984538f6ff`, and the SHA list SHA-256 is `2025615752068828bb362210743ba6424011f7fc9d3b670ed171f1edf26874df`. Thus the per-mode callback failure count is 55 distinct ordinals (34 at 102,400 and 21 at 49,152) tested twice, for 110 injected callback outcomes total.
- The original small-body serial and parallel matrix used test SHA-256 `3a191327d7645f08540a88f2c75c8e225acbf5226eb68c4ef39b73f5ea435ffc` and adapter SHA-256 `5513b95984b26971882f5515896595172d688acb35c8e6b8f8592801f4062dce` in the Hera worktree based on bare repo commit `31d2e8cd05afd4875d303dca1b52ea5c138aed0f`. No commit was made for those test changes.
- Earlier distinct attempts were preserved rather than overwritten: container `...-a` exited 1 because the image system Python has no pytest (log SHA `b72695fcb3e2889d64484497e2ea8079822f1532c2505f226cde970957bedf7d`); `...-b` exited 4 because the first command requested unavailable `-n`/xdist (log SHA `cbaeaf52bf24817d7af80dbff2df5edc728e17f89b4499c63e9892d838ebcc7c`). An initial serial run exposed an assertion that incorrectly expected the older generation even when a complete commit marker had been written before an error return; that run is preserved as `...-d.log` (SHA `3146ccbcd400c26951db7c07422ab675affec8df148512d1fd58e8204524953e`). The test now distinguishes partial writes from complete operations with lost acknowledgements.
- Local ASan/UBSan smoke ran all 60 adapter invocations successfully; `git diff --check` passed. The canonical full pytest run is the Hera receipt above.

## Remaining dependency and limits

The available image did not have xdist; the serial pass and 30-container parallel pass both completed. Each parallel container was individually limited to one CPU and 2 GiB memory/swap. There were no hardware or physical flash commands. The repository’s native SAVE preflight path remains a separate test dependency if the requirement is to prove oversized complete projects are refused before any erase. This store-level test deliberately does not make that claim.

## Follow-up: restored regressions and larger actual SAVE body

The test harness replacement initially omitted the former 30-case checks for
validation rejection, repeated commit, corruption fallback, and malformed or
oversize body latching. Those cases are restored as
`tests/native/project_store_legacy.c`, copied byte-for-byte from the original
`tests/native/project_store.c` at `e435edadad48641e9e08c0023b71b80b5692cd44`
(SHA-256 `cc535d8aa3857a2aae0c144e58b2f88537ccd1c78b93b207e24345e8651b9a36`).
`test_project_store_legacy_regressions` runs all 30 legacy cases separately;
the current torn-write adapter remains in `tests/native/project_store.c`.

The suite also generates a second payload through the actual app simulator's
project SAVE path and independently decodes its records before running the same
two-geometry, 30-shard interrupted-write/recovery matrix. The generated body
is exactly 35,176 bytes (not padded), with 4×149 sound parameters, 4×24 MIDI
FX parameters, eight modulation modules with nine parameters each and 32
cables, 32 DX7 voices, ten populated audio-FX placements, 64 full-length
accepted AU labels (space-free), all configured per-track note/lock/trigger
pools, and the maximum metadata strings. Whitespace-bearing AU labels are not
accepted by the app SAVE construction used here: a trial was truncated by the
app parser, so this fixture does not claim to exercise that raw fallback.

For the 35,176-byte payload, the callback counts are 165 at 102,400-byte slots
(25 sector erases, 138 page programs, header and commit-marker programs) and
152 at 49,152-byte slots (12 erases and the same 140 programs). Across both
geometries, the 30 shards cover all 317 callback ordinals in both partial
mutation/failure and completed-operation/lost-acknowledgement modes (634
outcomes). The restored legacy tests plus those 60 large-body cases passed in
the bounded Hera run: container `lunar-collector-store-legacy-large-20261014d`,
log SHA-256 `ef68a498bed46b52a5ef4a2b7c4bd63137f86a4f0ad7dc2ff55bca3d0aa1d1dc`,
`RUN_EXIT=0`.

That combined 90-case run used test source SHA-256
`c48a6e00c6a88bab2aef386d13f6c5d9aa15815ee6bd3622f03ca049c0074598`.

The one-case digest receipt generated the same payload and passed the
102,400-byte geometry, shard-00 recovery case. Payload SHA-256:
`8e0252875fd65e75bb99b657cd9381ecbce9c7bfec0d9ca3927ca82b3a1016af`.
Receipt log SHA-256:
`d353a0a61497bc4808bb2ed14648ecb16f2ebd10726093ed2b0bf33cfb2a8985`.
The repeatable fixture's collector-capacity test source snapshot SHA-256 is
`2668eb4857a07d3ac4668c433bfff661946149a7d96a266f7be144f51ea5ab4b`.
The source fixture—not fabricated padding—was used as the recovery payload.
Final test hashes: `tests/test_native_project_store.py`
`1e42c80c99ef6ede1e5755ef6ece2116787dec70246d6daeb09aa65276869e31`,
`tests/native/project_store_legacy.c`
`cc535d8aa3857a2aae0c144e58b2f88537ccd1c78b93b207e24345e8651b9a36`, and
current torn-write adapter `tests/native/project_store.c`
`5513b95984b26971882f5515896595172d688acb35c8e6b8f8592801f4062dce`.

The test module selects `-no-pie` and `--gc-sections` only on Linux, and uses
`-dead_strip` on macOS, so the linker options do not assume Linux on Darwin.

Earlier large-fixture setup attempts remain available as unique logs rather
than being overwritten: `legacy-large-20261014a.log` failed collection because
the old checkout lacked the capacity helper; `...b.log` lacked the imported
`tools` fixture; `...c.log` proved the spaced-label attempt was truncated
(34,408 bytes, not the asserted 35,176); `...d.log` is the passing 90-case
run. The one-case digest receipt's `large-body-sha-20261014a` through `...d`
logs record scope-authentication, missing mount, missing pytest and incorrect
node selection errors respectively; `large-body-sha-20261014e.log` is the
successful digest receipt above. All are under
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/project-store-geometry-20261014/logs/`.
