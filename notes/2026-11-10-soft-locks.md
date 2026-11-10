# Lifting the M10 soft locks (2026-11-10)

Owner decision docs/18 §3 item 8, answered 2026-11-10: "Must lift before
1.0". The full-UI FM-1 build (`LUNAR_FM1_FULL_UI=1`, pipelined app
`FM1_APP_RENDER_PIPELINE=1`) refused three things that the unpipelined app
(R0) does (`notes/2026-11-09-controls.md`, "Soft locks"):

- engine and insert selection (`FM1_APP_SELECT_LOCKED`, "cannot load");
- the effect-order swap ("Effect order is fixed");
- Macro models other than 0 (VA), held at 0 silently.

All three are gone. No device was touched: no FM-1 traffic, no Pico
transporter traffic and no dev-kit run.

## 1. Why the locks existed

The pipelined app renders Sound 2's chain on CPU1 while CPU0 renders the
next block. It checked a fixed arrangement once, then compared each unit's
geometry (engine, instance, arena, size, capacity) on every block and parked
the core for good on a mismatch. A change of engine after the first block
would have tripped that check, so the UI refused changes instead.

Macro's model was held at 0 for a different reason. Its Chip model
(model 3) has an arpeggiator whose random mode drew from `stmlib::Random`,
one global shared with Drums [verified: `arpeggiator.h` before this change,
`drums.cc:709-740`]. With Macro on CPU1 and Drums on CPU0, both cores would
read and write that global at once. Drums saves the global, seeds it with
each pad's own state and restores it [verified: `drums.cc:709-740`]. That
makes the result independent of the order of calls, but not safe against a
second core writing inside the bracket [inferred]. So the race cannot be
shown by a sequential host replay: with the old arpeggiator the pipelined
and reference PCM still match [verified: swaps script, both builds], and a
real two-core run would be needed to see it.

## 2. What changed

1. **Re-sealing at the barrier** (`sim/web/src/fm1_app.c`):
   - Every successful structural change (`fm1_app_select`, a swap of units,
     the effect-order swap) runs only while nothing is in flight. It already
     did, through `PIPELINE_GUARD(!pipeline_busy())`. Each one now also
     clears the seal (`PIPELINE_UNSEAL`).
   - The next block's preflight finds the seal clear. It then runs
     `pipeline_admit`, which needs `pipeline_pending == 0`, so it is a
     drained barrier. `pipeline_admit` checks each unit: its magic, its kind
     for its position, its callbacks, its arena (`self == mem`,
     `bytes <= cap`, no overlap). Then it records the geometry and seals.
   - Between barriers, the five-field compare on every block is unchanged.
     The fail-closed guards stay: `PIPELINE_REQUIRE` parks the core, and the
     fence refuses a mutation while a block is in flight.
2. **Which core renders Sound 2's chain** (`pipeline_shares`,
   `pipeline_admit`):
   - A table names the engines whose code reaches writable globals, in
     three groups:
     - `stmlib::Random`: drums, macro-heavy, shapes, sixop;
     - the Felucca bridge: drawbar, trio, phase-bend;
     - the Schwung shim: sw-sophie, sw-psxverb.
   - If Sound 2's engine and inserts share a group with any unit on CPU0,
     Sound 2's chain is rendered inline on CPU0, in dispatch order. CPU1
     then does only the level, the sum and the masters. An example is Drums
     on Sound 2 while Sound 3 is also Drums.
   - Otherwise it goes to CPU1 as before.
   - The masters must share nothing with CPU0, or admission fails closed.
   - An empty sound is summed as R0 sums it: not at all. Its inserts do not
     run.
3. **Every Macro model:**
   - Chip's arpeggiator now keeps its own LCG state, seeded `0x21` in
     `Init` (`engines/third_party/mutable/plaits/dsp/engine2/arpeggiator.h`,
     recorded in `engines/third_party/mutable/UPSTREAM.md`).
   - Macro's link closure then reaches no writable global [verified:
     `tests/test_pipeline_shares.py`].
   - The model-0 clamp in `fm1_app_set_param` and the `value[0]==0`
     requirement in preflight and record are removed.
   - Effect on sound: one Chip voice in random mode gives the stream the
     shared generator gave it from a fresh seed. Chip beside Drums no longer
     interleaves draws with Drums. Several Chip voices do not get different
     streams: every voice's `Init` seeds `0x21`, so voices started together
     step through the same sequence in lockstep, where the shared generator
     gave each the next draws [verified: `arpeggiator.h:55`, review
     2026-11-10; the audible effect is not listened to]. Owner item, §6.
