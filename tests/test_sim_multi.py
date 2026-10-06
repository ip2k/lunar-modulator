"""Multi-sound in the virtual FM-1 (docs/15 §3.16): up to four sound units,
each with two inserts and a level into the mix, then the master bus's two
slots; tracks routed to sound units by slot; the panel's gestures for
choosing the current sound; and the RAM meter that refuses any engine or
effect that would take the chain past the FM-1's budget. (Behind a lab
switch until 2026-10-05; the app has run it on every chain since.)

The parity scenarios (sim/web/test/scenarios.json) check the app against
fm1-render natively (tests/test_sim_web.py) and in WebAssembly (parity.mjs):
the multi-* ones against fm1-render --slots, every one-sound scenario
against fm1-render's one engine, to the bit. This file checks the panel and
the meter.
"""
import json
import subprocess

import pytest

from tests.test_sim_web import SCENARIOS, left_channel, run, scenario_args, tools  # noqa: F401

BUDGET = 387924
SEQ_FIXED = 31880 + 3264          # the sequencer's instance (8 tracks) and event buffer (272 events),
SEQ_MORE = 240 + 1024 + 20        # its pending record, the UI bound and the click,
MOD_BYTES = 26512                 # and the modulation runtime (fm1_mod_size(), docs/16 MG3; MG9 voices; glide)
FIXED = SEQ_FIXED + SEQ_MORE + MOD_BYTES
MIX_BLOCK = 512


def sim(tools, *args, seconds=1.0):
    """A run of fm1-sim-render."""
    return run(tools["sim"], ["--seconds", str(seconds), *args])


def instance_bytes(tools, engine_id, kind="sound"):
    if kind == "sound":
        return run(tools["render"], ["--engine", engine_id, "--seconds", "0.01"])["instance_bytes"]
    return run(tools["render"], ["--fx", engine_id, "--input", "sine", "--seconds", "0.01"])["fx_bytes"][0]


def test_shift_presets_chooses_the_current_sound(tools):
    """SEL held (SHIFT, outside FX mode) and PRESETS turned: the current
    sound, with a list of the four and what each holds, the current one
    chosen (three lines, "Sound 2 of 4" and its engine, until 2026-10-06);
    SHIFT is let go after."""
    s = sim(tools, "--engine", "macro", "--sound", "1:shapes", "--button", "0.1:SEL:0.2",
            "--turn", "0.15:PRESETS:1", seconds=0.5)
    assert s["current"] == 1 and s["popup"] == ["S1 Macro", "S2 Shapes", "S3 Empty", "S4 Empty"]
    assert s["popup_list"] == {"title": "Current sound", "first": 0, "total": 4, "mark": 1}
    assert s["seq_view"]["shift"] == 0 and s["engine"] == "macro"
    empty = sim(tools, "--engine", "macro", "--button", "0.1:SEL:0.2", "--turn", "0.15:PRESETS:3",
                seconds=0.5)
    assert empty["current"] == 3 and empty["popup"] == ["S1 Macro", "S2 Empty", "S3 Empty", "S4 Empty"]
    assert empty["popup_list"]["mark"] == 3
    fx = sim(tools, "--engine", "macro", "--button", "0.05:FX", "--button", "0.1:SEL:0.2",
             "--turn", "0.15:PRESETS:1", seconds=0.5)
    assert fx["current"] == 0, "SEL is the slot grab in FX mode, not SHIFT"


def test_the_keys_play_the_current_sound(tools):
    """Sound 1 at level 0, Sound 2 at full: a key is silent on Sound 1 and
    sounds once SHIFT + PRESETS made Sound 2 current; its release goes to
    Sound 2 even after Sound 1 is current again."""
    base = ["--engine", "test-sine", "--sound", "1:test-sine", "--level", "0:0"]
    quiet = sim(tools, *base, "--key", "0.3:5:100:0.3", seconds=0.8)
    assert quiet["peak"] == 0
    loud = sim(tools, *base, "--button", "0.1:SEL:0.1", "--turn", "0.15:PRESETS:1",
               "--key", "0.3:5:100:0.3", "--button", "0.4:SEL:0.1", "--turn", "0.45:PRESETS:-1",
               seconds=0.8)
    assert loud["peak"] > 0.1 and loud["current"] == 0 and loud["sounding"] == 0


