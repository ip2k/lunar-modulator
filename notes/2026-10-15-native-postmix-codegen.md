# Native postmix code generation

[verified: frozen target inspection] The d8586ae8 ELF contains a signed division
in each sample loop of `fm1_postmix_scope_and_gain`, plus three external
`fabsf` calls per sample. ELF SHA256
103e51f0e607f1b5ca4c8c978d2d905326f1772204666f16db95979691f226ad;
disassembly SHA256
a556236d799453cdbd866a84cb7f7bfb623249617675f86d28e3b10d95a4b685.

[verified: source/host] Replaced scope modulo with increment-and-wrap for the
existing valid-index, nonzero-size contract. Each input magnitude is calculated
once, retaining comparison/selection order. This preserves arbitrary supported
scope sizes and introduces no approximation. The independent previous two-pass
reference checks samples, the complete scope array, position and peak bitwise.
It covers sizes 1, 2, 3, 17 and 512, every valid starting index, multiple wraps,
unity/nonunity gain and IEEE edge samples: 58,608 cases at each of O0 and O2.
The worker also ran the harness with ASan/UBSan successfully.

No new target build, removed target divide, cycle reduction or hardware audio
improvement is established by these host checks. The running ROM83 campaign
uses immutable d8586ae8 artifacts and does not contain these source changes.
Private review and handoff: `scratch/native-hot-dsp-ram/`.