4. **Arenas** (`fm1_app_set_arena_pool`, `firmware/fm1/fm1_live.c`):
   - The FM-1 adapter hands the app its whole 148 KiB pool.
   - An engine that does not fit its unit's arena takes the first 16-byte
     aligned gap that no other unit's arena covers (first fit). An emptied
     unit gives its arena back.
   - No fit means `FM1_APP_SELECT_ARENA`. The PRESETS turn then steps over
     the engine and shows the refusal popup "<engine> does not fit". R0's
     RAM refusal shows the same words plus the RAM it would need.
   - `project_reset` keeps the pool.
5. **DX7 voice limit:** a DX7 created later is limited to 8 voices, like
   the startup ones. `limit_dx7` runs after each drained service and sets
   the limit on every DX7 each time (one store), rather than remembering
   instances by address: a DX7 replaced and re-created in one batch lands
   at the old address. A first version did remember addresses and left
   that DX7 at 12 voices [verified: `swaps` checkpoint t356 read
   `dx7_limit=12` before the fix, 8 after]. A failure is `init_error` 23.
6. **Where the seal is cleared** [verified: every write to a unit's engine,
   instance, arena, size or capacity in `fm1_app.c`, and `SetVoiceLimit` is
   a plain store that retires no voice, `msfa_dx7.cc:646`]: `fm1_app_select`
   (load, empty, the restore of the previous engine after a refused load,
   the pool's return of an arena) and `swap_units` clear it.
   `app_init`, and so a project reset, refuses once the pipeline has run
   (`PIPELINE_GUARD(!pipeline_owner)`), so it fails closed rather than
   changing units under a seal. `fm1_app_state.c` and `fm1_edit.c` change
   engines only through `fm1_app_select` [verified: source]. Both are
   linked into the image: `SIM_APP_OBJ` (`sim/web/mk/sim.mk:40-43`) is part
   of `DEVKIT_RENDERER_OBJ` (`tools/jieli/renderer.mk:5`) [verified: review
   2026-11-10; an earlier draft of this note said they were absent]. No
   panel path loads a project state, and the edit layer changes units only
   while it is open, when the pipeline refuses a block (`!a->edit` in
   preflight) [verified: source].

The default image (`LUNAR_FM1_FULL_UI=0`) makes no structural change after
init. Its control path is unchanged.

## 3. Tests

Host, macOS, clang. All 10 tests in `tests/test_fm1_live.py` pass. The
full-UI fixtures are built with `test-ext` added, so that one insert uses
engine API v3's `render_ext`. Each differential runs the script through the
live adapter and the drain barrier, plain and under ASan+UBSan, against the
same arrangement with no pipeline (`ref MODE`). At every checkpoint these
are equal [verified]: unit ids, Macro's model, mode, page, sound, popup, the
41 LEDs, the screen hash and a hash of every PCM word. Every DX7 a sound
holds, at start or later, reports a voice limit of 8 at every checkpoint
(`dx7_limit=`).

| Script | Checkpoints | What changes mid-stream |
| --- | --- | --- |
| `full` | 13 | the 68-event panel script of 2026-11-09 |
| `gestures` | 16 | the script that was refused on 2026-11-09:<br>- Sound 2 goes Macro → DX7 → Drums;<br>- Sound 1 goes Drums → DX7;<br>- the masters swap order (Echo,Comp → Comp,Echo);<br>- ALGORITHM reaches the new DX7 on Sound 2 (Macro stays on model 0 in this script) |
| `swaps` | 31 | - Macro models 0 to 7 and back to 0, each with a note held across the change;<br>- Chip's random arpeggio beside Drums;<br>- Sound 2 goes DX7 → Drums (inline, since Sound 3 is Drums) → empty → Macro;<br>- Sound 1 goes DX7 → Drums → DX7 in one drained batch, then DX7 → Drums;<br>- the masters are swapped and picked six ways |
| `inserts` | 19 | - Sound 2's first insert is set to Filter, Test Ext (`render_ext` on CPU1), Comp and back, while its engine goes Macro → DX7 → Drums → empty;<br>- then Sound 1's inserts |

`tests/test_pipeline_shares.py` (4 tests, new):

- It builds every engine with GPL modules on and follows each engine
  descriptor's link closure through the symbol tables (`nm -m` on macOS,
  `objdump -t` elsewhere).
- It asserts that the table and the objects agree:
  - an engine is in the table exactly when its closure reaches a writable
    global;
  - engines whose globals meet share a group;
  - nothing outside the engines refers to that state.
