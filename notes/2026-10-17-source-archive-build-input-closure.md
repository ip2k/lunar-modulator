# Source archive: runtime notices and sample regeneration inputs

[verified: bounded source and archive review] The native libc builder checks
every file in the musl source inventory before compilation, including
`firmware/third_party/musl/COPYRIGHT`. The source archive's old name/extension
filter omitted that file, so its hash row alone could not support that build.
The filter now retains `COPYRIGHT` files within its existing source prefixes.

[verified: source review] The same filter omitted X0X's `local.patch`, used by
its vendoring/check script, and its three tracked 909 recording inputs used
to regenerate the committed sample header. Text `.patch` files and exactly
`engines/third_party/fm1-x0x/assets/909/{hh,ride,crash}.wav` are now selected.
The existing `README.txt`, `UPSTREAM.md` and `LICENSING.md` describe these
recordings' upstream provenance and licensing; this change adds no new
recording or dependency. Their previously recorded provenance limits remain.
The separately named MIT notice `LICENSE-Open303` was also omitted and is
now retained. No general media-file selection was added.

[verified: host tests] The bundle suite passed 24 cases using the existing
arm64 `fm1-state` codec. Archive tests check exact fixture bytes and manifest
hashes/sizes for the added notice, patch and recording input; unrelated WAV
and firmware binary inputs remain excluded. A repository-based check confirms
every file named by the seven native runtime inventories passes the selector,
and all three exact recording paths are selected. Independent static review
found no actionable issue and `git diff --check` passed. This is bounded source
coverage, not a complete rebuild of an extracted archive.

All completeness, distribution and hardware flags remain false. An external
toolchain and generated catalogue are still needed for the fixed worker
invocation; their identity receipts are not their source bytes. This work
does not establish complete corresponding source, regeneration acceptance,
firmware build, physical playback, recovery or public release readiness.

Read-only audit handoff is retained in ignored
`scratch/source-bundle-closure-20261017/HANDOFF.md`. Its initial findings were
reviewed against `build_libc.py`, the runtime inventories and X0X's vendoring,
generator and component-notice files before this change.

## Extracted subset target smoke and default module input

[verified: Aeon offline build, independently checked report] A selected-path
export at commit `93f4bfc9a38e690165c86bc16d287a20e6ff304b` contained 1009 files
and compiled all 66 inventoried musl C units with zero failures and no SDK
archives. Export SHA-256:
`bc433bff62d5df1cbd744345c0c81438dcddf5d5ff68d005f331937c32afd41b`.
Build report SHA-256:
`ef11037e4ec9c82ff839d661b9f74af6501704f57af5813ea22d883f73bc26b7`.
This checks the COPYRIGHT omission fix through a real inventory check/compile.
It is a lower-level git export, not the tuple-bound bundle API or a full app
link. It used the identified pinned toolchain archive in a network-disabled,
resource-bounded container; that image differs from the production image pin.
The full environment, command and limits are retained on Aeon in
`/home/claude/.local/share/codex-coordination/handoffs/lunar--source-archive-rebuild-20261016.md`,
SHA-256 `2d123cf148965b6fce04e13cd411a5fbeec9547d7a5053677a7c9f5c1582a288`.

[verified: source and Makefile execution] The worker also identified omitted
`engines/modules/default.list`, consumed by `engines/modules/catalogue.mk` for
`FM1_MODULES=default`. The selector now retains that exact build-input path;
it does not admit arbitrary `.list` files. A local selected-source extraction
using the updated selector produced exactly the same `print-modules` output
as the full tree. Removing the file from that extraction fails with
`FM1_MODULES: no module "default"`. The check uses committed source inputs at
`63499641fa0eec921a2ffc44a02ef3ed88dc2f90` with the modified selector; it is
not a current trusted-tuple archive. Result retained in ignored
`scratch/source-default-module-smoke-20261017/result.json`.

The 24-case bundle suite passed again after the exact-path addition. The
first local extraction attempt used the system Python, which lacks tarfile's
`filter` argument; the unchanged check passed under the project's uv Python.
No application build or completeness/distribution/hardware flag changed.
