# Hand-off package — Lunar Modulator

**INTERGALACTIC MODULATION STATION.** Lunar Modulator is open firmware for
the M-VAVE FM-1; until 2026-10-01 the project was called "Open firmware for
the M-VAVE FM-1". Naming rules are in `CLAUDE.md` → "What this is".

Written 2026-09-06 at the end of the research session that created this
repository, so a fresh Claude project (or a human) can continue without the
original conversation; last updated 2026-10-11. Read this first, then
`DEVELOPERS.md` (the README is the product page), then `docs/`.

## Installable firmware image resumed — 2026-10-11

[verified: current physical state] The diagnostic image is installed on the
owner's FM-1. Full 1 MiB readback matches target `df6c963e…`; the exact physical
installation and independent replay are recorded in
[the boot-trial note](notes/2026-10-11-diagnostic-boot-trial.md).
One reviewed target reset transmitted at timestamp `1791775833.548683`;
its reply detached and the post-request binding check failed. Passive sysfs
then found new same-port ROM bus 3/device 26 at `1791775855.3214695`.
The immediate one-use chooser stopped before opening SG or probing RAM because
the capture includes a new-ROM standard CDB `1e0000000100` absent from its
allowlist. Independent capture review `a514eff1…` accepted exact paired
transfers, failed media-lock CSW and illegal-field sense as Linux-compatible;
it does not prove the process origin or ROM internals. Preserve the consumed
reset and chooser; no retry or original snapshot refresh. At that chooser stop,
diagnostic execution, display and recovery remained unaccepted. A distinct
reviewed successor subsequently completed exactly INQUIRY36 and FD07 IN32 at
`1791778274.585474`, returning coherent stage6/result0/elapsed20000/heartbeat1976
and the native write pointer. Independent physical review `99d3c4da…` and
native/source interpretation `2f6090d4…` accept conditional diagnostic execution.
Stage6 precedes P33 lock acquisition; visible pixels and recovery cause remain
unproved. Preserve its own consumed
marker and all owned capture evidence. See
[the first RAM-read note](notes/2026-10-11-diagnostic-first-ram-read.md).
No camera was identified in the bench's passive video-device inventory.

[verified: recovery preparation] The returned-ROM backup source `afeefe7b…`,
restore source `f5835237…`, and shared provenance helper `8fb33694…` are frozen.
The private genuine composed gate passed 182 unique cases: 179 repaired V3
cases in 16 Hera chunks plus three unchanged passing V2 actual cases, with
explicit source-version provenance. Independent review accepted aggregate
`87848de7…`; failed fixture runs remain preserved. Root's returned-stock reset
source `7af061b0…` now pins the accepted restore verifier `f5835237…`; its focused
58-case successor gate passed in 16 Hera chunks; final independent retained-evidence
review accepted `99643fd4…`. The closed private stock return capture wrapper
and pure-file preparer passed 60 unique mixed-version cases; independent review
accepted `715e4236…`. Six additional closed sources were staged without hardware
access, actual receipt `e60e3f8b…`, independent acceptance `ad6ad938…`. See
[the recovery design](notes/2026-10-11-returned-rom-recovery-design.md).

[verified: staged files only] Probe helper/native `8fb33694…`/`8ad32e42…` passed
101 unique cases plus one actual-private modeled smoke; independent review
accepted `cd990cc8…`. The chooser passed 26 unique cases plus its modeled smoke;
review accepted `70954552…`. The target-reset wrapper and chooser have now
been consumed as described above. Neither stage-probe
wrapper was launched. Source-only staging V2 wrote 31
exactly pinned files, checked the original 35-member packet and all 45 required
sources, and retained the completed install journal separately. The recovery
executor remains closed. Receipt `7ea7bfbd…` and independent review `2bbe8c01…`
prove file staging only; no device command, factory admission or activation.

[verified: earlier physical recovery boundary] A complete diagnostic install
and stock restore rehearsal passed both full 1 MiB readbacks, target `df6c963e…`
and stock `96006a51…`. A separate one-shot reset then produced normal same-port
USB and the exact known `FM-1_092` identity without an owner power cycle. The
later fresh matching stock backups and current diagnostic install preserve
all earlier consumed markers and receipts. These results prove restoration
and stock operation from the loader; they do not prove diagnostic boot or
rescue from an interrupted application write.

[verified: verification and backup state] The sealed older whole-suite gate
completed 6,389 collected cases in 16 Hera chunks: 6,352 passed, 35 skipped,
two expected failures, zero failures/errors. The strict private selector gate
passed 287 cases without skips. Native SG test portability repair passed 79
cases plus its smoke. Later recovery additions have the separate gates above.
GitHub run38201658769 on exact checkpoint `a6bce57abcef99ec8c1f5b1a33a83e1273840f68`
passed all thirteen jobs. The feature branch is
`feature/2026-10-11@installable-firmware`, with checkpoint
`aca0e686…` committed and remote-SHA verified. Its exact-head run38202646517
remains in progress; later uncommitted successors are outside that snapshot. No PR or
merge has occurred.

