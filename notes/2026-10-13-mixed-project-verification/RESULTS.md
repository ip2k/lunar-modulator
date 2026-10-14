# Mixed PROJECT verification checkpoint

## ISR allocation-prefix verification (2026-10-13)

[verified] inspect-isr-prologues.py checks all 20 functions in the union of
pinned timer/audio C closures. Decoded instruction bytes match the exact ELF,
and each function range has contiguous instruction coverage. All explicit
allocations precede control transfers; every local relative branch targets an
instruction after the allocation prefix. Table/repeat instructions, indirect
transfers and unsupported PC writes are refused. Local branches therefore
cannot accumulate these allocation sites. Receipt receipts/isr-prologues.json
reproduces byte-for-byte. Nine positive/negative model tests pass using the
primary checkout .venv; system python lacks pytest. Conditional software frame
costs remain 152/168 bytes. This is not a complete startup stack bound.

[reported] JieLi AC79 interrupt docs specify larger numeric priority is higher:
https://doc.zh-jieli.com/AC79/zh-cn/release_v1.0.3/module_example/system/interrupt.html
Compiled timer priority4 is above audio3. The page does not establish automatic
nesting, CPU stack switching or entry frame cost; those remain open.

Both semantic tools still select the primary checkout, whose HAL path is
absent. Rarefaction's bounded name search failed; Serena reported missing
fm1_irq.h. Shared selection was preserved. Exact target artifacts supply this
evidence. No firmware build or hardware command occurred. Next resolve remaining
startup callback provenance and complete caller/IRQ stack/timing before hardware
admission. Full13 acceptance, migration/rollback, web builder/install, licensing,
review/CI/integration remain open. Goal active. No live measurement job.
Previous verified pushed checkpoint: d976cfaa23858351258040e1553cf93fc73e5aed.

## Interrupt exposure checkpoint

[verified] Follow-up inspect-isr-call-stacks.py checks the exact inventory and
interrupt receipt hash chain. Timer C closure has 15 functions; audio C closure
has five. Both are acyclic with no unresolved calls, decoding gaps or missing
direct callees in that inventory. Explicit frame accounting yields timer
124 C-chain bytes plus 28 wrapper bytes = 152; audio 140 + 28 = 168. Longest
timer candidate is timer5 -> usb_poll -> uac_service -> sie_rd; audio is
alnk0 -> uac_tap -> uac_tap48 -> uac_s16. Receipts reproduce exactly and a
mismatched upstream ELF is refused. This conditional calculation sums all
allocation sites per function; allocation-loop exclusion, table control flow,
inventory completeness, hardware entry and stack selection/nesting remain
separate gates. No target firmware was changed to defer interrupts: the timer
services USB and input, so deferral needs watchdog/startup-time evidence first.

[verified] inspect-startup-interrupts.py binds the unchanged all13-v3 ELF and
r3 disassembly to its stack symbols and compiled entry setup: user reservation
24320 bytes, system reservation 7936 bytes. Both timer5 and ALNK wrappers save
28 bytes explicitly and restore the same registers before csync/rti. Compiled
attachment uses vector 11 priority 3 and vector 63 priority 4. Global sti at
0x205f422 precedes the PROJECT call at 0x205fde2 within fm1_cstart. Receipt
reproduction, changed-enable-expectation rejection, Python compilation and
whitespace checks pass. This is not exhaustive path analysis or a stack bound:
CPU stack selection/nesting, hardware entry cost and C-handler call chains
remain to be established. No firmware change or hardware command occurred.

[verified] Source review finds printf %n writeback enabled by default; constructor
null alone cannot establish pointer preservation for arbitrary inputs. Native
sources do not assign on_mod, while the shared state loader temporarily clears
and restores it. Neither optional hook has been removed from unresolved
coverage. Semantic navigation located mod_emit in the primary checkout; its
source line differs from this worktree, so target artifacts remain authoritative.

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

## Exact Schwung startup checkpoint (2026-10-13)

