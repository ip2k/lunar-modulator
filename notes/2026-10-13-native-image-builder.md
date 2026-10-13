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
