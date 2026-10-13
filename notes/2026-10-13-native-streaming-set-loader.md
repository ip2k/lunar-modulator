# Native packed-set loader [verified]

`firmware/native/content_set.c` connects `fm1_state_bin_read` to the existing
`fm1_seq_import_begin/feed/end` importer. Decoded `FM1_REC_LINE` fragments go
directly to the importer; a newline is fed only on `FM1_REC_LAST`. It neither
allocates nor retains a whole set or line. The source must remain immutable.

The caller supplies an initialized scratch sequencer. Failure may change that
scratch instance, which must be discarded. This API deliberately does not
accept a live application or activate playback. Only standalone SET containers
are accepted; applying project engine/effect/modulation state remains separate.

The established importer ignores unknown lines and truncates data outside its
fixed capacities. Matching that importer is not strict semantic acceptance or
proof that every requested event fits. Application admission, lane resolution,
an atomic activation path and realtime playback remain required. The binary
reader's measured entry frame alone exceeds 8 KiB; this API is main-thread only,
and target compilation is not a complete stack-margin verification.

## Verification [verified]

Sixteen independent Hera containers ran eight cases under each of `-Os` and
`-Oz`. All sixteen passed with no OOM. Each case compiled and executed a host
ASan/UBSan harness and compiled the bridge with the pinned pi32v2 toolchain.
Successful cases compared complete canonical sequencer exports with the existing
whole-text importer: the golden orbit set, a long 256-note line crossing decoder
fragments, unknown-line behavior and a track outside the destination's capacity.
Refusal cases covered truncation, corrupted payload, a project supplied as a set
and non-Lunar input. Null arguments and oversized input were also refused. The
harness checked that a distinct live instance remained byte-identical.

The first campaign failed at host linking because the test omitted `-lm`, needed
by existing sequencer code. That receipt is retained; it is not passing evidence.
The corrected `content-set-v2-verification.json` is retained privately under
`build/native-external-arenas-16-20261012/` and on Hera's corresponding `out/`.
No USB, RAM-loader or flash operation was performed. This component is not yet invoked by the native application probe and is not
an installable firmware milestone.

## Optional native link checkpoint [verified]

`build_application_probe.py --link-set-loader` retains the decoder entry as a
linker root, reusing freshness-checked state codec objects already in the native
catalogue. It reports link verification separately from activation, stack margin,
semantic acceptance and physical verification; all latter flags remain false.

The 16-container `content-loader-link-v2` campaign retained the five-engine
profile, optional Plate and 0/1/2/4 text/binary source assets. Eight profiles
without Plate passed the full linked-image audit and protected artifact guard,
and final ELF content was compared byte-for-byte. Eight Plate profiles linked
but were rejected by the unchanged safety audit. No campaign-wide pass is claimed.

The audit hit is `.text +0x3751d` in `fm1_app_render`. Pinned vendor disassembly
of shard 08 shows at 0x0203763a `80 ff 0c 2e 01 00`, a relative call to
`__umoddi3` at 0x0204a44c; at 0x02037640 `02 15`, a register-pair move.
The scanned LE32 stub signature `2e 01 00 02` crosses those instructions
[verified for shard 08]. This is an audit false positive, but the audit remains
unchanged and these builds remain refused. The existing proof mechanism covers
complete relative-call payloads for eFuse checks only. Next: extend it narrowly
with matching ELF-byte/instruction/call-target proofs and negative regression
cases for real loads, data constants, damaged disassembly and out-of-function
instructions. Do not bypass the audit or whitelist a whole function.

The first loader-link campaign duplicated codec objects already supplied by the
catalogue and failed with duplicate definitions; its receipt is retained.
The corrected campaign used those catalogue objects. No physical operations
occurred, and all test containers were removed.

## Audited loader-link verification [verified]

The follow-up `content-loader-link-v4` campaign passed all sixteen guarded native
links, including Plate and 0/1/2/4 content assets in text/binary source formats.
Each container first passed 68 safety-audit and artifact-layout regressions.
No container reported OOM. Both ELF and flattened-image audits passed with no
pending checks, and final content descriptors/payloads matched checked inputs.

