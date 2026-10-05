"""Modulation on the virtual FM-1's panel (docs/16 stage MG3; behind a lab
switch until 2026-10-05): the app hosts the runtime (fm1_mod) on the
sequencer's bridge, the default rack and its cables, the buttons and pages
(RACK, MATRIX, CHAIN), the routing gesture, and golden gesture traces that
replay through fm1-render --mod byte for byte.

A gesture trace is a .panel file (one --key, --button or --turn per line,
as tests/test_seq_ui.py's) and its golden .mod: what `fm1-sim-render
--log-cmds` writes for the modulation, the runtime's state at the start and
every edit at the block it led. Every trace here starts from
tests/fixtures/mod-ui/input.verbs with Macro and Plate. The parity
scenarios mod-macro-routes and mod-panel-gestures (sim/web/test/mod/) play
the same in WebAssembly on the build host.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ROOT
from tests.test_sim_multi import FIXED, instance_bytes
from tests.test_sim_web import left_channel, run, tools  # noqa: F401  (the native build)

TRACES = ROOT / "tests" / "fixtures" / "mod-ui"
PANELS = sorted(TRACES.glob("*.panel"))
INPUT = TRACES / "input.verbs"
CHAIN = ["--engine", "macro", "--fx", "plate"]
BUTTONS = ["OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO", "HOME", "SAVE", "ARP", "SEQ",
           "PLAY/STOP", "REC"]
MODES = {"HOME": 0, "FX": 1, "GLOBAL": 2, "SEQ": 3, "RACK": 4, "MATRIX": 5, "CHAIN": 6}
Q14 = 16384
ON, GATE_DST, VOICE = 0x01, 0x08, 0x80


def lit(summary):
    return {n for n, c in zip(BUTTONS, summary["leds"][27:]) if c == "1"}


def q14(pct):
    """fm1_mod_q14(pct / 100), as the panel makes amounts."""
    x = max(-1.0, min(1.0, pct / 100.0)) * Q14
    return int(x + 0.5) if x >= 0 else -int(0.5 - x)


def sim(tools, *panel, seconds="0.4", engine="macro", extra=()):
    return run(tools["sim"], ["--engine", engine, "--seconds", seconds, *extra, *panel])


def slots(summary):
    return {s["slot"]: s for s in summary["mod"]["slots"]}


# ---- from the start -------------------------------------------------------------------------

def test_the_runtime_runs_from_the_start_and_counts_in_the_ram_figure(tools):
    """Since the lab switch went (2026-10-05) every chain runs the runtime:
    ENV, LFO and EDIT open their pages, SAVE and ARP alone are still stubs,
    and the RAM figure counts the runtime (fm1_mod_size())."""
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    plain = sim(tools, seconds="0.1")
    assert "mod" in plain and plain["ram"] == instance_bytes(tools, "macro") + FIXED
    assert FIXED - z["mod_bytes"] == 31880 + 3264 + 240 + 1024 + 20
    for name, mode in (("ENV", 4), ("LFO", 4), ("EDIT", 5)):
        s = sim(tools, "--button", f"0.1:{name}", seconds="0.2")
        assert s["mode"] == mode and s["popup"] == [], name
    for name in ("SAVE", "ARP"):
        s = sim(tools, "--button", f"0.1:{name}", seconds="0.2")
        assert s["mode"] == 0 and s["popup"] == [name, "not in the", "simulator yet"]


def test_the_app_starts_with_the_default_rack_and_its_cables(tools):
    """Owner, 2026-10-02: LFO1, LFO2, ENV3, ENV4, CHN5 (Chance) and three empty
    positions; RTRG (every note on every sound: keys, MIDI in, the
    sequencer; each note-on restarts it, owner 2026-10-05) cabled into both
    envelopes' GATE at 100 %, re-patchable."""
    m = sim(tools)["mod"]
    assert m["rack"] == ["lfo", "lfo", "env", "env", "chance", "", "", ""]
    assert [(s["slot"], s["src"], s["unit"], s["dst"], s["amount"], s["flags"]) for s in m["slots"]] == [
        (1, 23, 8 + 2, 0, Q14, ON | GATE_DST), (2, 23, 8 + 3, 0, Q14, ON | GATE_DST)]
    assert [s["row"] for s in m["slots"]] == ["RTRG  >ENV3Gte +100", "RTRG  >ENV4Gte +100"]
    assert (m["sel_lfo"], m["sel_env"]) == (1, 3)


