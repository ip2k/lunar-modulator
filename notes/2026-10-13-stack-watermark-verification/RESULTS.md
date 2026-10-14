# Opt-in native stack watermark verification

[verified] The opt-in `--stack-watermark` paints only the reviewed user and
system stack spans before C startup. A separate assembly section preserves
the fixed application entry and rejection addresses. The scanner reads only
those spans once after startup and once per second, retaining minimum observed
pattern margins and sample count in diagnostic globals.

[verified] All 32 host tests passed across 30 Hera containers using ASAN/UBSAN.
Campaign receipts record terminal zero exits, no OOM, source and log hashes.
The final thirteen-engine FIRST ORBIT target linked with a 216064-byte instance
pool and passed strict artifact, SDK-free and eFuse checks. ELF SHA256:
`db10552381786339a40cffaec23a562c17842542cf78b6d1c6651f46192cfba1`.
The target verifier checks exact painter and stack-setup bytes and both call
targets against the ELF. Negative tests reject every changed painter byte,
a changed C target and mismatched call bytes. Existing artifact/catalogue
regressions also completed successfully; see artifact-regression.json.

[verified] Earlier target attempts failed on conflicting linker declarations
and then shortened entry-call encoding. Those failures were corrected by using
the HAL declarations and placing the painter in a separate section. No guard
was weakened; failed build evidence remains on Hera.

No physical device command was issued. Diagnostic globals currently have no
external readout. Pattern margins are observed measurements, not worst-case
stack bounds; untouched reservations and pattern collisions can hide usage.
Full startup/IRQ nesting/timing, physical all13 acceptance, settings migration
and rollback, web builder/install, GPL transition and review/CI remain open.

Hera evidence root: /home/claude/mvave-fm1/native-external-arenas-16-20261012,
stack-watermark-source-v4 and out/stack-watermark-v4, with target output under
out/mixed-project-all13-stack-watermark-v4. Private ELF files are not committed.