Next: integrate the distinct stopped-chooser recovery evidence admission,
its exact95-case sixteen-chunk Hera gate and actual-file replay, then review
separate backup and restore successors for the completed RAM-read lineage.
Preserve the original timestamp and consumed markers. Capture fresh matching target backups,
restore stock under the new binding and verify normal identity. The new closed
interrupted-restore evidence kernel `cef2d0ea…` passed 55 cases in 16 Hera chunks;
independent review `e0401d94…` accepted only its prefix/dual-dump scope. Genuine
stopped-lineage/current journal/capture and distinct partial-NOR acquisition
admission remain required; execution is unconditionally closed. Native write
completion is not NOR success: uncertainty clears only on matching FD05 readback.
The separate original-lineage evidence helper `dbe4191c…` passed all 33 unique
cases in sixteen Hera chunks, including one genuine private-input interrupted
program model. Final independent review `82e9b1a7…` accepted its closed evidence
scope and exact source/runtime receipts.
It preserves the genuine completed-backup/SDK/consumed-marker/current-journal
chain and deliberately leaves terminal capture, live acquisition and execution
unverified. It cannot open hardware or prepare an executable campaign.
The active goal remains a working physical diagnostic with verified recovery,
documented procedures and completed required review/CI/integration gates.

The following entries are historical checkpoints, superseded where the physical
result above supplies later evidence.

[verified: verification checkpoint] Rehearsal tests `95879aa0…` passed all
125 cases in 16 Hera chunks plus the separate actual-input modeled smoke,
zero failures/errors/skips/OOM and all containers removed. Independent retained
evidence review is pending. The distinct post-rehearsal stock reset `743ac876…`
/ tests `2ebf29e6…` passed its actual-input modeled smoke; final 107-case
campaign is running in 16 Hera chunks.
Bench packet v2 passes actual file-only preflight (`f6964845…`); private wrapper
`173a9705…` is independently reviewed and staged. No physical erase/program or
reset has run. Final test/review evidence gates one install/readback/restore
rehearsal, then separate stock reset and diagnostic boot/recovery work.

[verified: CI collection repair] Checkpoint `6188d8fc…` was pushed and remote
SHA verified. GitHub run 38187580322 failed both Python collection jobs because
bare sibling fixture imports require `tests` on Python's path. Pytest now sets
that path, matching Hera, and the repository interpreter collects all 107 reset
cases. Frozen device sources/tests are unchanged. Fresh CI is still required.

[verified: WIP transport checkpoint] Exact SDK rehearsal source
`f6964845…` is saved with its [work note](notes/2026-10-11-sdk-rehearsal.md).
Focused Hera16 tests and independent review are pending final freeze; no
physical erase/program has run. Complete install+restore, then separately
reviewed reset and diagnostic boot/display/recovery remain outstanding.

[verified: reviewed policy checkpoint] The SDK install/restore policy passed 61
checks plus an actual-ELF smoke, and the baseline-only fixed-loader reset passed
185 checks, each in 16 Hera chunks. Independent reviews are saved in
[SDK policy review](notes/2026-10-11-bound-sdk-diagnostic-review.md) and
[reset review](notes/2026-10-11-fixed-loader-baseline-reset-review.md). Both
actual-file SDK factories accepted today's backup/campaign evidence without
opening hardware. Today's backups reproduce target `df6c963e…`. The physical
install/readback/restore adapter is under separate review; no flash mutation has
run. After any rehearsal, the baseline reset's no-later-commands assertion is
invalid and requires a separately reviewed reset provenance path.

[verified: physical fixed-loader backups] One fresh FM-1_092 identity and soft
key took USB 3-2 device 22 to same-port ROM device 23. The fixed loader reader
exited 0 after 8,757 successful operations; both new 1 MiB dumps match each other
and the historical baseline (`96006a51…`) byte for byte. Passive usbmon matches
all 8,756 vendor CDBs and transfer lengths in order. No erase/program/reset was
sent. Private evidence is copied off bench01 under
`build/fixed-backup-physical/`; public-safe hashes and limits are in
[the physical backup note](notes/2026-10-11-fixed-loader-physical-backup.md).
The loader remains active at device 23. Next: separately reviewed active-loader
reset, SDK transaction binding/physical adapter, install/readback/restore, then
diagnostic boot/display/recovery. This is not goal completion.

[verified: fixed-loader reader checkpoint] Exact fixed-reader source passed 80
Hera checks in 16 parallel chunks, no skips/errors/OOM. Its independent review
is [saved](notes/2026-10-11-fixed-loader-backup-review.md); campaign details and
hashes are [recorded](notes/2026-10-11-fixed-loader-backup.md). Inputs are staged
privately at bench01 `/home/claude/fm1-fixed-backups-20261011/stage`, with that
fixed parent as the entry-consumption boundary. The completed physical campaign
used 47 exact RAM uploads and two full reads, no flash writes or retry. A concrete 1 MiB SDK
raw target was emitted from historical backups (SHA `df6c963e…`), but physical
install/restore binding and diagnostic boot/display acceptance remain pending.

[verified: offline SDK raw checkpoint] The SDK-only emitter now passes 95 Hera
checks in 16 parallel containers, with actual private ELF and historical backup
fixtures and no skips. It reconstructs the raw application and CRC/length deltas
while preserving protected bytes; original SDK-free/original-loader gates remain
separate. Independent review's ELF-architecture finding is fixed. See
[the raw SDK evidence](notes/2026-10-11-sdk-raw-diagnostic.md) and
[its review](notes/2026-10-11-sdk-raw-diagnostic-review.md). The diagnostic still
has no physical boot/display acceptance or physical write permit. Next: exact
separately bound SDK install/restore adapter and physical diagnostic/recovery
verification against the now-matching fresh backups.

