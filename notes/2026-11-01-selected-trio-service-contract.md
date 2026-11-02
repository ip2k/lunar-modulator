# Fixed Trio service contract, 2026-11-01

Base `7ab2810420999629d170531a6f2f78fd44a8484f`, tree
`38174abdaf5e6eda9ec3bf8a0198956cfc3d32ab`. Branch
`feature/2026-11-01@selected-trio-service-contract`; owner installer release audit.

Four new paths only: `tools/installer_service/build_capabilities.py`,
`tools/installer_service/selected_trio_profile.py`,
`tests/test_installer_selected_trio_profile.py`, and this note. No existing v1
canonicalization/API, launcher, worker, native, dependency or browser file changes.
The profile declaration explicitly keeps service and native-build capability
false. Package/install/release/hardware/distribution admission and ROM return
are false. The old missing-runtime refusal remains exercised and unchanged.

Version 2 accepts exactly Trio / init-starter-trio / startup0, no SET, no caller
FX/MIDI/modulation. Internal arp is a dependency, not caller selection. Runtime
is offline and the layout label is stock-sized-diagnostic: a flat ELF establishes
no correspondence to protected stock SPL/cfg/OTA/package contents. There is no
D9000, Hall, FM6, continuous or ROM20 translation.

The pure receipt validator checks exact schema and compiler recipe; externally
trusted source/toolchain/header/host-tool maps; actual prepared and object bytes;
actual ELF32 layout, symbols, flat bytes, linked 597-byte blob, arena/reader/stack
reservations; and recomputes the unchanged original SDK-free audit. Before that
reader runs, file/table/name/symbol bounds, overlap and relocation checks bound
its work for this fixed linked profile. Unknown claims and incoherent evidence
refuse. This validates coherence, not execution, authenticity, real stack high
water, audio/deadlines, complete MMIO/callgraph safety, or distribution rights.

`TrustedInputs` is a trusted operator/worker interface, not request data. A future
worker must independently obtain exact Git identity plus source manifest, actual
archive/tree binding, original and configured header maps, host tools/metadata,
compiler recipe and retained output bytes. It must not construct those anchors
from the client or receipt it is validating. This slice installs no worker or
route and exposes no listener. Source preflight checks only the committed named
prerequisites and does not replace inventories or external-input/runtime checks.

Actual exact-7ab retained-target positive smoke passed [verified], with no new
build or execution in this lane. Locally rehashed all 776 source files against
Git7ab blobs, all 123 objects and four prepared files, metadata exports, ELF,
flat/blob bytes and original audit. External inputs are attributed to the target
author's separate Aeon verification: 189 original and 189 configured headers,
694-entry extracted tree bound to the approved archive, compiler binaries and
host tools. Raw SDK/header inputs remained there; none were copied here.

- Receipt SHA256 `1093f36856071ce37db7923aa6b82c826d03d011ffc0a0a287f3eeead7b63244`.
- ELF SHA256 `75960e3e4011da43f26776cf356b23a338b6c5a925f950adcb83689e56612983`.
- Flat SHA256 `ee03de799a69410228af0cdff10cc07c3e3685fa51580344dd93ad16a83f2dfc`;
  178744 bytes of 581564-byte diagnostic flash budget.
- Packed PROJECT SHA256 `dc3c50d8da761fdfe36d17e1368d99f40740652192f14649230a9f8d7e3d58d4`;
  597 bytes, equal in prepared data, ELF and flat image.
- Toolchain archive SHA256 `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`;
  tree SHA256 `851733550499eca33cd737b2343bf48a1c846e0fe7246054d8372d43e7cfa066`.
- Metadata SHA256 `497976b740a83326224ed4820ee227941eaf111177d63780fe4f8047c82b6b0e`.

Test command uses existing service venv, `PYTHONDONTWRITEBYTECODE=1`, pytest
`-o addopts='' -q -p no:cacheprovider --basetemp=scratch/selected-trio-contract/pytest`,
with selected_trio_profile, request_contract, service, server, native_profile,
trusted_policy and audit_link test files. Result: 375 passed, 1 pre-existing
retained-native-input skip, 6 subtests passed; existing Starlette deprecation
warning. Fixtures prove request/receipt refusal, changed actual bytes, table/name
bounds, storage overlap, guard/blob/audit mismatches and unchanged v1 behavior.
Synthetic fixtures are format witnesses, never native acceptance.

Private evidence lives in this worktree's `scratch/selected-trio-contract/`:
`verify-real-receipt.py`, `actual-receipt-validation.json`, `actual-validation.log`,
`final-tests.log`. Original receipts/anchors and mirrored artifacts belong to the
target author's `lunar-selected-trio-target-20261101/scratch/selected-trio-target/target-evidence/`.
Retain small logs/scripts/receipts. This lane's pytest basetemp is removed after
checks. The target author owns object/stage cleanup after independent review.
This source worktree stays until reviewed/integrated, then remove normally.

Rarefaction's shared primary root is unchanged; orient/scope reject sibling
worktree escape. Serena absolute canonical_request lookup matched its source
bounds. No shared semantic root/server switch. Git and direct bounded inspection
are the coverage fallback. No hardware, Docker/service activation, native build,
SDK copying or heavy local job occurred in this lane. The next dependency is
independent review, then a separately authorized bounded worker adapter with
trusted input acquisition and existing bounded process capture, still disabled
until its own actual receipt and lifecycle/security checks pass.

Independent review requested pinning the accepted audit_limit prose to the exact
builder disclaimer, preventing that field from smuggling a complete-safety claim.
The fixed comparison and causal refusal regression are included; no gate changes.

Independent review also reproduced false coherence when entry and _start were
both moved to zero. Corrected startup checks require one section-associated
global label at fixed text origin, executable file-backed text and minimum
instruction extent; preserve actual assembler STT_NOTYPE/size0 semantics. Fixed
allocated section type/flag geometry and causal zero/outside/NOBITS/extent/storage
regressions accompany the correction. Actual target positive smoke also passes after the correction.
