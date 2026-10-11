# Fixed offline loader configuration profile

The offline preparation tool `tools/jieli/loader_config_profile.py` proposes a
fixed patch to the privately retained WL82 LoaderV2. It opens no device and
changes neither the old backup Reader nor the unused-sector physical writer
allowlist [verified: source inspection]. Physical activation remains outside
this tool. Vendor binaries and native listings remain ignored/private.

The original encrypted 24,064-byte loader SHA256 is
`d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376`;
its independent decoded pin is
`db8676b9cca4e2c0dfee062715cdb41528a2a8ccc827520ba8c194e4a2e0356e`
[verified: local private original file and existing native-review evidence].
The original initializer can parse retained configuration beyond its upload;
invalid CRC alone does not prevent parsing, and quad mode can issue NOR
status writes [verified: `notes/2026-10-11-loader-run-app-reset.md`].

The proposal changes three fixed spans, totalling 16 bytes [verified: byte
comparison]. The selector entry at `0x01C02084` returns `0x01C07C40`; the two
four-byte selected-block decode calls at `0x01C02666` and `0x01C02676` become
NOPs. The proposed zero-data extent `[0x01C07C40,0x01C07C80)` is inside the
existing loader upload, after the sole driver table ends at `0x01C07C34`.
It contains 64 zero bytes in the pinned decoded image [verified: file read].
Independent patched native review established a valid leaf return, NOPs and
zero padding unchanged on the traced initialization/read path [verified:
`build/loader-config-native-review.md`]. This is not a global RAM protection
claim.

The intended direct-call consequence is precise: all three traced selector
callers receive the image-owned zero pointer; the field parser reads its
first record length at pointer+34, exits with field absence, and the unchanged
SPI setup takes its default mode 2 path [verified: independent patched
native review, `build/loader-config-native-review.md`]. The original mode-2 branch bypasses the identified
quad-status write paths [verified: existing original-loader review]. This
proposal makes no claim about untraced indirect calls or external initializer
side effects. In particular, the external call at `0x01E00428` and ROM-supplied
operations still require separate evidence for any stronger safety assertion.

No generic RAM write is introduced. No upload is added to the retained
configuration windows `[0x01C07E00,0x01C08200)` or
`[0x01C08E00,0x01C09200)` [verified: emitted inventory]. Merely uploading zeros
there was not accepted as proof: the initializer's hardware CRC-driven cipher
would subsequently transform them, and its complete state semantics were not
established. The chosen proposal relies on zero data already included in the
47 decoded loader blocks and skips both later transformations.

The tool rejects original size/hash mismatches before decoding, checks the
independent decoded hash, checks every original instruction premise and the
zero extent, preserves bytes outside the three exact patch spans, and verifies
a per-512-block cipher round trip [verified: source and local emission]. The
private profile records all 47 fixed FB06 requests by address, length, CDB hash
and payload hash. The extent remains `[0x01C02000,0x01C07E00)`; it introduces no
jump, flash command or transport. Any physical adapter must independently bind
this new exact encrypted hash and the complete reviewed command sequence.

Local emission produced [verified: freshly calculated private artifacts]:

| Artifact | SHA256 |
| --- | --- |
| Patched encrypted loader | `fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c` |
| Patched decoded loader | `a228c6fa2dd733802723099dab8216edbfbdfcef1dc155ffcd8ac2b96fd480af` |

The profile always reports `hardware_ready=false`; generating it is not
permission to run a loader or proof that execution cannot affect flash.
It retains explicit false fields for independent patched-listing review,
external initializer effects, ROM runtime cipher proof and physical execution.
The independent review's result belongs in its separate source-backed report;
no code flips these flags based on file generation.

Tests in `tests/test_loader_config_profile.py` exercise pin rejection before
decode, independent decoded pin rejection, changed instruction and padding
premises, preservation outside the exact spans, the full 47-request inventory,
private file modes and refusal to overwrite. An explicitly supplied private
loader enables a regression against both actual candidate hashes. These are
software checks, not hardware acceptance. Root owns focused test execution on
Hera and integration/commit/push; this author did not run pytest or hardware
traffic. The independent review generated the actual vendor disassembly on Hera and
found no bounded offline patch defect. Its native-listing SHA256 is
`f8aeedf382158f17627ce119b01e451ab5611b6cafed485dca385a226334776e`.
External initializer effects and physical execution remain unverified.

Root focused Hera verification: 156 checks across 16 containers passed, including
the actual private-loader regression. Exact source/archive/plan/image pins and
limits are recorded in `2026-10-11-diagnostic-directory-last.md`.