The agreed first milestone is a diagnostic image that boots, shows a display
probe and retains recovery; playable Lunar follows later. Do not treat a
component checkpoint as completion. Active branch:
`feature/2026-10-11@installable-firmware`, managed checkout
`/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`,
from main `b335dc2c450473dc375163aec7fa679e1b099cc3`.

[reported: owner, 2026-10-11] This is now the explicit active goal: keep working
on recovery and verification until the diagnostic image is verified and
installable on the physical FM-1. Completion criteria and the current dependency
plan are in [the goal note](notes/2026-10-11-installable-firmware-goal.md).
The next work resolves a minimal startup architecture and the RAM loader's
retained-configuration initialization before a concrete installation campaign.

[reported: owner] The earlier power cycle returned to the normal screen.
[verified: 2026-10-11 receipt] A subsequent single, reviewed RAM-only probe
started from fresh FM-1_092 identity and same-port soft-key entry, uploaded
exactly two fixed blocks and jumped once. USB disconnected immediately and
the same port re-enumerated UBOOT. This does not independently prove marker
or P33 execution. No flash command was sent; no flash reread was performed.
Device commands stopped after that attempt. The owner subsequently asked
whether UBOOT can reboot without a physical power cycle. The exact loader
FC0C argument-1 body requests a core
soft reset, but loading it can parse stale RAM configuration and write NOR
status registers. Its new guard is simulation-only while that initializer
boundary remains unresolved. A separate minimal RAM reset stub and exact-image
guard pass offline build, static review and 170 combined Hera checks. Its
separately reviewed private adapter passed 48 isolated Hera mocks and was
attempted once: normal USB returned about 1.5 seconds after jump, followed by
a fresh read-only FM-1_092 identity reply (exact known checksum-bug frame).
Bench access is restored without an owner power cycle. No flash command or
flash reread occurred. The incomplete jump reply was latched without retry;
the consumed adapter cannot be reused. Bare-ROM reset opcode, independent
CPU-reset witness and full broken-app recovery remain unproven. See
[the reset bench result](notes/2026-10-11-fm1-core-reset-bench.md) and
[the reset audit](notes/2026-10-11-loader-run-app-reset.md).
See [the bench result](notes/2026-10-11-fm1-ram-probe.md).

**Build on Hera (`claude@192.168.1.48`); aeon is under owner maintenance.**
Use local `/home/claude/mvave-fm1` assets; avoid NFS paths. Three parallel target
profiles reproduce previous binaries and pass SDK-free audits. Prospective
SPI and fixed recovery-request components compile separately with no named
unresolved helpers, but remain excluded from boot images. Host fault checks
exercise both components. No installable diagnostic package or confirmed
custom application execution.

TIMER4 and recovery have 36 passing Hera host checks, including the stock
40 MHz oscillator alternative. An offline 700-byte
RAM recovery probe now has a concrete plan in `firmware/ram-recovery/README.md`;
its separate exact-image transport is tested and has no CLI.
The owner deferred Cynthion and subsequently authorized leaving the device in
UBOOT or hung until a later physical power cycle. The immediate power-cycle
restriction below is historical and superseded. Independent review conditionally
supports one exact 700-byte no-flash RAM probe with fresh unit/port binding,
no retries, and a durable receipt. Post-jump enumeration alone cannot prove
that P33 executed. Latest verified pushed source checkpoint:
`38a7d53cd101c03bd5319c0f202b8f4dfc5bbc57`, including the actual reset bench
receipt, native startup ownership contract, audited entry guard and offline
display/recovery composition. The agreed installable-image milestone remains
unfinished.

Recovery development now adds a persistent whole-flash protocol model, durable
transaction artifacts and a resumable fixed scratch-sector restore mode. The
physical adapter retains its exact existing sector/payload allowlist; wider
application writes and USB_KEY recovery remain physically unproven. Reviewed transaction/
read/restore/transport checks pass 41 tests on Hera; all 497 interruption and
corruption cases pass, with 32 campaign checks. The full Python suite was split
into 16 isolated Hera containers on exact source `38a7d53c`: all 5,851 unique
collected nodes across 131 modules ran exactly once; 5,813 passed, 36 skipped
and two were expected failures, with zero failures/errors or unexpected passes.
Root and independent receipt review verified the frozen source, every shard,
resource limits and successful removal of all sixteen containers. The 38
JUnit skipped/expected-failure nodes and reasons match the preceding run.
The earlier four manual-SVG discrepancies were fixed by stable summation;
standard full collection also exposed and resolved two peer-test imports.
Explicit diagnostic-profile propagation and raw FM-1_092 target validation
passed independent review. A separate injected-transport diagnostic adapter
passed independent review and 115 combined checks (two optional skips); the
fresh green full run includes that adapter, reset guard, entry audit and
display/recovery composition. The adapter has no physical opener or CLI.
This stream remains WIP; do not merge an unfinished checkpoint. See
[the recovery runbook](docs/17-recovery.md) for procedures and physical limits.

