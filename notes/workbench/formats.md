# Offline Workbench format pilot

2026-10-17. Lunar Modulator, open firmware for the M-VAVE FM-1. Personal
project. Source-only tool; no USB, MIDI, network or device operations.

## Retained slice and use

[verified] `tools/workbench/formats.py` converts one DX7 VCED dump or one
32-voice VMEM dump into an existing canonical Lunar **sound** file. It uses
`tools/lunar_state.py` with the checked-in `sim/web/www/meta.json` metadata,
selects FM6's **User 1**, and fills User 1 through User 32 in source order.
A single voice fills User 1. It does not create a second state model.
The output opens through Lunar's existing Open/drop flow; the other voices
remain accessible through the FM6 Patch parameter.

[verified] Lunar already imports SysEx through **Load DX7 patches** and the
normal Open/drop flow (`sim/web/www/files.js`, `app.js`). This pilot adds
strict offline validation, a consumable sound wrapper, deterministic export
and a reviewable loss/default report. It needs no new browser interface.
The reserved state kind `dx7bank` is rejected by the actual C and Python
readers; the adapter never emits it (`engines/state/fm1_state.h`,
`state_bin.c`, `state_json_read.c`).

From the repository root:

```sh
python3 tools/workbench/formats.py inspect input.syx
python3 tools/workbench/formats.py import input.syx -o imported.lunar --report import-report.json
python3 tools/workbench/formats.py export imported.lunar -o exported.syx --report export-report.json
```

[verified] Import/export require both explicit new output paths and a new
report path. Existing files, symlinks and input/output/report aliases are
refused. The tool reserves both files with exclusive creation and removes
only its newly created files if either write fails. It has no overwrite flag.
An export that loses state fails with the proposed JSON report on stderr;
review that report before repeating with `--allow-loss`. Preserve the
original Lunar file: accepting loss does not make it reversible.

[verified] API: `import_syx(bytes) -> (lunar_bytes, report)`;
`export_syx(bytes, channel=0, allow_loss=False) -> (syx_bytes, report)`;
`inspect_file(bytes) -> dict`. `ConversionError.code` identifies refusal;
loss refusals also expose `.report`. Loss reports use schema
`lunar-workbench-loss/1`, with `preserved`, `losses`, `defaults`,
`limitations`, source/target formats and voice count. Channel numbers are
zero-based 0..15; source channel is recorded but is not part of Lunar state.

## Format and loss matrix

The vendor facts below are [verified source] at M-VAVE
`fm1_open b178ac43c25f010c60a878056fb5331fe693fd62`; kit SHA-256
`2a3b2ede16ac49c867831315714ef9d8c532c70ce28ce1dcf3fc76f0a9f68f57`.
File length includes the container header.

| Format | Contract inspected | Conversion and loss boundary |
| --- | --- | --- |
| `.syx` VCED | 163 bytes, `F0 43 0n 00 01 1B`, 155 payload bytes, Yamaha seven-bit sum checksum, `F7` | Supported to/from Lunar sound. All voice parameter/name bytes and order retained. Lunar macros, level, inserts, MIDI FX, mod rack and metadata cannot be stored in SysEx; changed fields require explicit loss opt-in. SysEx has no song, chord, lock, sequence length, tuning or sample-reference data. |
| `.syx` VMEM | 4,104 bytes, `F0 43 0n 09 20 00`, 32 x 128 packed bytes, checksum, `F7` | Supported as exactly 32 contiguous voices. Packed reserved bits and out-of-range fields are refused. No padding, truncation, slot renumbering, raw 4096-byte banks, concatenated messages, realtime interleaving or third-party SysEx are accepted by this strict pilot. |
| `.fm1` | `FM1P`, LE version 3/4 in a 16-byte header with payload size/CRC32; 4064/4080/4280 bytes total. Payload 4048 is v3; 4064/4264 is v4; byte 3852 repeats version. Optional final 200-byte `FM1T` tuning block has its own CRC32. | Container/tuning inspection only. No conversion: vendor six-engine/8-track state differs from Lunar engine IDs, effects, chords, locks, lengths and musical model. A project references a shared sample bank and does not contain its audio. Envelopes passing inspection are not proof of playable preset/sequence semantics. |
| `.fm1t` | `FM1T`, LE version 1; 239 bytes total = 16 header +223 preset; payload CRC32 | Envelope inspection only. No conversion: source type/program, controls/ADSR/operator mask/mono, FX sends, source-specific data, requested sequence pages and sample references need explicit mappings. Export an FM voice as DX7 `.syx` in Workbench for the supported path. |
| `.fm1s` | `FM1S`, LE v1; 512-byte header, 16 table entries with slots9..16 empty; 8 shared sample slots; 32kHz SEA5, 320-frame chunks encoded to228 bytes; chunk marker `01 45 14 5A`; CRC32 treats bytes12..19 as zero | Structural inspection only; no SEA5 decode, sample conversion or replacement. Zero frames uses0 chunks; otherwise capacity rounds up to whole320-frame chunks. Readable size512..466944 bytes; new transfer maximum462848 reserves the final4096-byte tuning sector. A legacy full bank can inspect successfully yet exceed the new-transfer bound. |