def test_the_keys_follow_the_current_sounds_pads(tools):
    """The white-key pad map follows the current sound, not Sound 1: with
    Drums as Sound 2 and current, a black key is silent (no pad) and a white
    key plays a pad; with Macro current over Drums as Sound 1, the same black
    key plays its pitch."""
    to_two = ["--button", "0.1:SEL:0.1", "--turn", "0.15:PRESETS:1"]
    on_drums = sim(tools, "--engine", "macro", "--sound", "1:drums", "--level", "0:0", *to_two,
                   "--key", "0.3:1:100:0.2", seconds=0.8)
    assert on_drums["current"] == 1 and on_drums["peak"] == 0
    white = sim(tools, "--engine", "macro", "--sound", "1:drums", "--level", "0:0", *to_two,
                "--key", "0.3:0:100:0.2", seconds=0.8)
    assert white["peak"] > 0.05
    on_macro = sim(tools, "--engine", "drums", "--sound", "1:macro", "--level", "0:0", *to_two,
                   "--key", "0.3:1:100:0.2", seconds=0.8)
    assert on_macro["current"] == 1 and on_macro["peak"] > 0.01


def test_sophies_pads_follow_the_current_sound(tools):
    """The white keys play Sophie's pads when Sophie is the current sound,
    whichever unit holds her (found when multi-sound went public): as Sound
    2 with Sound 1 silent, white key 1 plays pad 1; with Macro current
    instead, the same key plays F3 on Macro, which Sound 1's level 0
    silences."""
    base = ["--engine", "macro", "--sound", "1:sw-sophie", "--level", "0:0", "--key", "0.3:0:110:0.3"]
    pad = sim(tools, *base, "--button", "0.05:SEL:0.1", "--turn", "0.1:PRESETS:1", seconds=0.7)
    assert pad["current"] == 1 and pad["peak"] > 0.05
    macro = sim(tools, *base, seconds=0.7)
    assert macro["current"] == 0 and macro["peak"] == 0


def test_a_midi_note_off_finds_the_sound_holding_it(tools, tmp_path):
    """A note at MIDI IN plays the current sound; if the current sound
    changes before its release, the release still reaches the sound that
    holds it, nothing is left sounding, and the run replays (the note is
    logged on the sound it played)."""
    panel = tmp_path / "p.panel"
    panel.write_text("--note 0.10:60:100:0.40\n--button 0.20:SEL:0.10\n--turn 0.22:PRESETS:1\n"
                     "--note 0.40:62:100:0.20\n")
    script = tmp_path / "in.verbs"
    script.write_text("#! rate=44118 block=64 tracks=2 end=44118\n@0 bpm 12000\n")
    s = run(tools["sim"], ["--engine", "test-sine", "--sound", "1:test-sine", "--cmd", str(script),
                           "--panel", str(panel), "--log-cmds", str(tmp_path / "c.verbs"),
                           "--out", str(tmp_path / "a.wav")])
    assert s["current"] == 1 and s["sounding"] == 0 and s["replayable"] == 1
    args = (tmp_path / "c.args").read_text().splitlines()
    assert args[:1] == ["--slots"] and "1:0.40:62:100:0.20" in args and "0.10:60:100:0.40" in args
    run(tools["render"], ["--cmd", str(tmp_path / "c.verbs"), *args, "--out", str(tmp_path / "b.wav")])
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()


