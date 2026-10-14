# All-thirteen native image: expanded layout proposal

Status: owner-approved implementation direction (2026-10-13); no write admission,
emitted package or device test.

Owner response: “Approve expanded layout with migration and rollback verification”.
This revises layout immutability for the explicit expanded profile only. All
boot-component, identity, dual-backup and concrete-image/recovery gates remain.

## Requirement and existing constraint

The owner requires a default image with all thirteen production engines plus a
selectable image builder. AGENTS.md currently requires keeping the partition
layout byte-identical to stock in experimental packages. Existing native link
and artifact checks enforce a 581,564-byte application extent; those gates remain
unchanged. The latest default-twelve-voice Shapes probe, with original Plaits
wavetables in flash and compressed Braids tables in RAM, exceeds it by 144,216
bytes for thirteen engines without effects [verified target link]. The earlier
both-banks-compressed sizing probe exceeded it by 126,184 bytes; neither fits.
Private receipts: `module-target-v3-flash-plaits-12-verification.json` and
`module-target-v2-verification.json` under the Hera root recorded in
`notes/2026-10-13-native-image-builder.md`.

## Reviewable alternative

Use the community-tested larger application partition ending at `0xD9000`,
retain the pinned FM-1 stock SPL, OTA loader and configuration **contents**, and
relocate application-area file records as necessary rather than overwrite them.
The owner's FM-1_092 already has VM at `0xD9000` with length `0x10000` [verified
historical package analysis; current device identity must be checked afresh].
A stock V15 installation has VM at `0x93000`, length `0x56000`; migration would
change its location and capacity, requiring explicit settings backup/migration
and rollback treatment. This is a proposed relaxation of layout immutability,
not permission to change SPL, OTA code, chip keys, reserved banks or eFuses.

The retained private full-catalogue sizing ELF measured 789,604 application
bytes with effects [verified earlier sizing receipt; optional eight-voice Shapes
profile; not the final twelve-voice release or hardware acceptance]. With the
existing raw app origin `0x4120`, the mathematical app end is
`0xC4D84`, leaving 82,556 bytes before `0xD9000` for application-area
records, configuration, alignment and embedded content. This upper-level size
calculation is not a finished package budget. Target RAM fit and timing remain
separate unresolved gates, particularly default twelve-voice Shapes.

Known source evidence: `docs/04-prior-art.md` describes FM-1+VA relocation and
rollback behavior; `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` records
byte-identical SPL/OTA/cfg contents and changed VM/PRCT records;
`tools/jieli/raw_flash_profile.py` pins the recorded FM-1_092 extent and reserves
all bytes from its cfg-tool offset onward. The existing guard therefore refuses
this proposal. It must not be bypassed or relabeled as an admitted image.

## Required engineering if the constraint is revised

1. A separate explicit layout profile with independently checked file extents,
   directory and payload CRCs, cipher transforms, unchanged pinned components,
   unchanged reserved bank boundaries and no overlapping records.
2. Native twelve-voice catalogue link and actual allocation/render-budget checks.
3. Offline interrupted-write/recovery and stock rollback simulations, including
   VM relocation and preservation/export of owner data.
4. Exact package and recovery plan review before fresh identity, two matching
   full backups, authorized physical installation, cold boot and listening.
5. Release builder output bound to this approved profile, its source revision
   and complete admission receipts. The default stays thirteen engines; no
   reduced profile is silently substituted.

The implementation begins with opt-in native link/artifact bounds. Raw-flash
packaging, settings migration, rollback and hardware acceptance remain separate
required gates; a passing ELF is not an installable package.


## Explicit link/artifact implementation checkpoint

[verified] `expanded-d9000` now supplies the same named byte budget to a generated
pinned linker script and the native ELF flattener. Default `protected` remains
581,564 bytes. Expanded budget is 868,836 bytes: `0xD9000 - 0x4120`, less
384 bytes for aligned cfg-tool and 2,940 bytes for aligned cfg. These are
conservative reservations from the recorded 092 components, not validation of
any other firmware version or a raw-flash package.

[verified] Hera target link with all thirteen production sound engines,
12-voice Shapes, flash Plaits tables, compressed Braids tables and retained
project/set staging produced 838,712 flattened application bytes; headroom
30,124 bytes. The full selected catalogue includes test-gain/test-ext fixtures;
release selection must omit those. No songs/sets were embedded in this fit run.
Actual source freshness, no undefined symbols, SDK-free key audit, ELF bounds
and flattening passed. RAM pool extent is 216,064 bytes; this is not proof of
all possible simultaneous allocations, timing or physical playback.

[verified] 80 audit/artifact cases passed in 30 independent Hera containers,
all inspected for zero exit/no OOM and removed. Includes full image load-boundary
checks (RAM initializers included), implicit-expansion refusal, exact linker
adaptation and previous entry/RAM safeguards. Initial collection v1 produced
only counts because pytest double quiet was configured; no test containers
launched. Collection was corrected explicitly. Initial target v1 linked but
failed a forbidden-address byte scan crossing a resolved `__fixunsdfsi` call
and `02 d6` (`r2 = r0 #`) in `draw`. Exact vendor-decode/function/ELF-byte proof
was added to the existing bounded call-boundary mechanism. Negative literal,
flat-image, damaged-decoder/bytes, target and function-boundary checks passed.
All original failure logs remain private; no global byte-scan exemption added.

Reproduction launchers and source-bound summary:
`notes/2026-10-13-expanded-layout-verification/`. Private complete receipts and
ELFs: Hera `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/`,
`flash-layout-v3` and `expanded-all13-v2`; copied JSON/log evidence under local
`build/native-external-arenas-16-20261012/`. No vendor/firmware binary committed.

Next: independently verified expanded raw-flash geometry and CRC/cipher output,
immutable component comparison, VM backup/migration and rollback fault cases.
Then prepared content/full startup, stack/timing and physical cold-boot/audio
acceptance, release installer and required review/CI/integration. No hardware
commands issued. Existing stock/092 package and hardware admission gates remain
unchanged; these artifacts explicitly report `installable: false`.
