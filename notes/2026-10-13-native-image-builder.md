# Default firmware and selectable image builder

## Owner decision

2026-10-13: “Stock image with thirteen plus a selectable image builder that lets
you build in what you want -- engines, effects, and songs / sets.”

The default means a Lunar image containing all thirteen production sound engines,
not the vendor firmware and not thirteen alternative packs. The selectable builder
is additional. No smaller default or reduced release polyphony is accepted by
this decision. Preserve stock SPL, OTA/cfg and protected partition bounds.

## Canonical module selection [verified source and target]

`tools/native/module_selection.py` resolves literal comma-separated IDs through
`engines/modules/catalogue.mk`. It accepts sound engines, audio effects, MIDI
effects and modulation modules using the existing GPL-enabled catalogue. It
rejects duplicate IDs and Make expressions/list paths at the external-input
boundary. Unknown modules and no-sound selections fail at the catalogue gate.

`build_application_probe.py --modules trio,plate,echo,lfo,env` now generates both
registry flags and omitted-module metadata from that catalogue. Existing
`--exclude` remains available but cannot be combined with `--modules`. The timed
probe still requires Trio as its initial engine. Its receipt records the selected
IDs, dependency objects and generated-header hash. This is backend preparation,
not a web builder or release image: twenty-second ROM return and no NOR writes
remain enforced. Catalogue cache/source admission and all link guards remain.

Hera verification in sixteen containers per campaign:

- 80 checks passed: 16 native module-selection cases and 64 existing stale/hash/
  ABI catalogue receipt cases. This includes hostile selection rejection and
  accurate omitted-module metadata. No OOM.
- 16 target profile links: 13 passed the existing SDK-free and layout audits;
  three failed closed on flash overflow. All used indexed TFT, compressed
  wavetable startup and the optional eight-voice Shapes profile. These checks
  do not establish target allocation, audio timing or physical acceptance.
- Thirteen production engines without effects overflow by 126,184 bytes;
  adding Plate overflows by 128,988. Twelve engines retaining Comet and omitting
  Shapes overflow by 53,908. Twelve retaining Shapes and omitting Comet link.
  These are sizing probes, not accepted substitutes for the default release.