def test_presets_on_another_sound_reaches_empty(tools):
    """Sounds 2-4 may be empty: their PRESETS list starts with Empty, which
    unloads the sound (Sound 1 always holds one, as before)."""
    on = sim(tools, "--engine", "macro", "--button", "0.1:SEL:0.1", "--turn", "0.15:PRESETS:1",
             "--turn", "0.3:PRESETS:1", seconds=0.5)
    assert on["sounds"][1] == "macro" and on["popup"][:3] == ["Empty", "Macro", "Shapes"]
    catalog = json.loads(subprocess.run([str(tools["sim"]), "--list"], check=True,
                                        capture_output=True, text=True).stdout)
    engines = sum(e["kind"] == "sound" for e in catalog)
    # With more than one sound in use the title says whose list it is.
    assert on["popup_list"] == {"title": "S2 engine", "first": 0, "total": 1 + engines, "mark": 1}
    off = sim(tools, "--engine", "macro", "--sound", "1:shapes", "--button", "0.1:SEL:0.1",
              "--turn", "0.15:PRESETS:1", "--turn", "0.3:PRESETS:-1", "--turn", "0.4:PRESETS:-1",
              seconds=0.5)
    assert off["sounds"][1] == "" and off["popup"][0] == "Empty" and off["popup_list"]["mark"] == 0


def test_fx_mode_walks_the_inserts_mix_and_master(tools):
    """FX mode opens on the master slot M1 (Plate); SELECT
    walks In1, In2, Mix, M1, M2; ALGORITHM on In1 loads an insert on the
    current sound; the Mix page's KNOB3 is Sound 3's level."""
    s = sim(tools, "--engine", "macro", "--fx", "plate", "--button", "0.05:FX", seconds=0.3)
    assert s["mode"] == 1 and s["fx_unit_slot"] == 3
    walk = sim(tools, "--engine", "macro", "--fx", "plate", "--button", "0.05:FX",
               "--turn", "0.1:SELECT:-64", "--turn", "0.15:ALGORITHM:2", seconds=0.3)
    assert walk["fx_unit_slot"] == 0 and walk["inserts"][0] == ["ensemble", ""]
    mix = sim(tools, "--engine", "macro", "--button", "0.05:FX", "--turn", "0.1:SELECT:-1",
              "--turn", "0.15:KNOB3:-30", seconds=0.3)
    assert mix["fx_unit_slot"] == 2 and mix["levels"] == [100, 100, 70, 100]
    s2 = sim(tools, "--engine", "macro", "--sound", "1:shapes", "--button", "0.05:SEL:0.05",
             "--turn", "0.07:PRESETS:1", "--button", "0.15:FX", "--turn", "0.2:SELECT:-64",
             "--turn", "0.25:ALGORITHM:1", seconds=0.4)
    assert s2["current"] == 1 and s2["inserts"][1] == ["plate", ""] and s2["inserts"][0] == ["", ""]


def test_sel_and_select_swap_the_inserts(tools):
    s = sim(tools, "--engine", "macro", "--insert", "0:ensemble", "--insert", "0:diffuse",
            "--button", "0.05:FX", "--turn", "0.1:SELECT:-64", "--button", "0.15:SEL",
            "--turn", "0.2:SELECT:1", "--turn", "0.25:SELECT:1", seconds=0.4)
    assert s["inserts"][0] == ["diffuse", "ensemble"] and s["fx_unit_slot"] == 1


def test_the_meter_counts_the_chain_and_the_fixed_costs(tools):
    """The RAM figure is every instance, the sequencer's instance and
    events, its pending record, UI bound and click, the modulation runtime,
    and a 512-byte block for each sound past the first."""
    s = sim(tools, "--engine", "macro", "--sound", "2:sixop", "--insert", "0:ensemble", "--fx", "plate",
            seconds=0.1)
    want = (instance_bytes(tools, "macro") + instance_bytes(tools, "sixop") +
            instance_bytes(tools, "ensemble", "fx") + instance_bytes(tools, "plate", "fx"))
    assert s["ram"] == want + FIXED + MIX_BLOCK
    one = run(tools["sim"], ["--engine", "macro", "--fx", "plate", "--seconds", "0.1"])
    assert one["ram"] == instance_bytes(tools, "macro") + instance_bytes(tools, "plate", "fx") + FIXED


