# Project generation ordering

[verified] Thirty cases in thirty concurrent Hera containers pass ASan/UBSan,
C99 Wall/Wextra/Werror. All thirty logs, exit status pairs, no-OOM status and
three source hashes were independently checked after retrieval. Session93119
is terminal exit0; no workers remain. No production code changed.

Fixture matrix: bases 0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF crossed with
unsigned deltas 0, 1, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF.
Both input slots contain CRC-valid committed payloads. Zero/half-range deltas
refuse scan/begin with -3, set failed/inactive state, reject further write/commit,
make zero erase/program calls and preserve both whole slots byte for byte.
Other deltas select the expected serial-number ordering, erase only the other
slot, increment generation through rollover, commit and select the new slot,
preserving the previous active slot byte for byte.

[verified] Tests exercise the production project_store.h with simulated NOR.
They do not validate real device geometry, full project format, physical reset,
application SAVE integration or flash timing. Previous project-stream campaign
supplies format validation/torn/lost-ack coverage. Hardware allocation and
watched all13 boot remain outstanding.

Serena located lunar_project_scan in the actual worktree header at zero-based
44..65. Rarefaction did not find the symbol because its selected primary
checkout lacks it; neither server was switched or used as target ABI evidence.
