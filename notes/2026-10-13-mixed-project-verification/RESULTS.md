# Mixed PROJECT verification checkpoint

[verified] The first combined PROJECT campaign failed in its MIDI-slot test
access; the corrected v2 campaign found a production DX7 descriptor-identity
bug. Application-specific DX7 descriptors supply saved patch names, so direct
catalogue-pointer comparison incorrectly refused correct installed DX7 units.
The native modulation preflight now recognizes only the exact application DX7
wrapper with a matching, in-range DX7 catalogue index. Copied descriptors and
mismatched indices remain refused.

[verified] All thirty v3 sanitizer shards passed startup, voice-bank bytes,
modulation seed, scalar/effect state, SET round-trip, explicit sequence playback
with finite nonzero audio, and three non-mutating descriptor/index refusals.
They failed afterward at fixture teardown: normal selection forbids removing
sound zero. Each shard's separate existing composition test passed. All v3
containers exited without OOM and were removed. Their logs remain private in
build/mixed-project-v3/; terminal states are in receipts/host-v3-containers.json.
The fixture now uses existing cold-test teardown for sound zero; v4 completed
on Hera in thirty containers: all sixty tests passed. Every quiet pytest log
and terminal exit/no-OOM receipt was inspected; source hashes match the immutable
remote snapshot. The earlier log-check script expected a pytest summary suppressed
by quiet mode; the corrected log check confirms the actual two-success output.

[verified] All-thirteen production link v2, with twelve-voice Shapes and the
embedded FIRST ORBIT project selected for startup, passed SDK-free/eFuse audits
and exact embedded-byte verification. It excludes diagnostic modules. Receipts
are in receipts/all13-v2-*.json. This is link evidence only: runtime, stack
margin, physical installation/recovery and web-installable release remain
unverified. No device command was issued.

Both semantic tools select the primary checkout; dx7_give navigation matched
its source, but native worktree additions are absent there and fallback clangd
cannot prove pi32v2 ABI. Shared selections were preserved; worktree source and
Hera compilation are authoritative for this fix.

Goal remains active. Next inspect all v4 terminal logs/states and tested source
hashes, then verify production-profile startup and target resources/timing.
Settings migration, physical rollback, web builder/install and required
exact-head review/CI/integration remain unfinished.

## Production-content verification correction

[verified] Production host v1 refused a parameter before allocation. Read-only
record diagnostics in v2 identify arp retired Swing UID 7. Both containers exited
1 without OOM and were removed; receipts are production-v1/v2-container.json.
The all13-v2 driver mistakenly chose tests/fixtures/state/1.0/first-orbit.lunar,
a frozen compatibility fixture, rather than engines/state/examples/first-orbit.lunar.
The current example has Macro bass, no retired arp Swing, new drum Choke/Kit Decay,
time/glide parameters, envelope Delay and set key. The compatibility fixture was
not modified and its refusal remains evidence; native retired-UID compatibility
is not verified. Earlier references to production FIRST ORBIT runtime failure
must be read with this distinction. Host v2 includes project_boot.h, correcting
a missing prototype in v1's acceptance probe.

The driver now selects the actual production example. All13-v3 link is running
on Hera using immutable mixed-project-production-source-v3. After its audits and
packed-byte check pass, production-v3 will test that same prepared content.
All13-v1/v2 retain their earlier legacy-fixture scope; they are not production
content acceptance. No hardware command issued. Semantic tools still select the
primary checkout, bounded state_kind bodies agree with source, but native worktree
additions and device ABI remain outside their verified coverage.

## Actual production startup result (2026-10-13)

[verified] All13-v3 native link and packed-byte check passed on the current
production FIRST ORBIT example (2784 packed bytes). The catalogue retains all
13 sound engines, 24 audio effects, two MIDI engines and 16 modulation modules,
with Shapes at 12 voices. Receipts: all13-v3-{link,content,container}.json.
ELF SHA256 df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e.
This is link evidence, not physical admission or target runtime acceptance.

[verified] Production host v3/v4 reached allocation but refused the fixed
216064-byte pool: 64-bit instances requested 218524 bytes before TLSF overhead.
Their exit-one/no-OOM receipts are retained. Production v5 recompiles the same
full catalogue with -m32 and address/undefined sanitizers in fresh build32.
Its ELF class is 1 (ELF32). Exact packed content from the audited native build
starts successfully and renders 4096 blocks of 64 frames with finite nonzero
audio, no sequencer drops and successful pool cleanup. Runtime receipt reports
energy 2917.86073, live pool bytes 192060 and nine allocations. Exit and state
exit are zero, no OOM; owned container removed. Source hashes match the immutable
Hera snapshot. Receipts: production-v5-{container,runtime,source-hashes}.json.
These assertions are host verification, not pi32v2 ABI, target stack or timing.
No engine, voice count, effect or content was removed to pass, and pool size
was not enlarged. Legacy compatibility fixture refusal remains unverified.

No physical device command was issued. Next inspect complete target PROJECT
startup call/stack paths and audio timing before fresh hardware admission;
settings migration, physical rollback, web installation/builder and required
review/CI/integration remain open. Full release goal remains active.

## PROJECT target stack exploration

[verified] Vendor objdump disassembly of the all13-v3 ELF was inventoried with
lunar_project_start as the root. The exploratory script reports 330 reachable
functions, 37 unresolved indirect calls and two paths to recursive strong().
The estimated direct loader chain is 14740 bytes, with a 2200-byte fm1_cstart
caller frame and 32-byte content activation frame. These are NOT a proven
maximum or stack admission: historical SET callback hints omit PROJECT sinks,
function aliases/local-name collisions may affect traversal, recursive calls
are cut during enumeration, and interrupt overlap/dynamic stack are unchecked.
Source inspection confirms strong() performs Tarjan graph traversal and only
recurses into unvisited nodes; a bound must include the configured position
count and actual target frame. The receipt preserves the exact ELF hash.

Reproduction: use vendor common/bin/objdump -d on linked/lunar-app-probe.elf,
then python3 explore-project-stack.py SOURCE_ROOT ELF DISASSEMBLY OUTPUT_JSON.
The source root must supply tools/jieli/audit_link.py. No hardware admission
follows from this exploratory result. Next resolve PROJECT reader/sink and
engine/modulation callbacks, bounded recursion, caller and IRQ paths before
using a calculated stack margin for a physical test.

### Bounded modulation recursion inspection

[verified] engines/include/fm1_mod.h defines FM1_MOD_POSITIONS as 8. Tarjan
strong() marks g->index[v] before descending and recurses only when the next
node is unvisited. Thus at most eight strong() frames can coexist for valid
planner-generated graph indices. The all13-v3 target stack instructions save
rets and r14-r4 (12 words, 48 bytes per frame), with no other stack adjustment
in this function: that recursion component totals at most 384 bytes. This
component bound does not bound the whole PROJECT path or interrupt overlap.
Both semantic tools located strong() in the primary checkout, matching source;
Rarefaction returned empty call hierarchy despite the visible recursive caller,
so source plus vendor disassembly remain authoritative for that relationship.
Shared project selection was preserved; no server configuration changed.
