# Private worker canonical build paths

Personal offline work; base `6bd944e808904f41cb263d72a52d3a450975a6d3`.
This is a deterministic-build correction, with no hardware or distribution
admission. The raw app and ELF identity gates remain unchanged.

[verified] The actual service run at source `67586bb6` produced the same
854,528-byte app as the retained trusted build (`f91bc8da94ddbf40ef1a75e85bf8802aef28a5b153025ce7f1d420e056907338`).
Its raw ELF differed: service `d89c988cf7394ab9149ba5e9294c3dea0a849fdf04d0897917b8d91a52c88f87`,
trusted `1f4c007df2216721fd44dd380b242d604930a812be9c813c4ed675ace2e5b132`.
Only `.symtab` and `.strtab` sections differed. The linker receives absolute
object paths, including `/tmp/lunar-worker/output/build/link/crt0.o` versus
`/output/build/link/crt0.o`. The compiler does not own those linker input
filenames; a compiler prefix-map alone would leave this discrepancy.

The retained comparison is
`/home/claude/mvave-fm1/private-adapter-real-run-67586bb6-20261017/elf-section-comparison.json`
on Aeon. That investigation compared bytes in memory; it never rewrote the ELF
or a receipt. Preserve this failed run and its original namespace.

## Contract

Use the existing trusted build's actual absolute paths in the service worker:
source `/workspace`, catalogue `/catalogue`, build `/output/build`, toolchain
`/opt/pi32v2`. No aliases, caller paths, new compiler flags, ELF rewriting or
relaxed identity comparisons. The trusted worker remains unchanged.

The adapter must provide real empty private `/workspace` and `/output` roots,
owned by the runtime UID/GID with mode `0700`. The worker rejects symlinks,
resolved path aliases, other owners/groups, permissions and existing content
before extraction. Archive traversal/link checks remain in place. Extracted
source files become `0444` or `0555` according to their executable bit;
directories become `0555`. These are read-only file modes, not a claim that
the writable tmpfs is a read-only mount. Source bytes do not change.

Host codec products move outside source into `/tmp/lunar-worker/state`.
The make recipe matches the trusted worker: absolute BUILD/target,
`FM1_GPL_MODS=1`, `-j4`, 180-second timeout. The target builder receives the
same canonical path options and fixed continuous profile as the trusted worker.
The previous service recipe relied on `FM1_GPL_MODS ?= 1` in
`engines/Makefile`; making that default explicit does not select new modules.
The codec source and packing policy are unchanged; actual packed-byte equality
still belongs to the fresh build comparison.
Evidence emitted by this worker accepts only `/catalogue/` and
`/output/build/link/` object namespaces.

The root approved an adapter scratch partition within the existing configured
total: workspace `budget // 8`, output `3 * budget // 8`, `/tmp` the remainder.
The default remains 3 GiB total: 384 MiB + 1152 MiB + 1536 MiB. Adapter mount,
legacy-evidence replay and shared fixture changes are coordinated separately
with the installer-evidence worker. Old evidence must retain its original
path interpretation; do not substitute canonical paths into old receipts.

## Checks and remaining acceptance

[verified] Focused tests exercise the actual trusted worker entrypoint with a
fake subprocess boundary, comparing its generated make/builder argv to the
service recipe. They cover canonical constants, malformed roots and read-only
modes preserving hashes and executable bits. These tests do not compile code
or establish raw ELF equality. Existing trusted-wrapper policy tests also pass.

The two service fixtures now supply canonical roots and generate canonical
object paths. Exact focused command:

```
python -m pytest -o addopts= -q tests/test_installer_worker_build_paths.py tests/test_native_continuous_build_wrapper.py tests/test_installer_service.py
```

[verified] At this worker-only checkpoint: **158 passed, 1 skipped, 1 failed**.
The failure is the coordinated old adapter reader refusing the new canonical
catalogue namespace in `test_worker_retains_real_builder_namespace_and_receipt_order`.
The separate worker-path plus trusted-wrapper suites pass **40 tests**.
The adapter patch must land before the full service suite and a fresh
exact-source operational runner preflight. No heavy build was launched
for this correction. A real fresh service plus trusted wrapper comparison is
still required; success cannot be inferred from path and command tests.

[verified] Both semantic tools still select the shared primary checkout at
`/Users/likwid/Developer/mvave-fm1-firmware`, not this isolated worktree. Serena
is ready only for C++; its worker overview returns FileNotFoundError.
Rarefaction Python status is ready there, but orient on this worker returns
ENOENT. No shared server was retargeted. Investigation used the actual isolated
worktree files and retained Aeon receipts; semantic coverage does not extend
to this branch's Python changes.

No Hera, bench, device, USB, MIDI, flash, power, public service or package
publication action was performed. All hardware, playback, recovery,
installable, updater and release eligibility remain unproven/false.

## Adapter dependency completed

The coordinator transferred adapter path ownership after receipt-ordering fix
`5f26d5f0f5d3a072e086556eb22f82fb49af556e`. The separate adapter branch is
`fix/2026-10-17@canonical-private-adapter-paths`, based on that exact fix plus
the worker patch. The adapter now mounts the read-only catalogue at `/catalogue`
and supplies the private `/workspace` and `/output` tmpfs roots. Both roots
receive the configured unprivileged UID/GID and mode `0700`. `/tmp` receives
the remainder of the existing scratch allowance. Page-sized partitions round
the configured total down first, so Linux tmpfs page rounding cannot push the
combined mounts above an odd byte limit. The minimum allowed 128 MiB cap still
has three positive partitions; capacity exhaustion fails the build normally.
Non-integer scratch caps are refused before forming Docker arguments.

The canonical reader accepts only the new literal catalogue/link namespaces.
It does not reinterpret old 675 receipts. The coordinator assigned that actual
retained replay to the receipt worker's frozen `5f26d5f0` checkout, which keeps
the old namespaces. Old evidence and binaries remain untouched.

[verified] Combined checks after both patches:

```
python -m pytest -o addopts= -q tests/test_installer_worker_build_paths.py tests/test_installer_adapter_build_paths.py tests/test_installer_service.py tests/test_installer_continuous_profile.py tests/test_installer_native_profile.py tests/test_native_continuous_build_wrapper.py tests/test_private_package_candidate.py
```

**274 passed, 1 skipped**; one pre-existing Starlette/httpx deprecation warning.
This includes the service evidence roundtrip, selected continuous cases,
historical Hall diagnostic policy, bounded mount defaults/minimum/odd budgets,
and actual adapter argv. Fixture path literals changed to match the current
worker namespace. A standalone native-profile test invocation without the
normal native-tool import path fails imports; the combined command above
establishes that path using the existing wrapper tests. No packaging dependency
or source import policy was changed for this unrelated test setup issue.

Next: root integrates worker and adapter path commits with the separate API
receipt fix, assigns an exact integrated source, then reviews a new operational
runner hash and independent preflight before any heavy target run. The real
service/trusted ELF identity comparison and private package result remain
pending. `uv.lock` and the trusted wrapper/compiler/linker are unchanged.