def test_sizes(tools):
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert z["mod_bytes"] == 22368 <= z["mod_arena"] == 24576
    assert z["mod_ui_bytes"] <= 256


# ---- buttons and pages -------------------------------------------------------------------

def test_lfo_and_env_open_the_rack_at_their_kind(tools):
    """A tap opens RACK at the selected module of that kind (the first by
    default); in RACK on one of its kind, the next one, wrapping round. The
    button lights while RACK shows its kind."""
    steps = [("LFO", 1), ("LFO", 2), ("LFO", 1), ("ENV", 3), ("ENV", 4), ("ENV", 3), ("LFO", 1)]
    panel = []
    for k, (button, pos) in enumerate(steps):
        panel += ["--button", f"{0.05 + 0.05 * k}:{button}"]
        s = sim(tools, *panel)
        assert (s["mode"], s["mod"]["pos"]) == (MODES["RACK"], pos), panel
        assert lit(s) == {button}
    walk = sim(tools, "--button", "0.05:LFO", "--turn", "0.1:SELECT:5")
    assert (walk["mod"]["pos"], walk["mod"]["page"]) == (3, 2)   # LFO1 1-2, LFO2 1-2, ENV3 1-2
    assert walk["mod"]["sel_env"] == 3 and lit(walk) == {"ENV"}


def test_edit_opens_the_matrix_and_sel_the_chain(tools):
    s = sim(tools, "--button", "0.1:EDIT")
    assert s["mode"] == MODES["MATRIX"] and lit(s) == {"EDIT"}
    s = sim(tools, "--button", "0.1:EDIT", "--button", "0.2:SEL")
    assert s["mode"] == MODES["CHAIN"] and lit(s) == {"EDIT", "SEL"}
    s = sim(tools, "--button", "0.1:EDIT", "--button", "0.2:SEL", "--button", "0.3:SEL")
    assert s["mode"] == MODES["MATRIX"]
    s = sim(tools, "--button", "0.1:EDIT", "--button", "0.2:EDIT")
    assert s["mode"] == MODES["HOME"] and lit(s) == set()
    for leave, mode in (("HOME", 0), ("FX", 1), ("GLO", 2)):
        for page in ("EDIT", "LFO"):
            s = sim(tools, "--button", f"0.1:{page}", "--button", f"0.2:{leave}")
            assert s["mode"] == mode, (page, leave)


def test_sel_grabs_a_module_and_select_moves_it(tools):
    """SEL in RACK grabs the module (SEL lit, the line under the rack
    starred); SELECT moves it, and every cable follows it."""
    s = sim(tools, "--button", "0.05:ENV", "--button", "0.1:SEL", "--turn", "0.15:SELECT:2")
    m = s["mod"]
    assert m["grab"] == 1 and "SEL" in lit(s)
    assert m["rack"] == ["lfo", "lfo", "env", "chance", "env", "", "", ""] and m["pos"] == 5
    assert [(x["unit"] - 8, x["dst"]) for x in m["slots"]] == [(4, 0), (2, 0)]   # the first envelope, ENV5 now


def test_a_tap_or_a_hold_of_env_and_lfo(tools):
    """Held while a knob turns, LFO makes a cable and leaves the page as it
    was; released without a turn, it is a tap."""
    held = sim(tools, "--button", "0.1:LFO:0.2", "--turn", "0.15:KNOB3:20")
    assert held["mode"] == MODES["HOME"] and 3 in slots(held)
    tap = sim(tools, "--button", "0.1:LFO:0.2")
    assert tap["mode"] == MODES["RACK"] and set(slots(tap)) == {1, 2}


