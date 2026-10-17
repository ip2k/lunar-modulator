# Tuple-bound libc++ source inclusion

[verified: source and focused host tests] The source bundler can optionally
include the pristine LLVM libc++ headers used by the native catalogue. The
operator supplies the retained catalogue root, its raw tree manifest, pristine
headers and official component notice together. A partial set is rejected.
The digest used to validate the catalogue is taken from the already validated,
tuple-bound build provenance, rather than accepted as another CLI trust anchor.

The new validator recomputes the captured canonical tree manifest, checks all
16 shard header copies for equal paths, bytes and modes, and reverses only
`compile_catalogue.py`'s single documented `__config` line replacement. It
requires the actual fixed pristine source pin (189 files, path/mode/content
SHA256), byte correspondence to those compiler inputs, and the fixed LLVM
12.0.0 component notice digest. Input files and traversal have explicit bounds;
header symlinks and nonregular files are rejected. The archive records external
source rows and component provenance separately from the project root license.

[reported: prior pinned SDK/header audit, retained private handoff] Source is
SDK commit e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d, subtree Git tree
43eed217352338ad4de6a824fc835befd2e60b18. Header manifest pin:
2e92acfe3d2c9cac278fa0ba30f0e9ecf542df52056a0984af6e33bc17a2a4ce.
Official LLVM llvmorg-12.0.0 libcxx/LICENSE.TXT pin:
539dd7aed86e8a4f12cbdd0e6c50c189c7d74847e4fecc64ce2c6ee3a01da38b.
The subsequent retained-artifact inclusion run is recorded below; focused
synthetic tests alone do not establish that result or a broader license audit.

[verified: host tests] Combined bundle/validator suites passed 39 cases with the
existing local fm1-state codec. Tests cover partial input rejection, forwarding
the provenance-bound digest, deterministic archive entries and false release
flags, as well as captured-tree mutation, missing shards, duplicated adaptation,
changed pristine inputs, wrong notice, symlink and nonregular input refusals.

A subsequent real extracted-archive preparation attempt found another source
closure gap: the recompressor imports tools/lunar_state.py, which imports
canonical layout code in tests/state_canon.py. The selector now retains those
two exact files and tests/__init__.py. An isolated Python -I subprocess imports
all three exclusively from exported files, without the original checkout or
user site packages. Unrelated tools and tests remain excluded.

This does not assert a completely reproducible environment, complete
corresponding source, distribution eligibility, hardware acceptance or
installability. Both completeness/distribution flags remain false. Device
recovery, realtime playback, persistent storage and public release gates are
unchanged. See HANDOFF for current artifact/worker state.

Independent static review found one status-text inconsistency: an archive without
prepared song snapshots still claimed to include them. The text now names only
the source classes actually included; prepared-only and header-only regression
assertions cover that distinction.

## Real Aeon checks

[verified: worker run and coordinator output rehash] The corrected source archive
is e104fbf44ec0d676067eb872c477e5da0b77f85bd8833c09c25999484318512e,
with 1026 regular unique members and 1021 committed-source rows, built using
7e614b20 bundler against the original clean352 source and original tuple53f682c0.
Actual extracted-source high-level build_demo_image completed under the pinned
bcff container with all55 modules. The prepared profile and packed project/SET
hashes match the original producer exactly:

- profile: 1723ae73ad99d3120d6b4b1c405c388b7c14c56f03481d8727d08b7213f7ff60
- packed project: b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163
- packed SET: 7c850fcf8fda9ea513c8d1f14a414f638c8c1cc931156f7b000c757e7cfd0625
- app: 888ef842ea67fb46a010226456568452bc32b3ceca13362caaab7119774db437
- ELF: fed2d7e47ff1120a4d5c15acdb57f21cfe6144e71dd6bf689408943dbd0e6c3b

