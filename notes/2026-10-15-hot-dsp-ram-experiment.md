# Selected DSP bodies in RAM: bounded diagnostic experiment

The prior physical PLL diagnostic still failed audio acceptance: approximately
257 produced blocks/s against 689 required. Moving selected render bodies from
XIP into existing reserved RAM tests one possible instruction-fetch cost; it
does not establish the cause or promise a performance improvement.

[verified: source and host tests] `--hot-dsp-ram` is an explicit catalogue,
application-builder and artifact-flattener option. Selected sixop, Hall, limiter
and application render bodies use a separate `.ram_dsp` load segment copied at
startup. Linker and artifact checks bound it below 0x01C06000, disallow overlap
with the flash writer and preserve the debug reservation. Flash-writer
`.ram_text` call allowlisting is unchanged. Raw image call and stub-boundary
proofs carry the new section's independently validated flash load mapping.

The effective default linker script matches original SHA-256
833d79ca882336b4d61b2a977e6b4e13b5aed99e26fa21423fceb0b58ca0f16b.
Catalogue receipts must explicitly bind the RAM option and source inputs.
Only bounded diagnostic and song-diagnostic modes accept this experiment.
Callees and data may still live in XIP; full RAM residency and execution during
flash writes are explicitly unverified. SAVE remains disarmed.

[verified: host] Coordinator reran the optimization, synthetic ELF artifact
and catalogue receipt suites successfully. Review additionally found and fixed
a missing raw-image stub-boundary mapping for `.ram_dsp`; its regression checks
exact mapped bytes and rejection after mutation. These are host checks, not
target ABI, linked footprint, instruction timing or physical audio acceptance.

Next: fresh exact-source sixteen-shard catalogue on Hera, bounded diagnostic
link, independent inspection of actual section and selected symbol extents,
startup copy/disassembly, call audits, app budget and immutable receipts. Only
after admission checks prepare a new one-use hardware capture campaign. Previous
ROM73 PLL campaign is consumed and must never be rerun. No device operation has
been performed for this source change. Firmware/recovery/web release goal remains
active and unaccepted.

## Fresh linked target and offline admission

[verified: Hera build and copied receipts] Exact source
`e85a42f3a0a031f1f0e4f2c7d4f12bc3bbbaa083` built successfully in sixteen
fresh bounded catalogue shards followed by the EH+SET diagnostic link. The
successful v3 run preserves matching pre/post input snapshots. Earlier runner
attempts remain separate: one rejected invalid Docker mount syntax before
compilation; another completed compilation but rejected a host-generated Python
cache mutation. Neither earlier attempt is used for admission.

The successful app is 852,928 bytes (7,716 bytes below its 860,644-byte budget),
SHA-256 `8e74b08991959e5d1b36f80b878227568ac6d25b9e9f229836b3f5680cccbc00`.
Its ELF SHA-256 is
`8bfd4577643e48e98a384f05cdf78feafa8b988370280a941e5e9e69722756b0`.
Actual `.ram_dsp` occupies 3,196 bytes at `[0x01c00544,0x01c011c0)`,
loaded from `0x020cf7ec`; the four selected render symbols are present.
Independent inspection confirms the linked startup copy precedes app dispatch,
and mapped section bytes match the flat app. Heavy callees can still remain
in XIP: this is not full DSP residency. The existing narrow two-function
RAM flash-writer audit passes unchanged. Full saved disassembly is receipt-bound;
a new independent vendor-objdump regeneration was not performed locally.

[verified: host] Offline reconstruction now accepts this extra RAM segment only
with explicit selection and matching bounded diagnostic, disarmed SAVE and exact
ELF extent receipts. Default reconstruction still rejects an unexpected segment.
The four candidate/diagnostic/manifest suites pass 90 tests. This is not physical
installation, runtime execution or performance acceptance. Private actual-ELF
review and original frozen receipts remain under `scratch/native-hot-dsp-ram/`
and `scratch/hot-ram-result/`; no vendor binaries are committed.
