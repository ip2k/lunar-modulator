# Bounded selected Trio worker adapter

This is an offline implementation for the fixed
`sdk-free-selected-trio-offline-diagnostic-v1` request. It does not enable a service,
produce an admitted install package, or establish target or hardware acceptance.
The default worker configuration still uses the existing legacy catalogue path
and its existing refusal gates. The selected API/server configuration is a
separately reviewed integration dependency.

The operator selects the exact clean source commit, reviewed immutable container
image, extracted toolchain, original pinned toolchain archive, original libc++
headers and private runtime directory. Request fields cannot select paths,
images, flags, commands or internal ARP dependencies. Writable runtime storage
must be disjoint from the read-only inputs. Each job receives a fresh Git source
archive and the worker entrypoint from that commit. Existing read-only input
mounts, bounded queue, Docker resource limits, private tmpfs, output capture and
immutable-ID cleanup remain in use. No source or object cache is reused.

The selected worker builds fresh Trio-only host tools, compares their metadata,
then calls the fixed selected diagnostic builder. Host admission performs strict
Pydantic request validation. The standalone worker repeats an exact fixed-request
check with the standard library, so it does not require Pydantic inside the fixed
build image. Its actual Python imports must resolve within the extracted source.
The diagnostic receipt source manifest and selected prerequisites now include
`process_capture.py` and its imported package initializer.

Each command captures at most 16 MiB per stream and has a deadline; the existing
capture helper kills and drains its owned process group, including descendants.
The diagnostic builder uses a 600-second command deadline. Preparation uses
90 seconds and 1 MiB per stream, covering the measured selected metadata near
39 KiB and full legacy metadata near 255 KiB. Overflow refuses rather than
returning truncated success. Worker host commands use 600 seconds, metadata and
compiler identity use 90 seconds, and the target builder uses 1,200 seconds within
the existing outer worker deadline. Failure diagnostics retain a bounded prefix;
combined selected command/build failure logs do not exceed 16 MiB.

Selected host bindings use schema 2 and identify the source commit/tree, source
archive, worker, image, request, toolchain tree, original archive and original
header tree. They do not reinterpret a header tree as a legacy catalogue.
The host independently acquires input manifests before dispatch and compares
them again after execution. The trusted pinned worker acquires fresh host-tool
hashes, metadata, compiler identity, actual objects and prepared files separately
from the receipt being checked. Audit source paths/text are compared with the
operator's pinned source. The full pure validator checks actual app/ELF bytes and
those trusted inputs before a WorkerResult is accepted.

Private selected evidence is limited to 16 MiB and 8,192 entries. Every retained
file is charged against the remaining budget before opening it; object traversal
is lazy, and JSON anchors share the same budget. The host accepts only the closed
selected evidence inventory. At most four selected jobs remain retained, counting
terminal jobs as well as active jobs. Immutable object/prepared byte values are
shared into trusted-input mappings. This avoids retaining the contract's larger
256 MiB theoretical evidence limit for every API record. Legacy limits remain
unchanged.

`verify_selected_trio_result(build_id, request_bytes, result)` performs pure
revalidation using private recorded inputs and an exact result fingerprint. It
launches no process and reads no external file. Envelope validation claims are
never trust anchors. The composing API must drain in-flight verification before
expiry, deletion or shutdown. A selected job remains present, retains its trust
state, and consumes capacity when container cleanup or owned filesystem removal
cannot be confirmed. The API confirms `adapter.get(id)` is absent before releasing
its corresponding admission record.

Local focused validation passed: 322 tests, one existing skip. It includes actual
small subprocess timeout/overflow/descendant checks, synthetic pi32 ELF plus actual
byte collection and full pure receipt validation, changed input/receipt refusals,
pure callback checks, read-spy evidence-budget checks, and causal failed-deletion
and fifth-job admission checks. No Docker daemon, target compiler, real worker,
listener, LAN build or device was used for this evidence. A source review and a
single coordinated bounded actual worker/composed-loopback run remain required.
All install, package, release, distribution, ROM-return and hardware admissions
remain false.