# ---- the gesture ----------------------------------------------------------------------------

def test_the_gesture_on_home_makes_and_adjusts_one_cable(tools):
    """Hold LFO and turn KNOB2 (Harmonics) on HOME: slot 3, LFO1 into the
    sound's Harmonics, its amount the turn's percent; turning on adjusts
    the same cable; the knob's base stays where it was."""
    s = sim(tools, "--button", "0.1:LFO:0.3", "--turn", "0.15:KNOB2:30", "--turn", "0.2:KNOB2:-12",
            "--turn", "0.25:KNOB4:-25")
    sl = slots(s)
    assert (sl[3]["src"], sl[3]["unit"], sl[3]["dst"], sl[3]["amount"]) == (64, 0, 2, q14(18))
    assert (sl[4]["src"], sl[4]["dst"], sl[4]["amount"]) == (64, 4, q14(-25))   # Morph, uid 4
    assert s["values0"][1] == pytest.approx(0.5)                 # Harmonics' base untouched
    assert s["popup"] == ["LFO1 > S1Morph", "-25%"]


def test_the_gesture_reaches_effects_and_modules(tools):
    """FX mode: ENV3 into Plate's Mix (unit FX1). RACK: ENV3 into LFO2's
    Rate (a chain); the gesture's source is the module of its button's kind
    last shown (here ENV3, then LFO2's own page does not change it)."""
    fx = sim(tools, "--button", "0.05:FX", "--button", "0.1:ENV:0.2", "--turn", "0.15:KNOB1:40",
             extra=["--fx", "plate"])
    assert (slots(fx)[3]["src"], slots(fx)[3]["unit"], slots(fx)[3]["dst"]) == (64 + 8 * 2, 1, 1)
    rack = sim(tools, "--button", "0.05:ENV", "--turn", "0.1:SELECT:-2", "--button", "0.15:ENV:0.2",
               "--turn", "0.2:KNOB1:25")
    assert (slots(rack)[3]["src"], slots(rack)[3]["unit"], slots(rack)[3]["dst"]) == (64 + 8 * 2, 8 + 1, 1)
    assert rack["mod"]["pos"] == 2 and rack["mode"] == MODES["RACK"]


def test_the_gesture_refuses_what_takes_no_cable(tools):
    """Macro's Model is NOLOCK: no cable, and the popup says so."""
    s = sim(tools, "--button", "0.1:LFO:0.2", "--turn", "0.15:KNOB1:20")
    assert set(slots(s)) == {1, 2} and s["popup"] == ["Model", "takes no cable"]


def test_a_routed_parameter_moves_round_its_base(tools):
    """Rule M1 on the panel: a knob turn on a routed parameter moves its base
    and the sound keeps swinging round it (the value sent is base plus the
    cable's offset), as fm1-render's --param-at does."""
    s = sim(tools, "--button", "0.1:LFO:0.1", "--turn", "0.12:KNOB3:50", "--turn", "0.3:KNOB3:20",
            seconds="0.6")
    base = s["values0"][2]
    assert base == pytest.approx(0.7)
    assert s["mod"]["sent0"][2] != pytest.approx(base)          # an LFO offset on top


# ---- several sound units (docs/15 §3.16) ------------------------------------------------------

SOUND2 = ["--sound", "1:shapes", "--insert", "1:ensemble"]
TO_SOUND2 = ["--button", "0.05:SEL:0.1", "--turn", "0.07:PRESETS:1"]   # SHIFT + PRESETS: Sound 2


