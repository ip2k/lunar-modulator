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
verified through `bf7a09546bc52d9b4126d34f543a75650a5c264b`. It is not a release
or hardware admission. Capture completion, streamed PROJECT persistence,
renderer fault/lifecycle handling, strict native preparation, a private build
worker/API and the host-only interactive owner are integrated. Required final
exact-head CI and real-Chrome acceptance remain. Prior head `13426bdc` CI
41325603135 was superseded without a failed job; Pages 41325603139 succeeded.

[verified] The latest actual canonical simulator build used frozen source
`5197daae`; its generated record is integrated at `13426bdc`. All 108 JS/musl
parity cases pass; glibc agrees exactly in 105 cases and within one LSB in the
remaining three. Metadata, SysEx, MIDI and routing checks pass. A 30-second DSP
edit storm completed 10,341 quanta with zero late blocks or resyncs; 7,049 browser
edits caused zero playback underruns, and Chromium passed all 99 page checks.
Coordinator strict record/drift checks pass. Earlier Firefox/WebKit targeted
state, sequencer and toolbar checks are historical evidence, not a fresh run on
this pin. Scripted checks do not establish real-Chrome visual, device, analog or
listening acceptance. The integrated CLI buffer cleanup changes the engine-source digest; a fresh
actual canonical run is assigned from `bf7a0954`. Until that completes, the
record is stale for current source. Never edit the source digest manually.

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
no-override actual-app proof passed normally and under ASan/UBSan. The separate
selected-Trio pi32 diagnostic linked from exact `7ab28104` and passed the original
12-check audit. Its generated 597-byte project is retained in the actual ELF,
and initialization precedes audio/IRQ setup. Text is 178,744 bytes; BSS is
277,760 bytes with 164,608 bytes to the guard. These are static layout results,
not runtime stack/timing evidence. General project loading, service activation,
reset/ROM return and hardware acceptance remain unsupported.

[verified] The selected-return policy is independently reviewed and integrated
as an offline GPL module. A separately selected target-binding candidate is now
integrated after independent review; its immutable zero qualification refuses
startup before timer, mailbox, P33, app, LCD or audio work. Review corrected a
recorded LCD timeout being treated as healthy completion. Sixteen independent
normal/sanitized host checks pass, including the actual candidate startup body
through typed HAL shims and unchanged default plans.

[verified] A fresh complete target build from `5197daae` passed its original
12-check audit and layout checks after a narrow compiler-fence fix removed an
unavailable synchronization helper. The four source ordering boundaries,
explicit target synchronization and immutable zero qualification are preserved.
The generated code deliberately refuses functional startup before timer,
mailbox, P33, app, display or audio work. BSS is 277,856 bytes, with 164,512 bytes
to the guard; reserved stacks are not runtime measurements. Actual MMIO,
watchdog, timer/mailbox behavior and physical recovery qualification remain
separate; no target reset or ROM-return behavior is admitted.

[verified] The disabled fixed-Trio v2 service contract is integrated after
independent review. It validates the actual retained target ELF, flat image,
project blob, source/object evidence and original audit against operator-owned
trust anchors. Review found and corrected acceptance of an invalid zero entry
address; startup must now be inside the fixed executable section. Coordinator
integration checks pass 137 tests plus six subtests; independent combined
checks pass 375 tests with one expected skip. The separate private API/factory is also integrated after independent review:
392 tests and six subtests pass, with one expected skip. Coordinator checks pass
196 focused tests and 70 combined-tree API/server tests. It remains disabled by
default and loopback-only, returns no binaries, and retains jobs through verifier
cancellation and unconfirmed cleanup. The separately reviewed worker is integrated with bounded evidence acquisition,
operator-owned trust anchors and confirmed cleanup before capacity release.
Independent worker/API composition checks pass 464 tests with one expected skip.
[verified] One real HTTP build through the actual private factory passed from
frozen `5197daae`: 123 target objects, four prepared files and the original
12-check audit. The factory reported success only after verification; the
coordinator independently revalidated the same held outputs with fresh
operator-owned trust inputs. The first attempt exposed read-only copied MSFA
header replacement; the one-line generated-file replacement fix has independent
causal RED/GREEN coverage. Resource/HTTP/cleanup evidence is retained privately;
build products and the container are removed. All seven hardware, installation,
package, release, distribution and ROM-return flags remain false.

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
  default arena in external-workspace mode. The 481,244-byte JSON writer
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
- [verified] Current canonical artifacts are recorded above. Native-only
  additions do not change their inputs; the integrated CLI engine-file change does.
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
- [verified] The selected interactive owner now composes the actual Trio app,
  ordered accepted scanner events, existing PCM queues and framebuffer leases,
  and an injected nonblocking SPI protocol. Independent review and normal plus
  ASan/UBSan proof cover 12,960 exact 64-frame blocks, 216 ordered controls,
  240 row payloads and fault/reentry cases. Coordinator combined-tree checks
  pass four focused tests and all 17 integrated paths match reviewed source.
  The actual rendered frame was inspected without visible label overlap.
  This is host-only: audio readiness during a real startup interrupt, target
  publication, SPI/DMA retirement, memory/stack and deadlines are still open.
- The next PROJECT composition slice stages the real selected app through the
  existing transaction codec before any platform or IRQ service starts, under
  an explicit offline exclusive-owner contract. It does not implement live
  pause, save through an already-running owner, real storage or the SAVE action.
- [verified] CLI process buffers now release on normal, refusal and error exits.
  Independent source-bound normal and Clang ASan/UBSan checks pass 28 actual CLI
  invocations per tool, including the exact module-independent regression body;
  this was not a pytest framework run. The original two 4,096-byte leaks are
  causally reproduced; successful packed bytes remain identical. The core codec
  and audio algorithms do not change.
- The historical general native-build prerequisite refusal remains. The
  separate fixed-Trio private worker has actual execution evidence above,
  but neither that witness nor test adapters enable public installation.

## Native and physical evidence limits

[verified] The fresh e267 native diagnostic uses a fixed FM6 eight-voice
arrangement and links without SDK archives. Original audit: 12 pass, no pending
rows. Fresh inputs and generated bytes are bound in its private receipt. App
239,360 bytes, total BSS 306,768, flash 210,804 and 135,584 bytes of gap are
specific to that frozen diagnostic. Its reserved stacks are not measured runtime
high-water or closed call-chain proof. It has blank LCD/limited HOME controls,
no persistence, pipeline, USB, bootguard or full interactive runtime. Later
source changes require new target evidence before admission.

The latest canonical browser build source is `5197daae`, record integrated at
`13426bdc`. Its actual module SHA is
`e4d0b94f4e05181afeb74f9a004c7a03f00a1370a2a99be204426ae33ef68755`.
The fresh actual private-worker Trio ELF is
`4e8df12f6bca03263d077acef9c32a14d437a8e3bc11fc5eaa8cf345cfce60cc`;
its flat app is 178,744 bytes, SHA
`ee03de799a69410228af0cdff10cc07c3e3685fa51580344dd93ad16a83f2dfc`.
Full app state occupies 239,360 target bytes, distinct from artifact size and
from host ABI size 241,536. Reserved stacks remain unmeasured at runtime.
No installation capability follows from the static diagnostic or build service.

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
worktrees, owner data and transcripts. Mac free space is 1,114 GiB against the
500 GiB floor. The release-readiness automation remains ACTIVE until verified
completion or an owner-requested pause.