Private evidence: Hera
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/`
`module-selection-v1-verification.json`, `module-target-v1-verification.json`,
and `module-target-v1-00..15/`. Launcher and receipt mirrors are in the ignored
local `build/native-external-arenas-16-20261012/`. No device command was sent.

## Builder implementation path [planned]

1. Export catalogue metadata from the same Make catalogue to the web selection
   UI. Do not duplicate module/object ownership in a second catalogue.
2. Bind each request to the source revision, selected module IDs, native ABI,
   voice profile and content hashes. Build outputs need their own complete
   admission receipts; source selection alone is not proof that an image fits.
3. Use the existing `fm1-state` host packer and state schemas for songs/sets.
   Validate dependencies against the selected catalogue and reject missing
   engines/effects rather than silently dropping content. Embed canonical
   compact data only after its native reader and storage budget are verified.
4. Build with the pinned SDK-free toolchain on Hera. Run the existing source,
   license, flash/RAM, recovery and package guards before offering installation.
   Oversized or otherwise rejected builds must not produce an install button.
5. Connect approved artifacts to the web installer after real OTA installation,
   cold boot, controls/audio/MIDI/persistence and recovery acceptance.

The existing browser state adapter cannot simply be added to the device link:
`sim/web/src/fm1_app_state.c` reserves a 480 KiB writer/check workspace plus
JSON/binary/set/clip/sequence buffers [verified source]. The core state format
already supports bounded readers and binary containers. Use those to develop
the device loader; keep the host writer on the build side. Embedded content also
consumes flash and cannot be omitted from the actual linked image-size gate.

All-thirteen flash fit remains unresolved. Full native functionality, bounded
content loading/persistence, web builder/installer and physical release/recovery
acceptance remain outstanding. Passing a smaller timed probe completes none of
those release gates.

## Content preparation [verified host; not native installation]

`tools/native/prepare_image_profile.py` accepts a version-1 JSON profile with
`engines`, `effects`, `midi`, `modulation` ID lists and `content` relative paths.
It uses the canonical Make catalogue and the supplied trusted `fm1-state`
executable. Inputs are bounded, snapshotted and hashed; duplicate profile keys,
wrong module groups, unknown/duplicate modules, content path escapes and missing
project dependencies are refused. A fresh output directory is mandatory, and
`profile.json` appears only after every input succeeds. Packed assets and the
generated module header remain build inputs, not an installable image.

The C state packer's set conversion wraps sequencer text; it does not validate
that text's commands. Each asset therefore records
`sequence_semantics_verified: false`; sets also record
`dependency_scan_complete: false`. A release consumer must resolve and validate
sets rather than interpreting an empty dependency list as approval. Link/RAM
verification and hardware acceptance are explicitly false in these manifests.

Sixteen integration cases passed in sixteen Hera containers using the existing
host state codec: real project and set packing, combined content, no content,
and twelve rejection cases. The first campaign found a test-fixture error
(Chance belongs to modulation, not MIDI effects); it was corrected, and refusal
tests now assert their specific reason to avoid masking unrelated failures.
Evidence: private `out/image-profile-v1-verification.json` (retained failure) and
`out/image-profile-v2-verification.json` (all sixteen pass; no OOM), under the
Hera root recorded above. Run with `FM1_STATE_TOOL=/path/to/fm1-state` and pytest
`tests/test_native_image_profile.py`. No device operation occurred.

## Prepared-input handoff integrity [verified host]

`tools/native/verify_image_profile.py` adds a consumer boundary for prepared
builder inputs. The trusted build controller must retain the SHA256 of
`profile.json` immediately after successful preparation and supply that digest
to `load_prepared_profile(directory, expected_sha256)` on the later worker.
Computing the expected digest from received files on that worker is not an
integrity check. This digest does not authenticate an untrusted builder service.

The loader checks manifest bounds and digest, duplicate keys, generated module
header, content snapshots, packed payload hashes/lengths and aggregate length.
Assets use canonical local names; missing files and symlinks are refused. The
returned header and packed-content bytes are the checked snapshots: consumers
must use them rather than reopen the paths. No codec, subprocess or device
command runs during verification. Firmware-admission flags and sequence semantic
acceptance must remain false in this build-input format.

Sixteen new cases cover four real-codec profiles, changed/missing artifacts,
path substitution, symlinks, malformed digests, duplicate keys, oversized
manifests and attempted firmware promotion. The combined 128 builder/catalogue
checks passed in sixteen Hera containers, with no OOM. Private evidence:
`out/builder-inputs-v5-verification.json` under the Hera root above, SHA256
`ebac6aa014472b5eee70d6483d509e5a63742e1dfb643713c95357c902998883`.
This verifier is available for the future build worker; the timed linker does
not yet embed these content inputs. Native content loading, realtime budgets,
all-thirteen flash fit, web installation and physical release acceptance remain
open.

## Selective wave-bank allocation [verified target link]

Custom selections now decode the Plaits integrated wave bank only when Macro or
Macro Heavy is selected, and the Braids bank only for Shapes. Scalar lookup
tables remain available through the original resource objects. The thirteen-
engine default retains both wave banks and is unchanged.

Hera `module-target-v2` repeated sixteen profile links: thirteen admitted by the
unchanged SDK-free/layout guards and three correctly refused for the same flash
overflows. Trio-only app size fell from 285,412 to 251,292 bytes; its instance
pool grew from 198,400 to 249,088 bytes. Trio+Shapes app size fell from 363,012
to 330,368 bytes and its pool grew from 165,376 to 216,064 bytes. Both-wave-bank
Trio+Macro+Shapes remained exactly 395,884 app bytes and 165,376 pool bytes.
The test links use the optional eight-voice catalogue; they do not verify default
twelve-voice allocation or hardware timing. No voice count or model was changed.

The combined `builder-inputs-v3` campaign passed 112 host checks in sixteen
containers: content preparation, module/wave-bank selection and catalogue
receipt admission. No OOM. Private receipts and per-profile artifacts are under
the same Hera root. The expanded-layout alternative is a separate design
proposal in `notes/2026-10-13-native-expanded-layout-proposal.md`; existing link,
artifact and physical write guards remain unchanged pending the owner's decision.

## Twelve-voice RAM tradeoff verification

Added explicit probe option `--flash-plaits-wavetables`, requiring
`--compressed-wavetables`; default behavior remains unchanged. It retains the
original Plaits immutable wave bank in XIP and decodes only the selected Braids
bank. The build receipt records the option. No engine sound data or Shapes
voice count changes [verified source inspection].

A freshly compiled twelve-voice indexed catalogue (167 objects across sixteen
Hera containers, all successful) was used for `module-target-v3-flash-plaits-12`.
Twelve of sixteen selected profiles pass the existing link/admission guards;
four refuse flash overflow of 70,508, 5,140, 144,216 and 147,016 bytes. The latter
two are thirteen engines without effects and with Plate respectively. These
are expected guard refusals, not installable outputs [verified].

A successful Trio/Macro/Shapes receipt records twelve Shapes voices, only
33,024 decoded Braids bytes and a 216,064-byte instance pool. Keeping Plaits
in flash recovers 50,688 pool bytes relative to decoding both banks [verified].
All 112 module/content/cache receipt checks passed in sixteen Hera containers
(`builder-inputs-v4`). Extended allocator tests cover pools of 165,376, 196,608
and 216,064 bytes: 48 ASan/UBSan cases in sixteen containers pass. The largest
pool accepts the measured 206,904-byte twelve-voice Shapes request after host
TLSF overhead; smaller pools reject it. Fragmentation, replacement failure,
coalescing, pointer stability and guard bytes remain checked [verified host].

Receipts are private under Hera
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/`:
`module-target-v3-flash-plaits-12-verification.json`,
`builder-inputs-v4-verification.json`, and
`instance-pool-capacities-v2-verification.json`. None reports container OOM.
Host allocator capacity is not pi32v2 execution, multi-track/effect allocation,
real-time acceptance or physical installation. The pending expanded-layout
proposal remains unimplemented; no partition guard or hardware operation was
changed.