def test_the_gesture_reaches_the_current_sound(tools):
    """With Sound 2 current (SHIFT + PRESETS), hold LFO and turn KNOB2 on
    HOME: the cable goes to Sound 2's Timbre (Shapes, uid 2), unit 17, and
    the popup names it S2."""
    s = sim(tools, *TO_SOUND2, "--button", "0.2:LFO:0.2", "--turn", "0.25:KNOB2:30", extra=SOUND2)
    assert s["current"] == 1
    x = slots(s)[3]
    assert (x["src"], x["unit"], x["dst"], x["amount"]) == (64, 17, 2, q14(30))
    assert s["popup"] == ["LFO1 > S2Tmbre", "+30%"]


def test_the_gesture_reaches_an_insert_and_the_master(tools):
    """FX mode on Sound 2: In1 (its Ensemble) takes ENV3's cable into Mix,
    unit 24 (20 + 4 x 1 + 0); M1 (Plate) takes one too, unit FX1."""
    s = sim(tools, *TO_SOUND2, "--button", "0.2:FX", "--turn", "0.25:SELECT:-64",
            "--button", "0.3:ENV:0.2", "--turn", "0.35:KNOB1:40", "--turn", "0.6:SELECT:64",
            "--turn", "0.65:SELECT:-1", "--button", "0.7:ENV:0.2", "--turn", "0.75:KNOB1:-20",
            extra=SOUND2 + ["--fx", "plate"], seconds="1.0")
    sl = slots(s)
    assert (sl[3]["src"], sl[3]["unit"], sl[3]["dst"]) == (64 + 8 * 2, 24, 1)
    assert (sl[4]["src"], sl[4]["unit"], sl[4]["dst"]) == (64 + 8 * 2, 1, 1)
    assert sl[3]["row"] == "ENV3  >S2I1Mix  +40" and sl[4]["row"] == "ENV3  >M1Mix    -20"


def test_a_new_cables_target_starts_at_the_current_sound(tools):
    """MATRIX: KNOB2 on an empty slot opens the target picker at the
    current sound's first parameter (Sound 2's Timbre here, Macro's
    Harmonics with Sound 1), and it commits a second later."""
    for to2, unit, dst in ((True, 17, 2), (False, 0, 2)):
        s = sim(tools, *(TO_SOUND2 if to2 else []), "--button", "0.2:EDIT", "--turn", "0.25:SELECT:2",
                "--turn", "0.3:KNOB2:1", extra=SOUND2, seconds="1.6")
        x = slots(s)[3]
        assert (x["unit"], x["dst"], x["src"]) == (unit, dst, 64), to2


def test_cables_on_several_sounds_replay_through_fm1_render(tools, tmp_path):
    """Two-step parity across sound units: cables into Sound 2, its insert
    and the master from the panel, notes on both sounds; the harness's
    .mod log and sidecar (--slots, --sound, --insert) replay through
    fm1-render to the same bytes, every cable counted there."""
    log, a, b = tmp_path / "c.verbs", tmp_path / "panel.wav", tmp_path / "replay.wav"
    s = run(tools["sim"], [*CHAIN, *SOUND2, "--cmd", str(INPUT), *TO_SOUND2,
                           "--button", "0.2:LFO:0.2", "--turn", "0.25:KNOB3:45",
                           "--button", "0.5:FX", "--turn", "0.55:SELECT:-64", "--button", "0.6:ENV:0.2",
                           "--turn", "0.65:KNOB2:-60", "--key", "0.8:12:100:0.6",
                           "--note", "1.0:55:90:0.5", "--log-cmds", str(log), "--out", str(a),
                           "--seconds", "2.0"])
    assert s["replayable"] == 1 and {x["unit"] for x in slots(s).values()} >= {17, 24}
    sidecar = (tmp_path / "c.args").read_text().splitlines()
    assert "--slots" in sidecar and sidecar[-2:] == ["--mod", str(tmp_path / "c.mod")]
    r = run(tools["render"], ["--cmd", str(log), "--frames", "64", *sidecar, "--out", str(b)])
    assert a.read_bytes() == b.read_bytes(), "two-step parity: the replay differs"
    assert r["mod_refused"] == 0 and r["mod_active"] == 4 and r["mod_sound_writes"] > 100


