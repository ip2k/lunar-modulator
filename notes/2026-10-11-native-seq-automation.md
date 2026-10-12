# Native sequencer effect and mixer automation

Active endpoint: root owns complete DAW stream integration, CI, merge and live
browser deployment. This subtask provides native automation and isolated tests.
Personal project; no hardware writes or listening acceptance claimed.

Branch: `feature/2026-10-11@midi-sequencer-workspace`.
Root checkpoint at note creation: `23d08688012214939ffa65e565d4ac9d2a9e29a9`.
No commits made by this subagent; root owns checkpoint and verified push.

## Saved implementation

- `engines/include/fm1_seq_host.h`, `engines/seq/seq_host.c`: reserve app target
  prefixes, preventing an effect `Mix` lock from resolving to synth `Mix`.
- `sim/web/src/fm1_app.c/.h`: frame-tagged insert/master locks through the
  effect write queue, independent effective mixer levels, D6/base restoration,
  modulation base precedence, knob/base synchronization, reset/import cleanup,
  route/label boundary cleanup, fixed queue capacity/counters and RAM accounting.
- `fm1_app_export_sound_mask(app, mask)`: contribution bits 0..3, default15;
  applied after sound inserts/effective gain before summing; all event/voice/mod
  activity remains running; never saved. Root owns Wasm wrapper/export list.
- `sim/web/test/fm1_seq_automation_check.c`, `sim/web/test/automation.mk`,
  `tests/test_sim_automation.py`: acceptance probe with deterministic independent
  test engines and real core transport/lock commands. Python target reuses
  existing native fixture flags (including GPL switch and sanitizer variants).
- `engines/seq.md`: grammar, execution/restoration and export mask contract.

## Exact grammar

`in1:Param`, `in2:Param`: track ENGINE route sound0..3 insert1/2.
`m1:Param`, `m2:Param`: global master1/2, including MIDI-routed tracks.
`mix:Level`: routed sound level, 7-bit0..127 => percent0..100 linearly.
`synth:Param` and legacy labels retain existing sound behavior.
Total token <=23 bytes. New effect NOLOCK/PER_FOCUS targets refused; legacy
synth focus locks unchanged. Parameter conversions use existing linear/enum/log
law. App counters record refusal/drop; app targets do not resolve in the generic
single-sound `fm1-render` bridge. Native `fm1-sim-render` and Wasm app implement them.

## Evidence [verified]

Isolated Hera staging `/home/claude/mvave-fm1/midi-automation-20261011/src`,
`claude@192.168.1.48`; Docker emsdk6.0.10 with2CPU/2GiB (no heavy local build).
Native incremental build and focused acceptance probe passed. Probe covers:
exact sample frames across insert1/2/master1/2/mix, identical parameter-name
isolation, no-mod runtime operation, block carry, real core Stop D6, lane clear,
reset restore, current knob base updates, route invalidation, global master on
MIDI route, enum/log conversion, NOLOCK/PER_FOCUS effect refusal, legacy synth
PER_FOCUS, masked sounds rendering with zero contribution, and modulation added
above lock/D6 bases. Zero automation dropped writes in probe.

Native sizeof app:4,948,736B (< existing4,960,000B bound); core unchanged
31,944B/8tracks; event buffer272. New runtime memory is accounted in app RAM
meter separately from the historical36,864B core/event/UI/click subtotal.
Build logs: staging `sim/web/build/automation-build.log` and
`sim/web/build/automation-check-build.log`.

Command (inside resource-limited container, source at/src):

```
make -C engines -f Makefile -f /src/sim/web/mk/sim.mk \
  -f /src/sim/web/test/automation.mk SIM=/src/sim/web \
  BUILD=/src/sim/web/build/native -j2 \
  /src/sim/web/build/native/fm1-seq-automation-check
/src/sim/web/build/native/fm1-seq-automation-check
```

Rarefaction bounded orient and Serena find_symbol both located the existing
`fm1_seq_host_dispatch_slots_ticks` architecture in the primary checkout.
Shared selection was preserved; the worktree's actual edited source was checked
by file inspection and native compiler. Rarefaction used fallback clangd flags
(no compilation database), gave incomplete/wrong C type signatures and zero
callers; these are navigation limits, not proof of no callers or target ABI.

## Pending integration gates / next owner action

Root must rebuild Wasm after latest app.c changes (knob/base sync, RAM accounting
and defensive null-mod tick), then rerun full parity/storm and exporter sibling's
new actual-module mix-level stem leakage test. Root earlier108parity/storm pass
predated these final C changes. Native Python wrapper and broad regression gates
pending at note creation; subsequent results appended below. Hardware/device ABI,
owner listening and physical acceptance remain untested. Parent owns commits,
verified backup SHA, CI and merge; do not report this note as pushed independently.

## RAM fixture follow-up

Final accounting exposed the existing mod-multi-routes fixture near the real
387,924 B budget. Its master Plate is replaced by Room (same Mix parameter),
preserving every routing/modulation branch with headroom; no budget changed.
Native --sizes exposes seq_automation_bytes and the exact RAM assertion includes
it. Focused test renamed test_sim_automation.py to inherit simulator CI variants.

## Final native regression [verified]

Focused wrapper, exact RAM bound and repaired routing scenario: 3 passed.
Expanded tests/test_sim_web.py + test_sim_mod.py + test_sim_multi.py +
test_sim_automation.py: **281 passed, 2 deselected** in 12.43 s on isolated Hera
with emsdk6.0.10, 2CPU/2GiB. Exclusions: generated DX7-assets tool/staleness gate
not staged here; committed module metadata warned stale because root owns the
final rebuild. Log: `/home/claude/mvave-fm1/midi-automation-20261011/native-pytest.log`.
Recovery image pytest pure-Python libs reused in staging; no host install.

Exact additional automation storage: 7,760 B native64 / 7,248 B target32.
RAM FIXED assertions now respect FM1_SIM_EXTRA=-m32 and account this storage.
Root checkpoint now `7abc36c7b39f254395e78beabe01c74e9b2af68b`; final RAM test
expectation changes and this note still pending root checkpoint. No push claim
by this subagent. Root must save these final tests/note and verify its backup SHA.

Root final rebuild [verified]: module SHA-256
`b98e8e3295dba072a65d2d49bd5e1b3d57afc63ce2b2aa33027202e1d7c8c258`.
Complete build passes 108 parity scenarios, metadata consistency, DX7 assets,
and 30-second edit storm with zero late blocks. This supersedes the stale-module
warning and pending rebuild above; browser/export reruns and CI remain separate.