`stub_call_boundary_patterns` recognizes only the observed six-byte resolved
relative call followed immediately by the byte-exact `02 15` register-pair
move in the same sized function and executable section. The matching LE32
signature must cross that exact boundary. It does not exempt other unaligned
constants, loads, literals or entire functions. Flattening carries the proof
through the validated section load mapping and rechecks all eight bytes.
Negative regressions cover altered decodes/bytes/targets, function bounds and
separate address constants. Each byte of the flattened instruction pair is
mutated separately to verify rejection. Other safety checks are unchanged.

The v3 campaign passed the ELF audit but correctly failed the independent
flattened-image audit before that proof mapping was implemented; its receipt
is retained. The v4 evidence includes each ELF/app SHA and complete artifact
key audit, retained privately as `content-loader-link-v4-evidence.json`, SHA256
`6eb8c83ab553ad0e4cff0c4c174792685be27b483cdb85377c01fd4ee74fe13b`.
This supersedes the earlier loader-link rejection; activation, complete stack
margin, sequence admission, hardware playback and installability remain open.


## Staged activation checkpoint (2026-10-13, validation in progress)

`lunar_content_activate_set` now loads a standalone packed SET into a caller-owned
initialized arena, then calls `fm1_app_seq_activate`. The sequencer core exposes
`fm1_seq_can_replace`/`fm1_seq_replace` for compatible, disjoint initialized
instances. Limits and rate must match and the staged source must be stopped,
with no gates or pending/held recording notes. This is not a deserializer of
arbitrary sequencer memory. Same-task ownership and immutable staging are required.
The app releases old sequenced engine notes, clears pending commands/events and
locks, preserves the prior dropped-event total, copies the offset-based arena,
and rebinds parameter labels through the existing host bridge.

[verified] The first `-Os` host case passed under ASan/UBSan on Hera, exercising
the actual shared app, sequencer, binary codec and modulation runtime. The
sixteen-case Os/Oz campaign is running; full target catalogue rebuild/link and
remaining regression results are pending at this checkpoint. The native link
option retains the new activation entry point, but the timed probe does not
call it. There is no new device write, physical acceptance, demonstrated staging
RAM margin, parser call-chain stack bound, strict content capacity admission,
project engine/effect application or installable release claim.

## Staged activation verification [verified]

Sixteen Os/Oz host cases passed on Hera under ASan/UBSan with the actual shared
app, sequencer, binary codecs and modulation runtime. Valid SET activation
releases old sequenced notes, clears pending commands, advances the host
generation and resolves imported lane labels to parameter UIDs. Invalid
containers leave both the live app and arena byte-identical. Cases reject
identity, unaligned sources, mismatched sample rates/limits and playing staging
instances. The historical importer still ignores unknown lines and truncates
out-of-capacity content; these cases preserve that behavior, not strict admission.

The fresh native catalogue v3 rebuilt all 167 objects in sixteen Hera chunks.
The content-loader-link-v6 campaign passed sixteen guarded native links with
68 audit/artifact regressions per container, no OOMs, matching frozen content
bytes and descriptors, and retained standalone-load/activation entry points.
Private evidence receipt SHA256:
`26c75dc2d29e54f54629cdf07bd62f88c19dc933e15d9f3302a68145ec0210d5`.
It includes ELF/app hashes, complete key audits and dependency receipt hashes.
The v5 links passed safety audits but the test harness then incorrectly required
a separate internal `fm1_app_seq_activate` symbol that LTO inlined. The failed
receipt is retained; v6 removes only that assertion, retaining both public API
symbol checks and all safety checks. All campaign containers were removed.

The timed probe still does not invoke activation. Startup staging might borrow
the instance pool before any sound allocation, but this is only a candidate:
its ownership, exact limits and bounded stack must be verified before integration.
The Shapes twelve-voice instance leaves too little pool space for a full staging
sequencer during ordinary playback. Runtime hot-loading needs separate admission.
No hardware operation, installable release, sequence completeness, project
application or real-time playback acceptance is claimed.

Semantic navigation limits: Rarefaction and Serena remain selected on the primary
checkout, not this worktree. The bounded sequencer/app queries returned stale
line locations or incomplete caller information; Rarefaction had no native
compilation database. Actual worktree source and target builds are authoritative.
Shared semantic servers were not retargeted.

## Startup allocation-order experiment [verified host]