# ---- MATRIX and CHAIN -------------------------------------------------------------------------

def test_matrix_edits_every_field(tools):
    """Slot 3 from scratch: KNOB1 a source, KNOB2's picker a destination
    (it commits a second after its last turn), KNOB3 an amount, KNOB4 an
    offset; page B: VIA, curve, polarity, off and on."""
    s = sim(tools, "--button", "0.05:EDIT", "--turn", "0.1:SELECT:2", "--turn", "0.15:KNOB1:3",
            "--turn", "0.2:KNOB2:2", seconds="1.1")
    assert 3 in slots(s) and slots(s)[3]["dst"] == 0 and s["mod"]["picker"] == 2   # still choosing
    s = sim(tools, "--button", "0.05:EDIT", "--turn", "0.1:SELECT:2", "--turn", "0.15:KNOB1:3",
            "--turn", "0.2:KNOB2:2", "--turn", "1.4:KNOB3:45", "--turn", "1.45:KNOB4:-10",
            "--turn", "1.5:ALGORITHM:1", "--turn", "1.55:KNOB2:2", "--turn", "1.6:KNOB3:1",
            "--turn", "1.65:KNOB1:1", "--turn", "1.7:KNOB4:-1", seconds="1.8")
    x = slots(s)[3]
    assert (x["src"], x["unit"], x["dst"], x["via"]) == (2, 0, 3, 0)    # RAND > Timbre, VIA VEL
    assert (x["amount"], x["offset"]) == (q14(45), q14(-10))
    assert x["flags"] == (2 << 4) | (1 << 1)                           # cube, uni, off
    assert x["row"] == "RAND  -S1Tmbre  +45" and s["mod"]["mpage"] == 1


def test_matrix_clears_a_slot_with_knob1(tools):
    s = sim(tools, "--button", "0.05:EDIT", "--turn", "0.1:KNOB1:-64")
    assert set(slots(s)) == {2}


def test_chain_select_steps_between_cables(tools):
    s = sim(tools, "--button", "0.05:EDIT", "--button", "0.1:SEL", "--turn", "0.15:SELECT:1")
    assert s["mode"] == MODES["CHAIN"] and s["mod"]["slot"] == 2
    s = sim(tools, "--button", "0.05:EDIT", "--button", "0.1:SEL", "--turn", "0.15:SELECT:5")
    assert s["mod"]["slot"] == 2                                       # no cable past slot 2


def test_a_kind_change_switches_cables_off_and_back(tools):
    """docs/16 §2.4: changing a module's kind switches off the cables that
    touch it, never deletes them, and changing it back switches them on."""
    gone = sim(tools, "--button", "0.05:ENV", "--button", "0.1:ENV", "--turn", "0.15:ALGORITHM:1",
               seconds="1.3")
    assert gone["mod"]["rack"][3] == "chance" and slots(gone)[2]["flags"] == GATE_DST
    back = sim(tools, "--button", "0.05:ENV", "--button", "0.1:ENV", "--turn", "0.15:ALGORITHM:1",
               "--turn", "1.3:ALGORITHM:-1", "--button", "1.4:HOME", seconds="1.5")
    assert back["mod"]["rack"][3] == "env" and slots(back)[2]["flags"] == ON | GATE_DST


