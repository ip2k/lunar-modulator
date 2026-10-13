# All-thirteen native image: expanded layout proposal

Status: offline design proposal; no write admission, emitted package or device test.

## Requirement and existing constraint

The owner requires a default image with all thirteen production engines plus a
selectable image builder. AGENTS.md currently requires keeping the partition
layout byte-identical to stock in experimental packages. Existing native link
and artifact checks enforce a 581,564-byte application extent; those gates remain
unchanged. Thirteen engines without effects exceed it by 126,184 bytes in the
latest canonical-module sizing probe [verified].

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

No implementation or hardware operation uses this proposal yet.
