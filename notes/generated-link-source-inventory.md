# Tuple-bound generated link source inventory

**[verified: source review and focused tests]** Fresh trusted tuple captures now retain the staged generated text inputs in
`build-provenance.json` under the existing `module_and_generated_inputs` and
`generated_link_resources` row sets. The additive
`generated_link_source_inventory` marker records schema 1, the exact source
payload paths, and their aggregate byte count. The tuple already binds the
provenance sidecar digest, so the marker and each file digest are covered by
the existing tuple anchor. Older tuples remain readable through the existing
package path; requesting generated-link export from provenance without this
marker fails closed.

The bounded archive option `--generated-link-root` copies the exact staged
bytes into `generated-link/link/...`. Its fixed source allowlist contains
`crt0.S`, `fm1_gpl_mods.h`, `gfx.c`, `libc.c`, `lunar_font.h`,
`measure_app_storage.c`, and `platform.c`, plus the previously inventoried
`fm1_modules.h` and `wave_tables.inc`. It includes `content_catalogue.c` only
when the captured embedded-content receipt selects it, and includes both
resource source/header files for each selected `braids` or `plaits` namespace.
No source path is accepted solely because it appears in a receipt. Per-file
and aggregate generated-source limits are 8 MiB and 32 MiB.

Capture continues to regenerate and compare the existing wave-table and
resource outputs against the pinned source tree. The newly inventoried staged
link inputs are hash-pinned by the tuple-bound provenance; they are not
claimed to have been consumed by a compiler. The archive manifest lists their
source and archive paths, sizes, and hashes. Corresponding-source completeness
and distribution eligibility remain false, and the external compiler/toolchain
and container dependencies remain outside this inventory.

No new target build or hardware run was performed for this change. Tests cover
synthetic capture/export, conditional content selection, deterministic archive
bytes, tamper/path/bound rejection, and downstream loader/packager row
validation.
