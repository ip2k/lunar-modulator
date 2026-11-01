# Selected Trio PROJECT adapter, milestone 1 (offline)

Base: `5c5237b013fee9cb6da806136579e4aca85aa1d7`. This is a source
checkpoint, not an installable native profile or a claim that Lunar has run
on an FM-1. The general installer service PROJECT/SET/SAVE request remains
refused. No device, native target build, Docker, or service activation was
performed.

## Contract

`firmware/native/selected_project.c` consumes a stable, immutable binary
PROJECT through the shared bounded state reader. It accepts the current
`init-starter-trio` shape: five supported metadata fields, one Sound 1 Trio
unit with all 14 parameters and level, seven empty sound/effect units, and
END. It rejects every other record and semantic variant before selecting an
engine. Two complete reader passes fill and compare fixed plans; no file
record is applied during either pass. The caller must provide a fresh app,
external arenas, a separate 16-byte-aligned reader workspace, and exclusively
stable input. CRCs and two-pass comparison are not authentication or a
concurrency lock. Engine constructor/rate/RAM failures remain separate app
errors; no native RAM fit or target ABI proof is claimed here.

The first host oracle uses the current app's general state loader only as a
comparison, in host memory. That loader needs over 544 KiB of workspace and
is not proposed for native use. The new adapter itself uses the shared
9,536-byte host reader context from the separate persistence lane plus two
small fixed plans. The selected Trio engine reports 4,240 instance bytes;
the host app's current RAM meter reports 86,648 bytes. These are source and
host facts, not a linked target memory report.

The source is
`engines/state/examples/init-starters/trio-init.lunar`, SHA-256
`46541967e4fa7321f4efe1105632de3613064a2fbcf7d71490cb647247a97c1b`.
The exact current `FM1_MODULES=trio` renderer export has 14 parameters and
produces 30 logical records, with `skipped=repaired=unknown=0`. Its stored
uncompressed container is 597 bytes, SHA-256
`dc3c50d8da761fdfe36d17e1368d99f40740652192f14649230a9f8d7e3d58d4`.
The old static `engines/state/examples/metadata.json` drops all 14 parameters
yet returns `code=OK` with `skipped=14`, `unknown=1`; production preparation
must use a fresh exact-build export and reject all soft-success counters.

## Provisional proof and dependency

The host oracle test links the fixed reader `state_bin.c` and header from
onset's frozen `2cb13c5838583517ad0f169ca8240ec3722e1276` as an
explicit *provisional* dependency, without copying or cherry-picking it.
The parser source Git blob is `78c35d407c0c946d26020c0ec4a0b44f3112477a`;
its header blob is `65130050cdca6cfdcec99c8ac2671cf817be2b9c`.
`tests/test_native_selected_project.py` builds an isolated current app and
compares the selected applier to that app's actual general state loader: all
14 values, level, info, and a 64-frame PCM block agree. A corrupted CRC and
five structurally valid but unsupported variants (missing parameter, extra
info, wrong engine, out-of-range parameter, missing level) refuse before any
app or arena mutation. The 1-test provisional pytest run passed. Normal CI
cannot pass this test until the reviewed bounded reader is integrated into
the branch; after integration, rerun without the provisional environment
variables. Exact commands and small logs are retained in ignored
`scratch/selected-project-m1/` while review proceeds.

## Next dependency

Review/integrate the shared bounded reader before treating this GREEN as
accepted. Then add a dedicated source-bound selected diagnostic builder and
receipt, using opt-in native strict pack after its separate review. The
builder must embed the exact packed bytes actually read by diagnostic startup
and record source/export/container/toolchain hashes. Review that source and
the native closure before any target profile or ROM-return glue build. Dinghy
GPL HAL provenance and private-only/no-redistribution restrictions remain
mandatory for any later linked target artifact. No service admission or
hardware assertion follows from this milestone.
