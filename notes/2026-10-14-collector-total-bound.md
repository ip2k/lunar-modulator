# Native project collector: conservative full-container bound

**Scope.** Static source-derived upper bound for the firmware SAVE adapter and its compact binary stream writer at base `31d2e8cd05afd4875d303dca1b52ea5c138aed0f`. This asks whether the current app's emitted project can exceed 64 KiB. It does not change the generic import format or prove physical storage-slot acceptance.

## Result

A deliberately conservative sum of collector-reachable payload maxima plus maximum per-chunk alignment is **43,130 bytes**. This is below 65,536 bytes by 22,406 bytes. The static bound therefore supports a 64 KiB raw binary ceiling for files emitted by this native project collector without shrinking its existing sequencer, voices, parameter records, module-data, or cable limits.

The bound safely overcounts some mutually constrained dimensions: it grants every optional INFO string its full field capacity, every one of 18 UNIT chunks its maximum 15-byte ID, every module position 32 parameters, eight Register data records, 32 maximum-length cable labels, every optional VIEW key, and three alignment bytes before each of 24 chunks. It is a conservative source bound, not a synthetic run through the writer or proof that all maxima coexist in one runtime state.

| Emitted component | Conservative bytes | Derivation |
| --- | ---: | --- |
| INFO | 750 | 2-byte count + six entries × 6-byte KV header + text bytes: BY `firmware` (8) + name32 + title64 + about512 + author64 + licence32 = 712 text bytes |
| PROJ | 58 | Three signed values, key root and scale `mixolydian` (10): 2 + 3×10 + 10 + 16 |
| UNIT and MODR parameter rows | 10,656 | Corrected registered-descriptor bound: 1,044 ordinary rows × 8 + 256 module rows × 9 |
| UNIT framing and level | 480 | 18 × (4-byte prefix + 1-byte ID length + max 15-byte ID + 2-byte parameter count + 2-byte level count) + four sound levels × 12 |
| DX7V | 5,121 | Count byte + 32 voices × (slot1 + flags1 + VCED155 + reserved3) |
| MODR excluding parameter rows | 1,480 | Header/seed8 + 8 module records × (tag/position/length3 + max ID15) + 8 Register records × 10 + 32 cables × 39 |
| SEQS | 23,095 | Eight-track bound including 64 maximum-length space-containing AU labels that use raw-text fallback; correction from previous 22,455-byte estimate is +640 bytes (37-byte raw versus prior 27-byte assumed typed); see `notes/2026-10-14-collector-sequence-bound.md` |
| VIEW | 102 | Count2 + mode and all nine possible view key/value entries × 10; app emits fewer keys |
| Alignment | 72 | 24 possible chunk starts × at most 3 bytes |
| **Chunk payloads and alignment** | **41,814** | Sum above |
| Stream header/directory reservation | 1,316 | Fixed `STREAM_BASE = 32 + 20×64 + 4`, including the maximum 64-entry directory reservation |
| **Full container** | **43,130** | 41,814 + 1,316 |

## Source basis

- Native SAVE substitutes INFO `by=firmware` (`firmware/native/project_save_app.h:14-23`) and calls `fm1_app_state_collect_project(..., include_view=1)` (`:25-33`). The collector emits five app metadata strings, one session, four sound units and levels, eight inserts, two master effects, one MIDI-FX per active sound, every loaded DX7 voice, modulation and sequencer records, then VIEW (`sim/web/src/fm1_app_state.c:445-477`). For the conservative count, the MIDI-FX multiplicity is four, all 18 UNIT chunks are treated as populated, and app metadata array capacities are taken from `fm1_app.h:363-369`.
- Binary KV records cost a 2-byte count plus 6-byte per-entry header and payload. Session writes three integer fields and, when `has_key`, root plus scale (`engines/state/state_bin.c:425-443`). Scale strings are the fixed eight-entry table, whose longest member is `mixolydian` (10 bytes) (`sim/web/src/fm1_app_state.c:40-44`). INFO and PROJ remain far under their respective 2,048-byte chunk caps (`state_bin.c:61-68`).
- The UNIT row bound and engine/mfx/mod parameter multiplicities are in `notes/2026-10-14-collector-parameter-bound.md`. Writer UNIT framing is visible at `engines/state/state_bin.c:445-481`: four prefix bytes, one length byte, NUL-terminated ID, 2-byte parameter count, and a 2-byte level count; sound levels add a 10-byte KV item. `fm1_state.h:206` bounds IDs to 15 non-NUL bytes. This deliberately uses that generic maximum for every UNIT, not measured registry ID lengths.
- DX7 voices are fixed-width 160-byte records plus the count byte (`engines/state/state_bin.c:484-489`); there are 32 user slots (`engines/include/fm1_dx7.h:35`).
- MODR starts with eight bytes; module items encode tag/position/length/ID, module params are the 9-byte rows already counted in the parameter subtotal, Register data and cables use the previously reviewed limits (`engines/state/state_bin.c:491-522`, `engines/include/fm1_mod.h:71-82`, and the collector/registry evidence in the sequence-bound note). The maximum ID uses the same generic 15-byte bound as UNIT. This MODR subtotal excludes the module-parameter rows to avoid double-counting the 256 × 9 bytes.
- The application collector emits set lines, not project CLIP records; it emits no settings (`fm1_app_state.c:445-477`). Thus this container has at most one each of INFO, PROJ, DX7V, MODR, SEQS and VIEW, plus 18 UNIT chunks; CLIP and SETG are absent. The count is 24. The streaming writer reserves a fixed `STREAM_BASE` for all 64 directory entries, regardless of the actual count (`engines/state/state_bin.c:147,180,357-360`); chunk start alignment is at most three bytes (`:260-279`).
- The firmware SAVE path uses the compact stream writer and passes the slot-derived capacity through `lunar_project_save` (`firmware/native/project_save.h:7-8,58-75`). The writer's 98,304-byte `FM1_STATE_BIN_MAX` remains the generic maximum (`engines/state/fm1_state.h:106-107`; enforced by stream writer and reader in `state_bin.c:180,362,1299-1304`). The same container format is used for generic imports, so this result does **not** prove that accepted input may be capped at 64 KiB: only native app emission is bounded here. Existing generic chunk caps and accepted import limits are unchanged.

## Limits and next step

The parameter term was corrected after checking the registered Sophie descriptor: 273 rows relied on the full 18-entry backing array, but `kExposed=P_CRUSH` registers only eight parameters. The sequence term includes the raw-text AU fallback for worst-case space-containing labels; the fallback adds ten bytes per maximal label over the prior assumed 27-byte bound. The corrected source-derived total bound is 43,130 bytes. The maximal four-Drums fixture produced and decoded a 35,176-byte native SAVE body through the actual collector and compact writer, below this conservative bound. Its SAVE/recovery path was then retested with 49,152-byte slots; see `notes/2026-10-14-collector-max-validation.md` for the exact run and outcome. The combined fixture validates an admitted state but cannot prove every independently maximal dimension coexists. This inventory changed no production source and ran no hardware commands. Semantic tools were left on the primary checkout rather than redirected from this assigned worktree; navigation used bounded source reads.