Unlike the earlier direct-link check, this high-level ELF matches the original
producer too. The initial pass used the original same-source state codec.
[verified: worker follow-up and coordinator output rehash] Rebuilding the codec from extracted source produced
the same codec hash6b551c1798cc6f2d90c20fd55e881ff7aeae6ed1d46fb90415de0ac170697511
and preparation reproduced profile, selection, raw inputs and packed bytes.
A trailing summary print queried an absent return key and exited1 after successful
preparation; the worker independently checked the saved files afterward. Preserve
that distinction rather than reporting that shell command as exit0.

[verified: worker retained-input run and coordinator archive rehash] Two header-inclusive archives are identical:
4288773 bytes, SHA52914fc9f7f56aadce410cb1a27c8ee334eaa213fc9548a905d00f3e3e5e8895.
The raw retained catalogue manifest matches the tuple-bound provenance digest;
all189 pristine headers and the official fixed notice passed actual byte checks.
There are190 external rows. No catalogue rebuild was used to recreate provenance.
Completeness/distribution and all hardware/admission flags remain false.
These runs used Aeon only. They do not verify real-time audio or physical recovery.

Durable Aeon reports (private host paths):
`handoffs/lunar--source-closure-prepare-20261017.md` SHA256
99f6add31ffbf456f89868d4e15278b5b8a97274aa0b07b1d369d2d5cea32f0a;
`handoffs/lunar--aeon-libcxx-source-bundle-20261017.md` SHA256
0be225adcfc2a521ba1d7a200b03c4a42b2701774f4fc1608ab85eeb649162b5.
Both workers released their claims after saving the reports. No owned build
containers remain. The coordinator reviewed both reports and independently
rehashed the reported app/ELF, profile, packed bytes, rebuilt codec and archives.

## Fresh catalogue from the header-inclusive archive

[verified: worker run, coordinator report review and output rehash] The archive
52914fc9 was safely extracted and all committed/selected/external rows checked.
All16 fresh catalogue shards exited0 under four parallel bounded Aeon containers,
using only extracted source, archived libc++ headers and the pinned compiler.
All167 object hashes and549 source rows matched their reports. Options were
-Oz, LTO, indexed TFT, Shapes8 and shared resampler, matching the original.
No retained catalogue or external libc++/SDK header tree was mounted.

The codec rebuilt from this extract again hashes6b551c17. Actual high-level
continuous all55/Event Horizon/SET/D7000 build with the fresh catalogue passed
SDK-free and layout audits. App888ef842, ELFfed2d7e4, profile1723ae73 and packed
projectb6ca5a03/SET7c850fcf match the complete hashes recorded above. Coordinator
independently rehashed all six outputs. App852720 bytes, D7000 slack7924.

The separate pinned compiler mount remains an external dependency, including
its implicit target C/sysroot and resource headers. This check proves archived
libc++ source use, not independence from compiler-provided headers or complete
corresponding source. It is not a fresh trusted tuple or a physical result.
SAVE remains linked/disarmed; all installability/hardware/playback/completeness/
distribution gates stay false. No Hera or device operations occurred.

Private Aeon output root:
`/home/claude/mvave-fm1/private-header-inclusive-full-build-20261017/`.
Shared handoff `handoffs/lunar--header-inclusive-full-build-20261017.md`, SHA256
19337868e1cdf12ca6b594a7f1a570c3bc95d302c23584d8041dbdd14f94ea57.
All containers are terminal and the task claim was released.

[verified: coordinator reviewed retained-input inventory] The captured link
lists281 direct objects:161 catalogue,66 musl,31 compiler-rt,20first-party/generated,
and one each printf/tinf/tlsf. Thus167 freshly built catalogue objects should
not be described as167 linked catalogue objects. The link has zero SDKarchives;
repo-built runtime/startup/linker sources are archived. The remaining header
search roots outside this archive are pi32v2/include (107files/498895bytes) and
Clang4.0.1 resource include (93files/6237896bytes). Their hashes are pinned in
the retained695-row toolchain manifest1484c315, but per-TU dependency receipts
were not retained. A dependency-only pass is assigned to identify the consumed
subset with exact target/defines/include flags. Compiler/linker/LTO/container
are build tools; their presence alone is not evidence of linked runtime code.
No completeness or legal conclusion follows from this inventory.

## Historical dependency evidence boundary

