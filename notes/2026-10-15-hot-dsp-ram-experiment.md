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