[verified] Target compilation on Hera measured the Module descriptor at 48
bytes, sound API at 32 bytes and shim effect API at 28 bytes, with four-byte
pointers. The actual PSX effect API symbol is 24 bytes: its older declaration
omits the newer MIDI member. Reviewed startup uses the common prefix only.
Header and source hashes are retained in receipts/schwung-layout.json and
receipts/schwung-callbacks.json. The initial measurement failed because the
vendor toolchain has clang but no clang++; the corrected run uses clang -x c++.
The failed v1 log/state remain on Hera under out/schwung-layout-v1*. The v2
container exited zero without OOM and was removed.

[verified] inspect-schwung-callbacks.py checks the exact all13-v3 ELF, initialized
Sophie API words and PSX initializer stores into its BSS table. It binds eleven
init/create/destroy/parameter/MIDI/focus call sites to defined function targets.
Expansion reaches 1102 functions with 31 candidate rules and seven unresolved
indirect calls, including two newly exposed host hooks. This is candidate
coverage, not complete runtime provenance, a stack bound or hardware admission.

[verified] Python compilation and receipt reproduction pass. Callers are sorted
to avoid set iteration changing JSON order. The prior r3 receipt reproduces
byte-for-byte without the optional Schwung argument; the new expanded receipt
also reproduces byte-for-byte. Signed ifs branches are now recognized alongside
if and iff. No firmware or physical device state changed.

Both semantic tools remain ready on the primary checkout; their shared selection
was preserved. An exact-position Rarefaction query using worktree line numbers
resolved popup instead of mfx_sink because primary source lines differ. Serena
found mfx_sink by name and confirmed its note_off target is mfx_off. Semantic
results are navigation only; immutable target source/disassembly are required
for coverage and ABI claims.

Next resolve fx_log, sophie_get, mod_emit, run_quiet, record and printf gadget
callbacks; then bound complete caller/IRQ stack overlap and target timing before
fresh identity/backups and physical admission. Settings migration, physical
rollback, web builder/install, licensing and required review/CI/integration
remain open. Full thirteen-engine goal active. Prior verified pushed checkpoint:
c259deea66942840ad09098d21cd9f4e902db06f. No running measurement job.

### Compiled host-hook coverage

[verified] Exact all13-v3 disassembly stores HostLog at host offset24 and
HostClockStatus at offset36 before module init. PSX fx_log loads offset24 at
0x20142EC before its indirect call; sophie_get loads offset36 at 0x201B7BE.
The inspector now asserts each literal target/store/load and adds both host
call sites. HostLog returns immediately; HostClockStatus returns unavailable.
Expansion reaches1104functions with33rules and five unresolved sites:
mod_emit observer, two run_quiet sites, record note callback and printf gadget.
Both updated receipts reproduce byte-for-byte; Python compilation passes.
This is still candidate coverage, not complete provenance or stack admission.
No hardware commands or firmware edits. Previous verified pushed17ad65f01643fb596181bf8734c94248b7e109f4.
Next inspect native observer initialization, MFX sink/process binding, actual
record symbol origin and formatting gadget construction, then stack/IRQ overlap.
Full release goal and physical migration/rollback/web/CI gates remain open.

### Catalogue and MIDI candidate coverage

[verified] Source hashes for state_names.c, state_registry.c, project_units.c,
mfx_host.c and fm1_app.c match the immutable production-source-v3 snapshot
on Hera. The record call at0x2060D08 is names->known from inlined
fm1_state_note_unknown, NOT an engine note callback; this corrects the earlier
checkpoint wording. fm1_state_names_default installs fm1_absent_find via the
compiled pair store at0x204F5FC (r0 at+40, r1 at+44).

[verified] run_quiet loads the MIDI process slot at+84 before0x2042BCC and
sink->note_off at+4 before0x2042C20. Source mfx_sink assigns mfx_off. The latter
loads engine->note_off at+48 before0x203A888. Whole-function candidate rules
now include catalogue-known, MIDI process/MFX sink and sound note-off targets.
All covered caller PCs must match the exact inventory; source hashes are pinned.
This remains conservative candidate coverage, not complete object provenance.