[verified: retained-receipt audit and coordinator report review] The original
capture did not save per-TU compiler argv or dependency receipts for catalogue
and ordinary app objects. Common musl flags and66result rows, and state-bin
compile flags, survive; they do not fill the other historical rows. The six
built-but-unlinked catalogue objects are explicitly identified in private
handoff lunar--aeon-translation-header-deps-20261017.md SHA256
19cfcf34e80ce52ba12d4fc0155308e19db07177de041417f4e78c48d0829248.
The earlier external-input inventory appSHA typo was corrected; report digest is
ece8911a0f8d4bb986968b7a51483a7069e0b11bc4d571724e8de9fe3e3168ca.

Do not reconstruct recipe flags and label them historical consumed dependencies.
The next private smoke instead traces the fresh reproducible build: run original
compile argv unchanged, then a separate system-inclusive -M preprocessing pass.
An immutable pinned compiler and read-only extracted source sit behind a private
facade; compare direct/facade object hashes before attempting full trace. Record
cwd, argv, source/compiler/object identity and bounded hashed dependency rows.
This is a design/assigned experiment, not a completed trace. Component header
provenance is separately under bounded read-only review. All releaseflagsfalse.

A design worker initially attempted to save its handoff to obsolete Hera .48;
SSH returned no route before any connection/change. It corrected to Aeon .25,
saved handoff lunar--compile-trace-design-20261017.md SHA256
b64d4b48f36c7b51a7ca2d3f97cfa80b16cf9f923d47d53d364112360c39d9c5,
and released only its own Aeon claim. Do not repeat the excluded-host probe.

## Bounded compiler-header source comparisons

[reported: worker primary-source comparison; coordinator reviewed report]
Both full compiler-header roots match their retained manifest rows (107target,
93resource). Representative official source checks identify Newlib tag
newlib-2_2_0 commit7e72fffc61b29325ac5a875c5318cdf2f294ae28 and LLVM tag
llvmorg-4.0.1 commit449c3ef93afc7a668eb35e67a83717453e28b25a.
The vendor Clang resource stddef.h and stdint.h exactly match tagged originals.
Vendor target stdint.h differs from Newlib2.2.0; vendor newlib.h is configured/
generated and differs from newlib.hin. Do not describe either as unchanged
release source. Four samples establish no claim for the unsampled headers.