The follow-up v3 campaign passed all sixteen Os/Oz sanitizer cases, including
an initialized eight-track staging sequencer allocated through the actual TLSF
pool adapter. The 216064-byte pool holds staging; both valid and rejected loads
can release it, after which a 206904-byte Shapes budget allocation succeeds.
Staging allocation fails while that budget is held. Allocator counters return
to zero after reclamation; no OOMs or sanitizer findings occurred. Receipt
SHA256: `245fc48efac0bc53bda6ddadd68f392cf5fc4816e62f4a763754ebe1cd5169ba`. The target compiler still compiles the packed-set bridge;
this host experiment does not establish the target allocator ABI, instantiate
Shapes, invoke complete app initialization or establish parser stack margin.
No new runtime startup hook or hardware write was introduced.

## Observed-loss admission [verified host and target link]

The compatibility importer now reports observed range loss, text truncation,
unknown fields and increases in the sequencer's refusal counter. Its legacy
return value and imported output remain unchanged. The native checked loader
rejects these diagnostics, and activation uses that loader before releasing
old notes or replacing live state. The refusal category includes invalid routes
as well as exhausted pools; it is not exclusively a RAM-capacity diagnostic.

Thirty-two Os/Oz ASan/UBSan cases passed in sixteen Hera containers: valid and
long sets, unknown fields, out-of-range tracks, truncated labels, oversized
note/trig data, exhausted song/note/lock pools, invalid routes and corrupt or
wrong-kind containers. Rejection leaves the live application and arena
byte-identical. These tests also preserve the compatibility loader's output.
A fresh 167-object target catalogue (v4) compiled in sixteen chunks; sixteen
native loader/activation links (v7) passed 68 audit/artifact regressions each,
with matching embedded bytes/descriptors and no OOMs.

Separately, the existing core, Movy, song and oracle suites ran 468 collected
nodes in sixteen disjoint Hera chunks: 466 passed, two pre-existing expected
failures for the unported undo ring. The shared host binaries were built once
and mounted read-only during tests. The first launcher stopped at collection
because inherited quiet flags produced file counts instead of nodes. The second
completed tests but its log collector had a path-formatting error. Logs, XML
and exited-container states were recovered without repeating the tests;
collection failures were retained, and all sixteen containers were removed.

Private combined receipt SHA256:
`5ebcc01e1fcdf47b06370428aa3133486181a815649aa9637d0731d67c5cce60`.
Local receipt: `build/native-external-arenas-16-20261012/content-loader-link-v7-evidence.json`;
Hera root: `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out`.

Zero loss flags are not complete syntax, dependency or playback admission.
Malformed/skipped items, scalar normalization, engine availability and complete
project application still require work. Parser call-chain stack margin and
startup use remain unverified. Semantic queries still resolve to the primary
checkout with stale/incomplete navigation; the actual worktree and compiler
results are authoritative. No device operation or installable release is claimed.


## Opt-in startup staging [verified host and target link]

The timed probe now accepts an explicit `--startup-set-index` together with
`--link-set-loader` and a prepared profile. The builder rejects out-of-bounds
indices and project containers. Startup borrows a sequencer-sized allocation
from the instance pool, uses checked activation, and releases staging before
Trio allocation. Loading does not start playback. The default probe is unchanged.

Thirty-two Os/Oz ASan/UBSan cases passed in sixteen Hera containers, including
valid/corrupt/lossy sets, sample-rate mismatch, pool exhaustion, unchanged live
state on rejection and zero residual staging allocations. This harness manually
initializes the application/limits; it does not execute the complete target
startup or allocate an actual Shapes engine. Sixteen native links (v10) passed,
each with 77 audit/artifact/option tests. They cover zero/one/two/four embedded
assets, text/binary input and Plate enabled/disabled; startup is enabled only for
the two/four-asset profiles. Payloads match the prepared inputs byte-for-byte.

Failed v8 and v9 campaigns are retained: v8 omitted the host packer environment
variable; v9's index-refusal test profile omitted the project fixture's required
modules. Both stopped at tests before linking, without OOM. The corrected v10
campaign and host startup campaign completed, and all containers were removed.
Combined private receipt SHA256:
`88eb3f5cad38039b05034976d4f97bcbdba8ef1d48ac2cecc7d4f36bc9a51568`,
local `build/native-external-arenas-16-20261012/startup-v1-evidence.json`.

Runtime startup, parser call-chain stack margin, complete syntax/dependency
admission and real playback remain unverified. No device operation occurred;
these are private probes, not installable release packages. Existing layout
guards remain intact; expanded-layout authorization is pending.


