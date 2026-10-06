"""Engine API v3 (engines/include/fm1_engine.h; engines/README.md, "Engine
API v3"; docs/16 §2.3 for LOG under modulation):

- the effect extension, fm1_fx_ext_t: v2 effects are called exactly as
  before; Test Ext (engines/src/test_ext.cc) hears its key, the tempo, and
  the sequencer's Start, Stop and beats at their exact frames, in fm1-render
  and in the virtual FM-1 alike, at any block size (fm1-fx-ext-test,
  engines/test/fx_ext_test.cc, where fm1-render cannot reach);
- the LOG law: positions, the 7-bit lock grid, the app's knob detents and
  bars, and modulation in octaves, where NOTE at +100 % into a cutoff tracks
  the keys one octave per octave.

16-bit flags and the dB unit are checked with every parameter in
tests/test_engine_params.py; the Comb split in tests/test_engines_comb.py.
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, render, renderer  # noqa: F401
from tests.test_sim_web import run, tools  # noqa: F401

TOOL = ENGINES / "build" / "fm1-fx-ext-test"
RATE = 44118
THRESHOLD = RATE * 6000          # the sequencer's clock (fm1_seq_clock_t)


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    return json.loads(subprocess.run([str(TOOL)], check=True, capture_output=True,
                                     text=True).stdout)


def beat_frames(bpm_x100, until):
    """Where beat k starts after a Start at frame 0: the frame at which the
    sequencer services master tick 96 k, from its integer clock."""
    inc = bpm_x100 * 96
    out, k = [], 0
    while True:
        need = (96 * k + 1) * THRESHOLD
        f = (need + inc - 1) // inc - 1
        if f >= until:
            return out
        out.append(f)
        k += 1


# ---- the extension's plumbing ----------------------------------------------------

def test_only_test_ext_asks_for_the_extension(renderer):  # noqa: F811
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    for e in listed:
        if e["id"] == "test-ext":
            assert e["kind"] == "audio_fx" and e["render_ext"]
            assert e["fx_wants"] == ["key", "tempo", "transport"]
        else:
            assert not e["render_ext"] and e["fx_wants"] == [], e["id"]


def test_a_v2_effect_is_rendered_as_before(tool):
    # fm1_fx_render calls a v2 effect's render once per piece, at the
    # piece's frames, whatever the block's clock and events; Test Gain
    # through it is its own render, bit for bit.
    assert tool["v2"] == {"one_call": True, "same_as_render": True}


def test_the_key(tool):
    k = tool["key"]
    assert k["null_is_self"]            # NULL is a copy of the input, bit for bit
    assert k["listen_null_is_input"]
    assert k["key_heard"]               # Listen Key: the output is the key
    assert k["key_untouched"]           # read-only
    assert k["render_is_render_ext"]    # render: no key, no events, stopped
    assert k["probe"] == pytest.approx(0.09, abs=1e-7)   # the tempo it was given


def test_start_stop_and_beats_land_on_the_sequencers_frames(tool):
    t = tool["transport"]
    assert t["block_independent"]       # blocks of 64, 7, 13 and 1: the same samples
    beats = beat_frames(12000, 99008)   # 120 BPM, stopped at 99,008
    assert t["beats"] == beats == [229, 22288, 44347, 66406, 88465]
    assert t["starts"] == [0] and t["stops"] == [99008]
    want = [[0, 0.8]] + [[f, 0.8 if k % 4 == 0 else 0.4] for k, f in enumerate(beats)] + [[99008, -0.8]]
    assert [c[0] for c in t["clicks"]] == [w[0] for w in want]
    assert [c[1] for c in t["clicks"]] == pytest.approx([w[1] for w in want])
    # A piece per block, plus one at each beat inside a block; at 1 frame a
    # block, every frame is a piece.
    assert t["pieces"][0] == math.ceil(110000 / 64) + 5 and t["pieces"][3] == 110000


def test_beats_off_the_block_grid(tool):
    o = tool["odd_tempo"]               # 87.5 BPM: beats on no block's edge
    assert o["same"]
    assert o["beats"] == beat_frames(8750, 70000)
    assert o["clicks"] == [0] + o["beats"]


def test_position_is_exact_and_monotonic(tool):
    p = tool["position"]
    assert p["monotonic"] and p["in_range"]
    assert p["starts"] == 1 and p["start_ok"] and p["first_beat"] == p["first_beat_want"]
    assert p["stopped"] == [0, 0, 0, pytest.approx(133.77, abs=1e-4)]   # running, beat, phase, bpm
    assert p["no_clock"] == [0, 0, 0, 87]


def verbs(tmp_path, text):
    path = tmp_path / "t.verbs"
    path.write_text(text)
    return path


def nonzero(left):
    return [(i, x) for i, x in enumerate(left) if x != 0.0]


def test_fm1_render_gives_an_effect_the_transport(renderer, tmp_path):  # noqa: F811
    script = verbs(tmp_path, "#! rate=44118 block=64 tracks=1 end=110000\n@0 bpm 12000\n@0 play\n"
                             "@99008 stop\n")
    wavs = []
    for frames in ("64", "7", "1"):
        wav = tmp_path / f"b{frames}.wav"
        subprocess.run([str(renderer), "--cmd", str(script), "--frames", frames, "--fx", "test-ext",
                        "--fx-param", "Click=0.8", "--out", str(wav)], check=True, capture_output=True)
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]
    data = wavs[0][44:]
    left = [int.from_bytes(data[i:i + 2], "little", signed=True) / 32767.0
            for i in range(0, len(data), 4)]
    assert len(left) == 110000
    beats = beat_frames(12000, 99008)
    q = round(0.8 * 32767) / 32767.0
    h = round(0.4 * 32767) / 32767.0
    want = [(0, q)] + [(f, q if k % 4 == 0 else h) for k, f in enumerate(beats)] + [(99008, -q)]
    assert nonzero(left) == pytest.approx(want)


def test_fm1_render_gives_its_tempo_without_a_sequencer(renderer, tmp_path):  # noqa: F811
    for args, bpm in (([], 120), (["--tempo", "90"], 90), (["--tempo", "172.5"], 172.5)):
        _, left, _ = render(renderer, tmp_path, input="silence", seconds=0.05, name="t",
                            fx=[("test-ext", ["Probe=1"])], extra=args)
        assert set(left) == {round(bpm / 1000 * 32767) / 32767.0}
    res = subprocess.run([str(renderer), "--input", "silence", "--fx", "test-ext", "--tempo", "10"],
                         capture_output=True, text=True)
    assert res.returncode == 2 and "--tempo" in res.stderr


def test_the_app_gives_an_effect_what_fm1_render_gives(tools, tmp_path):  # noqa: F811
    # The virtual FM-1 runs every effect through the same fm1_fx_render: the
    # same clicks at the same frames as fm1-render, Start, beats and Stop.
    script = verbs(tmp_path, "#! rate=44118 block=64 tracks=1 end=88236\n@0 bpm 9300\n@0 play\n"
                             "@60032 stop\n@70016 play\n")
    out = {}
    for tool_name in ("render", "sim"):
        wav = tmp_path / f"{tool_name}.wav"
        run(tools[tool_name], ["--engine", "test-sine", "--cmd", str(script), "--fx", "test-ext",
                               "--fx-param", "Click=0.5", "--out", str(wav)])
        out[tool_name] = wav.read_bytes()
    assert out["render"] == out["sim"]


# ---- the LOG law -----------------------------------------------------------------

def test_log_law_and_lock_grid(tool):
    ends = {"Cutoff": (20, 18000), "Release": (1, 1000), "Time": (10, 1000), "Xover": (80, 400)}
    for p in tool["log"]:
        lo, hi = ends[p["name"]]
        assert p["is_log"] == 1
        assert (p["at0"], p["at1"]) == (lo, hi) and p["lock_ends"] == [lo, hi]   # exact ends
        assert (p["pos_min"], p["pos_max"], p["pos_nan"]) == (0, 1, 0)
        assert p["trip"] < 1e-6                 # position -> value -> position
        assert p["lock_round_trip"] and p["lock_monotonic"]   # every 7-bit value comes back
        assert p["lock_vs_geometric"] < 2e-6    # value v7 is min (max/min)^(v7/127)
        assert p["detent_ratio_error"] < 2e-6   # a detent is a constant ratio
    assert tool["log_needs_min_above_0"]        # LOG on a range from 0: linear
    assert tool["exp2_exact"]
    assert tool["log_shift"] == [2000, 500, 18000]   # +1 and -1 octave, and clamped


def ppm_pixels(path):
    data = path.read_bytes()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    px = parts[3]
    return w, h, lambda x, y: tuple(px[3 * (y * w + x):3 * (y * w + x) + 3])


def rgb565(r, g, b):
    return ((r >> 3) * 255 // 31, (g >> 2) * 255 // 63, (b >> 3) * 255 // 31)


def test_the_app_steps_and_draws_log_knobs_in_ratios(tools, tmp_path):  # noqa: F811
    # FX mode, the Filter's page 1: KNOB2 is Cutoff (LOG), KNOB3 Resonance.
    base = ["--engine", "macro", "--fx", "filter", "--seconds", "0.3", "--button", "0.01:FX"]
    octaves = math.log2(18000 / 20)
    pos = math.log2(2000 / 20) / octaves          # the default, 2 kHz
    # (An encoder event moves at most 64 detents: the ends take two.)
    for turns, want in (([12], 20 * 2 ** ((pos + 0.12) * octaves)),
                        ([-30], 20 * 2 ** ((pos - 0.3) * octaves)),
                        ([64, 64], 18000), ([-64, -64], 20)):
        args = list(base)
        for k, turn in enumerate(turns):
            args += ["--turn", f"{0.1 + 0.05 * k}:KNOB2:{turn}"]
        s = run(tools["sim"], args + ["--out", str(tmp_path / "a.wav")])
        assert s["values1"][1] == pytest.approx(want, rel=2e-5), turns
    s = run(tools["sim"], base + ["--turn", "0.1:KNOB3:5", "--out", str(tmp_path / "b.wav")])
    assert s["values1"][2] == pytest.approx(0.30)  # a linear knob steps as before
    # The bar shows the knob's position: 2 kHz fills 0.677 of Cutoff's bar
    # (154 of 228 pixels), not the 11 % a linear bar would.
    screen = tmp_path / "fx.ppm"
    run(tools["sim"], base + ["--screen", str(screen), "--out", str(tmp_path / "c.wav")])
    w, _, at = ppm_pixels(screen)
    accent = rgb565(0xc4, 0xa7, 0xe7)
    # The second row's bar, its middle line: FX mode's rows start at 68 since
    # the UI audit's context line (fm1_app.c FX_ROWS_Y: the chain in MAIN,
    # the effect's line in MID, 4 px after each).
    y = 68 + 36 + 22 + 3
    fill = [x for x in range(w) if at(x, y) == accent]
    assert fill and fill[0] == 6 and len(fill) == round(pos * 228)


# ---- LOG under modulation (docs/16 §2.3) ---------------------------------------------

def mod_file(tmp_path, *lines):
    path = tmp_path / "m.mod"
    path.write_text("seed 1\n" + "\n".join(lines) + "\n")
    return path


def fx1_cutoff(log_path):
    """(base, value) of the first effect's Cutoff (uid 2) at every tick."""
    out = []
    for line in log_path.read_text().splitlines():
        tick = json.loads(line)
        for s in tick["s"]:
            if s["u"] == "fx1" and s["uid"] == 2:
                out.append((tick["t"], s["b"], s["v"]))
    return out


