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

### Address-based callback inventory checkpoint

[verified] Target compilation on Hera measured fm1_engine_t at 84 bytes,
fm1_midi_fx_t and fm1_mod_kind_t at 88 bytes, and pointers at four bytes.
The measurement uses the immutable all13-v3 source headers and pi32v2/r3
compiler; header hashes are pinned in receipts/callback-layout.json.
The address-based ELF inventory validates descriptor magic, terminated IDs,
registry bounds and every non-null callback against a defined function address.
It finds 37 sound/effect descriptors, two MIDI descriptors and 16 modulation
descriptors in ELF df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e.

[verified] The direct PROJECT graph has 311 functions and 43 unresolved
call sites before callback expansion. Source-reviewed, whole-function callback
role unions add 24 candidate rules, reaching 965 functions and leaving 30
unresolved call sites. These unions are exploratory overapproximations, not
proven per-site targets. The application DX7 wrapper, C++ virtual dispatch,
Schwung internal module hooks, MIDI sinks, optional observers and formatting
callbacks still need complete provenance checks. Static modulation destroy
roles are empty in this catalogue; that alone does not prove arbitrary dynamic
descriptors cannot enter the path. See receipts/project-callback-candidates.json.

[verified] Inspecting apparent external branches exposed a disassembly limit:
vendor objdump prints unknown prefixes followed by apparent conditional branches
in floating-point functions (for example SqSqrtf at 0x20327A6/0x20327A8).
The inventory now records those unknown instructions and apparent external
conditional branches as decoding limits, rather than treating them as calls.
Some unresolved unconditional branches also target non-entry addresses.
Neither ignoring those branches nor the direct graph proves complete control
flow. The earlier estimated stack chain must not be used as a maximum.

Reproduction scripts: measure-callback-layout.py SOURCE TOOLCHAIN OUT_DIR;
inventory-target-callbacks.py SOURCE ELF DISASSEMBLY LAYOUT_JSON OUTPUT_JSON;
expand-project-callbacks.py INVENTORY_JSON OUTPUT_JSON. The full inventory is
private under build/native-external-arenas-16-20261012/address-inventory-v2.json
and Hera out/callback-layout-v1/address-inventory-v2.json. Its hash, registries
and root summaries are retained in receipts/address-inventory-summary.json.
No firmware source, flash or hardware state changed in this checkpoint.

Serena is ready for C/C++ in the primary checkout; Rarefaction's Python query
returned no semantic references for Elf.read. Both tools still select the
primary checkout, not this worktree. Their configuration was preserved and
file inspection plus immutable target compilation are authoritative here.
No semantic result is being used as device ABI or callback coverage proof.

Next: resolve C++/module callback tables and non-entry branch decoding, then
calculate caller/IRQ stack overlap and verify actual target timing. Fresh
hardware identity/backups, settings migration, physical rollback, web builder
and installation, required review/CI and integration remain open. Goal active.

### Macro virtual startup edges (2026-10-13 continuation)

[verified] The all13-v3 ELF contains 21 model vtables selected by Macro's
eight-model switch and Macro Heavy's thirteen-model switch. Each is 24 bytes:
two zero header words followed by Init, Reset, LoadUserData and Render function
pointers. Every method pointer resolves to a defined function address with the
expected method name. Render is not added to startup edges. The four reviewed
source hashes match the immutable production-source-v3 snapshot on Hera.

[verified] Vendor instruction inspection at the six BuildEngines indirect call
sites shows vptr field loads at +0 (Init), +8 (LoadUserData), and +4 (Reset).
ModalEngine::Init calls Reset virtually at 0x202B71A, loading vptr +4. The
receipt retains these seven PCs with separate role-specific target sets.
The call expansion still uses whole-function unions; source/field agreement
does not prove runtime object provenance outside the reviewed constructors.

[verified] Expansion now reaches 1065 functions with 27 candidate rules and
24 unresolved call sites. This does not establish a stack maximum or hardware
admission. The script refuses an ELF hash or reviewed source hash different
from this exact artifact. Reproduce with expand-project-callbacks.py INVENTORY
OUTPUT ELF SOURCE; receipt is receipts/project-callback-vtables.json. Python
compilation, reproduction and diff whitespace checks pass. No firmware or
device state changed. The earlier inventory checkpoint is backed up at
228ac369158a0430a846164fba5d5e857237905f.

Next dependency: bind Schwung module init/create/destroy/parameter/MIDI hooks
and application wrapper/sink callbacks, resolve instruction decoding gaps,
then bound caller/IRQ overlap and verify target timing before fresh backups
and physical admission. Settings migration, physical rollback and the full
web-installable thirteen-engine release remain unfinished.

## Correct r3 decoding checkpoint (2026-10-13)

[verified] The apparent floating-point decoding gaps in the earlier full
objdump output were caused by missing CPU selection. Vendor objdump -d
-mcpu=r3 on the identical all13-v3 ELF succeeds with empty stderr and produces
SHA256 46ff199b5288a37be1f7e3f155cf93bce765b9cf888d31cb8110648740de6e38.
The same bytes previously split into an unknown prefix and a misleading
conditional branch now decode as one four-byte iff floating-point instruction.
The address inventory now recognizes both if and iff branch mnemonics.

[verified] Regenerating the inventory and exact-ELF Macro expansion records
zero decoding-limit instructions and removes the previous false external
branch sites. The candidate startup graph reaches 1065 functions with 27
callback rules and 16 unresolved indirect sites. This supersedes the prior
24-site result; it does not prove callback provenance, stack safety or timing.
Receipts: disassembly-r3.json, address-inventory-r3-summary.json and
project-callback-r3.json. Full disassembly and address graph are private build
artifacts; no vendor ELF is committed.

Use objdump -d -mcpu=r3 for subsequent startup inventories, then run
inventory-target-callbacks.py SOURCE ELF DISASSEMBLY LAYOUT OUTPUT and
expand-project-callbacks.py INVENTORY OUTPUT ELF SOURCE. The probe builder's
RAM-section disassembly now explicitly selects the same CPU as its linker.
The existing key audit has not been changed or revalidated by this checkpoint.

Next: resolve Schwung and application callbacks, then caller/IRQ stack overlap
and target timing. No device command was issued. Full thirteen-engine release,
settings migration, physical rollback and web installation remain unfinished.