## Startup stack exploration [verified ELF inventory; inferred estimate]

Sixteen Hera containers inspected the v10 ELF function extents, avoiding internal
jump-table labels that split printed function bodies. Source-scoped callback
mappings cover the loader's fixed sink/reader and binary codec callbacks. The
inventory reaches 99 functions, with no unresolved direct/indirect call sites
or call-graph cycles under those mappings. Direct external goto targets are
included. All sixteen estimates are 9,924 bytes below `load_set`; startup-enabled
profiles add the 3,060-byte `fm1_cstart` frame and 76-byte activation frame,
yielding 13,060 bytes versus the 24,320-byte user-stack reservation.

This is an exploratory estimate, not a certified bound: it sums negative SP
adjustments and register saves, assumes four-byte saved registers, and does not
prove control-flow stack balance, absence of repeated stack allocation on a
cycle, callback argument provenance in the machine code, the device ABI or
interrupt-stack isolation/margin. Full startup, other startup/render paths,
stack guards and real-device high-water measurements remain separate work.
There were no simple dynamic SP assignments in the inventoried loader functions.
No hardware admission flag was changed.

Private receipt SHA256:
`bf3d020263a2620cbe6ab73841e883da0a03c428009b004cfb2cc0a929fc053b`;
local `build/native-external-arenas-16-20261012/startup-stack-v1-verification.json`.
Exploratory script is retained beside it and on Hera. All containers exited
successfully without OOM and were removed. Expanded-layout approval is pending.

## Malformed numeric diagnostics continuation

[verified] Added `FM1_SEQ_IMPORT_SYNTAX` without changing compatibility-import
output or return semantics. It observes failed `word_u` conversions, failed CP
transpose/quantize conversions, invalid list fields, extra note fields and
incomplete note/lock/trigger rows. Native checked admission rejects this flag
before live activation. This remains partial admission: scalar fields parsed
outside `word_u`, missing/extra line words, normalization and module/parameter
bindings still need explicit checking. Standalone sets identify routing and
labels rather than a complete engine/effect configuration.

[verified] Sixty-four Os/Oz packed-set ASan/UBSan cases passed across sixteen
Hera containers (32 cases including sixteen new malformed examples). Existing
compatibility suites passed 466 cases with two pre-existing expected failures,
468 collected nodes in sixteen chunks. No OOM; owned containers removed. The
first compatibility attempt failed during read-only-mount rebuild setup; logs
are retained, tools rebuilt on Hera, then v2 ran successfully. Native link v11
correctly refused a stale catalogue after the header change; all source
catalogue v5 shards rebuilt successfully before native link v12 was started.
Private receipts live under `build/native-external-arenas-16-20261012/`.
No device write or execution, new stack proof or release readiness is claimed.

[verified] Native v12: all sixteen links passed after catalogue v5 rebuild,
with 77 audit/artifact/option checks each and byte-exact linked content.
Combined private receipt SHA `d055dfe0b84878f977c12809947dfdfb877175b7d5bf4d2c1280dc0b43a234b0`. All owned containers removed.
Previously inferred stack estimates describe older ELFs, not these new links.

## Scalar and line-arity diagnostics continuation

[verified] Import diagnostics now observe malformed bpm/swing/link/sg/tk/dq/se
scalar conversions and missing/excess words in supported fixed-arity records.
Legacy handling and return semantics are unchanged; native checked admission
refuses the syntax flag before activation. This still does not prove complete
syntax, normalization, module/parameter binding or playback admission.

[verified] Hera set-syntax-v2 passed 96 Os/Oz packed-set ASan/UBSan cases
in sixteen containers. Compatibility v3 collected 468 nodes: 466 passed,
two pre-existing expected failures, no errors or unexpected failures. Fresh
catalogue v6 and all sixteen native v13 links passed, each with 77
audit/artifact/option checks. No OOM; owned containers removed. Private
combined receipt SHA `9f025258ab11921b402c8ce2106c7f408dc68d66db2c158003db09f8ab2c74d7` in
`build/native-external-arenas-16-20261012/syntax-v2-evidence.json`.
The earlier stack estimate describes v10 ELFs; it is not a bound for v13.
No hardware action or release acceptance. Expanded-layout approval is pending.
