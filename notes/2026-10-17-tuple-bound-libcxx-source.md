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
