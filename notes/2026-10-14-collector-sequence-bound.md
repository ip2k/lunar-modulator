# Native collector sequencer and modulation-data bound

Read-only source inventory at base `31d2e8cd05afd4875d303dca1b52ea5c138aed0f`.

## Finding

The native app's eight-track default sequencer has a conservative source-derived upper bound of **23,095 encoded bytes in the SEQS body**, assuming every bounded optional/exportable field is populated at its largest value and the event pools are distributed across all 64 track/clip slots. This is below the binary writer's 49,152-byte SEQS chunk cap. This is a calculated bound from the exporter and codec, not a measured maximum fixture. Most typed item fields use fixed-width little-endian integers, regardless of their decimal text width; lane labels can trigger the codec's raw-item fallback.

For the modulation pattern-data records, the compiled registry contains only one data-bearing kind: Register, with exactly five bytes per occupied Register instance. Eight Register modules therefore encode at most **8 × (5-byte record header + 5 data bytes) = 80 bytes** of module-data records. The 32-cable matrix contributes at most **32 × 39 = 1,248 bytes**. The maximum complete MODR chunk is not computed here: module parameter counts/IDs and their simultaneously reachable kind combinations need a separate registry-wide calculation. The writer enforces a 12,288-byte MODR cap.

## SEQS derivation

`fm1_seq_limits_default(..., 8)` sets 1,536 notes, 1,536 locks, 256 triggers, 64 song bytes, and 16 pad-mutes per track (`engines/seq/seq_engine.c:49-65`). The application uses eight tracks (`sim/web/src/fm1_app.h:252-260`; creation applies the default at `sim/web/src/fm1_app.c:3664-3674`). It exports these fields through the real collector's `fm1_state_seq_export` call (`sim/web/src/fm1_app_state.c:338-347`); the production project SAVE adapter calls that collector (`firmware/native/project_save_app.h:31-32`).

The typed item widths are specified in `engines/state/state_movy1.c:15-32`. Event payload is fixed at 8 bytes/note, 3 bytes/lock, and 6 bytes/trigger. Clip/lock/trigger headers are respectively 9/5/5 bytes, and each existing clip emits its 7-byte `cp` record (`engines/seq/seq_persist.c:144-193`). There are 8 × 8 = 64 possible clips and each clip-specific pool cap (512 notes, 1,024 locks, 1,024 triggers) permits distributing the defaults over those slots. Thus the upper bound's event subtotal is:

```
notes:    1,536 × 8                       = 12,288
locks:    1,536 × 3                       =  4,608
triggers:   256 × 6                       =  1,536
headers: 64 × (cl 9 + cp 7 + lk 5 + tg 5) =  1,664
event subtotal                                 20,096 bytes
```

The remaining exporter-emitted records (`engines/seq/seq_persist.c:77-143`) add at most 2,999 bytes:

```
movy1, bpm, swing, link                    13
song: tag + u16 count + 64 u8 entries      67
key + dq + non-loop se                      7
8 scene names: 8 × (tag + scene + len + 6) 72
8 tracks: tk                                  32
8 × 16 pad mutes                             384
8 pad-solo lines                               24
8 × 8 lane lines: max 37-byte raw item each 2,368
8 route lines                                 32
                                             ----
                                             2,999
```

Total: **20,096 + 2,999 = 23,095 bytes**. The lane item calculation corrects an earlier undercount: a typed `au` item has five fixed bytes (tag, track, lane, base and label length) plus up to 23 label bytes, for 28 bytes. `fm1_movy1_encode` falls back to a raw item when a label contains a space (`engines/state/state_movy1.c:163-174,423-457`), and labels are stored up to 23 bytes (`engines/seq/seq_cmd.c:514-516`). The exporter line can be 34 bytes without its line terminator (`seq_persist.c:131-135`): `au ` + one-digit track + space + one-digit lane + space + three-digit base + space + 23-byte label. The raw tag and u16 length add three bytes, so the maximum is 37 bytes per lane, 10 bytes above the old 27-byte calculation. This remains an upper bound; some combinations may be semantically redundant or unreachable, which can only lower it. It excludes the binary file header/directory/alignment, which are outside the SEQS chunk cap and do not change the chunk-body bound.

The compact writer streams each encoded SEQS line to the destination and checks cumulative bytes against `kCap[CH_SEQS] = 49,152` (`engines/state/state_bin.c:61-68,333-345`). The source also caps MOVY1 text input at 65,536 (`engines/include/fm1_state_caps.h:14-20`): that is the larger general text-format cap, not the encoded binary SEQS allowance. The writer line staging limit is 16 KiB (`engines/state/state_bin.c:120-138,524-531`); bounded native exporter lines fit beneath it under the per-clip pool limits. The independent test fixture's 32,924-byte full project (`tests/test_native_project_capacity.py`) is therefore not a maximum and is unnecessary to infer this sequence bound.

## MODR data and cables

The public limits are eight rack positions, 32 cable slots, and 1,024 generic bytes/module (`engines/include/fm1_mod.h:71-82`). The app collector emits data only when `fm1_mod_get_data` returns nonzero (`engines/state/state_mod.c:151-195`). Registry source shows non-Register descriptors use zero data bytes; Register uses `REG_DATA_BYTES=5`, layout 1 (`engines/mod/kinds/mod_register.c:124-158`). Its five-byte payload is four register bits plus length, and its setter accepts length 1..32 (`:126-142`). Multiple positions may hold the kind; the positions and collector loop permit at most eight data records.

Each encoded data record has a 5-byte header (tag, position, version, u16 length) followed by payload (`engines/state/state_bin.c:503-512`), so eight occupied Registers are exactly bounded by 80 bytes. The reader independently enforces 4,096 bytes per module and 8,192 aggregate (`engines/state/state_bin.c:1120-1127`; `engines/state/fm1_state.h:105-110`); these generic reader ceilings do not make 1,024-byte patterns reachable in the current compiled registry.

Cable records use 14 bytes of fixed fields plus a one-byte name length and up to 24 name bytes, hence 39 bytes each (`engines/state/state_bin.c:514-522`). At 32 cables this is 1,248 bytes. Together, cable records and all Register data records occupy at most **1,328 bytes**, before the MOD header/seed, module IDs, and module-parameter records. MODR's chunk cap is **12,288 bytes** (`engines/state/state_bin.c:61-68`). A tighter full-MODR maximum is unproved in this inventory because it would require enumerating parameter counts and module-ID lengths across all compiled kinds and proving the maximum combination can occupy all eight positions while accepting all 32 cables.

## Tool and validation limits

The required semantic services were available but selected `/Users/likwid/Developer/mvave-fm1-firmware`, not this assigned worktree. Per the shared-root instruction, I did not redirect or reactivate them. Serena instructions/configuration and Rarefaction status were checked; source navigation therefore used bounded `rg`, `sed`, and numbered reads in the assigned checkout. No tests, builds, device operations, or production edits were performed. Only this report was added; the pre-existing untracked `notes/2026-10-14-physical-storage-compression.md` was left untouched.