def test_a_kind_change_back_keeps_both_kinds_cables(tools):
    """Review fix: ENV3 becomes Chance (RTRG > its GATE goes off), the Chance
    gets a cable of its own (LFO1 into its Rate), and the change back to
    Envelope brings RTRG > GATE back and switches the Chance's cable off;
    changing to Chance again brings that one back. Before the fix the
    Chance's cable made the Envelope's forgotten."""
    to_chance = ["--button", "0.05:ENV", "--turn", "0.10:ALGORITHM:1", "--button", "1.3:LFO:0.2",
                 "--turn", "1.35:KNOB2:30"]
    back = sim(tools, *to_chance, "--turn", "1.6:ALGORITHM:-1", "--button", "1.65:HOME", seconds="2")
    assert back["mod"]["rack"][2] == "env"
    assert slots(back)[1]["flags"] == ON | GATE_DST and slots(back)[3]["flags"] & ON == 0
    again = sim(tools, *to_chance, "--turn", "1.6:ALGORITHM:-1", "--button", "1.65:HOME",
                "--button", "1.7:ENV", "--turn", "1.75:ALGORITHM:1", "--button", "1.8:HOME", seconds="2")
    assert again["mod"]["rack"][2] == "chance"
    assert slots(again)[1]["flags"] == GATE_DST and slots(again)[3]["flags"] == ON
    assert (slots(again)[3]["src"], slots(again)[3]["unit"]) == (64, 8 + 2)


def test_a_hold_with_any_turn_is_no_tap(tools):
    """Review fix: ENV held while a knob turns in SEQ mode (where the knobs
    turn the sound and no cable is made) is not a tap: letting go leaves
    SEQ mode as it was."""
    s = sim(tools, "--button", "0.05:SEQ", "--button", "0.1:ENV:0.2", "--turn", "0.15:KNOB3:5")
    assert s["mode"] == MODES["SEQ"] and set(slots(s)) == {1, 2}
    assert s["values0"][2] == pytest.approx(0.55)


def test_a_new_matrix_cable_starts_from_the_selected_lfo(tools):
    """Review fix: an amount turned on an empty slot before KNOB1 or KNOB2
    makes a cable from the selected LFO (LFO2, the last one shown), as the
    destination picker's own commit does, not from VEL."""
    s = sim(tools, "--button", "0.05:LFO", "--button", "0.1:LFO", "--button", "0.15:EDIT",
            "--turn", "0.2:SELECT:4", "--turn", "0.25:KNOB3:20", "--turn", "0.3:KNOB2:3", seconds="1.5")
    x = slots(s)[5]
    assert (x["src"], x["unit"], x["dst"], x["amount"], x["flags"]) == (64 + 8, 0, 4, q14(20), ON)


def test_chain_does_not_run_on_through_a_refused_cable(tools, tmp_path):
    """Review fix: LFO2 has two cables out, into Macro's Model (NOLOCK:
    refused, `!` in MATRIX) and into Timbre. CHAIN through LFO1 > LFO2 Rate
    follows the one that carries something."""
    script = tmp_path / "m.mod"
    script.write_text("rack default\nslot 1 lfo1 > lfo2.rate amt=20\nslot 2 lfo2 > snd:Model amt=50\n"
                      "slot 3 lfo2 > snd:Timbre amt=30\n")
    s = sim(tools, "--mod", str(script), "--button", "0.05:EDIT", "--button", "0.1:SEL")
    assert s["mode"] == MODES["CHAIN"] and s["mod"]["refused"] == 1 << 1
    assert s["mod"]["chain"] == ["LFO1 Out", " +20 >LFO2 Rate", "LFO2 Out", " +30 >S1 Timbre"]
    assert s["mod"]["chain_hl"] == 1


# ---- envelopes follow every note --------------------------------------------------------------

def rms(samples):
    return (sum(x * x for x in samples) / max(1, len(samples))) ** 0.5


