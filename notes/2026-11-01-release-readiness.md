# Lunar release and installation readiness — 2026-11-01

## Goal and acceptance

The owner authorized continuing parallel implementation to make Lunar Modulator
ready for release and installation, including firmware, web installation and
customization. This is a personal, non-commercial project. Eight voices is the
release target; twelve is a stretch goal. The owner approved trunc12 by A/B
listening. Historical fixed-eight dev-board arrangement soak results do not
establish interactive runtime, physical FM-1 or owner listening acceptance.

Completion requires reviewed source, exact-head CI, a truthful customization and
installer flow, compatible admitted artifacts, demonstrated boot/fail-open,
storage/update/recovery, actual FM-1 audio/display/controls, and applicable
listening and publication gates. SDK/vendor material and private captures stay
private. Diagnostics and offline receipts are not installable releases.

## Integration status

[verified] Remote main is `8d790e3060643ab4e4f8404a7dbf52505ec9b303`.
PR #151 merged after its exact-head CI passed. Preserve its synchronous
`action()` browser fix.

[verified] Foundation PR #161 is open at
`e80ac1788d2968e9779577a7a7d66aa13c2a37c5`. Service PR #162, native
foundation PR #163 and OTA transport PR #164 passed their own exact-head CI and
independent reviews, then merged into this foundation. They have not merged
to main. Combined CI 41304070922 is not green: the Mac job found a missing
TLSF inventory assumption in a source-bundle test. Pages build passed; PR
deployment was skipped. Do not rerun passing checks to hide that failure.

[verified] Corrections PR #165 is the combined integration candidate on
`fix/2026-11-01@release-state-corrections`, pushed and remote verified through
`59084596a4a668220a15d7055b34557a0408c89e`. It is not a release or
hardware admission. Capture command completion and bounded codec phase 1 are
now independently reviewed and integrated. A new frozen-source WASM build and
final exact-head CI remain. Prior-head CI found a 32-bit effect-walk expectation
mismatch under causal diagnosis; all three browser jobs passed.

The foundation provides DX7 bank export, ordered MIDI realtime input,
queue-margin telemetry, offline customization/catalogue and a shared request
contract. The public page exports requests and inspects packages. Public build
and installation capability remain closed. The extracted private service also
refuses production startup without complete native prerequisites; API tests do
not imply a runnable native build or device installation.

Real-Chrome visual and interaction acceptance remains pending. The owner
approved the chrome-browser skill, but browser access was disabled in Work
settings and no extension tools are available. The enablement question remains
pending; do not bypass the setting. The owned loopback preview is
`http://127.0.0.1:8767/installer.html`; stop it after review or before pausing.

## Reviewed corrections integrated

- Native Capture checks representability before changing a clip or clearing
  history. Takes outside the unchanged 256-step format refuse transactionally;
  valid clip growth and the explicit Movy compatibility oracle remain. Endpoint
  arithmetic checks bounds before rounding, including UINT32_MAX. A retained
  take receives a readable refusal popup. Panel feedback now follows the exact
  command through the held slot and completes only when it runs. BUSY refuses
  without retry, and reset/successful import cancel pending feedback. Author normal/sanitizer checks,
  independent arithmetic/FIFO checks and coordinator focused tests pass.
- WebKit transport updates preserve unchanged icon nodes. An actual-app held
  pointer regression demonstrated the old lost click and passes in all three
  browser engines with the fix. This does not replace real-Chrome acceptance.
- Scene launch requires successful decode. Stopped-ARP fixtures finish all six
  straight/swing intervals and releases. The RAM-edge fixture removes an unused
  Ensemble that made its initial chain 612 bytes too large, while retaining
  explicit oversized-chain and ARP refusal witnesses. Production limits stay.
- Explicit aligned state workspaces preserve host behavior and guard aliases,
  reentry and lifetime. Actual pi32 object evidence removes a 917,536-byte
  default arena in external-workspace mode. The 481,244-byte JSON writer is
  still too large for native persistence; workspace APIs alone do not solve it.
- The renderer protocol now has a shared core and explicit platform ports,
  preserving the SDK wake paths. Native lifecycle tests cover publication,
  readiness, timeout, late entry and poison refusal. The production native
  CPU1 backend is disabled and cannot be enabled by a build flag.
- The LAN browser wrapper isolates remote staging, claims canonical output
  paths and cleans only owned resources. Validated SSH-config and CPU/CPU-set/
  memory hooks apply to every container. Independent fake-transport lifecycle
  tests pass. The actual e267 combined browser batch also passed through this
  revised wrapper with the designated SSH and resource settings.
- MATRIX stack frames were reduced with bounded snapshots. Actual pi32 local
  frames fell to 652/376/404 bytes; this is not a whole-call-chain stack bound.
