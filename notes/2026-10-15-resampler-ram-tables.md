# Shared resampler coefficient placement trial

The physical ROM97 comparison still misses the audio deadline: 446.075 blocks/s
against 689.344 required. See the separate Fabs results note for measurement
limits. Moving the ready-pop FIR code alone does not move its coefficient data.

The hot-DSP ELF profile now places the single shared coefficient definitions in
`.ram_dsp.tables`; the existing linker wildcard collects that into the startup-
copied `.ram_dsp` region. Default and header-only builds retain their placement.
No coefficient, sample-rate requirement, filter arithmetic or alias-rejection
requirement changes. The two tables contain 769 + 62 floats (3,324 bytes).

[verified] Eleven focused host checks passed, including cross-compiled ELF32
objects whose two table symbols have the expected read-only section, sizes and
identical coefficient bytes between default and hot profiles. The resampler
ready-path equivalence and native limiter equivalence checks also passed.
An independent source review plus placement/catalogue/candidate-verifier suites
passed 56 checks (private review: `scratch/ram-table-source-review.md`).

[inferred] Keeping the coefficient loads in RAM may reduce flash contention.
This is not a measured performance improvement. A fresh pi32v2 target build
must verify final section addresses, startup/load bytes, RAM guard fit and
coefficient identity before a separately reviewed physical comparison.
The frozen exact162 comparison does not contain this change.
