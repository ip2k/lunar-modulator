# Exact FM-1_092 disassembly review

[verified: input identity, offline tooling and retained output] The exact public
092 app (691,744 bytes, SHA-256
`9c5a44706b7686746b389e3e8fe6ff051fc50028f9b708ac59f493300f793a7b`)
was wrapped with `.incbin` and disassembled on Aeon with the pinned JieLi
r3 decoder. Worker reports complete `.text` extraction equals the input;
coordinator independently checked the retained section report (size `0xA8E20`,
VMA `0x02000000`), listing hash and candidate instruction below. This is a
linear code/data sweep, not a recovered function graph.

[reported: existing V15 SPL analysis; inferred applicability from matching
protected SPL] Raw-app origin `0x02000000` is supported by the retained V15
boot analysis. Package entry metadata `0x02000120` is a separate field; the
unpacker records that field and writes the raw app member independently.
Exact092 SPL execution was not observed here. The earlier wrapper placing
raw byte zero at `0x02000120` is superseded and must not supply call addresses.
No byte was omitted from the corrected complete payload; the draft problem
was an address shift, not missing input bytes.

The corrected listing is ignored scratch:
`scratch/fm1-092-objdump-20261017/FM-1_092-app-origin-02000000-linear-sweep.txt`,
SHA-256 `f62050c81be2ff7e1f5645873bc47ca07c52c7a95b9e7752b5792a5a181767d8`.
Detailed method, source/tool hashes, commands and limitations are in the
sibling `README.md` (reviewed SHA-256
`d9d58ad23c396dcd38638ad0a135e5812136b81533d69f89e343fee8716b3918`)
and `AEON-HANDOFF.md` (SHA-256
`50a0b816b066c180b40410703388169cbc408dacda487ee28b2e7195d1ca31df`).
The wrapper SHA-256 is
`88483cfa2d276d22bb0e5a9ae8771cda41b49fc330a21ccf8f1acf0a8fc2f64c`.
No vendor binary or full disassembly is committed.

[verified: narrow literal/data reference only] The decoder shows an immediate
address at `0x0202CBE4` referring to the bytes labelled `usr_audio_task` at
`0x0204E6D8`. Surrounding indexed reads establish a data use only. Other
VM/USR-like literals are locators; neither their presence nor missing raw
absolute pointers establishes a storage reader or allocator. This review
provides no semantic migration, ownership, erase-safe, SAVE, physical recovery
or performance acceptance. A follow-up searches meaningful path suffix starts
and decoded operands before attempting bounded call/data-flow analysis.

The worker used one serial, constrained Aeon container (1 CPU, 1 GiB with
memory=swap, network disabled, read-only source/toolchain, docker-batch.slice),
saved the coordination handoff and released its claim. Hera and hardware were
not used. The next trace is local read-only work on the public payload/listing.