def test_note_at_full_amount_keytracks_a_log_cutoff_exactly(renderer, tmp_path):  # noqa: F811
    # The octave rule: NOTE (SEMI) into Cutoff (LOG) at +100 % moves it by
    # the note's semitones, so Cutoff = base x 2^((note - 60) / 12).
    notes = [60, 72, 48, 67, 61, 84, 36]
    args = ["--engine", "macro", "--fx", "filter", "--fx-param", "Cutoff=1000", "--seconds", "1.6",
            "--mod", str(mod_file(tmp_path, "slot 1 note > fx1:Cutoff amt=100")),
            "--log-mod", str(tmp_path / "m.jsonl")]
    for k, n in enumerate(notes):
        args += ["--note", f"{0.2 * k}:{n}:100:0.15"]
    subprocess.run([str(renderer), *args, "--out", str(tmp_path / "o.wav")], check=True,
                   capture_output=True)
    ticks = fx1_cutoff(tmp_path / "m.jsonl")
    for k, n in enumerate(notes):
        t = int((0.2 * k + 0.1) * RATE)           # mid-note
        _, base, value = min(ticks, key=lambda x: abs(x[0] - t))
        ratio = value / base
        want = 2 ** ((n - 60) / 12)
        if (n - 60) % 12 == 0:
            assert ratio == want, n                # whole octaves: exact
        else:
            assert ratio == pytest.approx(want, rel=1e-6), n   # 0.002 cent