[verified] Normal imports default Lunar's sound macros, level and empty FX,
because SysEx does not encode those controls. Re-exporting the generated sound
has no voice losses. Export permits exactly one voice in User1 or exactly
32 voices in User1..32; sparse/partial banks are refused. The selected Patch
setting is reported as loss if it differs from the generated User1 baseline.
Voice-only round trips are byte-identical at matching channel for canonical
valid VMEM/VCED inputs. This does not claim sound parity between synthesizers.

[verified] `.fm1/.fm1t` inspection validates their containers, not complete
native preset/sequence validity. `.fm1s` inspection validates header/table/
CRC/chunk markers, not decoded audio or audible quality. Unsupported formats
fail conversion before creating outputs. All unsupported fields remain in
the untouched source file.

## Reuse, provenance and implementation choice

[verified] Existing MIT Lunar code already supplies the canonical JSON/binary
state codec, field ranges, checksum and synthetic voice definitions. The
adapter reuses those directly. `tools/dx7_bank.py`'s high-level `Voice`
packing goes through floating ratio/frequency quantization; the adapter's
small exact integer field packing preserves VCED's original coarse/fine bytes.
The native C codec has equivalent raw-byte packing
(`fm1_dx7_pack_voice`, `fm1_dx7_write_voice`, `fm1_dx7_write_bank`).
A new framework/third-party parser adds no necessary capability to this
bounded stdlib file adapter. No vendor GPL implementation was copied into
the MIT adapter; vendor sources supplied format facts and citations only.

Primary source references:

- [M-VAVE file envelopes and SysEx](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/WebUpdate.js#L474-L561).
- [M-VAVE sample bank and capacity](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Samples.js#L4-L43).
- [M-VAVE preset/project layout and tuning reservation](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/app/instrument.h#L134-L173).
- [M-VAVE tuning/sample region relationship](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/app/instrument.h#L289-L296).
- Lunar `engines/include/fm1_dx7.h`, `engines/src/dx7_voice.cc`,
  `tools/dx7_bank.py`, `tools/lunar_state.py`,
  `engines/state/state_json_read.c` and `sim/web/www/meta.json`.

## Reproduction and acceptance limits

[verified] `tests/fixtures/workbench/generate.py` materializes synthetic
source-owned voices and structural probe files into an explicit directory.
It includes empty/truncated/bad-checksum SysEx, 1/32 voices, v3/v4/tuned project
envelopes, unsupported timbre version, empty samples, chunk-rounding
boundaries and the old readable maximum. No vendor binary or owner recording
is included. Envelope-only projects/timbres and marker-only sample chunks are
parser probes, not playable vendor content.

[verified tool setup] Rarefaction status and Serena configuration selected
`/Users/likwid/Developer/mvave-fm1-firmware`, not this Aeon isolated checkout.
They were not retargeted over the shared session. The bounded Rarefaction
Python position query returned no reliable callable hierarchy, and Serena
refused `tools/dx7_bank.py` as ignored. Exact pinned source reads and executed
Python codec checks are the evidence here; neither absence of references nor
tool readiness establishes remote source coverage.

[verified source comparison] Native architecture reference
`1f12ad5b8d6a865268af94179a3442183a680602` has unchanged
`dx7_bank.py`, `fm1_dx7.h` and `dx7_voice.cc` versus the pilot base.
Its state/metadata differences include newer-main browser bindings and
native streaming binary writer changes; the generated sound uses only the
common v1.0 sound/unit/DX7 fields. This is an offline file pilot. No target
build, current hardware state, browser visual test, device transport,
rendered-audio or listening acceptance is implied.


[verified executed checks] The source-owned one-voice and 32-voice banks
round-tripped byte-identically through this adapter at channel0. The exact
native-reference Python state codec and metadata were read from Git objects
into a temporary directory: both generated sounds parsed with zero skipped,
repaired or unknown fields; each155-byte voice matched, Patch UID1 had
index32 (User1), and native canonical rewrite re-exported the same SysEx.
This is native-branch Python file-codec compatibility, not execution of the
native C loader or firmware. Synthetic container inspection accepted project
v3/v4/tuned envelopes, v1 timbre, empty/rounded samples and legacy maximum;
bad checksums, truncation and newer timbre version were refused. CLI
exclusive output/report creation and repeated-output refusal passed.
