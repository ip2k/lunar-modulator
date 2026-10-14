# Current installable milestone checkpoint — 2026-10-14

## Authority and endpoint

Coordinator checkout: `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
Branch: `feature/2026-10-11@installable-firmware`.
Last preceding verified GitHub head: `e05f616a18445f491e2bad85a728c9ab89867872`.
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
  preflight. Production default acceptance remains pending; the static page
  exports JSON until a trusted private same-origin service enables its marker.
- The real FastAPI/DockerJobAdapter path built the default candidate and all
  13 engines/all 55 modules. Its diagnostic app is 862,296 bytes, SHA-256
  `7175f6d1e97563b07350e0bccb10a9820104eb47a4fc67212797c68651fbd575`.
  Packed project size is 4,345 bytes; exact embedded content/order and receipt
  checks passed. Hardware/installability/default-acceptance fields remain false.
  See `2026-10-14-real-installer-worker-api-e2e.md`.
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
  now running; `38584247667` completed with failed Python collection jobs
  while its other jobs passed. No overall passing CI claim is supported.

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
D7674. The target-adapted loader size and staging ownership are still unproved.
A new existing-codec compressed-wavetable link saves 18,012 bytes: app 844,284
bytes, leaving 16,360 bytes against that D7000 arithmetic budget. It reserves
an additional 50,688 bytes in RAM, reducing the instance pool to 165,376.
Cold-start/target timing remain unproved; see `2026-10-14-wavetable-fullsong-fit.md`.

Continuous-mode/diagnostic-overhead A/B did not close this gap. Matched -Os
compilation made the feature-identical app 100,292 bytes larger than -Oz and
failed the actual D9000 link. Keep -Oz. No feature removal or relaxed safety
gate is accepted as the size solution.

## Active lanes and remaining acceptance

- Hera `installer_preload_connection`: independent compressed-worker source /
  receipt and memory-preflight review, note-only first.
- Hera `demo_controller_review`: meaningful host cold-start with the actual
  decoded tables and 165,376-byte allocation pool, real default-song load,
  bounded allocator metrics and sanitizer checks. No target timing claim.
- Hera `physical_storage_compression`: target-adapted rescue-loader fit and
  safe expanded bounds, offline only. Independent USB_KEY route review is
  complete: owner-unit entry is still untested, Cynthion does not establish
  physical FM1 power/reset control. See independent-recovery-route note.

Coordinator reviews returned artifacts, backs up exact commits, integrates
through required checks and continues. Owner accepted audible Trio probe
screen/keys/encoders earlier; this does not accept the all13 full-song image.
Native full-song listening/control checks, SAVE/reload, storage ownership and
migration/rollback, persistent recovery, installable download/flash path,
review/CI/main integration and public release remain open.