- FM6 descriptor identity, sound/insert release, finite edit indices,
  transactional imports, immutable queued locks, Compare/Acid/Divide chronology
  and transitive sound/FX save dependencies have focused regression coverage.
  Increased static event storage must be charged in the current native link.
- Buffered-soak terminal reasons and browser negative witnesses reject unrelated
  failures. Dongle LED indication follows ACK/SOF/PC handoff rather than delaying
  that path; physical timing remains unmeasured.

Scoped notes retain exact commands, source pins, checks and their limits. The
private coordinator checkpoint retains detailed receipts and current lane state.

## Current dependent work

- [verified] PROJECT saves now distinguish an absent set from an oversized
  export and refuse before output. Normal and ASan/UBSan preserve app, edit
  history and nonzero PCM. Independent comparison proves exact output for 40
  valid operations. The default dense fitting pool and supported custom pool
  that actually overflows are explicitly distinguished in the evidence note.
- [verified] The source-bundle test requires all four committed inventories and
  checks any additional tracked imports. Independent bundle checks pass 41
  tests with one existing skip; seven service tests confirm production still
  refuses missing native prerequisites. No selector or startup gate changed.
- [verified] The full e267 browser batch passed 108 parity scenarios, metadata,
  SysEx/routing/MIDI, zero-late/resync DSP storm and Chromium wrapper checks.
  Browser-state, sequencer UI and toolbar regressions passed all three browsers.
  Generated artifacts and strict provenance were integrated, but later C changes
  make them stale. Regenerate from the next reviewed frozen source.
- [verified] Native codec phase 1 uses the existing encoder with explicit host
  backing and a bounded two-pass plain path. Independent normal and sanitizer
  checks compare 387 cases against the exact old implementation, including
  bytes, full reports and failing positions. Constructor aliases and sink
  reentry refuse; root combined-tree normal/sanitizer tests pass. Target compact
  scratch is 43,788 bytes plus a 1,072-byte manifest, not a complete native save
  memory or stack bound. PROJECT provider/emitter and fake transactions remain
  active work. No SAVE UI or real storage is bound.
- The offline CPU1 candidate has host adapter/core fault tests; separate target
  CRT/link/profile and compiler inspection remain. Production enable stays
  rejected and hardware admission is false.
- The offline panel proof covers actual-app display/control/PCM and threaded
  publication, pending independent review. Default startup/HAL/profile stays
  unchanged and hardware LCD completion remains unbound.
- Narrow Docker ownership, build-setup cleanup and soak-receipt prerequisite
  findings are being fixed and independently reviewed. Production native-build
  prerequisite refusal must remain; no test-only adapter admits real builds.

## Native and physical evidence limits

[verified] The fresh e267 native diagnostic uses a fixed FM6 eight-voice
arrangement and links without SDK archives. Original audit: 12 pass, no pending
rows. Fresh inputs and generated bytes are bound in its private receipt. App
239,360 bytes, total BSS 306,768, flash 210,804 and 135,584 bytes of gap are
current for that diagnostic only. Its reserved stacks are not measured runtime
high-water or closed call-chain proof. It has blank LCD/limited HOME controls,
no persistence, pipeline, USB, bootguard or full interactive runtime. Later
source changes require new target evidence before admission.

Last successful full browser build source is e267d7cd. Module SHA
12a607b8cc78e35d8c4bee299dc0ed386e16676c510142dc95aa172a28c61c92
and its actual build record are integrated. Later codec/Capture source changes
require regeneration; historical passing artifacts do not validate newer C.

No device traffic occurred during this release-coordination resume. The physical
FM-1 boots recovered stock V15; D1–D4 and docs/17 still govern firmware-changing
tests. Routine dev-board work uses acknowledged UART entry, application flashing
and fresh results, without repeated full backups/readbacks/factory rehearsals.
Never retry a consumed reset. Mac coordinator alone owns device operations.
Native boot/fail-open, interactive timing/stack/underruns, storage/update,
display/controls/audio and owner listening acceptance remain open.

## Audit, persistence and data lifecycle

[verified] All 803 first-party manifest files at pinned b831 were read, totaling
225,835 lines, with zero hash/count mismatches or unassigned files. Later source
deltas have separate reviews; the current entire tree is not claimed audited,
and its audit mark is not advanced.

Authoritative private continuation:
`scratch/release-coordinator-checkpoint-20261101.md`, atomically mirrored to the
owned Aeon coordinator dataset. Source changes use explicit-refspec pushes with
remote SHA verification. Preserve reviewed branch backups and required CI;
never force-push or merge unfinished work.

Heavy work uses coordinated Aeon lanes of four CPUs and 6 GiB in
`docker-batch.slice`, labelled disposable containers and exact owned staging.
Retain small evidence, delete owned reproducible products, and preserve sibling
worktrees, owner data and transcripts. Mac free space is 1,116 GiB against the
500 GiB floor. The release-readiness automation remains ACTIVE until verified
completion or an owner-requested pause.