@pytest.mark.parametrize("cable", ["rtrg", "key"])
@pytest.mark.parametrize("source", ["sequencer", "note", "key"])
def test_envelopes_follow_every_note(tools, tmp_path, source, cable):
    """The default cable RTRG > ENV3 GATE, or KEY in its place,
    opens ENV3 for a note from the sequencer, from MIDI in (--note) and
    from the keys. With ENV3 into HOST AMP, Test Sine gets louder while the
    note holds."""
    script = tmp_path / "m.mod"
    script.write_text(f"rack default\nslot 1 {cable} > env3:gate amt=100\nslot 3 env3 > host:amp amt=50\n")
    if source == "sequencer":
        cmd = tmp_path / "p.verbs"
        cmd.write_text("#! rate=44118 block=64 tracks=8 end=44118\n@0 tog 0 0 69 100;slen 0 0 0 -1 300;play\n")
        play = ["--cmd", str(cmd)]
    elif source == "note":
        play = ["--note", "0:69:100:0.8", "--seconds", "1"]
    else:
        play = ["--key", "0:16:100:0.8", "--seconds", "1"]   # key 16 is D5 at octave 0
    out = {}
    for name, mod in (("with", ["--mod", str(script)]), ("without", [])):
        wav = tmp_path / f"{name}.wav"
        run(tools["sim"], ["--engine", "test-sine", *play, *mod, "--out", str(wav)])
        out[name] = left_channel(wav.read_bytes())
    held = slice(int(0.4 * 44118), int(0.6 * 44118))
    assert rms(out["with"][held]) > 1.5 * rms(out["without"][held])


@pytest.mark.parametrize("source", ["note", "key"])
def test_a_note_over_a_held_one_restarts_the_envelope(tools, tmp_path, source):
    """The owner's rule of 2026-10-05 through the app (play_on feeding the
    runtime): a second note played while the first still holds restarts
    ENV3's attack with RTRG, the default cable, where KEY, the legato
    gate, lets it decay on. Until the second note both sound the same."""
    rate = 44118
    if source == "note":
        play = ["--note", "0:69:100:1.4", "--note", "0.7:72:100:0.7"]
    else:
        play = ["--key", "0:16:100:1.4", "--key", "0.7:19:100:0.7"]
    out = {}
    for cable in ("rtrg", "key"):
        script = tmp_path / f"{cable}.mod"
        script.write_text(f"rack default\nset 3 attack=0.55 decay=0.55 sustain=0\n"
                          f"slot 1 {cable} > env3:gate amt=100\nslot 3 env3 > host:amp amt=50\n")
        wav = tmp_path / f"{cable}.wav"
        run(tools["sim"], ["--engine", "test-sine", *play, "--seconds", "1.5", "--mod", str(script),
                           "--out", str(wav)])
        out[cable] = left_channel(wav.read_bytes())
    first = slice(int(0.1 * rate), int(0.65 * rate))
    second = slice(int(0.85 * rate), int(1.05 * rate))
    assert out["rtrg"][first] == out["key"][first]
    assert rms(out["rtrg"][second]) > 1.4 * rms(out["key"][second])


def test_the_default_cable_is_repatchable(tools, tmp_path):
    """Re-patched to SEQ2, ENV1 follows track 2 alone: track 1's notes, on
    the sound, no longer open it (its GATE is cabled, so the normal to KEY
    is broken)."""
    cmd = tmp_path / "p.verbs"
    cmd.write_text("#! rate=44118 block=64 tracks=8 end=44118\n@0 tog 0 0 69 100;slen 0 0 0 -1 300;play\n")
    levels = {}
    for name, first in (("key", "key"), ("seq2", "seq2")):
        script = tmp_path / f"{name}.mod"
        script.write_text(f"rack default\nslot 1 {first} > env3:gate amt=100\nslot 3 env3 > host:amp amt=50\n")
        wav = tmp_path / f"{name}.wav"
        run(tools["sim"], ["--engine", "test-sine", "--cmd", str(cmd), "--mod", str(script), "--out", str(wav)])
        levels[name] = rms(left_channel(wav.read_bytes())[int(0.4 * 44118):int(0.6 * 44118)])
    assert levels["key"] > 1.5 * levels["seq2"]


