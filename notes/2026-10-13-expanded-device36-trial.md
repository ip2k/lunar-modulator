# Exact device36 thirteen-engine trial and recovery plan

Status: preparation and source review; no physical installation or boot performed.
This is a private twenty-second hardware probe, not a release image or OTA package.
The owner authorized native development and the expanded layout with migration
and rollback verification. AGENTS.md retains the all-thirteen release and custom
web builder requirements.

## Concrete candidate and preserved bytes

[verified] Current candidate full-flash SHA256:
`c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903`.
ELF SHA256:
`35655a21de5c08d09fa19ef2fd4f253efbc107346c6e107a1988dca4e69dac29`.
The application is845916 bytes. The independent constructor receipt at
`build/native-current-candidate-20261013/receipts/candidate.json` verifies ELF
reconstruction, SDK-free/eFuse gates, geometry and configuration contents.
All bytes below0x4000 and from0xD9000 to the end of1MiB flash are preserved.
The owner's recorded092 VM already starts at0xD9000; this trial preserves its
raw bytes. It does not establish migration for stock V15 VM at0x93000.
Vendor-derived images remain private and must not enter Git or a web release.

[verified] Fresh physical device36 paired flash readbacks SHA256:
`770fd5f275110f017329dda30315343d766ff4a6c6beaa62f5a0060c629dc561`.
The exact native plan changes213 sectors and commits directory sector0x4000
last. Plan SHA256:
`2e1b90e7fcf7c14722336224818eb9d4d0ca7148bf8d1ff619d0602e153ef9b1`.
Its baseline is the installed Trio image, not original stock. Recovery order
is native restore to that complete Trio baseline, verify the complete1MiB,
then the separately pinned13-sector stock installation if requested by the
recovery procedure. Do not apply the stock plan directly to mixed all13 bytes.

## Bench preparation and admission

[verified] Tested installation-proof and boot tools were copied to Pi root
`/home/claude/fm1-expanded36-source-20261013/`, with hashes checked:
- expanded_install_proof.py: b9596bf0b364b57780f5d351f3d4abcca10d7fedd6e208cb24f17c2b73b3a3f9
- expanded_boot.py: 2ec7931831eb534260b1dcf80d18862fb0771409725fdbec75240537fcba24ec

[verified] Passive sysfs/stat observation still identifies USB1-1 bus1 device36,
4c4a:8057 and /dev/sg0 node identity[6,1666,5376]. The original connection
already runs the fixed RAM loader; its ROM upload is consumed. Do not upload
again, reset speculatively, reuse device31 boot, or run the expired campaign.
Normal-app identity has not been queried afresh while this loader is running;
current evidence binds chip response, original connection and exact paired bytes.

Before opening the writer, require successful terminal fresh-Trio recovery
campaign receipts, all30 chunk exits/no-OOM/logs/source hashes, unchanged exact
source/image/plan evidence and a freshly observed SG mapping. Generate a new
native-install-campaign.json timestamp and run preflight within120 seconds.
The writer begins with loader/JEDEC checks and complete baseline readback;
any mismatch must stop before an erase. No blanket erase, bank or eFuse writes.
The source-reviewed transport allows only aligned reads, exact planned sector
erases and direction-bound pages. Every mutation has a durable intent first.
The command/time bounds are32768/2700 seconds. Any ambiguous result stops;
no automatic retry, reset or re-enumeration is authorized by a consumed marker.

## Installation, boot and observations

After successful installation, independently replay the saved physical transcript
using expanded_install_proof.verify with the campaign digest retained before the
writer starts. Require the complete target readback and journal verification.
Keep all private receipts; do not substitute simulated proof for physical proof.
Create a fresh boot campaign only on the same loader with no intervening commands.
The staged expanded_boot module permits one literal FC0C argument1, consumes a
durable marker before opening and issues no flash/upload commands.

Announce boot immediately before sending it when the owner is watching. Record
screen/project name, audible playback and keyed notes, encoder response, any
visible stack-margin/sample footer, USB identity while native, and return to
recovery after approximately20 seconds. Request completion alone is not boot
acceptance. One twenty-second observation does not validate every engine,
maximum polyphony, MIDI, effects, persistence, cold boot or a production soak.

If installation stops ambiguously, preserve the journal and transport evidence.
Do not retry that consumed live campaign. Review the exact observed interruption
and loader state before creating a separately admitted restore campaign.
If the app returns to mask ROM, a fresh audited recovery-loader campaign and
matching reads must establish its new connection before any restore. If it
hangs before returning, record that failure and use the documented physical
power-cycle/recovery entry; do not claim Cynthion USB switching cycles internal
battery power. Physical rollback remains unverified until actual bytes and
subsequent boot are checked.

## Outstanding release acceptance

All13 physical startup, per-engine audio/timing, controls/MIDI, persistent release
mode and storage, stock-layout settings migration and physical rollback,
web OTA package/installer and custom builder, GPL notices/source distribution,
required review/CI and integration remain open. The recovery campaign is still
running; this document does not grant completed physical admission.