- Three kinds of symbol are exempt (corrected in review, 2026-11-10):
  - the DX7 rate and the LFO and pitch-envelope units, written only by the
    first DX7 create, at a barrier [verified: `msfa_dx7.cc:217-226`,
    `lfo.cc:28`, `pitchenv.cc:23`];
  - `fm1_freqlut`, which is not create-only as the first draft said:
    every DX7 `RenderBlock` stores it (`msfa_dx7.cc:690`), so two DX7s on
    two cores both write it. At 44,118 Hz every instance stores the address
    of the one ROM table, the same word each time; at another host rate each
    instance stores its own table's address (equal contents). A new test
    pins `kFreqLutRateHz` (`msfa.h:63`) to `LUNAR_FM1_RATE`
    (`firmware/fm1/fm1_live.h`) [verified: source, test];
  - `fm1_sintab`/`fm1_exp2tab`, initialised to const tables and never
    assigned, and Braids' arrays of pointers, never written [inferred: not
    written in the source].
- Results [verified]:
  - 4 passed on macOS (clang) and 4 passed on aeon (Linux, gcc, `objdump`);
  - with the old arpeggiator restored, 2 fail on macOS and 3 on Linux,
    naming `stmlib::Random::rng_state_` in Macro's closure.

Other runs, host, macOS, at `75b56b30` [verified: pytest output]:

- `tests/test_pipeline_shares.py` with `tests/test_engines_reference_plaits.py`
  (the vendored-code pin, now with the recorded local change): 205 passed.
- The whole suite, run once (`python -m pytest -rsx`): 6,509 passed,
  43 skipped, 2 xfailed, 0 failed, in 31 min 49 s.
  - The skips are references not cloned, stock images not supplied, a
    missing `markdown` module and Linux-only harnesses. None of them is in
    `test_fm1_live.py`, `test_pipeline_shares.py`,
    `test_devkit_queue_integration.py` or `test_gpl_switch.py`.
  - `test_devkit_queue_integration.py` passed whole. Earlier runs on
    2026-11-10 timed out at 120 s under a load average of 340 to 410 from
    other work on the Mac; this run's load was lower.
- The simulator module (`sim/web/www/fm1.wasm`, GPL switch on as published)
  was rebuilt with `sim/web/build-on-aeon.sh --no-screenshot`, because the
  arpeggiator is an engine source and the committed module's source hash
  no longer matched; `test_gpl_switch.py` skipped its licence-list check
  with a warning until then. Parity: 108 of 108 scenarios passed, the edit
  layer's storm had 0 late quanta. `test_gpl_switch.py` and
  `test_sim_files.py` then gave 14 passed, 1 skipped (`markdown`).
- With the old `limit_dx7` built into the `swaps` replay, checkpoint t356
  read `dx7_limit=12`, which the differential's assertion (8 or 0)
  rejects. pytest itself was not re-run against the old code.

### Review additions (adversarial review, 2026-11-10)

- `tests/test_pipeline_shares.py`, now 6 tests:
  - the descriptor search also finds `mi_fx.cc`'s `FM1_MI_FX` macro, and
    the set found must equal every sound and audio effect `fm1-render
    --list` registers, so a missed descriptor fails instead of going
    unchecked [verified: 6 passed, macOS];
  - `test_freqlut_rate_is_the_fm1_rate` (above);
  - `test_no_device_master_effect_shares_state`: no audio effect in
    `LUNAR_MODULES` (`tools/jieli/devkit-renderer-sdk.mk`) is in the shares
    table, so no master pick on the FM-1 can reach admission's fail-closed
    park.
- `tests/test_fm1_live.py`: the differentials now check which core ran
  Sound 2's chain at every checkpoint. A host-only accessor
  (`fm1_app_pipeline_sound2_deferred`, under `FM1_APP_PIPELINE_HOST_PROBE`,
  never in a device image) is printed by the replay, and the test works the
  expected route out of the printed units and the shares table. `swaps`
  must show both routes. Before this, a deferral that was always 0 or
  always 1 passed, since a sequential replay gives the same PCM either way.
  Three mutations of `pipeline_admit` (always inline, always deferred,
  ignoring `SHARE_RNG`) each fail 2 tests; restored, 10 passed [verified:
  pytest, macOS].

## 4. FM-1 image size (aeon, `lunar-jieli-check:bookworm`)