def test_a_route_moves_a_log_parameter_in_octaves(renderer, tmp_path):  # noqa: F811
    # An LFO at 20 % into Cutoff swings it 20 % of its knob either way:
    # 0.2 x log2(18000 / 20) octaves, symmetric in ratio round the base.
    args = ["--engine", "macro", "--note", "0:48:100:2", "--fx", "filter", "--fx-param",
            "Cutoff=1000", "--seconds", "2",
            "--mod", str(mod_file(tmp_path, "mod 1 lfo rate=0.6", "slot 1 lfo1 > fx1:Cutoff amt=20")),
            "--log-mod", str(tmp_path / "m.jsonl")]
    subprocess.run([str(renderer), *args, "--out", str(tmp_path / "o.wav")], check=True,
                   capture_output=True)
    values = [v for _, _, v in fx1_cutoff(tmp_path / "m.jsonl")]
    swing = 2 ** (0.2 * math.log2(900))
    assert max(values) == pytest.approx(1000 * swing, rel=0.01)
    assert min(values) == pytest.approx(1000 / swing, rel=0.01)


def test_log_routes_are_block_size_independent(renderer, tmp_path):  # noqa: F811
    mod = mod_file(tmp_path, "mod 1 lfo rate=0.7", "slot 1 lfo1 > fx1:Cutoff amt=35",
                   "slot 2 note > fx1:Cutoff amt=100", "slot 3 lfo1 > fx2:Time amt=-20")
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, "macro", notes=["0:52:100:1.2"], seconds=1.2,
                           name=f"f{frames}", fx=[("filter", ["Resonance=0.6"]), ("echo", [])],
                           extra=["--mod", str(mod), "--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


def test_a_log_route_at_zero_changes_nothing(renderer, tmp_path):  # noqa: F811
    plain = render(renderer, tmp_path, "macro", notes=["0:52:100:0.6"], seconds=0.8, name="plain",
                   fx=[("filter", ["Cutoff=700"])])[2]
    zero = render(renderer, tmp_path, "macro", notes=["0:52:100:0.6"], seconds=0.8, name="zero",
                  fx=[("filter", ["Cutoff=700"])],
                  extra=["--mod", str(mod_file(tmp_path, "slot 1 note > fx1:Cutoff amt=0"))])[2]
    assert plain.read_bytes() == zero.read_bytes()