[verified] Expansion reaches1133functions with36rules and two unresolved sites:
mod_emit.4780 at0x203A80C and putchar_via_gadget at0x206D8E6. New and historical
r3 receipts reproduce byte-for-byte; Python compilation and whitespace checks
pass. No physical command, runtime or firmware change. Prior verified pushed
77ba8c2303a0ee19bd654816e749dd377eed3a5e.
Next prove native observer initialization and formatting gadget construction,
then calculate complete startup/caller/IRQ stack and test target timing.
Physical migration/rollback, installer/builder, licensing and review/CI remain
open. Full release goal remains active; no live measurement job.

### Optional-hook construction evidence

[verified] inspect-printf-construction.py binds the identical all13-v3 ELF,
r3 disassembly and address inventory. The only direct caller of
vsnprintf_impl is vsnprintf. Console/function-output entry points and
putchar_wrapper are absent from linked function symbols. At 0x206EA8C r4
becomes zero; 0x206EA9E stores it in the stack gadget's first word, the
function slot loaded at 0x206D8DC before the optional tail call at 0x206D8E6.
The exact printf source hash is pinned. Receipt printf-construction.json
reproduces byte-for-byte. A deliberately changed callback store was rejected
even after updating the inventory's disassembly hash to match the altered
text. This verifies the instruction assertion rather than merely a hash.

[verified] inspect-observer-construction.py asserts native fm1_cstart's
memset arguments and the mod_emit load: app address 0x1C0EA10, zero length
38468, observer offset 7710*4 = 30840. The callback word is covered by the
compiled initialization. Receipt observer-construction.json reproduces
byte-for-byte. Both scripts compile and whitespace checks pass.

[inferred] These construction facts support null optional hooks during cold
native startup. They do not alone prove preserved pointer values through all
formatting/state paths or exclude address-taken formatter entries. The startup
graph therefore still retains both unresolved calls; neither an empty target
rule nor hardware admission was added. Next review source pointer flow and
compiled stores before changing graph coverage, then complete stack/IRQ overlap.

Both semantic tools are ready on the primary checkout, not this worktree;
shared selection was preserved. Rarefaction located fm1_app_init's three
callees but returned no callers despite the known native caller. Serena located
mod_emit and its conditional observer plus edit-ring scan. These navigation
results do not prove target call completeness or ABI. No firmware/device
command or heavy build was performed. Full release gates remain open.

## Table branches and bounded chord sort (2026-10-13)

[verified] Supplementary inspect-table-branches.py records 90 compiled tbb/tbh
sites, 47 in the 1133-function candidate PROJECT graph. Every opcode/register
pair matches ELF bytes; all table boundary symbols pair correctly. Under the
compiler's table_start + 2 * unsigned offset model, all entries land inside
the owning function. Retained target codec assembly expresses tbh entries as
.short (target-table_start)/2. Runtime bounds/alignment of each index are NOT
proved. The prior zero-decoding-limit result therefore does not establish
complete control-flow coverage. Historical callback receipts remain unchanged.

[verified] inspect-chord-sort.py pins the four-note ChordBank header, compiled
begin/end difference of16bytes, initial sort branch path, six-entry byte table
and entry4 destination0x206351A. That branch calls sort4, which calls sort3;
neither helper has other calls or unresolved sites. The conditional four-note
sort path uses one56byte sort frame and two16byte helper frames:88bytes, with
the20byte ChordBank caller present separately. This does not bound ratio
normalization, outer callers, interrupts or hypothetical address-taken entry.
The complete call inventory names only ChordBank and sort itself as direct
callers of this sort specialization. No recursive edge is deleted globally.

[verified] Both receipts reproduce byte-for-byte, Python compilation and
whitespace checks pass. A mutated branch register is rejected by opcode matching
with upstream hashes updated; a changed entry4 target is rejected by the chord
inspector. No native build or device command occurred. No physical admission.
Serena finds the ChordBank Sort source; Rarefaction's exact-position query at
line61 returned no resolved symbol/callers, so it is not coverage evidence.
Shared semantic selection stays on the primary checkout.

Reproduce from this worktree:

```
N=notes/2026-10-13-mixed-project-verification
B=build/native-external-arenas-16-20261012
python3 "$N/inspect-table-branches.py" . "$B/all13-v3.elf" "$B/full-disassembly-r3.txt" "$B/address-inventory-r3.json" "$N/receipts/project-callback-schwung.json" "$B/state-codecs-v3/shard-00/codec.s" /tmp/lunar-table-branches.json
python3 "$N/inspect-chord-sort.py" . "$B/full-disassembly-r3.txt" "$B/address-inventory-r3.json" /tmp/lunar-table-branches.json /tmp/lunar-chord-sort.json
```

