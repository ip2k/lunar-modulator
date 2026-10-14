# Native project collector: reachable parameter-record upper bound

**Scope.** Static source bound for parameter records emitted by `fm1_app_state_collect_project` in the firmware SAVE route. This is not a maximum binary-size proof, a writer-workspace bound, nor flash-bank/physical acceptance. A second native collector SAVE fixture validates the largest registered sound-engine expansion (four Drums units) together with populated app pools; a four-Sophie attempt was rejected by the app RAM admission check. No hardware operation was run.

## Result

The earlier 273-row Sophie figure was an overcount of parameters present in the backing descriptor array but not exposed by the registered engine. `sw-sophie` registers only `kExposed = P_CRUSH` (enum ordinal 8), so the app can see Pad plus seven per-pad parameters. The collector emits the selector once and those seven values for each of the 16 pads: `1 + 7*16 = 113` records per Sophie sound. The largest reachable expansion is Drums at `9*16 + 5 = 149` records per sound; four Drums sounds yield 596.

| Native project parameter source | App multiplicity | Per-instance bound | Project records |
| --- | ---: | ---: | ---: |
| Sound engines (largest expansion is Drums) | 4 sounds | `9*16 + 5 = 149` | 596 |
| Insert/master audio effects | 8 inserts + 2 master = 10 | 32 | 320 |
| MIDI effects | one collected per populated sound | 32 | 128 |
| Modulation modules | 8 rack positions | 32 | 256 |
| **Parameter-record subtotal** |  |  | **1,300** |

The 32-parameter audio-effect bound follows the app admission check (`FM1_APP_MAX_PARAMS` and `e->n_params > FM1_APP_MAX_PARAMS`); it is a descriptor ceiling, not a claim that a concrete effect has 32 parameters. MIDI-FX uses its separate `FM1_APP_ARP_PARAMS` admission ceiling of 32. The sound-engine figure is an exact maximum across the thirteen registered engines; the audio-effect term is intentionally conservative and not witnessed by a single registered effect with 32 descriptors. This bound assumes every relevant slot is populated and all 8 module positions are used. It does not count sequencer records, DX7 voice records, UNIT framing, level/session/info/view records, module/cable/data records, or binary headers/CRCs.

Native compact serialization is fixed-width, not varint: each ordinary UNIT parameter row is 8 bytes (`u16 uid + u8 focus + u8 value type + u32 value`); a modulation module parameter row is 9 bytes (tag/slot + uid + value type + value). Thus the corrected parameter-record subtotal contributes at most `1,044*8 + 256*9 = 10,656` bytes of parameter rows, excluding unit/chunk framing. This is a record-payload bound; it is not the whole-file maximum.

The serializer permits at most 512 ordinary parameter rows in any one UNIT. The largest collector-reachable UNIT here is Drums at 149 sound rows; audio-FX and MIDI-FX descriptors are separately admitted only up to 32 rows. The per-unit format guard therefore does not bind. The independent 32,924-byte dense fixture is an observed accepted example, not the maximum: its four Drums units produce `4*9*16 = 576` focused rows, and its 69 module parameter rows are only one chosen rack population.

## Thirteen-engine descriptor counts

`P_COUNT` is the descriptor length for the first ten; the final three use array lengths referenced by the engine descriptor. `Focused expansion` is the number of rows the collector emits for that engine per sound unit, including the one focus selector. Only rows marked `PER_FOCUS` are multiplied by the focus count.

| Engine | Descriptor parameters | Focused expansion / unit | Basis |
| --- | ---: | ---: | --- |
| Macro | 15 | 15 | `mi_macro.cc:99-111` |
| Shapes | 10 | 10 | `mi_shapes.cc:94-103` |
| Macro Heavy | 16 | 16 | `mi_macro_heavy.cc:230-246` |
| Sixop | 8 | 8 | `mi_sixop.cc:145-154` |
| DX7 | 9 | 9 | `msfa_dx7.cc:83-92` |
| SW Sophie | 8 registered (18 backing-array entries) | 113 | `sw_sophie.cc:42-50,69-87,136-156`; `kExposed=P_CRUSH` exposes indices 0..7 only: Pad selector plus seven per-focus params |
| Drums | 14 | 149 | `drums.cc:253-258,276-294`; 9 per-focus rows x 16 pads, plus 5 once |
| Acid Bass | 12 | 12 | `acid_bass.cc:83-91` |
| Comet Kit | 13 | 148 | `comet_kit.cc:108-116,131-150`; 9 per-focus rows x 16 pads, plus 3 once |
| Crater Kit | 11 | 116 | `crater_kit.cc:102-110,133-151`; 7 per-focus rows x 16 pads, plus 3 once |
| Drawbar | 13 | 13 | `felucca_shim.cc:168-181,267-273` |
| Trio | 14 | 14 | `felucca_shim.cc:202-219,267-273` |
| Phase Bend | 16 | 16 | `felucca_shim.cc:237-255,267-273` |