Built with `tools/jieli/build-fm1-app-on-aeon.sh` in containers labelled
`session=soft-locks-1110`. The base is `091df132`, which has the same code as
`origin/main` `fb6d4d6f` (docs only since then). The lane was measured at
`c0c6f593` and again at `75b56b30`, after `limit_dx7` lost its cache; the
table gives `75b56b30`, the image's last source change in this lane. The
full UI was turned on with `sed` on the aeon copy of `fm1_live.h`.
[verified: `fm1_budget.py` and `audit_link.py` logs]

| Build | `app.bin` | Slot margin (581,564 B) | `.text` | RAM margin over minimum | `audit_link` | `fm1_budget` |
| --- | --- | --- | --- | --- | --- | --- |
| base, default, GPL 0 | 550,300 B | +31,264 | 393,024 | +960 B | PASS | PASS |
| lane, default, GPL 0 | 551,260 B (+960) | +30,304 | 393,952 | +864 B | PASS | PASS |
| base, full UI, GPL 0 | 620,700 B | -39,136 | 464,192 | +1,728 B | PASS | FAIL `app_slot` |
| lane, full UI, GPL 0 | 621,148 B (+448) | **-39,584** | 464,576 | +1,632 B | PASS | FAIL `app_slot` only |
| lane, full UI, GPL 1 | 621,148 B | -39,584 | 464,576 | +1,632 B | PASS | FAIL `app_slot` only |

- Lifting the locks costs 448 B in the full-UI image and 960 B in the
  default image. At `c0c6f593`, before the `limit_dx7` fix, they were
  621,244 B (+544) and 551,324 B (+1,024).
- The default image grows more, which is not explained [inferred: admission,
  the shares table and the pool search are linked into both images; the
  difference is not bisected].
- The GPL 0 and 1 full-UI images differ in content at equal size (first
  difference at byte 173,707).
- The GPL 1 image is not shared and was not copied off aeon.

## 5. What is not done or not verified

- **No dev-kit run.** The dev-kit flow (`firmware/devkit/renderer_live.c`,
  the queue and pipeline preparers) plays a fixed arrangement with no panel
  path, so it cannot make a change mid-stream without a new diagnostic image.
- **Not measured on hardware:**
  - The time a change takes at the barrier on CPU0: creating DX7 or Drums,
    or admission.
  - A Macro model change on CPU1. It happens when Sound 2 is deferred:
    `set_param` builds the new Plaits engine inside a CPU1 block.
  - Both need the dev kit, as the barrier latency of 2026-11-09 does.
- **The arena pool is the remaining difference from R0.**
  - Instance sizes on the host (64-bit) [verified: `instance_size` probe]:
    DX7 16,248 B, Macro 32,880, Drums 7,792, Echo 65,744, Filter 656,
    Drive 240, Comp 208.
  - The startup arrangement uses about 140 KB of the 151,552 B pool, which
    leaves about 11.5 KB free.
  - So Macro (32.9 KB) cannot be added to Sound 1 unless another unit is
    emptied first. The `swaps` and `gestures` scripts show this: PRESETS
    steps over Macro with its refusal popup and lands on Drums.
  - R0 in the simulator has a larger RAM budget and would load Macro there
    [inferred: not run side by side].
  - Target sizes are smaller (4-byte pointers) and are not measured
    [inferred].
- **Fragmentation.** The first-fit pool does not compact. A long session of
  changes can leave gaps too small for an engine that would fit in the total
  free space [inferred: not exercised].

## 6. Owner decision raised

**Arena pool size for the full-UI image.** Options:

- (a) **Recommended:** keep 148 KiB, and measure free SRAM on the target
  first. `fm1_budget` reports a heap margin of +1,632 B over the minimum,
  so the pool can grow only by moving RAM from elsewhere.
- (b) Re-create all units at a barrier to compact the pool. This costs
  their sound state, held notes and tails, and diverges from R0.
- (c) Accept the refusal popup as the FM-1's documented limit, as R0's RAM
  meter already refuses on the device budget.

If there is no answer, (c) is how the build behaves now.

Raised in review (2026-11-10):

- **Chip arpeggiator seeding** (§2.3). Recommended: seed each voice
  differently (for example from the voice index) so several Chip voices do
  not run in lockstep; it changes the local patch in
  `engines/third_party/mutable/`. Without an answer the lockstep stays.
- **`fm1_freqlut` stored every block.** Safe on the FM-1 at 44,118 Hz.
  Recommended follow-up: store it only when it changes, or pass the table
  per instance, so a DX7 at another rate could share cores. Without an
  answer the exemption and its rate test stand.
