# Native project capacity measurement

**Scope.** This records one dense, accepted Lunar app project sent through the
actual app collector, compact binary serializer, and native two-slot SAVE
simulator. It is a bounded fixture measurement, not a proof of the maximum
serialized project or firmware flash-bank fit.

## Result

The test serialized a 31,736-byte native payload. The current format permits a
98,304-byte payload (`BIN_MAX` in `tools/lunar_state.py`); the native NOR slot
adapter is 102,400 bytes. This composition therefore fit both limits with
66,568 bytes below the payload ceiling. The evidence proves this particular
accepted composition fits; it does not prove that all valid project
compositions fit, or characterize a maximum.

The active set had eight tracks. Independent decoding of the saved `set` lines
found exactly 1,536 notes, 1,536 locks and 256 triggers: 192 notes and locks
and 32 triggers on each track. The test checks each decoded row count and MIDI
pitch range, so dropped or clamped invalid rows cannot inflate the claimed
fixture density. The input set text was 45,711 bytes.

The modulation fixture occupied all 32 cable slots and retained the five-byte
Register module data payload. It serialized two modules (LFO and Register),
not the rack's eight-module maximum. Four sound units had populated parameters;
the fixture also included inserts on units 2–4, two master effects and DX7 user
voices. The mod input text was 1,119 bytes. This is representative dense state,
not every maximum parameter, pad, module, or voice combination.

## Method and validation

`tests/test_native_project_capacity.py` creates valid `.movy1` and modulation
inputs, launches the native app SAVE path, reads the produced binary with the
independent Python decoder, and asserts exact sequencer, cable, module-data,
writer-identity and size counts. The SAVE harness exercises the two-slot
commit and recovery simulator before emitting the committed body. The final
Hera run log is at
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/project-capacity-v1/test-final.log`;
it records 31,736 bytes and the decoded counts above, followed by the passing
pytest test marker. Local `py_compile` also passed.

The run used the pinned `lunar-recovery-pytest:20261011` image digest
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
on `claude@192.168.1.48`, with the prescribed batch cgroup, memory limits and
network isolation. No FM-1, USB, bench or flash operation was performed.

## Limits and follow-up

The binary/payload constants and host simulator are not evidence of physical
flash-bank headroom, boot behavior, SAVE/recovery on an FM-1, or updater
acceptance. No production source or format limit changed. Device-level
acceptance remains a separate gate; parent work is currently focused on the
diagnostic image and physical recovery path. Any future maximum-capacity claim
needs a fixture that proves exact accepted counts across the maximum module,
parameter/pad, voice and sequencer state, plus the physical bank geometry and
target-device SAVE/recovery evidence.

## Denser accepted fixture (2026-10-14)

The updated test now exercises all eight mod positions, all 32 cable slots,
all eight insert and both master FX positions, four populated sound units,
32 DX7 voices, and exact full accepted pools on all eight sequencer tracks.
Independent decode found 1,536 notes, 1,536 locks, and 256 triggers. The four
Drums units expose nine accepted pad parameters each; the saved project has
exactly 576 focus-scoped pad parameter records (nine × 16 pads × four units).
The modulation rack has 69 parameter records and the five-byte Register data
record. These counts are asserted from the serialized output; they are fixture
counts, not a claim that every possible engine or content combination was
enumerated.

The actual collector and compact binary serializer produced **32,924 bytes**
for this composition, against the enforced 98,304-byte binary payload limit
and 102,400-byte simulator slot. The exact decoded output contained 1,001
records. Source `.movy1` and mod text inputs measured 45,711 and 1,977 bytes,
respectively. This supersedes the earlier 31,736-byte v1 measurement as the
denser accepted fixture; it still does not prove an application maximum.

The limit is live: `FM1_STATE_BIN_MAX` is checked by the native writer and
reader in `engines/state/state_bin.c`, and the independent Python binary reader
uses the same 98,304-byte ceiling. Per-chunk caps are info 2,048, PROJ 2,048,
UNIT 6,144, DX7V 5,200, MODR 12,288, SEQS 49,152, CLIP 16,384, view 2,048,
and SETG 2,048 bytes. Project files can contain repeated UNIT chunks; therefore
summing just one UNIT cap understates the format allowance. With the 64-chunk
container cap, raw per-chunk allowances can exceed the 96 KiB whole-file cap.
Those format caps do not establish a tighter all-state app-reachable bound:
the test does not prove every maximum-length record can be jointly generated
by the app collector, nor does it show whether app or firmware constraints
refuse a valid project before 96 KiB. Thus 98,304 bytes is the conservative
enforced binary-format ceiling, not a measured or proven reachable app-state
maximum. The 4,096-byte difference to a 102,400-byte simulator slot is
arithmetic headroom only, not physical flash-bank evidence.

The passing final run used the cached native executable at
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/project-capacity-v2/debug/fm1-sim-render`;
its captured output is
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/project-capacity-v2/test-final.log`.
It ran inside the pinned Hera container described above with network disabled.
No production source changed, and no physical-device, updater, boot, recovery,
or bank-fit claim follows from this host-side fixture.