[verified: final live GitHub run and saved JSON] Exact-source
[CI run 38179739714](https://github.com/ip2k/lunar-modulator/actions/runs/38179739714)
completed successfully at 2026-10-11 22:37:17 UTC: all thirteen expected jobs
passed on `38a7d53cd101c03bd5319c0f202b8f4dfc5bbc57`. Later documentation
commits are not that CI head. The final snapshot and root handoff are in ignored
`build/recovery-python-shards-entry-bringup/`, covered by the refreshed
`root-supplemental-sha256.txt`; the original 152-entry Hera manifest stays pinned
unchanged. This is a software checkpoint, with no new PR, merge, installable
package or physical acceptance. Startup/core/exception premises remain the
next dependency, as detailed in the native startup contract below.


Offline raw flash profile/target validation now checks both complete backups,
exact recorded geometry, actual app/ELF/audit inputs, protected bytes and derived
changed sectors. It emits JSON evidence only; no physical writer is opened.
The [final stock SPL contract review](notes/2026-10-11-stock-spl-final-contract.md)
resolves the ordinary XIP entry and conditional callback, but does not prove
core, exception or complete RAM ownership. The
[native startup contract](notes/2026-10-11-native-startup-contract.md) preserves
the independent core/exception reviews: no finite secondary-core hold
acknowledgment, masked exception-delivery specification or safe SSP transition
was established. A separate 26-byte no-stack entry prerequisite now passes
strict native auditing, final independent review and 178 focused Hera checks.
The display/recovery controller passes 117 combined component checks with one
optional private-stock fixture skip; five native C objects link relocatably
without unresolved runtime helpers. These offline components do not enable
board output or form an installation candidate. See
[their evidence and limits](notes/2026-10-11-offline-entry-and-bringup.md).
Stock watchdog setup/feed instructions are documented in ignored
`build/watchdog-contract-review.md`; this does not establish inherited SPL
state or safe cross-core P33 ownership. Startup/core/exception ownership,
calibrated timer/clock, watchdog, PA2 and
recovery from the actual application context still need resolution. See
[the session note](notes/2026-10-11-installable-firmware.md) for artifact hashes,
checks, source-navigation limitations and exact next steps. Recovery code and
its limits are in `firmware/recovery/README.md`. Preserve stock SPL/OTA/cfg and
partition guards; review the concrete candidate/recovery plan and compare
backups before any flash mutation. Full broken-app restore remains unproven.

## Active work — 2026-10-10

Live `origin/main` is `bdba4476570b0a77d13c76a38dfb3bcfd364277b`. The combined
Warble/Repeat/PSX candidate is open as [PR #140](https://github.com/ip2k/lunar-modulator/pull/140)
on its separate branch and is not merged to `main`. Its actual regenerated
source checkpoint `3519c3857d9bddb8007e14de7ef84525ef8df96a` built 108/108
simulator scenarios, with 24 non-test audio effects; the committed Wasm/build
record and both source hashes match. Expanded native checks pass 271 tests,
and the corrected Repeat pins/enums and metadata contract pass 22 focused
checks. The reviewed documentation bundle and PR132 CI configuration are
already integrated. Fresh exact-head CI and normal reviewed merge remain
required; earlier strict-browser failures remain recorded and are not waived
by candidate checks.

Merged PR #104 links an inert offline diagnostic variant, but no full-DSP
Lunar application has run on or been installed on the FM-1. The offline
diagnostic is not a physical runtime test. Full-image restoration,
broken-app recovery and hardware audio remain unverified; no device traffic
occurred in the work summarized here. The owner's reported Sound 2 A/B
crackles remain unresolved and require a by-ear retest; automated Safari/UI
and audio-capture evidence does not replace that judgment.

Four complete demo songs, full-chain renders, browser project workflows and
owner listening reviews are not complete. See the current
[demo prerequisite review](notes/2026-10-09-demo-prerequisite-review.md).
The whole-code audit is not blanket-closed: findings are classified by demo
impact in the audit/remediation ledger, while developer-tool, unused-module,
and hardware-readiness items remain tracked without being treated as automatic
song blockers. Re-read the dated reconciliation sections below as history,
not as current branch/PR status, and check live remote refs/checks before
continuing integration.

## Audit remediation — 2026-10-08

PR #100 merged at `3c7b6a0`; its full CI passed. The managed
`full-code-audit` worktree holds `feature/2026-10-09@envelope-graph`.
The completed source review is recorded in
[its report](notes/2026-10-07-full-code-audit.md); verified corrections,
test results and remaining firmware prerequisites are in
[the remediation ledger](notes/2026-10-08-audit-remediation.md).
Native sanitizer and four-profile target compile checks pass (164 unique
objects per profile, now including the previously omitted state codecs). This is not a
linked firmware application: simulator arenas and persistence scratch exceed
device SRAM and require a device layout. No hardware traffic in this work.
PR #100 holds this batch. The codec suite passes (105 passed, one corpus skip),
including compressed stream termination and duplicate-field rejection. The committed Wasm has been rebuilt: all 104 parity scenarios pass and
Chromium's LAN page storm reports zero underruns. PR #100 merged the rebuilt
commit as `3c7b6a0`; CI run `37890685197` passed all jobs. The runtime choice
(independent permissive board implementation versus Felucca GPL reuse) is
pending; linked diagnostic and inert handover preparation do not establish
device runtime behavior. The concrete next milestone
and memory/link/audio gates are in
[the device bring-up plan](notes/2026-10-08-device-bringup-plan.md). The
editor PR #99, envelope PR #101 and save-durability PR #103 are merged.
The linked diagnostic in merged PR #104 is an independently authored,
permissive 200-byte image with guarded stock-component staging and 71 focused
tests; it has not run on native hardware. Stock handover and visible transport
remain pending. The envelope work implements zero-default Delay, Log/Smooth
curves and the live graph; its focused tests, 104 parity scenarios and
4,621-screen layout sweep pass; see
[the envelope note](notes/2026-10-09-envelope-graph.md).
Completed review does not mean all findings or dead-code candidates are
remediated; the remaining-work ledger records the source/status reconciliation.

## Latest hardware update — 2026-10-07

The original research summary below is historical. The owner authorized
staged recovery experiments, superseding the prior dump-and-restore
prerequisite. Soft-key UBOOT entry works on FM-1_092; the audited loader ran
in RAM, matching full backups were saved off-host, and an unused 4 KiB
sector was programmed and restored with the entire flash unchanged
[verified: [bench note](notes/2026-10-07-fm1-softkey-bench.md)]. Full-image
restoration and a Lunar application on hardware remain untested. Normal
boot after both the initial dump and the restoration was owner-confirmed. The
mobile hardware editor is explicitly deferred until installable firmware; see
[its resume plan](notes/2026-10-07-mobile-advanced-editor.md).

## 1. Where things stand

- **Owner:** Sean (GitHub `ip2k`). Works from a MacBook with Claude Desktop /
  Claude Code; has **one FM-1** on his desk (do not brick it) and has downloaded
  the official updater disk image **`M-UPGRADE-FM1*.dmg` into `~/Downloads`**
  (that updater embeds **V14**, not V15; V15 is only on the CDN, docs/02 §1).
- **This repository** is the research output: nine documents, three tools, one
  research log, plus bench session 1 (`notes/2026-09-06-bench.md`): the unit
  answered the identity query as `FM-1_015`, V15 is unpacked and diffed against
  V14. At that research checkpoint, this project had written nothing to the device. The case has been
  opened for photos (2026-09-29, `photos/2026-09-29/`, described in
  `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`).
- **The owner's unit now runs Baud Girl's FM-1+VA**: the owner installed it
  through Baud Girl's browser installer, and the unit identifies as
  `FM-1_092` [verified 2026-09-29]. The `FM-1_092` package is V15 plus 90 hook
  patches and 110 KB of appended code, with VM moved to `0xD9000` (note §3).
  The way back to stock is V15's `.fwsc` through the same installer.
- **Elsewhere, non-stock firmware runs on FM-1s**: Echomatter's `FM-1_016`
  (2026-09-04), and since 2026-09-26 **Baud Girl's FM-1+VA**, a modified V15
  with a virtual-analog engine installed from a browser (`FM-1_020` …
  `FM-1_092`; source not published). See docs/04.
- **Open firmware runs on FM-1s too** (2026-10-05,
  `notes/2026-10-05-community-repos.md`): Felucca 1.0 (hugelton) and its
  fork SLOOP 2.2 (isod89), bare metal and GPL-3.0-only, install and roll back
  through the stock path; fm1-nes (Keitark) runs an AC79 SDK app on one V14
  unit, written through mask ROM [reported]. Their code maps the board
  (docs/01 §3.1): audio is ALNK0 (I2S) to an external codec, not the internal
  DAC, and the encoders are scanned in the key matrix. Stock V15 also enters
  mask ROM on the SysEx "soft key" `F0 22 24 35 7D F7`, which was subsequently verified on this unit under the revised staged
  policy (see the latest hardware update above).
- **Where the repo lives now:** `~/Developer/mvave-fm1-firmware` on the
  owner's MacBook (the folder keeps its old name), branch `main`, remote
  `ip2k/lunar-modulator` (published 2026-09-06 as
  `ip2k/mvave-fm1-open-firmware` and renamed with the project on
  2026-10-01; GitHub redirects the old URLs). Moved there on
  2026-09-06 from the orphan branch `claude/mvave-fm1-open-firmware-ly2w6u` of
  `ip2k/busybar-dual-timer`, which the cloud session used because its GitHub
  integration could not create repositories. That branch was deleted on
  2026-09-06.
- **Unrelated to the BUSY Bar project.** Do not mix the two.

## 2. The ten facts that matter

1. SoC = **JieLi AC791N** (WL82), two custom **pi32v2** cores at 240 MHz
   (stock: the OS on cpu0, the msfa voices bare-metal on cpu1 [inferred],
   docs/11 §2), 578 KB SRAM, 1 MB flash (probably in-package), XIP from
   `0x02000000`, RAM at `0x01C00000`. Marking `C156211-11B8` (aroum's unit) /
   `C188612-11B8` (the owner's), LQFP48.
2. Stock firmware = JieLi AC79 SDK (FreeRTOS-derived kernel, closed `.a` libs
   for BT/audio/fs/cpu) + M-VAVE glue + **Google msfa (Dexed) FM engine**.
   Verified here: msfa algorithm table at `0x8C46C` (V13) / `0x8CBCC` (V14) of
   `app.bin`, with the Dexed-family fix in algorithms 4 and 6.
3. Update = **USB-MIDI SysEx**, device-pull protocol, **CRC16 only, no
   signature**, chip key `0x980F` in the package. Two stages: verifier in the
   app → reboot into a RAM OTA loader (`4D4A:4155`) → flash write → reset.
4. **The step-1 gate is a same-version refusal; content is not
   authenticated.** Baud Girl measured on hardware that a package with the
   running version stops after 9 requests, even when its contents differ,
   while any other version installs. Echomatter's `FM-1_016` and Baud Girl's
   `FM-1_020` … `FM-1_092` all went through the stock path, with rollbacks to
   V15. Two further reported facts: the OTA loader **can rewrite the flash
   head** (`uboot.boot`, `isd_config.ini`), so keep it byte-identical; and a
   loader left waiting after step 1 (`ota-FM-1`) can be resumed (docs/03 §5).
5. **No recovery path proven on this project's unit.**
   - Single flash bank, no debug pads or buttons. The one candidate header
     was the battery connector's leads (2026-09-29).
   - AL-255's verdict: NO-GO for non-stock flashing. This is the gate for
     everything.
   - Our `USB_KEY` dongle, which should open it, is specified and implemented
     (docs/10, `dongle/`), not yet tried.
   - Since 2026-09-16, other owners report that mask-ROM USB boot works on
     *their* FM-1s with czietz's simpler Pico dongle. One of them backed up
     and wrote firmware that way [reported: issue #2, docs/10 §1.1].
     FM-1-transporter (kurogedelic) and fm1-nes report dumps and writes
     through mask ROM too (docs/10 §1.1, docs/04).
6. Most promising recovery: JieLi **`USB_KEY`** (`0x16EF` bit-banged on D+/D−
   at ~50 kHz at power-up, ACK = both lines low 1–2 ms, then SOF clock
   detection) → mask-ROM "UBOOT1.00" mass-storage mode → `jl-uboot-tool`
   with its `wl82loader.bin` (`0x1C02000`) or vendor `isd_download`.
   - The clock is D+: czietz's dongle reached UBOOT mode that way on two
     FM-1s (issue #2).
   - kagaimiq's `usb-key.md` and the diagram in `how-to-enter-uboot.md`
     agree; only that page's prose says D−.
   - Try D+ first (docs/10 §1 item 3).
7. Toolchain = JieLi's closed **Clang/LLVM 4.0.1** fork (`pi32v2` backend),
   Linux build available from `pkgman.jieliapp.com`; AL-255 built C++11 with
   it. No Rust, no GCC/LLVM upstream, no JS runtime.
8. Vendor SDK `fw-AC79_AIoT_SDK` (Gitee, current to V1.2.13; our pin is the
   V1.2.13 libraries at `e30b1ee` since 2026-10-05, never its SPL or loader:
   the key check it carries is inert on the FM-1, gated by
   `tools/jieli/audit_link.py` and `tools/jieli/package_guard.py`, CLAUDE.md
   trap 11) is Apache-2.0 (with GPL parts, docs/12 §6) with a
   public register map `WL82.h`, linker scripts, `demo_hello`, flashing tools,
   `wl82loader.bin`, a JTAG/debug-TAP folder, and datasheets; ~110 closed `.a`
   libraries per CPU. JieLi's `fw-Bootloader` (Apache-2.0) targets wl82.
9. **schwung-movy is not portable** (TS + Rust on a quad-A72 Linux box). Reuse
   its *design*: 8-knob parameter pages (FM-1 has 8 knobs), Move-style
   sequencer semantics, `seq-core` as a desktop test oracle.
10. USB IDs: normal `4C4A:C755` ("FM-1 Midi" + "FM-1 Audio" UAC1), OTA
    `4D4A:4155`. Identity query `F0 00 32 45 00 00 00 40 7F F7` → 41-byte
    reply `F0 00 32 45 58 01 00 00 23 4D 5A 44 …` (verified; the owner's unit
   decodes to `FM-1_015`, see docs/03 §2).

## 3. Decisions taken

- Target **L1** first (open application on the vendor SDK), then open
  bootloader (L4), then blob removal (L2); an open compiler (L3) is out of
  scope unless a contributor wants it. See docs/05.
- **Recovery before any flash.** Bench work is read-only until docs/07
  Phase 2 is done. Rules of engagement in docs/07 §4.
- Do not port Movy; reimplement in C with Movy as the reference (docs/06).
- Never commit vendor firmware (`.fwsc`, `app.bin`) or the JieLi toolchain;
  `.gitignore` enforces the first.
- Confidence marks **[verified]/[reported]/[inferred]** in all docs; keep them
  honest (the owner's other projects work the same way).
- License MIT for our material.

## 4. Open questions (ranked)

1. Does `USB_KEY` reach the AC791N's mask ROM through the FM-1's USB-C port,
   and with which clock/data polarity and power sequence? Reported yes on two
   other FM-1s (issue #2, docs/10 §1.1):
   - the clock is D+;
   - the FM-1 is switched on while the key runs;
   - the cable is then moved to the PC.

   Not yet tried on this project's unit; try polarity A first.
2. ~~What does the step-1 verifier compare?~~ Largely answered (2026-09-29,
   [reported] Baud Girl): it refuses the running version; whether by version
   string or file list is still open, and matters little.
3. Knobs: `RW1` is a potentiometer (MASTER, probably) and the other seven are
   encoders ([verified] owner's photo 2026-09-29); still to reconcile with the
   firmware's 2 hardware decoders + 2 ADC channels.
4. Flash: in-package or discrete, exact size (JEDEC ID)?
5. AC791N variant and pinout; UART and debug-TAP pins reachable on LQFP48?
   There is no header: the 3-pin "header" left of U2 is the battery
   connector's leads (2026-09-29). Still unread: the bottom-side SOIC-8 `U12`
   (charger or external flash?) and the SOP-10 `SLS316D` (docs/09 §5).
6. ~~Does the SoC enumerate on USB with the power switch off?~~ No (verified
   2026-09-06): the unit vanishes from USB when switched off, so the switch is
   the power-up moment for the `USB_KEY` attempt.
7. Any GPL-only Dexed code in the stock image (licensing lever)?

## 5. Immediate next actions (in order)

1. ~~Move the repo.~~ Done 2026-09-06: `~/Developer/mvave-fm1-firmware`,
   pushed to the repository now named `ip2k/lunar-modulator`.
2. ~~docs/09 §1–§3.~~ Done 2026-09-06 (`notes/2026-09-06-bench.md`).
3. ~~Power-switch-off enumeration test.~~ Done 2026-09-06 (no enumeration when
   off). Still open: the case-open photo list (docs/09 §5).
4. **Buy JieLi's "JL USB Updater 4.0" dongle** (US$8–18, AliExpress/Taobao;
   docs/07 §2.1) plus a USB-A-female-to-USB-C-male adapter, and use it with
   jl-uboot-tool on a Linux PC for read-only dumps (docs/10 §5). The RP2040
   dongle in docs/10 is the open fallback (UF2 from CI). Ideally also a
   JL_AC79_DevKit or a second FM-1 to rehearse on.
5. ~~Contact aroum and AL-255.~~ Done 2026-09-06: AL-255 PR #3 (V15 package),
   comments on their PR #2 and issue #1, aroum issue #2 (docs/04). Watch those
   threads for replies before posting anything further.
6. **Baud Girl's FM-1+VA (2026-09-29).** Done: `FM-1_092.fwsc` diffed
   against V15 (note §3; the package stays in `scratch/`). Still the owner's
   call: (b) whether to contact Baud Girl about the FINDINGS document and
   emulator; (c) whether AL-255's thread should hear about the same-version
   finding (oss-contributions rules); drafts for both are in `scratch/drafts/`,
   unsent. The owner installed FM-1+VA on the unit themselves; docs/07 §4
   still governs this project's own images.
7. **Engine / plugin platform (docs/11, 2026-09-29).** The feasibility report
   says: Schwung modules from source through a shim (subset), Mutable
   Instruments engines first (Plaits' light engines, Braids), and a static
   engine registry before any loader. **Stage A, 2026-09-30**, in `engines/`:
   the API and desktop renderer; sound engines Macro, Shapes, Macro Heavy and
   Six-Op FM from Mutable code; effects Plate, Ensemble and Diffuse; the
   Schwung v2 shim with Sophie and PSX Verb compiled through it unmodified;
   about 360 engine tests, also run 32-bit and under ASan/UBSan in CI
   (`engines/README.md`). The exit test is met: at the upstream rates the
   engines match upstream Mutable code sample for sample or within 0.5 LSB,
   which found and fixed a Shapes block-size bug (drift and a crash). Left
   before stage B: Shapes' memory (207 KB for 12 voices). Since 2026-10-01
   the Mutable engines run at their native rates (Braids 96 kHz, Plaits
   47,872.34 Hz) through `fm1_resampler.h` and match upstream at 44,118 Hz. Six-Op
   FM's 23 patch names that are trademarks or a person's name are shown
   under names of our own since 2026-10-01, because the browser simulator is
   going public; `-DFM1_SIXOP_ORIGINAL_NAMES` restores them for personal
   builds (`engines/plaits-heavy.md`). Stage B, the pi32v2 benchmark and a
   `-fPIC` test, wants the AC79 dev board from item 4
   (the JL-AC79-DevKit V1.0 with an AC7916; docs/07 §3).
8. **Sequencer (docs/12, docs/13, 2026-10-01).** An Elektron-style
   sequencer with parameter locks is feasible (docs/12). The owner then chose
   Movy as the target: docs/13 is the port plan, pinned to Movy `9190e79`,
   for a no-heap C99 `fm1_seq` core with Movy's semantics, a `compat` mode
   for tests, and seven deliberate deviations. Waiting on the owner: the
   docs/13 §10 questions (deviations, track count, a 72 KiB budget, and
   approval to build Movy's `seq-core` as a test oracle). **Since then
   (2026-10-01):** the owner answered (fix everything; 4–8 routed tracks;
   about half the budget; oracle approved; 7-bit locks), and stages M1 and
   M3 are built: `fm1_seq` (engines/seq.md) matches Movy's own code in 23 of
   24 golden fixtures (undo is not ported) and in thousands of random
   scripts. Capture is on by default with 256 packed 12-byte events (the
   owner's choice; 31,944 B at 8 tracks since stage E1). Open: undo, the note-index
   rebuild cost on pi32v2 (stage B).

## 6. Reference material already gathered (clone these locally)

| Repo | Commit inspected | Why |
| --- | --- | --- |
| `aroum/fm1-custom-fw` | `d08360f` 2026-08-21 | updater analysis, photos, untested flasher |
| `AL-255/FM-1-RE` (`main`) | `95eca84` 2026-08-16 | disassembly, protocol, safety, firmware images V13/V14 |
| `AL-255/FM-1-RE` (`with-custom-firmware`) | `628fcaf` 2026-08-02 | experimental pi32v2 firmware, package builders, Synth_Dexed port |
| `kagaimiq/jielie` | `1657d25` 2024-09-15 | JieLi docs: ISA, USB_KEY, formats |
| `kagaimiq/jl-uboot-tool` | `adb3f18` 2025-03-16 | UBOOT dumper/flasher, `wl82loader.bin` |
| `kagaimiq/jl-misctools` | `0a5b12d` 2025-02-20 | `fwunpack_newfw.py` |
| Gitee `Jieli-Tech/fw-AC79_AIoT_SDK` | `e30b1ee` 2026-06-09 (= V1.2.13 + README) is our pin for the libraries since 2026-10-05; tag V1.1.9 `8eae664` holds the FM-1's SPL; branch `AC791N_OTA_loader` `79eda0c` | vendor SDK: `WL82.h`, `cpu/wl82/tools`, datasheets, the OTA loaders. Gitee is reachable but its SSL is flaky: pin by commit, clone blobless and sparse with `tools/jieli/ac79-sdk-sparse.txt`, and avoid commands that fetch blobs lazily, which hung. The GitHub mirrors are stale (`amitv87` to 2024-07, `jeffreywugz` V1.0.3): do not cite them |
| `hugelton/Felucca` | `727f272` 2026-10-05 (v1.0); `b0dcd53` 2026-10-06 for the vendored engines | bare-metal FM-1 firmware; pin map, update-service design (GPL-3.0-only: facts only, but WHEEL, TRIO and PHASE, vendored behind the GPL switch in `engines/third_party/felucca/`) |
| `charlesvestal/fm1-x0x` | `80b7d40` 2026-10-05 | open FM-1 firmware with a 303, 909 and 808 and TB-3PO; those four vendored behind the GPL switch in `engines/third_party/fm1-x0x/` (GPL-3.0-only; `notes/2026-10-06-fm1-x0x.md`) |
| `isod89/sloop-fm1` | `f2b44c2` 2026-10-04 (v2.2) | Felucca fork; boot guard, loader checks (GPL-3.0-only: facts only) |
| `Keitark/fm1-nes` | `870f305` 2026-10-03 | SDK app on an FM-1; board support, sparse mask-ROM planner (Apache-2.0 root) |
| `kurogedelic/FM-1-transporter` | `a632d92` 2026-10-01 | RP2040 `USB_KEY` + USB host recovery tool (MIT); read through the API |
| `DimaDake/schwung-movy` | `5627d51` 2026-09-05 (v0.31.0) | design reference only |

Web pages that were **blocked** from the research sandbox and still need a
human read: cuvave.com product page, the user manual PDF, synthanatomy.com
articles, fwradar.com history, elektronauts/gearspace/reddit threads,
fm1-editor.com, kagaimiq.github.io (use the repo), madushan.caas.lk blog
post. gitee.com was on that list; it was reached on 2026-10-05 (above).

## 7. Kick-off prompt for the new Claude project

Paste this as the first message of the new project (adjust paths):

> This project, Lunar Modulator, is the open-source firmware effort for the
> M-VAVE FM-1 FM synthesizer. The repository
> (`~/Developer/mvave-fm1-firmware`) contains a completed research phase:
> read `HANDOFF.md`, then `DEVELOPERS.md`, then `docs/01`–`09` and `CLAUDE.md`. Rules: the FM-1 on my desk is the only unit;
> nothing may be flashed or sent to it beyond the read-only identity query
> until recovery is proven (docs/07). Today's tasks: (1) run
> `docs/09-first-session-checklist.md` §1 to extract and analyse the V15
> firmware from `~/Downloads/M-UPGRADE-FM1*.dmg`; (2) §2–§3 USB descriptors and
> identity query with the FM-1 plugged in; (3) write results to
> `notes/<date>-bench.md` and update the open questions in `docs/01` §6 and the
> version table in `docs/02` §1. Keep the [verified]/[reported]/[inferred]
> marks honest.


### Installable-image build access restored — 2026-10-11

[verified] Aeon and Hera SSH/Docker are reachable. Target builds of inert,
handover and panel-protocol pass link/audit; 33 focused tests pass without
skips. Fixed a target-generated unresolved memcpy in SPI binding and added a
symbol-table dependency gate. SPI is still disconnected from boot. Bench01 subsequently returned to normal USB enumeration after the owner
power-cycled; the owner confirmed diagnostic bring-up first. See `notes/2026-10-11-installable-firmware.md` for artifact hashes,
remaining platform/recovery contracts and remote build paths. Active branch:
`feature/2026-10-11@installable-firmware`; no package/install/PR/main merge.


### Current build host: Hera — 2026-10-11 owner instruction

[reported: owner] FM-1 power-cycle returns to the normal screen. [verified]
Bench01 sees `4c4a:c755` plus MIDI. Prior UBOOT power-cycle wait is closed.
Use `claude@192.168.1.48` for builds; aeon is under owner maintenance. Hera
has the hash-pinned toolchain and build image locally. Three parallel target
builds pass audit and reproduce aeon's images/SPI object byte for byte. See
`notes/2026-10-11-installable-firmware.md` for exact paths and receipts. Endpoint
is confirmed as diagnostic bring-up first; no package or device write has occurred.

Installable diagnostic checkpoint: fixed loader configuration and directory-last
transactions passed 156 focused Hera checks in 16 chunks (no skips). Native
loader review is in `notes/2026-10-11-loader-native-review.md`; exact test pins
are in `notes/2026-10-11-diagnostic-directory-last.md`. SDK recovery/native review,
fresh physical backups, installation/restore and panel acceptance remain pending.

SDK diagnostic checkpoint: C-only pinned V1.2.13 dual-core build is saved in
firmware/sdk-diagnostic/, with native audit and builder. Hera linked a 120432-byte
private app (SHA256 991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9);
18 focused checks passed, including actual ELF mutations. Independent startup,
registry, ordinary NOR-path and P33 review found no actionable defect within
its stated scope; see notes/2026-10-11-sdk-diagnostic-review.md. Hardware remains
unverified. The healthy-runtime recovery attempt does not cover a stalled
P33 lock owner or failure to create the worker. Root is implementing the distinct
raw SDK gate; a reviewed fixed-loader reader and fresh dual backups are still
required before installation. Last prior verified backup: fa11706831a9f74347c6d4966276c11ef88b7c36.