Next: finish optional-hook provenance, account for table-index bounds where
needed for startup reachability, and combine caller/IRQ stack and target timing.
All13 physical acceptance, migration/rollback, web builder/install, licensing,
review/CI/integration remain open.

## Native formatter writeback disabled

[verified] The native application builder compiles the pinned, unmodified
printf source with PRINTF_SUPPORT_WRITEBACK_SPECIFIER=0 and reports the setting.
The source search found output formatting does not require %n; matching desktop
uses belong to sscanf parsing, whose behavior is unchanged. The library's own
build option avoids a fork; its default switch and guarded case are in
firmware/third_party/printf/printf/printf.c:106 and :1559. Upstream:
https://github.com/eyalroz/printf . This removes formatter argument writeback,
not every possible alias or a complete optional-hook preservation proof.

[verified] Thirty Hera sanitizer chunks cover six writeback length forms across
five output capacities, unchanged argument sentinels, and existing UI format/
length/truncation/canary comparisons against libc. All logs, terminal zero exits,
no-OOM states and six local/remote source hashes checked. New campaign containers
were removed. Initial v1 failed before compilation due to a runner string-quoting
error; all thirty failure receipts/logs remain on Hera in out/formatter-no-writeback-v1.
Corrected v2 is retained locally in build/formatter-no-writeback-v2.

[verified] All13-no-writeback-v4 full pi32v2 link passes SDK-free/eFuse audits,
exact embedded production FIRST ORBIT bytes and unchanged production module
selection:13 sound,24 audio effects,2 MIDI,16 modulation,Shapes12. ELF SHA256
4b340d1aa4f67737d102441680df5d28a2740d6a2eaa83feb028ea19a9f49e2b.
Receipts all13-no-writeback-{link,content,container}.json and
formatter-no-writeback-{host,source-hashes}.json. This ELF supersedes v3 as the
latest build; address-specific v3 startup/stack receipts do not prove v4.
No new physical command or hardware acceptance. Fresh v4 disassembly/callback/
stack inspection is next, followed by timing/hardware admission. Full13 runtime,
migration/rollback, web builder/install, GPL transition and exact-head review/
CI/integration remain open. No campaign is still running.

Both semantic tools remain on the primary absolute checkout. Bounded formatter
caller navigation returned empty/non-callable results; it does not establish
absence of callers. Worktree-only builder changes and target ABI are outside
that index. Shared selection was left unchanged.

[verified] Full r3 disassembly/address inventory regenerated for no-writeback-v4.
Registry counts remain37 combined sound/audio descriptors,2MIDI,16mod. Direct
PROJECT closure has311functions/43unresolved sites; fm1_cstart844/110. These
are unexpanded direct closures, not comparable to v3's1133 expanded candidate
functions. Exact hashes/root details in address-inventory-no-writeback-summary.json;
full private inventory/disassembly retained with the ELF under
build/mixed-project-all13-no-writeback-v4. No complete stack or admission claim.
Native formatter change and30-shard/full-link evidence committed and verified
pushed222b423bd54df643c729bc0dc6380b9d6b12b532. Next rebind expanded candidate
callback rules and stack inspections to this new inventory without relaxing
unresolved paths. No live job. Full release goal remains active.

## Current candidate callback checks rebound (2026-10-13)

[verified] The formatter constructor inspector now supports two explicit ELF
profiles, retaining the historical profile and adding no-writeback-v4. The
constructor moved by -0x9e; its callback hook remains at0x206d8e6. Selected
instruction bytes are checked against the ELF. New receipt reproduces; the
historical profile passes. Altered opcode and altered null-store text are
rejected even after updating the inventory disassembly hash. Receipts:
printf-construction-no-writeback.json and its -checks.json.

