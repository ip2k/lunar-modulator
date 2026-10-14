# Native project collector: reachable parameter-record upper bound

**Scope.** Static source bound for parameter records emitted by `fm1_app_state_collect_project` in the firmware SAVE route. This is not a maximum binary-size proof, a writer-workspace bound, nor flash-bank/physical acceptance. No build or hardware operation was run for this note.

## Result

The sound-unit record maximum is set by `sw-sophie`: 18 descriptor parameters, of which Pad is the focus selector and the other 17 are per-focus. The collector emits the selector once and each per-focus value for every focus entry, capped at 32. Sophie has 16 focus entries, so that is `1 + 17*16 = 273` parameter records per sound unit; four units yield 1,092.

| Native project parameter source | App multiplicity | Per-instance bound | Project records |
| --- | ---: | ---: | ---: |
| Sound engines (largest is Sophie) | 4 sounds | `1 + 17*16 = 273` | 1,092 |
| Insert/master audio effects | 8 inserts + 2 master = 10 | 32 | 320 |
| MIDI effects | one collected per populated sound | 32 | 128 |
| Modulation modules | 8 rack positions | 32 | 256 |
| **Parameter-record subtotal** |  |  | **1,796** |

The 32-parameter audio-effect bound follows the app admission check (`FM1_APP_MAX_PARAMS` and `e->n_params > FM1_APP_MAX_PARAMS`); it is a descriptor ceiling, not a claim that a concrete effect has 32 parameters. MIDI-FX uses its separate `FM1_APP_ARP_PARAMS` admission ceiling of 32. The sound-engine figure is an exact maximum across the thirteen registered engines. This bound assumes every relevant slot is populated and all 8 module positions are used. It does not count sequencer records, DX7 voice records, UNIT framing, level/session/info/view records, module/cable/data records, or binary headers/CRCs.

Native compact serialization is fixed-width, not varint: each ordinary UNIT parameter row is 8 bytes (`u16 uid + u8 focus + u8 value type + u32 value`); a modulation module parameter row is 9 bytes (tag/slot + uid + value type + value). Thus this parameter-record subtotal contributes at most `1,540*8 + 256*9 = 14,624` bytes of parameter rows, excluding unit/chunk framing. This is a record-payload bound; it is not the whole-file maximum.

The serializer permits at most 512 ordinary parameter rows in any one UNIT. The largest collector-reachable sound UNIT here is 273, so that per-unit format guard does not bind. The independent 32,924-byte dense fixture is an observed accepted example, not the maximum: its four Drums units produce `4*9*16 = 576` focused rows, and its 69 module parameter rows are only one chosen rack population.

## Thirteen-engine descriptor counts

`P_COUNT` is the descriptor length for the first ten; the final three use array lengths referenced by the engine descriptor. `Focused expansion` is the number of rows the collector emits for that engine per sound unit, including the one focus selector. Only rows marked `PER_FOCUS` are multiplied by the focus count.

| Engine | Descriptor parameters | Focused expansion / unit | Basis |
| --- | ---: | ---: | --- |
| Macro | 15 | 15 | `mi_macro.cc:99-111` |
| Shapes | 10 | 10 | `mi_shapes.cc:94-103` |
| Macro Heavy | 16 | 16 | `mi_macro_heavy.cc:230-246` |
| Sixop | 8 | 8 | `mi_sixop.cc:145-154` |
| DX7 | 9 | 9 | `msfa_dx7.cc:83-92` |
| SW Sophie | 18 | 273 | `sw_sophie.cc:42-47,68-87`; focus has 16 entries and its other 17 parameters are per-focus |
| Drums | 14 | 149 | `drums.cc:253-258,276-294`; 9 per-focus rows x 16 pads, plus 5 once |
| Acid Bass | 12 | 12 | `acid_bass.cc:83-91` |
| Comet Kit | 13 | 148 | `comet_kit.cc:108-116,131-150`; 9 per-focus rows x 16 pads, plus 3 once |
| Crater Kit | 11 | 116 | `crater_kit.cc:102-110,133-151`; 7 per-focus rows x 16 pads, plus 3 once |
| Drawbar | 13 | 13 | `felucca_shim.cc:168-181,267-273` |
| Trio | 14 | 14 | `felucca_shim.cc:202-219,267-273` |
| Phase Bend | 16 | 16 | `felucca_shim.cc:237-255,267-273` |

The largest expansion is therefore Sophie (273). The highest raw descriptor count is also Sophie (18), but raw `n_params` alone misses per-focus expansion. Four Sophie units fit below the writer's 512-row UNIT guard.

## Source chain and limits

- `engines/src/registry.cc:67-84` lists these thirteen sound engines; the next entries are test/audio-effect engines.
- `sim/web/src/fm1_app_state.c:158-177` emits every descriptor parameter, multiplying only state-focus category 2 across the engine focus count and `FM1_STATE_PADS`; `fm1_app_state.c:179-195` emits MIDI-FX descriptor parameters once each.
- `sim/web/src/fm1_app_state.c:456-470` traverses four sound units, each sound's two inserts, two master effects, one MIDI-FX per active sound, loaded DX7 slots, modulation, and the active sequencer set. The firmware SAVE adapter calls this collector with view enabled (`firmware/native/project_save_app.h:27-33`).
- `sim/web/src/fm1_app.h:166-180` fixes four sounds, two insert positions per sound, two master positions (10 audio FX slots), and `FM1_APP_MAX_PARAMS=32`; `sim/web/src/fm1_app.c:1021-1025` rejects an audio engine whose descriptor exceeds that limit. MIDI-FX separately uses `FM1_APP_ARP_PARAMS=32` (`fm1_app.h:281-289`; admission at `fm1_app.c:2606-2610,2660-2668`). `engines/include/fm1_mod.h:71-73,267-268` gives eight module positions and at most 32 parameters per module kind.
- `engines/include/fm1_engine.h:127-134,456-459,573-583` defines the focus/per-focus flags and 32-entry global focus ceiling. The project collector additionally caps at `FM1_STATE_PADS` (`fm1_state.h:108`); each of these pad engines exposes 16 pads.
- `engines/state/state_bin.c:465-476` shows fixed-width 8-byte UNIT rows and the 512-row limit; module rows are fixed-width 9 bytes at `state_bin.c:465-470`. DX7 voices are separate records (`state_bin.c:484-489`): the app has 32 user slots (`tests/test_native_project_capacity.py:28`) and each binary voice payload is 160 bytes, not a parameter record.
- `tests/test_native_project_capacity.py:5-8,21-34,145-167` explicitly labels the fixture a concrete state rather than a maximum proof, sets 8 sequencer tracks/32 matrix cable slots/8 modules/32 voices/4 sounds/10 FX slots, and checks the 69 module rows and 576 Drums pad rows. `notes/2026-10-14-project-capacity-measurement.md:71` records the measured 32,924-byte body.

## Verification and next dependency

This was checked by reading source and computing the table from enum/descriptor declarations and the collector multipliers. Tests were not run; no source changed outside this note. Semantic tools were not used against this assigned worktree because their active project root was the primary checkout; I did not alter shared tool selection. The 1,796 row result is a conservative parameter-only bound under current app slot/count constants. To make it an exact full-project byte ceiling, next derive maxima for populated effect descriptors, MIDI-FX descriptors, module kind combination/data/cables, sequencer serialization, strings and container framing, then exercise a synthetic state through the actual collector and binary writer. That full bound is the coordinator's next dependency if deciding native SAVE workspace/slot capacity.
