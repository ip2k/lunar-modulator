# Incomplete native source/notices bundle prototype — 2026-10-14

This is a private inventory prototype, not a corresponding-source release bundle,
legal conclusion, build-reproduction proof, or distribution approval.

## Implementation

`tools/native/create_gpl_source_bundle.py` exports selected committed files from
a clean source checkout, checks an externally supplied raw schema-2 tuple SHA,
checks the tuple-pinned provenance and full source-tree manifest, and writes a
deterministic gzip-compressed tar archive. The archive includes root licensing
files, source/build material under a bounded set of native/engine/tool paths,
per-component notices, a file-hash manifest, and an explicit incompleteness
notice. It excludes known private material paths and compiled/vendor binaries.

The tool never accepts a tuple's self-declared hash as its trust anchor. Caller
must provide `--expected-tuple-sha256` from a separate trusted receipt. It
requires the tuple's admission flags to be false and refuses schema-1 tuples.
No retained schema-1 tuple or private owner source corpus was used to create an
archive in this task.

## Explicit unresolved inputs

The tuple/provenance records the packed project and companion SET data, but do
not bind the original source bytes from which those prepared assets were
created. Those original source bytes are therefore absent from the source tree
archive. The external JieLi toolchain is identified by digest and is not
included. Build instructions are a provenance summary, not a complete
reproducible environment recipe. The bounded path selection is not asserted to
cover every possible build dependency.

Every archive and manifest sets
`corresponding_source_complete=false` and `distribution_eligible=false`.
This is deliberate fail-closed behavior. Release remains blocked until a new
trusted build-input capture binds the original project/SET bytes (and the
applicable source/build dependency set is audited).

## Validation

On Hera, the four focused tests pass. They create a temporary Git source tree
and verify deterministic bytes, retained license/source files, exclusion of
private/compiled paths, refusal of an incorrect external tuple anchor, refusal
of old schema, refusal of dirty source, and refusal of a modified source
manifest. No real build tuple was packaged; no firmware binary, private project
data, or vendor toolchain was copied. No device or hardware operations occurred.

## Limits and next step

Before any release use, extend the trusted build capture to bind original
project and SET source bytes and the complete source/build inputs for the exact
image. Then independently review the archive inventory and notices against
that captured tuple. This prototype must not be used to distribute an image.

