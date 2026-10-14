# Demo profile staging adapter (2026-10-14)

`tools/native/stage_demo_profile.py` turns stable IDs from the server-side
`export_image_catalogue.export_preload_projects()` result into a fresh profile
directory consumable by `prepare_image_profile.py`. The adapter is an input
stager only: it does not pack projects, validate their complete module
dependencies, link firmware, prepare an installable image, or authorize a
default composition.

The caller supplies a module-only version-1 profile, the trusted catalogue
`projects` array, a non-empty ordered list of selected IDs, an output directory,
and an optional startup index (default zero). Zero-project selection is
currently unsupported. IDs must be unique and appear in the current catalogue.
Each catalogue entry must match the fixed `PRELOAD_PROJECTS`
ID/title/source-path registry. The adapter rejects non-regular source paths,
symlinks in the repository-relative source chain, paths outside the resolved
exporter root, files above 1 MiB, and source bytes whose SHA-256 differs from
the catalogue snapshot.

The resulting `profile.json` keeps `prepare_image_profile.py`'s existing schema:
the module groups plus `content` paths such as
`projects/legacy-example-afterglow-relay.lunar`. These paths are relative to
the staged profile file, so no repository traversal enters the prepare step.
The adapter copies the exact verified source bytes. `selection.json` retains
the ordered project IDs, startup index, selected startup ID, repository source
paths and source hashes. Startup metadata stays out of the prepare profile,
whose schema does not define a startup-index field; a later runtime/builder
integration must explicitly consume the sidecar. This adapter checks profile
shape and module-group value types; canonical module IDs and group membership
are resolved downstream by `prepare_image_profile.py`. A future API must load
catalogue entries on the trusted server side and accept only project IDs and
module choices from the request.

All source records and hashes are checked before output creation. The output
directory must be new; the adapter refuses reuse. It writes the prepare profile
last and removes the complete directory if writing fails, so a partial directory
is not presented as a valid staged profile. It currently requires the output
parent directory to exist. The catalogue SHA is the freshness receipt; callers
should obtain the catalogue and stage within one request and must not accept a
catalogue object supplied by an untrusted client.

## Verification and limits

Using the project venv, `python -m pytest tests/test_native_stage_demo_profile.py
-q` passes 9 cases. They cover current exporter records and exact byte/hash
identity, requested ordering and startup index, unknown/duplicate choices,
changed source bytes, a symlink escape, a catalogue path override, invalid
startup index, existing output refusal, and cleanup after a failed profile
write. No packing tool, builder, linker, or hardware was used. Module names are
only schema-checked here; `prepare_image_profile.py` remains responsible for
canonical module resolution, group membership, packed-content validation,
dependency checking and its own receipt. Selection metadata is not a full-song
default or product UI claim.

Rarefaction and Serena are still selected to the primary checkout rather than
this worktree, so shared semantic project selection was not changed. Source
navigation used direct inspection of the exporter, prepare-profile schema and
their existing tests. Root review is the next step; integration needs the
trusted request handler to load the exported catalogue, call this adapter, and
pass its `profile.json` to the existing preparation path while retaining
`selection.json` for startup selection.

## Source-provenanced `fm1-state` build handoff

`engines/state/README.md:29-32` documents `make -C engines` and the
`engines/build/fm1-state` host tool. The narrower reproducible target is
`$(BUILD)/fm1-state` in `engines/mk/state.mk:22-40`; from an exact source
snapshot mounted read-only at `/src` with writable output mounted at `/out`,
use:

```sh
make --no-print-directory -C /src/engines \
  BUILD=/out/fm1-state-build FM1_GPL_MODS=1 FM1_MODULES=all \
  /out/fm1-state-build/fm1-state
```

This target compiles `host/state/state_tool.o` and links state codecs/registries
with `RENDER_OBJ`, excluding only `our/host/render.o` and
`our/host/render_state.o`. It does **not** depend on or invoke the
`fm1-sim-render` executable, so producing that executable is unnecessary.
However, it does reuse the renderer's engine/runtime object graph; it is not
independent of engine sources or their host compilation. `RENDER_OBJ` is the
all-module object list (the module-choice filtering only affects
`RENDER_PRODUCT_OBJ` for `fm1-render`), and `FM1_GPL_MODS=1` is required here
for the complete registry and matches the repository default. This is a host
state tool build only, not the pi32v2 firmware link or a device check.

For provenance, the Hera job should copy the *current installable checkout
working tree* to a new task-specific source snapshot, including any owned
uncommitted implementation files and excluding `.git` and build outputs;
record its source revision/status and a recursive per-file SHA-256 manifest
before running the command. Bind that snapshot read-only as `/src`, bind a
fresh task output directory as `/out`, and retain the command, container image
digest, resource/network limits, build log, resulting ELF SHA-256, and
`fm1-state meta`/`fm1-state check` results beside the manifest. Existing Hera
collector validation output at
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/collector-max-validation-v1/source`
is a different snapshot and only contains `fm1-sim-render`; it cannot provide
the requested source-provenanced tool. No Hera snapshot or `fm1-state` build
was created in this task, so the exact current-source binary, its hash, and
the demo projects' pack/prepare receipts remain outstanding. This build does
not require or depend on a sim-render test run.
