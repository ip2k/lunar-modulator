# Editor CI accessibility and build-profile repair

Scope: isolated branch `fix/2026-10-12@editor-ci-accessibility`, based on
`969259d4bc9fb2bf7030daa1eb34d01e6573cdf3`. Personal project. Parent integrates
this change and the separately owned desktop overlap/Firefox history fixtures,
then reviews and runs CI against the combined head before merge/deployment.

## Findings and changes [verified]

- Old CI run 38223359215 (ef55216b) reported a real CPU speech-input label
  mismatch: adjacent label/value spans produced `CPU6.7 %`, while its accessible
  name contained `CPU 6.7 %`. Adding a literal space to the label fixes the
  boundary; the accessible name and axe rule remain intact. Three repeated
  isolated axe probes reproduced the failure before, and passed afterward.
- Song transport intentionally has a polite `status` region in addition to
  editor feedback. The old reach fixture assumed only one. Its replacement
  requires exactly the named editor-feedback and transport regions, polite
  semantics and a meaningful Stopped/Playing/Paused state; it still rejects
  unrelated announcements and retains the refusal/burst checks.
- A real 320 px preview overflow came from the action row. At container widths
  up to 320 px, its five icon controls use 24 px widths, meter gaps use 2 px,
  and the meter tracks use 6 px. The row stays single, with readable values.
  The compact fixture now includes 320 px, forces CPU 100.0% and RAM 100%,
  and checks all targets are at least 24 by 24 px, containment, overflow and
  the single row. WebKit's actual 320 px peak screenshot was inspected.
- The pause regression executable was an optional target. CI prebuilt i386
  objects, then its Python wrapper tried to link the missing executable with
  default x86_64 flags. Adding the harness to default `all` makes it inherit
  the original CI build profile. The wrapper uses the existing default-build
  fixture instead of initiating an extra optional build.
- `seq.mk` is an engine source-hash input. An actual isolated Hera Wasm rebuild
  regenerated metadata: engines digest
  `1d4a8474ed97cdf99bbbdd810cf873de63db04130a6383d88431315c0eb87ab1`.
  Binary remains `761b18d3e9a676494a02e2d87867aa0eeab45bad6ab82062fad385a2f8bc2ebc`.
  No manual metadata hash editing occurred.

## Checks and receipts [verified]

Heavy work ran on Hera in private stages:
`/home/claude/mvave-fm1/editor-ci-accessibility-20261012` and
`/home/claude/mvave-fm1/ci-final-build-20261012`.

- Chromium, Firefox, WebKit: reach and resources pass. WebKit editor-v1 99/99;
  Chromium and Firefox 98/99, failing only the separately owned desktop
  overlap fixture. CPU axe checks pass in all three full suites.
- Compact peak-meter fixture: 22 viewport/view cases per browser, including
  editor Flow and Song at 320 by 812. All three browsers pass.
- Native default build with `EXTRA=-m32 -msse2 -mfpmath=sse`, GPL enabled:
  harness is ELF32 Intel 80386. Python pause regression passes (1 test),
  retaining this executable/profile. ASan/UBSan, GPL disabled: 24 pause
  scenarios pass with leak detection and halt-on-UB enabled.
- Wasm rebuild: 108/108 parity, identical JS/musl; 30-second edit storm,
  zero late blocks, zero resyncs. Node syntax and `git diff --check` pass.
- A host-side attempted run cannot execute the container's i386 loader and
  encountered root-owned build files; the authoritative run used the same
  isolated container as the successful 32-bit build. This is not a host gate.

Local ignored receipts: `scratch/editor-ci-accessibility/results-final/`,
`results-fixed/`, `results/`, and `wasm-build.log`. Remote final browser logs
are `compact-final-{chromium,firefox,webkit}.log`. The wasm build log records
actual compiler, source hashes, parity and storm output.

Rarefaction and Serena readiness were checked. Both pointed to the primary
checkout, and Serena selected C only. Their shared selection was left intact;
this isolated JS/build investigation used source inspection and actual browser
checks. Neither tool establishes isolated-worktree semantic coverage here.

Acceptance limits: these receipts cover this branch, not the eventual combined
CI head, deployed page, owner listening or physical FM-1 operation. Next step:
parent cherry-picks this commit, integrates sibling fixtures, reviews combined
changes and waits for required CI before merge and deployed reload validation.