## Constant content embedding [verified host and target compilation]

`tools/native/embed_image_content.py` consumes the verifier's checked snapshots
and emits `content_catalogue.c`, its module header and a commit-last embedding
receipt. `firmware/native/content_catalogue.h` describes constant project/set
bytes and their lengths. Empty selections use one unused sentinel for C99.
Each packed file retains the existing 96 KiB format bound; the aggregate is
bounded by physical flash capacity, with the smaller application limit still
requiring a real link. These files do not claim playback or firmware admission.

Already-packed binary projects and sets are now preserved after the state
reader validates their bounds and CRCs. Previously the preparer routed binary
sets through the host packer's JSON conversion, which sets do not support.
The first campaign exposed that failure; its receipt is retained. Corrupted
binary inputs still refuse preparation without writing an accepted manifest.

The corrected campaign passed 151 combined checks in sixteen Hera containers,
with zero nonzero exits and no OOM. Thirty-two text/binary, zero/one/two/four-
asset and `-Os`/`-Oz` combinations verified host executable output byte-for-byte
and actual pi32v2 compilation. Target objects have no undefined symbols or
writable data/BSS; the descriptor occupies twelve bytes per entry. Additional
checks cover corrupt project/set input, output refusal and descriptor bounds.
Private receipt: `out/content-embedding-v2-verification.json` under the Hera
root above, SHA256
`982423c2fa058170a12468701bcf506ccf297c9af1deae255216722280c4f59c`.
Embedding is not yet wired into the timed application linker or native playback.
The thirteen-engine default, full-app flash/RAM/timing, web builder/installer,
and physical release/recovery acceptance remain open.

## Prepared profiles in the timed application link [verified target]

`build_application_probe.py --prepared-profile DIR
--expected-profile-sha256 DIGEST` now consumes the checked content snapshots and
selects the profile's canonical modules. These options require each other and
refuse concurrent `--modules`/`--exclude` overrides. The freshly regenerated
module header must exactly match the prepared header. Constant content and
catalogue/count roots are linked into the ELF and counted by the unchanged
application flash limit. The link report retains manifest/source/payload
hashes; native playback and sequence acceptance remain explicitly false.

Sixteen Hera containers linked five-engine profiles, with and without Plate,
text and binary sources, and zero/one/two/four assets. All SDK-free link audits,
undefined-symbol checks and guarded artifact flattening passed. Independent
ELF reads checked the count, twelve-byte descriptors, flash pointer bounds,
kinds, lengths and every payload byte. The largest test content occupied
6,116 bytes. No device commands ran. These are timed diagnostic builds, not
installable release firmware or proof that these songs can play on the device.
Private receipt: `out/content-link-v1-verification.json`, SHA256
`7d256412511bcd4faae5273acf230a1586e776a65c16e8a05157419ca1b7c24c`.

Five new refusal cases cover unpaired options, selection overrides and a
self-consistently hashed but noncanonical module header. The expanded 156
builder/catalogue checks passed in another sixteen Hera containers, no OOM.
Receipt: `out/content-embedding-v3-verification.json`, SHA256
`9987be700f80fc1077d7edb0a806218fa9aa940cc77532b6d289493c8a76c6ee`.
