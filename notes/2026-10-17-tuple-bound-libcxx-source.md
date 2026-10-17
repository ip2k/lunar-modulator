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
The implementation still needs a real retained-artifact inclusion run; focused
synthetic tests are not a substitute for that check or a broader license audit.

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
