# Current installable milestone checkpoint — 2026-10-14

## Authority and endpoint

Coordinator checkout: `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
Branch: `feature/2026-10-11@installable-firmware`.
Last preceding verified GitHub head: `fb972a0a9a14058ebb42d715e9890952657f65c7`.
Every returned worker commit through that checkpoint has a verified GitHub backup.
No main merge, public installer deployment or release occurred.

The endpoint remains fully functional SDK-free Lunar on physical FM1s, all
13 engines in the default image, selectable engines/effects/projects/sets,
at least one complete default song, verified persistence/migration/rollback,
interrupted-write recovery, reviewed exact-head CI/integration and web shipping.
Expanded app end D9000 is owner-approved subject to the retained boot/configuration
safeguards. Mac alone owns device/Cynthion operations; Hera workers are offline.

## What is now implemented and checked

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

- Hera `installer_preload_connection`: repair obsolete fixture expectations
  and separate optional target-adapter compilation from host SAVE roundtrips.
  Receipt validation and real worker build notes are integrated and backed up.
- Hera `demo_controller_review`: repair Darwin/Linux native test flags while
  preserving sanitizer coverage. Fresh Shapes-8 target evidence is integrated.
- Hera `physical_storage_compression`: investigate actual stock SPL frozen
  header contract and independent recovery entry after a synthetic fixed-entry
  verifier linked successfully. Synthetic proof is backed up, not admitted.
- Coordinator: portable allocator instrumentation and Darwin host wavetable
  section selection are pushed. Fresh three-file host regression is running
  at `e404fddd`; device generator defaults and production allocator are unchanged.
- Passive bench enumeration at approximately 08:28 Pacific found the FM1 in
  mask-ROM USB mode (`4c4a:8057`, bus 1/device 36). No device mutation or power
  cycle occurred. Independent USB_KEY entry on the owner unit remains untested;
  Cynthion does not establish physical SoC power/reset control.

Coordinator reviews returned artifacts, backs up exact commits, integrates
through required checks and continues. Owner accepted audible Trio probe
screen/keys/encoders earlier; this does not accept the all13 full-song image.
Native full-song listening/control checks, SAVE/reload, storage ownership and
migration/rollback, persistent recovery, installable download/flash path,
review/CI/main integration and public release remain open.

## Latest continuation

[verified] Fresh e404fddd three-file host regression completed: 43 passed, 13 skipped, exit zero. The dependency-mounted, bounded pinned Hera container preserves ASan/UBSan checks. Content embedding repair is integrated at fb972a0a (41 passed, 16 target-only skips); current-state demo fixtures at95c30133 had194 passed/1 target skip. CI now builds an isolated current fm1-state before image tests at843b33c3. Further ordinary host/optional-target fixture separation remains active.

[verified] FIRST ORBIT was booted once and native USB appeared, then timed return enumerated device38 in ROM. Owner perceptual observations pending; fresh device38 admission is required before another installation. See `2026-10-14-first-orbit-watched-boot.md`. Event Horizon is owner-approved as default, not yet physically accepted.