def test_the_meter_refuses_what_would_not_fit(tools):
    """Shapes twice passes the budget: the harness's load is refused (-4).
    PRESETS steps over a sound that would not fit, with a popup that says by
    how much; the chain never passes the budget."""
    res = subprocess.run([str(tools["sim"]), "--engine", "shapes", "--sound", "1:shapes",
                          "--seconds", "0.1"], capture_output=True, text=True)
    assert res.returncode == 1 and "(-4)" in res.stderr
    s = sim(tools, "--engine", "macro", "--sound", "1:shapes", "--turn", "0.1:PRESETS:1", seconds=0.3)
    assert s["engine"] not in ("macro", "shapes")
    assert s["popup"][:2] == ["Shapes", "does not fit"] and s["popup"][2].endswith("K over budget")
    over = int(s["popup"][2].split("K")[0])
    shapes = instance_bytes(tools, "shapes")
    assert over == -(-(2 * shapes + FIXED + MIX_BLOCK - BUDGET) // 1024)
    assert s["ram"] <= BUDGET


def test_the_refusal_popup_gives_the_first_refusals_figure(tools):
    """PRESETS steps over two sounds that would not fit (Shapes, then Macro
    Heavy) to Six-Op; the popup names the first one skipped and by how much
    that one would pass the budget, not the last one's figure. (The second
    master effect is Ensemble since glide: with Diffuse, Macro and Shapes no
    longer fit together once both carried glide's state.)"""
    chain = ["--engine", "macro", "--sound", "1:shapes", "--fx", "plate", "--fx", "ensemble"]
    s = sim(tools, *chain, "--turn", "0.1:PRESETS:1", seconds=0.3)
    assert s["engine"] == "sixop" and s["popup"][:2] == ["Shapes", "does not fit"]
    rest = (instance_bytes(tools, "shapes") + instance_bytes(tools, "plate", "fx") +
            instance_bytes(tools, "ensemble", "fx") + FIXED + MIX_BLOCK)
    assert rest + instance_bytes(tools, "macro") <= BUDGET, "the chain must fit to begin with"
    assert rest + instance_bytes(tools, "macro-heavy") > BUDGET, "Macro Heavy must be refused too"
    over = rest + instance_bytes(tools, "shapes") - BUDGET
    assert s["popup"][2] == f"{-(-over // 1024)}K over budget"


def test_a_note_on_an_empty_sound_replays(tools, tmp_path):
    """A key and a MIDI note on an empty current sound play nothing; the
    sidecar carries them as --sound-note, which fm1-render takes and plays
    nothing with, so the run replays byte for byte."""
    script = tmp_path / "in.verbs"
    script.write_text("#! rate=44118 block=64 tracks=2 end=44118\n@0 bpm 12000\n")
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(script), "--note", "0.05:57:100:0.6",
                           "--button", "0.1:SEL:0.1", "--turn", "0.15:PRESETS:1", "--key", "0.3:5:100:0.2",
                           "--note", "0.5:60:100:0.1", "--log-cmds", str(tmp_path / "c.verbs"),
                           "--out", str(tmp_path / "a.wav")])
    assert s["current"] == 1 and s["sounds"][1] == "" and s["replayable"] == 1 and s["peak"] > 0.1
    args = (tmp_path / "c.args").read_text().splitlines()
    assert args.count("--sound-note") == 2
    run(tools["render"], ["--cmd", str(tmp_path / "c.verbs"), *args, "--out", str(tmp_path / "b.wav")])
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()


