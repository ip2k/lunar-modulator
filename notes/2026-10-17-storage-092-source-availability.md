# Exact FM-1_092 source artifact located

[verified: coordinator and independent reviewer] The exact public package from
the September 29 research session is retained in the primary checkout:
`/Users/likwid/Developer/mvave-fm1-firmware/scratch/baudgirl-2026-09-29/fw/FM-1_092.fwsc`.
It is 810,548 bytes, SHA-256
`ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80`,
matching the strict model's input pin. Its adjacent `FM-1_092.fwsc_unpack`
tree contains the extracted app and protected components. Nothing was fetched
from Hera, written to a device or committed as a vendor binary.

[verified: independent reviewer] Extracted `files/app.bin` is 691,744 bytes,
SHA-256 `9c5a44706b7686746b389e3e8fe6ff051fc50028f9b708ac59f493300f793a7b`.
The retained `jlfw.yaml` records app entry `0x02000120`. SPL, configuration,
CFG tool and CFG digests match the strict 092 model. The review found no matching
text disassembly or symbol map in the examined retained files.

This corrects the narrower inventory of the integration checkout: absence of
that checkout's ignored `scratch/092-package-model/` path did not mean the
package was absent from the workstation. The corrected detailed inventory is
in ignored `scratch/storage-ownership-092-lineage-inventory.md`, SHA-256
`8935c00abe726bd486655ebacb91ebfcaabe72e8d235b33f27c28d6f93f89bcd`.

The next bounded task is vendor-tool disassembly with verified address mapping
on Aeon, followed by an exact-lineage startup/storage call trace. Package and
app availability do not supply a VM/USR record decoder or allocator semantics.
Unknown records, bank ownership, semantic migration, first-format interruption
safety, SAVE admission and physical rollback remain unresolved.
