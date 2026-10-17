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
