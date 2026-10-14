# Current installable milestone checkpoint — 2026-10-14

## Authority and endpoint

Coordinator checkout: `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
Branch: `feature/2026-10-11@installable-firmware`.
Last preceding verified GitHub head: `620cc306a83addb0104fc2c3f328e53e070a0446`.
Every returned worker commit through that checkpoint has a verified GitHub backup.
No main merge, public installer deployment or release occurred.

The endpoint remains fully functional SDK-free Lunar on physical FM1s, all
13 engines in the default image, selectable engines/effects/projects/sets,
at least one complete default song, verified persistence/migration/rollback,
interrupted-write recovery, reviewed exact-head CI/integration and web shipping.
Expanded app end D9000 is owner-approved subject to the retained boot/configuration
safeguards. Mac alone owns device/Cynthion operations; Hera workers are offline.

## What is now implemented and checked

### Latest continuation (supersedes earlier running/boot status below)

[verified] The completed Event Horizon installation and one timed boot remain
as recorded below: full-image readback matched, native USB appeared and ROM
device40 returned after about 122.5 seconds. Owner screen/audio/control
observations remain pending. No further device command was sent. Consumed
device38 installation/boot admissions must never be reused.

[verified] Owner musical approval is integrated at `da6b5943`; nine focused
Node tests pass. The catalogue preserves false installability and physical
acceptance flags. Target-dependent wavetable symbol prefixes are fixed at
`64bf3bc0`; actual Darwin wavetable sanitizer checks passed, and pinned pi32v2
compiler preprocessing confirmed its empty symbol prefix. This is not a new
target application build.

[verified] CI run `38599904562` at earlier `9c5b3df3` completed with 11 of 13
jobs passing; both Python jobs failed. Stale packet audit pins and historical
catalogue source availability are repaired through `634e99a2`. The Python CI
checkout now fetches history; 22 focused catalogue/dependency tests pass.
Darwin linker-flag and large SAVE-fixture repairs await review/integration;
there is no passing exact-current-head CI claim.

[verified] The named `expanded-d7000` link profile is integrated at `a491c106`
with an 860,644-byte app budget. A Hera worker is assigned the actual fresh
all13/55 Event Horizon target link. This reserves budget only; no rescue tail
is installed or admitted. NOR adapter design is recorded at `620cc306`;
SPI timeout propagation, IRQ restoration, RAM callgraph, watchdog margin and
physical sector ownership remain prerequisites to enabling SAVE writes.

Active offline tasks: D7000 target link, semantically valid large SAVE fixture
and Darwin host flags, and fail-closed NOR transport error propagation. Their
unique claims/checkouts are on Hera. Mac retains exclusive device ownership.

- The installer chooser offers eight demo candidates including the four
  restored original projects. Event Horizon Showcase is preselected at startup
  index zero. Two oversized replacement choices remain disabled by memory
  preflight. Owner approved Event Horizon Showcase as the default song; physical full-song acceptance remains pending; the static page
  exports JSON until a trusted private same-origin service enables its marker.
- The real FastAPI/DockerJobAdapter path built the default candidate and all
  13 engines/all 55 modules. Its diagnostic app is 862,296 bytes, SHA-256
  `7175f6d1e97563b07350e0bccb10a9820104eb47a4fc67212797c68651fbd575`.
  Packed project size is 4,345 bytes; exact embedded content/order and receipt
  checks passed. Hardware/installability/default-acceptance fields remain false.
  The current independently checked receipt path also passed an actual
  API-to-Docker build at `9424959c`, preserving every admission flag as false.
  See `2026-10-14-checked-receipt-realbuild.md` and
  `2026-10-14-real-installer-worker-api-e2e.md`.
- Root repeated 18 Node installer/page/client tests successfully. The earlier private
  browser review used API stubs; the new live Chromium-to-real-API-to-Docker
  worker check also passed with matching request/app hashes. See
  `2026-10-14-live-browser-worker-e2e.md`. The temporary loopback service and
  worker were removed; no public deployment occurred.
- The offline CRC-header model passed four tests with the repository Python
  3.12 venv and independent retained-capture review. It proves only the XOR/CRC
  property. Its narrow SPL helper and supplied rescue-validity booleans are
  not a complete SPL or hardware recovery proof.
- The CI PIO dependency repair is integrated at `83069368`: emulator 0.88.0
  and compatible pytest range. Hera passed 17 focused waveform/dongle tests,
  full collection and pip check. Fresh CI `38586683710` at exact 83069368 is
  complete and failed both Linux and macOS Python jobs. Its macOS job failed with
  native test platform flags, obsolete fixture assumptions and missing
  optional target-tool environment. Eleven other jobs passed. The earlier
  `38584247667` failed Python collection. No overall passing CI claim is supported.

## Recovery and fit findings that govern the next step

Stock SPL bypasses its rescue-record scan when the ordinary app header is
valid. Body-first/directory-last alone therefore does not establish cold-boot
recovery. The current one-bit header-invalidation idea is disarmed: JEDEC
85 60 14 does not uniquely identify the fitted Puya variant, matching-family
datasheets do not guarantee interrupted-program atomicity, and the reviewed
RAM-loader external write path handles aligned 256-byte pages. See the SPL,
header-model and NOR-program-semantics notes.

The original maintained loader is 6,954 wrapped/compressed bytes. Proposed
two-sector tail D7000..D9000 fits that loader and record in isolation, but the
complete image does not fit: app origin 4120 plus retained 384-byte tool and
2,940-byte configuration extents leave an app budget of 860,644 bytes. The
862,296-byte current app exceeds it by 1,652 bytes; complete records end at
D7674. The target-adapted loader now measures 6,954 wrapped bytes and fits
the two-sector reservation arithmetically, with 1,158 bytes around its record.
Staging ownership and physical recovery remain unproved. The test-only expanded
loader fixture checks D7000 write bounds and retains a counterexample: failed
body writes leave an old CRC-valid header. The tracked Dinghy updater uses a
distinct E0000 staging geometry; these tests do not implement its migration.
See `2026-10-14-expanded-rescue-loader-fit.md` and
`2026-10-14-expanded-rescue-host-tests.md`.
A new existing-codec compressed-wavetable link saves 18,012 bytes: app 844,284
bytes, leaving 16,360 bytes against that D7000 arithmetic budget. It reserves
an additional 50,688 bytes in RAM, reducing the instance pool to 165,376.
The coordinator's fresh `9961f64b` compressed-table host fixture passes
ASan/UBSan startup for Event Horizon Showcase at that pool size, with exact
table-byte equality (27 passed, 13 intentionally skipped across startup and
expanded-loader files). The older worker receipt's launcher was incomplete
and a saved intermediate log contained two unit-count assertion failures;
the new explicit dependency-mounted container run establishes current success.
All thirteen individual engines start at an eight-voice Shapes configuration;
twelve Shapes voices do not fit. Satellite Hearts still fails after Shapes
at eight voices and remains unavailable for this profile. Target timing/audio
and complete-project acceptance remain unproved. See
`2026-10-14-wavetable-fullsong-fit.md` and
`2026-10-14-compressed-native-startup.md`.
The fresh sixteen-shard Shapes-8 target build is 845,036 bytes, leaving
15,608 bytes against the D7000 arithmetic budget; its actual link remains
expanded-D9000 and non-installable. See `2026-10-14-shapes8-target-fit.md`.

Continuous-mode/diagnostic-overhead A/B did not close this gap. Matched -Os
compilation made the feature-identical app 100,292 bytes larger than -Oz and
failed the actual D9000 link. Keep -Oz. No feature removal or relaxed safety
gate is accepted as the size solution.

## Active lanes and remaining acceptance

- Hera `installer_preload_connection`: verify the named eight-voice,
  compressed-Plaits/Braids receipt profile and transport correspondence. Its
  raw Event Horizon candidate is constructed and backed up; transport admission
  remains blocked until the producer checker validates this memory profile.
- Hera `demo_controller_review`: separate optional SDK target compiles from
  host roundtrips, incorporating the native test portability helper. The
  SDK-absent run is green; configured-SDK compilation is being checked.
- Hera `physical_storage_compression`: construct exact device38 Event Horizon
  install/current-image rollback/stock rollback transactions offline from the
  fresh matching physical backups. No worker has device-write authority.
- Coordinator: portable startup regression completed, 43 passed/13 skipped.
  Capacity/hash repairs and exact device38 read adapter are integrated and
  backed up. Fresh device38 dual reads succeeded with no flash/reset operations;
  see `2026-10-14-device38-fresh-dual-backup.md`. The new read session leaves
  the reviewed RAM loader available; old device36 admissions cannot be reused.
- Independent USB_KEY entry on the owner unit remains untested. Cynthion does
  not establish physical SoC power/reset control. Interrupted-write physical
  recovery remains a separate acceptance gate.

Coordinator reviews returned artifacts, backs up exact commits, integrates
through required checks and continues. Owner accepted audible Trio probe
screen/keys/encoders earlier; this does not accept the all13 full-song image.
Native full-song listening/control checks, SAVE/reload, storage ownership and
migration/rollback, persistent recovery, installable download/flash path,
review/CI/main integration and public release remain open.

## Latest continuation

[verified] One Event Horizon boot request was submitted at Unix time
1791998065.9516. Its SG completion was ambiguous (`host=7`, `resid=16`,
`info=1`, zero reply), so the one-use adapter stopped and did not retry.
Passive sysfs subsequently showed native USB device39 (`1209:0001`, product
`Felucca`), then ROM device40 (`4c4a:8057`, `WL80UBOOT1.00`) at
1791998188.5178, consistent with the diagnostic's two-minute return.
These observations do not retroactively establish a complete reset reply.
Owner screen/audio/control observations remain pending. Device38 admission
and consumed boot campaign must not be reused; any later hardware command
requires fresh device40 binding. The exact partial-reply mock now verifies
one ioctl, retained completion logging, closed ambiguity and rejection of a
second request; all nine boot/reset focused tests pass.

[verified] Event Horizon V2 installation completed: 208 changed sectors and
the complete 1 MiB flash readback match target SHA
`145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`.
The completed offline proof replayed 25,347 commands and 57,976 events,
including the immutable zero-command V1 stop. The initial checker failed
because its SG mapping fixture assumed an absent nested USB field; corrected
source pins the actual mapping and separately verifies the backup USB identity.
The failed check evidence is retained. The corrected actual-bundle proof is
`event120-install-v2/offline-proof-002.json` in the private bench receipt root.
Boot/reset focused tests pass (8). No Event Horizon boot has been sent yet.
Public installability, hardware listening and recovery acceptance remain open.

[verified] Event Horizon Showcase is owner-approved as the default song. The
845,036-byte Shapes8 candidate contains all thirteen engines and has been
staged privately on bench01 with the exact device38 208-sector install plan.
The fresh matching current-image backups remain the rollback baseline.

[verified] The first Event120 install attempt stopped during session binding,
before any SG command or flash operation. Its only two transcript events are
`native_transaction_prepared` and `native_transaction_stopped`; the transaction
journal remains `prepared`. The v1 marker, campaign and log are retained and
backed up privately. The inherited constructor checked the original loader hash
instead of the reviewed patched loader. A new v2 adapter and campaign require
that defect fixed and the preserved no-command failure checked; the consumed v1
campaign must not be reused.

[verified] The canonical USB-mapping adapter fix is integrated. Pure installation
replay passes twelve simulator cases and now matches the writer's strict false
admission flags. Completion-first reboot logging passes three ioctl mocks,
including expected detach and failed completion; it has not been used on the
device. Source is backed up at `86dd635081ab7bf3cc3e43270a162d25896dc29c`.
CI run `38599904562` checks earlier exact head `9c5b3df3` and is still running;
it does not cover the newer writer/reboot integrations. The watched Event120
boot has not started, and full-song hardware acceptance remains pending.

[verified] V2 fixed-loader binding is integrated at `6fa8c987` and backed up
with a matching GitHub SHA. Its fifteen focused tests include the production
SG class with mocked system calls and altered prior-attempt evidence rejection.
The stopped v1 evidence was mirrored privately on bench01 and checked byte for
byte. V2 preflight accepted campaign
`3e90b2b4e79fd98350f953dc3cfcf10c1361d26f6397671dbcbe7070e82ede05`;
the one-use 208-sector installation is running in coordinator exec session
`50859`. Do not restart it or reuse its consumed campaign. Installation and
readback completion are not yet established. The boot adapter at `af8b3f07`
passes eight focused boot/reset tests but is deliberately disarmed until the
independent completed-install verifier is integrated and pinned. No Event
Horizon boot request has been sent.

[verified] Fresh e404fddd three-file host regression completed: 43 passed, 13 skipped, exit zero. The dependency-mounted, bounded pinned Hera container preserves ASan/UBSan checks. Content embedding repair is integrated at fb972a0a (41 passed, 16 target-only skips); current-state demo fixtures at95c30133 had194 passed/1 target skip. CI now builds an isolated current fm1-state before image tests at843b33c3. Further ordinary host/optional-target fixture separation remains active.

[verified] FIRST ORBIT was booted once and native USB appeared, then timed return enumerated device38 in ROM. Owner perceptual observations pending; fresh device38 admission is required before another installation. See `2026-10-14-first-orbit-watched-boot.md`. Event Horizon is owner-approved as default, not yet physically accepted.
