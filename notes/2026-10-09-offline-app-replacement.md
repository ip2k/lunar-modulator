# Bounded offline app replacement model

2026-10-09. Personal MIT stream `feature/2026-10-09@offline-app-replacement`,
explicitly stacked on PR #108 commit `2807f73`; integrate after that stream.
No device traffic, binary container output or installation occurred.

## Concrete checkpoint

`tools/jieli/model_app_replacement.py` constructs an altered stock V15 FWSC
**in memory**, independently checks the resulting layers and emits only a new
JSON report. The CLI requires the actual ELF and flat application; it freshly
runs the SDK-free link/eFuse audit and exact diagnostic link/load report.
The stock inspector remains stock-only. The private replacement verifier
labels its result `modified-app-inspected-model-only`; it does not classify
a replacement as stock or permit a changed stock reference.

The app must be nonempty and fit the original stock app byte extent. Entry,
app offset, all enclosing directory lengths, resource placement, reservations,
SPL/config/OTA, unknown metadata and auxiliary/trailer bytes remain exact.
Only the supplied app prefix and its length/data/header CRC, app-directory
data/header CRC and outer flash/list/header CRCs change. The old unused app
tail remains byte-identical and unreferenced by the shortened child record;
there is no invented padding rule or physical erase claim.

Independent verification parses the modified image again, binds its app to
the supplied bytes and every other component to original guarded stock,
and masks only the explicitly allowed changed decoded fields/range before
comparing against the original. It separately compares outer metadata,
records, padding and all non-flash bytes. Tests repair CRCs after corrupting
the unused app tail, resource bytes, outer metadata or trailer to prove that
CRC validity alone cannot bypass preservation. Empty and oversized app
inputs fail closed. Repaired-CRC oversized apps that still fit a directory
gap, app relocations and changed partition descriptors are rejected. CLI
tests confirm report overwrite refusal and no binary-output option.

112 focused tests pass, including actual V15 and the existing
linked inert diagnostic [verified]. Actual in-memory result:

- Original FWSC SHA-256:
  `db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a`.
- Model SHA-256:
  `12a3ca23dd77a4d99c27ccb1760343c2fde3688aee001230f7e16a73aa07ba83`.
- App SHA-256:
  `5566edb6742aebb695a4ed2ab0e9d979ebadb615190bb030c55f59f2258fee08`.
- App 200 bytes, old stock extent 581564, untouched tail 581364; 204 physical
  bytes differ across 16 exact ranges recorded in the ignored JSON report.

These are offline format/link results. The image retains `FM-1_015` identity.
Same-version refusal is reported; acceptance of an arbitrary new version is
not established by that fact. AL-255's V13 analysis also reports cfg/OTA
checks; their applicability to V15/092 is unresolved. See the exact evidence
and preserved opaque trailer profile in
`notes/2026-10-09-version-trailer-contract.md`. No version policy is invented, the remaining trailer
semantics stay unresolved, and no claim of installation acceptance follows.
FM-1_092's auxiliary-origin refusal is unchanged. Observable output and full
SP/SSP/exception/clock/core/IRQ/watchdog startup remain unresolved; the inert
variant stays intact. Missing full-image/broken-app recovery is a specific
risk to assess under the owner's staged candidate/range review and fresh
backup policy, not a blanket ban inferred from this model.

Rarefaction's root remains the original checkout and excludes the managed
worktree/new files; original package-guard navigation works. Serena rejected
the new ignored Python path in its active project. Both were attempted;
bounded file inspection and actual parsers/tests provide the local evidence,
without claiming semantic checks succeeded on the new module.

## Reproduce and continuation

```sh
python3 tools/jieli/model_app_replacement.py \
  /Users/likwid/Developer/mvave-fm1-firmware/scratch/FM-1_v15_cdn.fwsc \
  --stock build/jieli-diagnostic/stock-v15-reference \
  --elf build/jieli-diagnostic/diagnostic.elf \
  --app build/jieli-diagnostic/diagnostic.bin \
  --json build/jieli-diagnostic/offline-app-replacement-report-new.json
```

Report output refuses overwrite; no binary-output option exists. Existing
report is `build/jieli-diagnostic/offline-app-replacement-report.json` (ignored).
Focused tests use the original project's `.venv/bin/python`; set
`FM1_STOCK_FWSC`, `FM1_STOCK_UNPACK`, `FM1_DIAGNOSTIC_ELF` and
`FM1_DIAGNOSTIC_APP` to enable actual-file verification. Parent owns review/CI
integration. Next: independent review and CI, then explain identity/version
and trailer policy before any emitted container. A later diagnostic should
own SSP/exception state and supply observable output after clock/power/core
handover evidence; this stream deliberately retains the inert variant.

## Change log

- 2026-10-09: Implemented and verified fixed-allocation in-memory app
  replacement, independently checked changed layers and byte-preservation
  contract, corrected cache/load-range provenance and staged recovery wording.