def test_the_unit_route_api_goes_in_as_a_typed_command(tools, tmp_path):
    """fm1_app_unit_route (stage S6's API) sends a typed `route t 1 k`, so
    the harness logs it with the panel's commands and fm1-render replays
    it: track 1, on MIDI by default, plays Sound 2 from then on. A sound
    past the fourth is refused."""
    script = tmp_path / "in.verbs"
    script.write_text("#! rate=44118 block=64 tracks=2 end=44118\n@0 bpm 12000\n"
                      "@0 tog 0 0 60 100;tog 1 4 67 100;tog 1 8 72 100;play\n")
    units = ["--engine", "test-sine", "--sound", "1:test-sine", "--level", "1:50"]
    s = run(tools["sim"], [*units, "--cmd", str(script), "--unit-route", "0.2:1:1",
                           "--log-cmds", str(tmp_path / "c.verbs"), "--out", str(tmp_path / "a.wav"),
                           "--log-events", str(tmp_path / "a.jsonl")])
    assert s["replayable"] == 1 and s["seq_notes_to_engine"] == 2
    assert [c[1] for c in s["seq_ui_cmds"]] == ["route 1 1 1"]
    assert "route 1 1 1" in (tmp_path / "c.verbs").read_text()
    args = (tmp_path / "c.args").read_text().splitlines()
    r = run(tools["render"], ["--cmd", str(tmp_path / "c.verbs"), *args, "--out", str(tmp_path / "b.wav"),
                              "--log-events", str(tmp_path / "b.jsonl")])
    assert r["seq_notes_to_engine"] == 2
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()
    past = subprocess.run([str(tools["sim"]), "--engine", "test-sine", "--cmd", str(script),
                           "--unit-route", "0.2:1:4", "--seconds", "0.3"], capture_output=True, text=True)
    assert past.returncode == 2 and "refused" in past.stderr


def test_levels_stay_in_range(tools):
    """--level and --level-at take 0..100, in the harness as in fm1-render."""
    for tool in ("sim", "render"):
        for flag, value in (("--level", "0:150"), ("--level-at", "0:0.1:-5")):
            res = subprocess.run([str(tools[tool]), "--engine", "test-sine", flag, value,
                                  "--seconds", "0.1"], capture_output=True, text=True)
            assert res.returncode == 2, (tool, flag)


def test_algorithm_steps_over_an_effect_that_would_not_fit(tools):
    """In FX mode ALGORITHM steps over an effect the meter refuses, so
    every effect past it stays reachable, and says which one it skipped:
    with Shapes and Macro Heavy loaded, PSX Verb on M1 would pass the
    budget, so a turn back from Crush lands on Diffuse."""
    s = sim(tools, "--engine", "shapes", "--sound", "1:macro-heavy", "--fx", "crush", "--button", "0.05:FX",
            "--turn", "0.1:ALGORITHM:-1", seconds=0.3)
    assert s["fx"][0] == "diffuse" and s["popup"][:2] == ["PSX Verb", "does not fit"]
    assert s["ram"] <= BUDGET


def test_every_scenario_fits_the_meter(tools):
    """The parity scenarios play on the panel's chain, under the RAM meter:
    every one loads (a chain past the FM-1's budget would be refused, -4)
    and stays inside the budget. fx-turns-diffuse-psxverb ran Shapes, which
    with Diffuse and PSX Verb would pass it, until the lab switch went."""
    for s in SCENARIOS:
        if "panel" in s:
            continue
        r = run(tools["sim"], scenario_args(s) + ["--seconds", "0.01"])
        assert r["ram"] <= BUDGET, s["name"]


ROUTED = ("#! rate=44118 block=64 tracks=4 end=44118\n"
          "@0 tog 0 0 60 100;tog 1 2 64 100;tog 2 4 67 100;tog 3 6 72 100\n"
          "@0 route 0 1 0;route 1 1 1;route 2 1 2;route 3 1 3;play\n")


