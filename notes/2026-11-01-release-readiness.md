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
`fix/2026-11-01@release-state-corrections`. Reviewed source is pushed and remote
verified through `a68a9e31c8c2ec3a4327b9a6029a7eede3767d31`. It is not a release
or hardware admission. Capture completion, bounded codec phase 1, fault handling,
lifecycle cleanup, exact audit proofs and target-derived test expectations are
integrated. Required exact-head CI and real-Chrome acceptance remain.

[verified] The actual simulator build for frozen source `5c5237b0` passed
108-case parity, SysEx, MIDI, metadata, 30-second edit stress with zero playback
underruns, and scripted Chromium/Firefox/WebKit state, sequencer and toolbar
checks. Generated artifacts were integrated at `b088606e`. Subsequent strict
native packing changes affect the source digest, so another canonical build is
required after the next source batch. These scripted results do not establish
owner visual, device, analog or listening acceptance.

[verified] Pinned musl and compiler-rt sources now close the reviewed native
math/string/remainder dependencies without substitutes or budget changes.
Strict installer preparation rejects skipped or repaired JSON fields; the
combined tree passes 22 focused tests, including the 4096-byte boundary.
The offline CPU0 publication port is independently reviewed and integrated;
seven focused tests pass in the combined tree. Its separate actual target link
and original audit passed. No target startup or hardware profile is enabled.

[verified] Persistence phase 2 and the offline CPU1 candidate are integrated.
The exact-root persistence component linked 134 pi32 objects, passed the original
12-check audit and preserved old PROJECT output normally and under sanitizers;
549 transaction fault cases passed per build. Its conditional incremental memory
charge is 98,036 of 98,304 bytes. This excludes borrowed application storage and
assumes bounded callbacks, caller frames, IRQ nesting and backend allocations;
it is not full application fit or storage admission.

[verified] The cold selected-project loader is independently approved and
integrated. It accepts the fixed starter Trio project only, checks both parses
and all soft-loss counters before application mutation, and refuses redirected
live state. Generated project bytes feed the actual-app oracle. The combined
no-override proof is running. General project loading, native startup and service
activation remain unsupported. An offline selected-Trio target lane is preparing
source; it has no reset import, hardware activation or ROM-return claim.

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
  was too large for native persistence. The integrated streamed path now has a
  separately bounded component proof; workspace APIs alone were insufficient.
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
  integrated with independent review and exact-root component evidence above.
  No SAVE UI or real storage is bound.
- The offline CPU1 candidate has host adapter/core fault tests; separate target
  CRT/link/profile and compiler inspection pass for the offline candidate only. Production enable stays
  rejected and hardware admission is false.
- The offline panel proof covers actual-app display/control/PCM and threaded
  publication, independently reviewed and integrated. Default startup/HAL/profile stays
  unchanged and hardware LCD completion remains unbound.
- [verified] Docker cleanup now requires immutable ID plus expected ownership
  labels, refuses unsafe CID files and retains unconfirmed jobs/evidence. Build
  setup cleanup removes only acquired paths; after a container-create attempt,
  mounted snapshots remain until owned absence is confirmed. Independent fake
  tests pass, and root combined-tree focused checks pass. No daemon was used.
- [verified] Soak receipts now require readiness, valid queue depth and a run
  within CPU1 lifetime. Independent negative probes refuse missing/malformed
  prerequisites; root parser checks pass. These are receipt tests, not analog
  or physical acceptance.
- [verified] Shared pipeline startup/finish waits escape permanent poison even
  when the clock stops. Actual protocol tests preserve first error and retained
  ownership. Test-only ABI fixture expectations now use measured full candidate
  RAM; native and 32-bit runs retain the unchanged budget and refusal policy.
- Production native-build prerequisite refusal remains; no test-only adapter
  admits real builds. The private service still needs a genuinely supported
  native profile and prerequisite integration.

## Native and physical evidence limits

[verified] The fresh e267 native diagnostic uses a fixed FM6 eight-voice
arrangement and links without SDK archives. Original audit: 12 pass, no pending
rows. Fresh inputs and generated bytes are bound in its private receipt. App
239,360 bytes, total BSS 306,768, flash 210,804 and 135,584 bytes of gap are
current for that diagnostic only. Its reserved stacks are not measured runtime
high-water or closed call-chain proof. It has blank LCD/limited HOME controls,
no persistence, pipeline, USB, bootguard or full interactive runtime. Later
source changes require new target evidence before admission.

Last successful full browser build source is `5c5237b0`, integrated at
`b088606e`. The actual module SHA is
`1562f4d6660c2df9a333dc796905cb497f39002b7c4389a54a677026ec010fa4`.
Later persistence and packing changes require regeneration. A canonical build
and acceptance batch is running from frozen `a68a9e31`; no result is claimed yet.

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