def test_the_filters_cutoff_shows_in_hz(tools, tmp_path):
    """MG2's Filter on its RACK page: Cutoff shows the frequency it sets,
    0.05 Hz x 2^(13 x Cutoff) at the tick rate (fm1_mod_filter_hz, the
    kind's own formula), while the knob and its base stay 0..1 on the log
    scale; the other parameters show their numbers."""
    for cutoff, want in ((0, "0.05 Hz"), (0.3, "0.75 Hz"), (0.5, "4.53 Hz"), (0.7, "27.4 Hz"),
                         (1, "410 Hz")):
        p = tmp_path / "f.mod"
        p.write_text(f"mod 1 filter cutoff={cutoff} res=0.25\n")
        s = run(tools["sim"], ["--engine", "macro", "--seconds", "0.1", "--mod", str(p)])
        assert s["mod"]["values"][:2] == [want, "0.25"], cutoff
        assert s["mod"]["bases"][0][0] == pytest.approx(cutoff)


# ---- golden gesture traces and their replay -----------------------------------------------------

def test_there_are_the_mg3_traces():
    assert {p.stem for p in PANELS} >= {"hold-lfo-home", "hold-env-fx", "rack-gesture", "matrix-edit",
                                        "kind-change"}


@pytest.mark.parametrize("panel", PANELS, ids=lambda p: p.stem)
def test_a_trace_logs_its_golden_mod_and_replays_byte_for_byte(tools, tmp_path, panel):
    """Two-step parity with modulation: the harness logs the runtime's state
    and every edit (.mod) next to the sequencer's lines (.verbs), and
    fm1-render replays both with the sidecar's arguments, --mod included,
    to the same bytes."""
    log, a, b = tmp_path / "c.verbs", tmp_path / "panel.wav", tmp_path / "replay.wav"
    s = run(tools["sim"], [*CHAIN, "--cmd", str(INPUT), "--panel", str(panel),
                           "--log-cmds", str(log), "--out", str(a)])
    assert (tmp_path / "c.mod").read_text() == panel.with_suffix(".mod").read_text(), "not the golden log"
    sidecar = (tmp_path / "c.args").read_text().splitlines()
    assert sidecar[-2:] == ["--mod", str(tmp_path / "c.mod")]
    r = run(tools["render"], ["--cmd", str(log), "--frames", "64", *sidecar, "--out", str(b)])
    assert s["replayable"] == 1 and s["mod"]["unloggable"] == 0
    assert a.read_bytes() == b.read_bytes(), "two-step parity: the replay differs"
    assert r["mod_refused"] == 0 and s["peak"] > 0.01


def test_a_routed_trace_writes_to_the_sound(tools, tmp_path):
    """hold-lfo-home's cables move the sound: the replay counts writes."""
    log = tmp_path / "c.verbs"
    run(tools["sim"], [*CHAIN, "--cmd", str(INPUT), "--panel", str(TRACES / "hold-lfo-home.panel"),
                       "--log-cmds", str(log)])
    r = run(tools["render"], ["--cmd", str(log), "--frames", "64",
                              *(tmp_path / "c.args").read_text().splitlines()])
    assert r["mod_sound_writes"] > 1000 and r["mod_active"] == 4


def test_script_lines_round_trip(tools):
    """Every edit the pages make is a line mod_script.c reads back to the
    same runtime state: random racks, bases and slots written whole, and
    random edits (slots, kinds with their switch-off and restore, bases,
    moves) applied line by line to a second runtime."""
    res = subprocess.run([str(tools["sim"]), "--mod-format-check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["failures"] == out["refused_lines"] == 0 and out["rounds"] >= 300
    assert out["lines"] > 10000


def test_a_mod_script_replaces_the_default_runtime_and_the_pages_show_it(tools):
    """--mod (a parity scenario's modulation) builds a new runtime in place
    of the default one, and the pages show it: ENV opens RACK at ENV3."""
    s = run(tools["sim"], ["--engine", "macro", "--fx", "plate", "--fx", "echo", "--seconds", "0.2", "--mod",
                           str(ROOT / "sim" / "web" / "test" / "mod" / "routes.mod"), "--button", "0.1:ENV"])
    assert s["mod"]["rack"][:5] == ["lfo", "lfo", "env", "env", "chance"]
    assert s["mode"] == 4 and s["popup"] == []