def test_tracks_play_the_sound_their_route_names(tools, tmp_path):
    """A track routed to the engine plays the sound unit its route index
    names, and nothing when that unit is empty; the app agrees with
    fm1-render --slots on every sample and event (fm1-render without --slots
    plays every engine-routed track on its one engine)."""
    path = tmp_path / "r.verbs"
    path.write_text(ROUTED)
    units = ["--engine", "test-sine", "--sound", "1:test-sine", "--sound", "3:test-sine"]
    out = {}
    for name, tool, extra in (("sim", "sim", []), ("ref", "render", ["--slots"])):
        wav, log = tmp_path / f"{name}.wav", tmp_path / f"{name}.jsonl"
        out[name] = (run(tools[tool], ["--cmd", str(path), *units, *extra, "--out", str(wav),
                                       "--log-events", str(log)]), wav.read_bytes(), log.read_bytes())
    s, r = out["sim"][0], out["ref"][0]
    assert out["sim"][1:] == out["ref"][1:]
    assert s["seq_notes_to_engine"] == r["seq_notes_to_engine"] == 3, "track 2's slot is empty"
    one = run(tools["render"], ["--cmd", str(path), "--engine", "test-sine"])
    assert one["seq_notes_to_engine"] == 4, "fm1-render without --slots plays every engine route"


# Track 1 holds one note for a bar (2 s at 120 BPM) on Sound 1; a quarter of
# a second in, it is routed elsewhere ({route}).
REROUTED = ("#! rate=44118 block=64 tracks=4 end=66177\n"
            "@0 bpm 12000;tog 1 0 60 100;slen 1 0 0 -1 384;route 1 1 0;play\n"
            "@11025 {route}\n")


@pytest.mark.parametrize("route,slots", [("route 1 1 1", True), ("route 1 0 5", True),
                                         ("route 1 0 5", False)])
def test_a_track_routed_elsewhere_lets_go_of_its_note_where_it_sounds(tools, tmp_path, route, slots):
    """docs/15 S6, found in its review: the Track page reroutes a playing
    track, and before the fix the note it held stayed on, on Sound 1, for
    good (its note-off went to the new route). The core now closes the
    track's gates on a route that moves it, and the bridge sends those
    note-offs where the notes went; the app agrees with fm1-render, with
    several sound units (--slots) and with one (fm1-render's one engine)."""
    path = tmp_path / "r.verbs"
    path.write_text(REROUTED.format(route=route))
    units = ["--engine", "test-sine", "--sound", "1:test-sine"] if slots else ["--engine", "test-sine"]
    out = {}
    for name, tool, extra in (("sim", "sim", []),
                              ("ref", "render", ["--frames", "64"] + (["--slots"] if slots else []))):
        wav, log = tmp_path / f"{name}.wav", tmp_path / f"{name}.jsonl"
        out[name] = (run(tools[tool], ["--cmd", str(path), *units, *extra, "--out", str(wav),
                                       "--log-events", str(log)]), wav.read_bytes(), log.read_bytes())
    assert out["sim"][1:] == out["ref"][1:]
    ev = [json.loads(line) for line in out["ref"][2].decode().splitlines()]
    notes = [(e["kind"], e["track"], e["a"]) for e in ev if e["kind"] in ("on", "off")]
    assert notes == [("on", 1, 60), ("off", 1, 60)]
    off = next(e for e in ev if e["kind"] == "off")
    assert off["block"] == 11025 // 64 + 1, "the note-off comes with the route, not a bar later"
    left = left_channel(out["ref"][1])
    assert max(abs(x) for x in left[5000:11000]) > 0.05
    assert max(abs(x) for x in left[13000:]) == 0, "nothing left sounding on Sound 1"


def test_a_bend_on_another_sound_is_not_replayable(tools, tmp_path):
    script = tmp_path / "in.verbs"
    script.write_text("#! rate=44118 block=64 tracks=2 end=22059\n@0 bpm 12000\n")
    s = run(tools["sim"], ["--engine", "test-sine", "--sound", "1:test-sine", "--cmd", str(script),
                           "--button", "0.05:SEL:0.1", "--turn", "0.08:PRESETS:1", "--bend", "0.2:2",
                           "--log-cmds", str(tmp_path / "c.verbs")])
    assert s["replayable"] == 0
