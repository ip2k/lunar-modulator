# Native project scalar startup restoration

The cold-start adapter reads the complete immutable binary PROJECT and validates
its container/CRC before applying sound levels and SESSION current sound, octave
and transpose through the shared app. Invalid or duplicate scalar records,
nonfinite/clamped levels, bad session ranges, live rendering and overlapping
input/app/report are refused. Refusal leaves the app unchanged [verified source].
Other project records still require separate staging and activation; this is not
complete startup, persistent settings migration or an installable release.

Actual pi32v2 compilation at -Os and -Oz passed in all 30 target shards; the
public scalar entry point is present in the objects [verified]. This is compile
coverage, not a final native link or execution. Binary reader main-task stack
requirements remain greater than 8KiB.

Host v1 failed to compile a fixture that accessed a nonexistent app member;
v2 passed 28 cases and failed two fixtures (chunkless PROJECT and SESSION in
SETTINGS). Those failures are retained privately in build/scalars-host-v2.
Corrected fixtures use real codec writers and valid files: units without scalar
records, and a metronome SETTINGS record. No production loader behavior changed
between v2 and v3. V3 runs 30 scalar cases plus 16 existing arena/audio cases in
30 Hera containers using ASAN/UBSAN; all 46 pytest cases passed. All 30 terminal exit states are zero, no OOM or
sanitisers reported errors, every log was inspected and the four changed source
hashes match the immutable Hera snapshot [verified]. Owned containers removed.

Semantic navigation: Serena and Rarefaction select the primary checkout rather
than this worktree. Both resolve the shared level setter; their caller coverage
is incomplete without the actual build database. Worktree sources and actual
pi32v2 compiles are the authoritative evidence; shared servers were not retargeted.

## Final ELF retention

Optional project-loader linking now roots lunar_project_restore_scalars and
reports scalar_restore_link_verified separately from activation. All30 native
links passed final ELF public-symbol checks, SDK-free audits, embedded asset
byte verification and existing audit/option regressions [verified]. Every log,
zero exit/noOOM state and the three changed source hashes were checked; owned
containers removed. These use five-sound selected profiles, optional Plate and
0/1/2/4 text/binary content assets; not the all-thirteen release image. No startup
execution, physical write, timing or installable-release claim follows.
