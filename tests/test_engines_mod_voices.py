"""Per-voice modulation (docs/16 stage MG9) and the MG3 follow-ups the owner
answered on 2026-10-05, through fm1-render --mod: a slot flagged VOICE runs
once per note, its note sources being that note's and an Envelope, LFO or
Chance it reads one instance per note; it reaches the engines through their
per-note offsets (set_param_note, FM1_PARAM_NOTE_PITCH); poly never reaches
mono. Also: an Envelope with no GATE cable retriggers on every note (RTRG),
a pitch per sound unit and the current sound's, and each sound unit's own
note sources.

The tick log's `vw` lists the per-note offsets sent ([frame, unit, key,
index, offset], index 65535 the note's pitch) and `vo` the voices sounding
with their per-voice modules' outputs.
"""
import pytest

from tests.engine_helpers import RATE, renderer  # noqa: F401  (pytest fixture)
from tests.test_engines_mod_runtime import run, script, seq_text

TICK = 32
PITCH = 65535
# Each engine with per-note offsets and a POLY parameter of it.
POLY_PARAM = {"macro": "Timbre", "macro-heavy": "Timbre", "shapes": "Timbre", "sixop": "Brightness",
              "dx7": "Brightness", "drums": "Tone"}


def at(t, block=64):
    """The frame a --note at t seconds applies at: the first block start at or after it."""
    return -(-int(t * RATE) // block) * block


def chord(engine, times=(0.05, 0.12, 0.2), length=0.4):
    keys = (36, 38, 42) if engine == "drums" else (48, 55, 62)
    out = []
    for t, k in zip(times, keys):
        out += ["--note", f"{t}:{k}:100:{length}"]
    return out


def offsets(ticks):
    """{(unit, key, index): [(frame, offset), ...]} from a tick log."""
    out = {}
    for t in ticks:
        for frame, unit, key, index, value in t["vw"]:
            out.setdefault((unit, key, index), []).append((frame, value))
    return out


def bits(x):
    return [i for i in range(32) if (x >> i) & 1]


# ---- the identity, and each note its own ------------------------------------------------------

@pytest.mark.parametrize("engine", sorted(POLY_PARAM))
def test_zero_offsets_per_voice_are_an_identity(renderer, tmp_path, engine):
    """Per-voice cables at 0 % move nothing: every voice starts, no offset is
    sent, and the render is the one without them, byte for byte. At 40 %
    the same cables move every note."""
    args = ["--engine", engine, "--seconds", "0.8"] + chord(engine)
    _, plain, _ = run(renderer, tmp_path, args, name="plain")
    mod = ("rack default\nset 3 attack=0.2 decay=0.3 sustain=0.4 release=0.2\n"
           f"slot 1 env3 > snd:{POLY_PARAM[engine]} amt={{a}} voice\n"
           "slot 2 rand > host:pitch amt={a} voice\n"
           "slot 3 vel > env3:attack amt={a} voice\n")
    s0, zero, _ = run(renderer, tmp_path, args, mod=mod.format(a=0), name="zero", log=False)
    assert zero == plain
    assert s0["mod_voice_starts"] == 3 and s0["mod_voice_writes"] == 0
    assert s0["mod_refused"] == 0 and bits(s0["mod_voice_slots"]) == [0, 1, 2] and s0["mod_poly"] == 4
    s1, moved, ticks = run(renderer, tmp_path, args, mod=mod.format(a=40), name="forty")
    assert moved != plain and s1["mod_voice_writes"] > 0 and s1["mod_nonfinite"] == 0
    keys = {k for (_, k, _) in offsets(ticks)}
    assert len(keys) == 3


def test_each_note_of_a_chord_has_its_own_envelope(renderer, tmp_path):
    """ENV3 per voice into Timbre, three notes struck apart: each note's
    offset starts at its own note-on and climbs its own attack while the
    note before it holds its sustain; every one ends at 0 after its release,
    and its voice ends."""
    mod = ("rack default\nset 3 attack=0.45 decay=0.35 sustain=0.25 release=0.3\n"
           "slot 1 env3 > snd:Timbre amt=80 voice\n")
    notes = ["--note", "0.1:48:100:0.6", "--note", "0.4:55:100:0.6", "--note", "0.7:62:100:0.6"]
    s, _, ticks = run(renderer, tmp_path, ["--engine", "macro", "--seconds", "2.2"] + notes, mod=mod)
    off = offsets(ticks)
    assert set(off) == {("snd", k, 2) for k in (48, 55, 62)}           # Timbre is index 2
    for key, t in ((48, 0.1), (55, 0.4), (62, 0.7)):
        trace = off[("snd", key, 2)]
        assert at(t) <= trace[0][0] <= at(t) + 2 * TICK                  # starts with its note
        peak = max(v for _, v in trace)
        assert 0.75 < peak <= 0.8                                       # 80 % of a full envelope
        assert trace[-1][1] == 0.0                                      # released to 0
    # Just after the second note-on the first note holds its sustain (80 %
    # of 0.25) while the second climbs its own attack from 0.
    def value_at(key, frame):
        v = 0.0
        for f, x in off[("snd", key, 2)]:
            if f <= frame:
                v = x
        return v
    start, soon = at(0.4) + TICK, at(0.4) + 6 * TICK
    assert value_at(48, soon) < value_at(48, start)                    # the first decays...
    assert value_at(55, start) < value_at(55, soon) < 0.75             # ...the second climbs
    assert value_at(62, soon) == 0.0                                    # the third not struck yet
    voices = {t["t"]: len(t["vo"]) for t in ticks}
    assert voices[max(f for f in voices if f <= at(0.7) + 2 * TICK)] == 3   # the first in its release
    assert s["mod_voice_starts"] == 3 and s["mod_voice_ends"] == 3 and voices[max(voices)] == 0


def test_voices_are_the_same_at_host_blocks_of_1_7_and_64(renderer, tmp_path):
    """docs/16 §2.7 with voices: the sequencer's notes (whose frames do not
    depend on the block) start the voices, and the WAV, the tick log and
    every per-note offset are the same at host blocks of 1, 7 and 64."""
    mod = ("rack default\nset 1 mode=trig rate=0.7\nset 3 attack=0.2 decay=0.3 sustain=0.3 release=0.2\n"
           "slot 1 env3 > snd:Timbre amt=60 voice\nslot 2 lfo1 > snd:Morph amt=-35 voice\n"
           "slot 3 rand > host:pitch amt=0.5 voice\nslot 4 vel > env3:decay amt=30 voice\n"
           "slot 5 lfo2 > snd:Harmonics amt=20\n")
    out = {}
    for block in (1, 7, 64):
        args = ["--engine", "macro", "--fx", "test-gain", "--frames", str(block),
                "--cmd", str(script(tmp_path, seq_text(block), name=f"s{block}"))]
        s, raw, ticks = run(renderer, tmp_path, args, mod=mod, name=f"b{block}")
        out[block] = (raw, ticks, s)
        assert s["mod_voice_writes"] > 1000 and s["mod_refused"] == 0 and s["mod_nonfinite"] == 0
    assert out[1][0] == out[64][0] and out[7][0] == out[64][0]
    assert out[1][1] == out[64][1] and out[7][1] == out[64][1]
    for k in ("mod_ticks", "mod_voice_writes", "mod_voice_starts", "mod_voice_ends"):
        assert out[1][2][k] == out[7][2][k] == out[64][2][k], k


def test_a_voice_starts_with_its_note_and_steals_the_oldest(renderer, tmp_path):
    """A note's VEL and RAND per voice reach its engine voice right after its
    note-on (fm1_mod_voice_start), at the note's own frame; fourteen held
    notes take the twelve voices and steal the two oldest."""
    mod = "rack default\nslot 1 vel > snd:Morph amt=50 voice\nslot 2 rand > host:pitch amt=0.25 voice\n"
    notes = []
    for k in range(14):
        notes += ["--note", f"{0.02 * k:.2f}:{48 + k}:{60 + 4 * k}:1.0"]
    s, _, ticks = run(renderer, tmp_path, ["--engine", "macro", "--seconds", "1.3"] + notes, mod=mod)
    off = offsets(ticks)
    for k in range(14):
        frame, value = off[("snd", 48 + k, 3)][0]                        # Morph is index 3
        assert frame == at(0.02 * k) and abs(value - 0.5 * (60 + 4 * k) / 127) < 1e-6
        pitch = off[("snd", 48 + k, PITCH)][0]
        assert pitch[0] == frame and 0 < abs(pitch[1]) <= 15.0           # +-0.25 x 60 semitones
    assert len({off[("snd", 48 + k, PITCH)][0][1] for k in range(14)}) == 14   # each its own
    assert s["mod_voice_starts"] == 14 and s["mod_voice_steals"] == 2
    held = [t for t in ticks if t["t"] == at(0.5) + TICK or abs(t["t"] - int(0.5 * RATE)) < TICK]
    assert sorted(v[2] for v in held[0]["vo"]) == list(range(50, 62))   # the two oldest stolen


# ---- poly never reaches mono ------------------------------------------------------------------

def test_poly_into_mono_is_refused(renderer, tmp_path):
    """Surge's rule (canModulateMonophonicTarget): a VOICE cable into an
    effect, HOST AMP, a parameter the engine keeps for every note, a module
    that does not run per voice, or a sound whose engine takes no per-note
    offsets is refused; mono into a per-voice target is allowed."""
    mod = ("rack default\nmod 6 slew\n"
           "slot 1 env3 > snd:Timbre amt=40 voice\n"          # live
           "slot 2 env3 > fx1:Mix amt=40 voice\n"             # an effect
           "slot 3 env3 > host:amp amt=40 voice\n"            # AMP
           "slot 4 env3 > snd:LPG amt=40 voice\n"             # engine-wide
           "slot 5 env3 > slw6:in amt=40 voice\n"             # Slew: no POLY_OK
           "slot 6 vel > lfo2:rate amt=40 voice\n"            # LFO2 runs per voice for nothing
           "slot 7 clock > snd:Morph amt=20 voice\n"          # mono into poly: allowed
           "slot 8 env3 > snd:Harmonics amt=20\n")            # global: ENV3's global instance
    args = ["--engine", "macro", "--fx", "plate", "--seconds", "0.5"] + chord("macro")
    s, _, _ = run(renderer, tmp_path, args, mod=mod, name="a", log=False)
    assert bits(s["mod_refused_bits"]) == [1, 2, 3, 4, 5]
    assert bits(s["mod_voice_slots"]) == [0, 6] and s["mod_poly"] == 1 << 2
    s, _, _ = run(renderer, tmp_path, args, mod=mod + "slot 9 lfo2 > snd:Colour amt=30 voice\n",
                  name="b", log=False)
    assert bits(s["mod_refused_bits"]) == [1, 2, 3, 4]                 # LFO2 runs per voice now
    assert bits(s["mod_voice_slots"]) == [0, 5, 6, 8] and s["mod_poly"] == (1 << 1) | (1 << 2)
    sine = ["--engine", "test-sine", "--seconds", "0.3", "--note", "0.05:60:100:0.2"]
    s, _, _ = run(renderer, tmp_path, sine, name="c", log=False,
                  mod="rack default\nslot 1 env3 > snd:Volume amt=40 voice\n"
                      "slot 2 rand > host:pitch amt=1 voice\n")
    assert bits(s["mod_refused_bits"]) == [0, 1] and s["mod_voice_starts"] == 0


def test_a_global_cable_into_a_per_voice_module_moves_every_voice(renderer, tmp_path):
    """Mono to poly: LFO2 (global) into ENV3's Sustain moves every note's
    envelope alike, and a VOICE cable from VEL into its Decay each its own."""
    mod = ("rack default\nset 3 attack=0.05 decay=0.2 sustain=0.5\nset 2 rate=0.35\n"
           "slot 1 env3 > snd:Timbre amt=50 voice\nslot 2 lfo2 > env3:sustain amt=30\n")
    args = ["--engine", "macro", "--seconds", "1.0", "--note", "0.05:48:127:0.8", "--note", "0.05:60:30:0.8"]
    _, _, ticks = run(renderer, tmp_path, args, mod=mod, name="mono")
    late = [t for t in ticks if t["t"] > int(0.6 * RATE)][0]
    outs = sorted(v[4][0][1] for v in late["vo"])                      # each voice's ENV3 output
    assert len(outs) == 2 and outs[0] == outs[1]                       # the same: mono to poly
    _, _, ticks = run(renderer, tmp_path, args, name="poly",
                      mod=mod + "slot 3 vel > env3:sustain amt=40 voice\n")
    late = [t for t in ticks if t["t"] > int(0.6 * RATE)][0]
    outs = sorted(v[4][0][1] for v in late["vo"])
    assert len(outs) == 2 and outs[1] - outs[0] > 0.2                  # velocity apart


# ---- the MG3 follow-ups (owner, 2026-10-05) ----------------------------------------------------

def test_an_envelope_with_no_gate_cable_retriggers_on_every_note(renderer, tmp_path):
    """The Envelope's GATE with no cable reads RTRG, not the legato KEY: a
    note struck while another is held restarts the attack, as a cable from
    RTRG does; a cable from KEY keeps it legato."""
    notes = ["--note", "0.1:60:100:0.6", "--note", "0.3:64:100:0.2"]
    args = ["--engine", "test-sine", "--seconds", "0.8"] + notes
    rack = "mod 1 env attack=0.3 decay=0.4 sustain=0.4\n"
    env = lambda ticks: {t["t"]: t["m"][0]["o"][0] for t in ticks}   # noqa: E731
    _, _, normal = run(renderer, tmp_path, args, mod=rack, name="normal")
    _, _, rtrg = run(renderer, tmp_path, args, mod=rack + "slot 1 rtrg > env1:gate\n", name="rtrg")
    _, _, key = run(renderer, tmp_path, args, mod=rack + "slot 1 key > env1:gate\n", name="key")
    assert env(normal) == env(rtrg) and env(normal) != env(key)
    on2 = at(0.3)
    after = [t for t in sorted(env(normal)) if on2 < t < on2 + 0.1 * RATE]
    assert env(normal)[after[-1]] > env(normal)[after[0]]              # the attack again


def test_a_pitch_per_sound_and_the_current_sound(renderer, tmp_path):
    """HOST PITCH bends sound unit 1, PITCH2-4 sound units 2-4, and PITCHC
    whichever sound is current (`current K`): its cable leaves sound unit 1
    at the line's frame (back to its base) and bends sound unit 2."""
    mod = ("rack default\nset 2 rate=0.6\nslot 1 lfo1 > host:pitch3 amt=2\n"
           "slot 2 lfo2 > host:pitchc amt=4\n@13312 current 2\n")
    args = ["--engine", "macro", "--sound", "1:shapes", "--sound", "2:sixop", "--seconds", "0.6",
            "--sound-note", "1:0.05:60:100:0.5", "--sound-note", "2:0.05:64:100:0.5",
            "--note", "0.05:48:100:0.5"]
    s, _, ticks = run(renderer, tmp_path, args, mod=mod)
    w = [(t["t"], unit, index, value) for t in ticks for unit, index, value in t["w"]]
    assert {i for _, u, i, _ in w if u == "host"} == {0, 2, 3}         # no write to PITCH_CUR itself
    before = [x for x in w if x[0] < 13312]
    after = [x for x in w if x[0] >= 13312]
    assert any(i == 0 for _, _, i, _ in before) and not any(i == 2 for _, _, i, _ in before)
    assert any(i == 2 for _, _, i, _ in after)
    assert [v for t, _, i, v in after if i == 0] == [0.0]              # sound unit 1 back to its base
    assert all(i in (2, 3) for _, _, i, _ in after[1:])
    assert s["mod_refused"] == 0
    # The routed sinks list the current sound's pitch, which PITCHC's cable
    # alone routes (no destination of its own: a review fix under UBSan).
    assert {(x["u"], x["i"]) for x in ticks[-1]["s"]} == {("host", 2), ("host", 3), ("host", 5)}


def test_note_sources_of_one_sound(renderer, tmp_path):
    """S2KEY, S2TRIG and S2RTRG follow sound unit 2's notes alone; KEY all
    of them (owner, 2026-10-05: note sources selectable per sound, all by
    default). S2VEL and S2NOTE hold sound unit 2's last note."""
    args = ["--engine", "test-sine", "--sound", "1:test-sine", "--seconds", "0.6",
            "--note", "0.05:60:100:0.1", "--sound-note", "1:0.3:67:50:0.1"]
    mod = "rack default\nslot 1 s2vel > snd:Volume amt=10\nslot 2 s2note > snd2:Volume amt=10\n"
    _, _, ticks = run(renderer, tmp_path, args, mod=mod)
    rises = lambda sid: [t["t"] - TICK + f for t in ticks for s_, f, h in t["g"] if s_ == sid and h]  # noqa: E731
    assert rises(16) == [at(0.05), at(0.3)]                            # KEY: both
    assert rises(52) == [at(0.05)] and rises(53) == [at(0.3)]          # S1KEY, S2KEY
    assert rises(57) == [at(0.3)] and rises(61) == [at(0.3)]           # S2TRIG, S2RTRG
    last = {x["u"]: x["v"] - x["b"] for x in ticks[-1]["s"]}
    assert set(last) == {"snd", "snd2"}
    assert abs(last["snd"] - 0.1 * 50 / 127) < 1e-5 and abs(last["snd2"] - 0.1 * 7 / 60) < 1e-5