The largest descriptor expansion is Drums (149), not Sophie: its registered 14 parameters include nine per-focus values and five once-per-unit rows. Sophie has 18 backing-array entries but registers only eight, so the former 273-row expansion is unreachable through the app collector. Four Drums units fit below the writer's 512-row UNIT guard. Four Sophie units would emit 452 sound parameter records in total, but a concrete attempt to load Sophie into sound unit 3 was rejected with `FM1_APP_SELECT_RAM` (-4), so do not treat a four-Sophie configuration as an admitted combined state.

## Source chain and limits

- `engines/src/registry.cc:67-84` lists these thirteen sound engines; the next entries are test/audio-effect engines.
- `sim/web/src/fm1_app_state.c:158-177` emits every descriptor parameter, multiplying only state-focus category 2 across the engine focus count and `FM1_STATE_PADS`; `fm1_app_state.c:179-195` emits MIDI-FX descriptor parameters once each.
- `sim/web/src/fm1_app_state.c:456-470` traverses four sound units, each sound's two inserts, two master effects, one MIDI-FX per active sound, loaded DX7 slots, modulation, and the active sequencer set. The firmware SAVE adapter calls this collector with view enabled (`firmware/native/project_save_app.h:27-33`).
- `sim/web/src/fm1_app.h:166-180` fixes four sounds, two insert positions per sound, two master positions (10 audio FX slots), and `FM1_APP_MAX_PARAMS=32`; `sim/web/src/fm1_app.c:1021-1025` rejects an audio engine whose descriptor exceeds that limit. Thus 320 audio-effect records is a descriptor-admission ceiling over the ten slots, not a claim that a registered effect has 32 parameters. MIDI-FX separately uses `FM1_APP_ARP_PARAMS=32` (`fm1_app.h:281-289`; admission at `fm1_app.c:2606-2610,2660-2668`). `engines/include/fm1_mod.h:71-73,267-268` gives eight module positions and at most 32 parameters per module kind.
- `engines/include/fm1_engine.h:127-134,456-459,573-583` defines the focus/per-focus flags and 32-entry global focus ceiling. The project collector additionally caps at `FM1_STATE_PADS` (`fm1_state.h:108`); each of these pad engines exposes 16 pads.
- `engines/state/state_bin.c:465-476` shows fixed-width 8-byte UNIT rows and the 512-row limit; module rows are fixed-width 9 bytes at `state_bin.c:465-470`. DX7 voices are separate records (`state_bin.c:484-489`): the app has 32 user slots (`tests/test_native_project_capacity.py:28`) and each binary voice payload is 160 bytes, not a parameter record.
- `tests/test_native_project_capacity.py:5-8,21-34,145-167` explicitly labels the fixture a concrete state rather than a maximum proof, sets 8 sequencer tracks/32 matrix cable slots/8 modules/32 voices/4 sounds/10 FX slots, and checks the 69 module rows and 576 focused Drums pad rows (the additional 20 unit-scoped Drums rows are not included in that focused subset). `notes/2026-10-14-project-capacity-measurement.md:71` records the measured 32,924-byte body.

## Verification and next dependency

The table is derived from registered descriptor lengths, focus flags and collector multipliers. The maximal Drums fixture independently verifies 596 sound rows (including 576 focused values) and, through the native SAVE/recovery path, 72 module rows, eight nine-parameter Mix modules, 32 cables, four 24-row MIDI-FX units, 32 DX7 voices, ten populated audio-FX slots, 64 maximum-length space-containing AU labels, and full sequencer note/lock/trig pools. Its decoded compact body is 35,176 bytes and is below the source-derived 43,130-byte conservative bound. The test also verifies maximum metadata strings. This validates a combined admitted state, not the 32-row admission ceiling for every audio-effect descriptor. Four Sophie units are not an admitted state: a separate attempt failed at sound unit 3 with `FM1_APP_SELECT_RAM` (-4), so Sophie remains a per-unit static bound of 113 rows and is not used to inflate the reachable four-unit maximum. The 1,300-row total remains conservative because it assigns 32 rows to each of ten audio effects and each of four MIDI effects. The 48 KiB-slot SAVE/recovery test result and its interruption-coverage limit are recorded in `notes/2026-10-14-collector-max-validation.md`; no hardware operation was run.