[verified] Schwung callback checks and Macro/source candidate expansion now
support the exact v4 ELF while refusing unknown images. Actual vtables/API
words, source hashes, named methods, selected initializer/host-hook/call bytes
and indirect PCs are checked. Historical Schwung receipt reproduces byte-for-
byte; an altered host-hook store opcode is rejected with the inventory hash
updated. Expanded v4 graph:1133functions,36rules,two unresolved sites:
mod_emit.4780 and putchar_via_gadget. These remain candidate unions, not
complete runtime provenance. Receipts schwung-callbacks-no-writeback.json,
its -checks.json and project-callback-no-writeback.json.

A broad earlier-body byte identity attempt failed on CombCreate: relinking
changes embedded pointers even with unchanged function addresses. No blanket
identity claim is used. Initial Schwung invocation used the wrong layout
receipt and failed; corrected to schwung-layout.json. Checking every objdump
line also encountered literal/data output; byte validation now applies to
all instructions explicitly claimed by the Schwung receipt.

Source review finds formatter callback assignments only in construction;
output writes affect position and bounded buffer bytes. This is conditional
on valid, nonaliasing caller buffers and does not discharge provenance.
Both semantic tools select the primary checkout lacking this worktree-only
formatter file and returned file-not-found; shared selection preserved.
Python compilation and diff checks pass. No new firmware build/device command.
Next rebind observer and stack/IRQ checks, establish complete startup/timing
evidence, then safeguarded physical verification. Migration/physical rollback,
web builder/install, GPL and review/CI/integration remain open.

## Current candidate observer and interrupt evidence (2026-10-13)

[verified] Exact ELF/disassembly profile pairs added for no-writeback-v4 to
observer-construction and startup-interrupt inspectors. Their compiled
assertions pass: initial38468byte app zero covers observer offset30840;
user/system reservations24320/7936bytes; wrappers save28bytes and IRQ enable
precedes PROJECT. Handler inventory and prologue inspectors now accept only
the exact matching v4 inventory/receipt hashes alongside historical profiles.
Both direct ISR closures retain15/5functions,152/168explicit software bytes
with wrappers. All20function ranges have ELF-matched instructions, contiguous
coverage and no local branch into an allocation prefix. Nine prologue model
tests pass. All four historical receipts reproduce byte-for-byte. Python
compilation and diff checks pass. New receipts: observer-construction-,
startup-interrupts-,isr-call-stacks-,isr-prologues-no-writeback.json and
no-writeback-stack-reproduction.json.

These checks do not prove optional-hook preservation, hardware entry cost,
CPU stack selection/nesting, whole PROJECT margin or target realtime timing.
No physical command or new build; all13 real-device acceptance, settings
migration/physical rollback, web builder/install,GPL,review/CI/integration
remain open. Next complete provenance/control-flow/startup bounds and timing
without substituting historical proof for current-candidate evidence.

## Observer evidence integrity checkpoint (2026-10-13)

[verified] inspect-observer-construction.py now compares every asserted
initialization/load/call opcode, including the memset call, with bytes read from
the pinned current ELF. It rejects source hashes outside the four reviewed
native/application files rather than merely recording arbitrary input hashes.
The reviewed fm1_app_state_load source saves on_mod/context, clears the hook,
and restores the saved values in that order. The new v2 receipt records that
source evidence without claiming compiled preservation or alias safety.

[verified] Current v4 receipt reproduces byte-for-byte. Separate altered-source
checks replacing either callback save or restore with NULL fail before receipt
publication. Python compilation and git diff --check pass. Original receipts
remain as historical evidence; new receipts are observer-construction-no-writeback-v2.json
and observer-construction-no-writeback-v2-checks.json under the verification
receipts directory. No firmware or device command was issued.

Serena and Rarefaction remain selected on the primary checkout, not this
worktree; selection was preserved. Serena navigated the matching mod_emit body;
Rarefaction reported two ambiguous definitions. Target ELF and worktree source
are authoritative. Full startup margin, compiled callback preservation, aliasing,
interrupt nesting and timing remain open, followed by physical full-catalogue
migration/rollback and browser builder/install, licensing and review/CI gates.
The owner scope remains thirteen engines plus selectable content/effects builds.
Previous verified pushed checkpoint: 229c43f89f70c95df8f7f66910c61a2e0f10e053.
No live measurement job.