Primary references: [Newlib source](https://sourceware.org/git/newlib-cygwin.git)
and [LLVM tagged source](https://github.com/llvm/llvm-project/tree/llvmorg-4.0.1).
Newlib COPYING.NEWLIB/COPYING and LLVM clang/LICENSE.TXT/llvm/LICENSE.TXT were
retained with hashes in the private comparison report. The vendor bundle has no
root umbrella notices; representative headers have component-specific notices.
This is provenance evidence, not a distribution/legal/source-completeness claim.
Use the new consumed-header trace before extending exact-source comparisons.

## Aeon one-translation-unit trace smoke

[verified: coordinator inspected prototype and saved smoke result] The private
compiler facade preserved the original compile arguments for
`virtual_analog_engine.cc`. Direct and facade compiler/version/include-search
probes matched, and both object hashes were
`a6675e6c21ed13213156f976c3b06bdd30868a0a07337ef848e537fbe327c1e9`.
The separate system-inclusive dependency pass recorded 77 hashed prerequisites:
13 source, 40 configured libc++ and 24 pinned-toolchain files. This is new
single-file evidence, not historical receipts or whole-build coverage.

Private handoff `lunar--compilertrace-smoke-20261017.md` has SHA256
`536cdebae5d60161f220c9e46c3d25908f30a413a2be9208428dce1c729ce34a`.
Its artifact paths, input pins and constrained container settings are retained
there. No hardware action or Hera connection occurred.

Coordinator review identified that the prototype's single trace.json/temporary
filename would lose records under concurrent compilation. A new bounded Aeon
experiment is assigned to use unique atomic per-invocation records, verify
missing/duplicate object coverage and compare 2–4 concurrent compile outputs
with direct baselines. Full tracing remains gated on that result. All release
and source-completeness flags remain false.

## Concurrent tracing and consumed-header follow-up

[verified: coordinator read fresh concurrent-summary.json and recorder] Three
concurrent original Make compile recipes (two C++, one C) produced direct/facade
object hash equality. Six unique complete records cover three compiler probes
and three compiles; the aggregator's missing/duplicate check passed. A separate
64-writer synthetic check preserves every record and rejects publication of a
duplicate ID. The prototype now publishes unique complete records atomically
and forwards probe stdout/stderr. Earlier bounded attempts failed before
compilation on probe passthrough/recipe matching, or rejected stale probe
records; their output is separate from the clean run.

Clean summary: Aeon private
`source-libcxx-archive-check-20261017/scratch/compiletrace-concurrency-smoke-20261017/out/concurrent-summary.json`.
Dependency-manifest SHA256:
`aba2d9504dbcc3e40944ccc28d89ca7ab3b96c503c21def329994df5fd2ec382`.
This is three-TU evidence only. A full fresh traced catalogue/application
reproduction is now authorized after the worker's final negative-mode check;
unknown compiler modes or uncovered host/link steps must stop/report rather
than silently bypass tracing. No full trace result is claimed here.

[reported: worker comparison; coordinator read report] All 24 pinned-toolchain
headers consumed by the earlier one-TU trace match their recorded vendor
hashes/sizes. Nine match the pinned official tagged sources; thirteen differ
from same-path Newlib candidates, one is generated newlib.h compared to its
template, and sys/_stdint.h has no same-path file in that tagged include tree.
A different hash does not establish the reason or original source revision.
The report and retained component notices are provenance pointers, not a legal
or source-completeness determination. Shared handoff
`lunar--consumed-compiler-headers-20261017.md` SHA256
`c3e38ba1021a582441c67ec0249efd48e6100625be3e5779e5569a56cad371f9`;
private comparison manifest SHA256
`15875b688e45ba66847d6d12fefc8fe6e3a2215ee1fbc11f133638fc8ac062f6`.
All distribution, admission and source-completeness flags remain false.

## Linker-recorder prerequisite

[verified: coordinator independent hash check] The retained link input manifest
`linker-smoke-inputs.json` SHA256
`fb7b5942115bb4b0711a1b951f65daee2f390cacd5ba37c7a0c57d93371f92fa`
contains 281 distinct object paths, totalling 3,438,920 bytes (161 catalogue and
120 application/runtime objects). Every object hash/size matches. Linker, LTO
plugin, generated script and retained ELF also match their recorded hashes.
The generated script has no INCLUDE, INPUT, GROUP, SEARCH_DIR or STARTUP
directives after comment stripping. The smoke command is reconstructed from
the archived recipe and retained configuration, not original historical argv.

A private linker recorder is reviewed and its 11 synthetic tests independently
pass. It pins immutable ld/plugin/script, restricts argv/input/output roots,
uses bounded no-follow regular-file hashing and unique atomic receipts, and
records rejected preflight invocations when a trusted receipt directory exists.
Missing receipt environment variables fail; FIFO reads do not block. Child
stdout/stderr and exit status are preserved; nonzero exit or missing outputs
keeps trace_complete false. Prototype SHA256
`cf46e915844254bbfa6e7aae910be2bb5aa5092c98d43ff9e0d596d7cc8c4ebe`;
private local handoff SHA256
`b0e230cf12ad9f41173245dd1d0ed07cd6a12dbf20b34a0bf3b63696b2b509af`.
This is an ignored experimental recorder, not released infrastructure. Real
direct/facade link comparison is separately required before full tracing.

[verified: coordinator read final receipt and container inspections] The direct
and facade linker smoke both exited0. Facade receipt SHA256
`ccd82ae94ad0e22dfaea9aaefb24efdec4c069b0f00752bca03f505c6f7e8dd9`
contains349argv entries and284hashed inputs (281objects plus ld/plugin/script).
Its trace_complete is true; the987308-byte ELF SHA256 is
`fed2d7e47ff1120a4d5c15acdb57f21cfe6144e71dd6bf689408943dbd0e6c3b`,
matching the retained ELF. The407529-byte map SHA256 is
`7cbc06bfb8c7867df6aa645b435a8d8e54e2fa9c4dde7f72af7af9b4088f3b8d`.
Both inspected containers used docker-batch.slice,2CPU,3GiB memory/6GiB total
memory+swap,512pids,networknone,CapDropALL and no-new-privileges. They are
terminal and removed after inspection. Initial runner mount/argument errors
were pre-execution setup failures, not passing facade evidence.

Full fresh target compile/link tracing is now authorized on Aeon with both
reviewed facades and a new output tree. The previously rebuilt pinned host
state codec may be reused with that limitation explicit; it does not become
new host-compiler dependency coverage. No full trace result is yet claimed.
Shared linker-smoke handoff SHA256
`449d854152ce70906b06e2ab0eb1142255f0f24fc9efcb377acb014d6e0a0cf6`.

## Additional target invocation modes and real sizing comparison

[verified] Static command inventory found two additional families beyond ordinary
`-c` compilation and the final LTO link: two `-S -emit-llvm` C99 sizing commands,
and `tools/native/Makefile`'s 32-object arithmetic validation `ld -r` link. Both
clang paths resolve to the pinned common compiler; recording only the common
path without preserving the target alias would leave a coverage gap.

[verified] Private IR adapter SHA256
`e51cf6b1f7b0460152d8d1eb1d66e1d5b96176fafff45cb2df93ca57a980a418`
preserves original compiler arguments and removes both IR-mode flags only for
the separate dependency pass. Root reran its synthetic suite. The first real
fixture failed before the facade because a host-absolute include symlink did
not resolve inside the container. Its logs were preserved; it is not passing
evidence. A fresh corrected-mount run exited0 on Aeon:
`57c28fa0d16352bdd16c5627f436a21422d29864b1ad074af990ea09dec69209`.
Root independently compared actual direct/facade IR bytes, receipt status,
source and output hashes:

| Display index | App size | IR SHA256 | Receipt SHA256 |
| --- | ---: | --- | --- |
| 0 | 220848 | `86a609093b18315c9882510dba6b5be5f40a93733942331b30d57952d2f43b7f` | `1733b6486c1d8f5dc3bd5f9774f264975277d2fbad30cc51b631ab6fd21c1e66` |
| 1 | 163760 | `3f737a413a5f6a5c61ecf3addb590ce0919a0e0d054ea84da3bceec7ee6716df` | `d44fad3eaec766f6ec857bd606813f396144cc6d0593ffe9234b1c25d8c94e5d` |

Both receipts contain40 dependencies and successful compiler/dependency exits.
The sizes match retained constants; fresh IR hashes differ from historical IR
because its ModuleID includes the fresh source path. This proves current
fixture equivalence, not historical argv. Evidence root:
`/home/claude/mvave-fm1/private-compilertrace-full-build-20261017/ir-smoke-retry1/`;
summary SHA256 `e14e75f4106d60d6f1ef5a49281a18b24f179bf26dd4fc1ff1839919e4c08576`.

[verified] Separate private relocatable-link recorder SHA256
`422718061b59711603d1a8224f217baa79c07a574ee2b05c0fb6fc4326cefa49`
passed17 independently rerun tests, preserving the11 final-link tests. Its
real arithmetic comparison is assigned but not yet accepted at this checkpoint.
Full traced build and source/distribution/hardware acceptance remain open.

[verified] Arithmetic comparison subsequently passed: container479e34a1b87a
exited0 without OOM. Root read its receipt/inspect and independently rehashed
both generated objects:15636bytes, SHA256
`4f427eac4be57d92992f9d69c36bf382da577f330c335ed8b17cc4400eaca61b`,
matching retained output. Receipt has33 inputs (pinned linker plus32objects),
return0 and trace_complete=true. Summary SHA256
`310f4e72285384284dd3920b05bff3892896d4001bd9737697204e3928639226`;
receipt SHA256
`a82d32b89bd7cb25fff44a26a476138cbf84d8e9aa69da8238eb52a5d077d10b`.
Evidence root is the sibling `arithmetic-smoke-20261017/` under the private
full-build directory above. The initial Docker-create syntax error did not
create a container and is separately logged.

The complete fresh target compile/link trace is cleared on Aeon,16shards with
at most4concurrent containers. It has not completed at this checkpoint. The
host codec is explicitly reused and is outside new host-compile coverage.
CI run38998982780 completed SUCCESS across all15jobs; this is implementation
CI, not physical or public-release acceptance.


## Fresh full target trace on Aeon

[verified] Owner routing excludes Hera during RAID/M.2/NIC maintenance. All16
catalogue shards completed on Aeon, at most4 concurrent bounded containers.
Actual totals are167 distinct objects and167 successful compiler receipts:
shards00–06 each11, shards07–15 each10. Root independently rehashed all167
objects against their receipts and checked the pinned compiler identity.
Catalogue aggregate SHA256:
`dcbdc81ff921257451db7d5a865c2fb4f25611a6751ca5b1ed5e9d42b45a9dce`.

[verified] Highlevel retry2 container
`d0c426f1d09cb9d28a8a343336e66b84a41b9bd78d9de626cff016f296b6645f`
exited0 without OOM. Its852720-byte application SHA256 is
`888ef842ea67fb46a010226456568452bc32b3ceca13362caaab7119774db437`;
987308-byte ELF SHA256 is
`fed2d7e47ff1120a4d5c15acdb57f21cfe6144e71dd6bf689408943dbd0e6c3b`.
Both equal the retained continuous producer. Root independently rehashed all121
application/runtime compiler outputs, both storage-IR outputs, both linker
outputs and all output-mount linker inputs. Final link records284 inputs;
arithmetic relocatable link records33. Compiler and dependency exits are0 and
receipts report trace_complete=true. This is new invocation evidence for a
fresh reproduction, not a recovered historical invocation trace.

The initial highlevel attempt stopped at the recorder's missing real receipt
directory guard; no parser was loosened. Retry1 produced identical firmware
but its ELF string table contained a different absolute crt0.o path. Retry2
used the original `/output/build` path and reproduced the ELF exactly. Failed
and intermediate attempts remain private evidence. A root audit initially read
the object hash field for storage-IR receipts; selecting their `ir_sha256` field
confirmed both actual files match. No output mutation was found.

Evidence root:
`/home/claude/mvave-fm1/private-compilertrace-full-build-20261017/full-trace-run2/`.
Canonical outputs are `build/link/artifact/app.bin` and
`build/link/lunar-app-probe.elf`; receipts are under
`trace/highlevel-retry2/records` and `trace/highlevel-retry2-ldrecords`.
Final consumed-header union/provenance review is still pending. The reused
host state codec remains outside new host-compiler dependency coverage.
No source-complete, distribution, installable-release or physical acceptance
flag is promoted by this result.


[verified: coordinator aggregate read/hash plus independent receipt checks]
Final aggregate SHA256:
`3e2d622ce8ff42274d04650bd076844ad78da32d86210b67f760e29f17251882`,
with empty errors. All281 final-link objects match fresh compile receipts;
288objects were compiled in total,7not linked. The36consumed toolchain-header
identities were independently reconstructed by the provenance worker and match
the aggregate exactly. All24prior identities remain unchanged. Of12new headers,
6match tagged Clang/Newlib sources and6differ from same-path Newlib candidates.
Overall classification is15exact,19same-path differences,1generated header and
1without a direct path in the selected tag. This is bounded comparison evidence,
not proof of all edit history or complete distribution clearance.

Delta manifest SHA256:
`24e73c191cc8497c3d3fc86beaaba12ce20848881f16a452cd6b5bb8d60789ff`;
shared handoff `lunar--compiler-header-full-build-delta-20261017.md` SHA256
`f538d7c54399a7b9f8e78db9a98dc011f2aa7d998a778d10d865942494da04a3`.
Official Newlib/Clang/LLVM notices are retained privately. Modified/generated
header provenance gaps and host/compiler environment limits remain recorded.
