# Source archive preload catalogue inputs

[verified: Aeon extracted archive] The genuine tuple-bound source archive from
3520274b contained the exact selected Event Horizon project and companion SET,
but omitted the eight committed `.lunar` sources read by
`export_preload_projects()`. `prepare_selection()` exports that entire fixed
catalogue before choosing requested IDs. Thus the high-level build path fails
on a missing unrelated legacy project even though the selected originals are
present under `selected-inputs/`.

[verified: source and host tests] The archive selector now retains exactly the
eight current `PRELOAD_PROJECTS.source_path` inputs, including the four legacy
examples and four replacement showcases. No general `.lunar` inclusion or
private song path was added. The regression checks equality of the allowlist
and the actual exporter catalogue, materializes source bytes through the real
selector, and runs the real project and companion SET exporters against that
isolated directory. Removing an unselected catalogue project reproduces the
failure. The bundle suite passed all 25 cases with the existing local
`engines/build/fm1-state` codec, including the real prepared-selection test.
An earlier run without that explicit codec path passed 24 and skipped one. Independent static review found no correctness or safety finding. Selected-source binding and false completeness and
distribution flags are unchanged.

The independent extracted-source worker continues on the frozen original
archive via the direct application-link path and retained verified prepared
profile. That is a separate, narrower check of the application build. It does
not establish that the original archive supports high-level preparation.
A new archive from the corrected selector still needs its own high-level
preparation check; neither check establishes complete corresponding source,
realtime hardware performance, recovery, persistence or release readiness.

Semantic-tool limitation: bounded Rarefaction orient and Serena symbol queries
both resolved the primary checkout, where this newer file is absent. The
shared servers were not retargeted; exact integration-worktree source reads
were used for this change.
