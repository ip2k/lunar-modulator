"""The arpeggiator in the virtual FM-1 (sim/web/README.md, "The arpeggiator";
engine API v3's MIDI effects, engines/include/fm1_mfx_host.h): ARP's tap,
hold and SHIFT gestures, its pages and presets, its LED, the RAM it takes,
the recording rule (the sequencer records what was played, owner
2026-10-05) and no note left sounding after a sound change, a sequencer
reset or a bypass.

The parity scenarios arp-* (sim/web/test/scenarios.json) check the app
against fm1-render --mfx natively (tests/test_sim_web.py, with the arp's
own log) and in WebAssembly (parity.mjs); arp-panel is a gesture trace that
replays through fm1-render from the harness's log and sidecar.

The owner's follow-ups of 2026-10-06: the global page's Key page sets the
project key (a typed `key` command, kept with the set and replayed); Stop
takes back what the sequencer gave a latched arp while the keys latched by
hand play on; and while the sequencer plays the arp's steps fall on its
grid (arp-panel-stop, arp-latch-stop).
"""
import json
import random
import subprocess

import pytest

from tests.engine_helpers import GPL_MODS, gpl_only
from tests.test_sim_web import RATE, SIM as ROOT_SIM, run, tools  # noqa: F401

# ALGORITHM's list on the ARP pages: the stock FM-1's six modes, then each
# other MIDI effect of the build (Acid Gen while the GPL switch is on).
PRESETS = 6 + (1 if GPL_MODS else 0)

ARP = 10                                   # FM1_BTN_ARP: the LED string's key count + 10
KEYS = 27


def sim(tools, *args, seconds=1.0):
    return run(tools["sim"], ["--seconds", str(seconds), *args])


def arp_led(s):
    return s["leds"][KEYS + ARP] == "1"


def param(s, name, sound=0):
    return s["arp"]["values"][sound][PARAMS.index(name)]


PARAMS = ["Mode", "Rate", "Gate", "Octaves", "Pattern", "Fill", "Rotate", "Length", "Chance", "Ratchet",
          "Vel Spread", "Loop", "Oct Mode", "Velocity", "Join", "Order", "Repeat", "Chord %",
          "Oct Jump", "Latch", "Sync", "Ratchet %", "Gate Sprd", "Seed"]


def test_the_catalogue_lists_the_arp_as_a_midi_effect(tools):
    catalog = json.loads(subprocess.run([str(tools["sim"]), "--list"], check=True,
                                        capture_output=True, text=True).stdout)
    arp = [e for e in catalog if e["id"] == "arp"]
    assert len(arp) == 1 and arp[0]["kind"] == "midi_fx"
    assert [p["name"] for p in arp[0]["params"]] == PARAMS


def test_arp_starts_bypassed_and_takes_no_ram(tools):
    plain = sim(tools, "--engine", "macro", seconds=0.1)
    assert plain["arp"]["on"] == [0, 0, 0, 0] and not arp_led(plain)
    on = sim(tools, "--engine", "macro", "--mfx", "0:arp", seconds=0.1)
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert on["ram"] == plain["ram"] + z["mfx_stage_bytes"] + z["arp_bytes"]
    two = sim(tools, "--engine", "macro", "--mfx", "0:arp", "--mfx", "2:arp", seconds=0.1)
    assert two["ram"] == plain["ram"] + z["mfx_stage_bytes"] + 2 * z["arp_bytes"]


def test_a_tap_switches_the_arp_and_its_pages(tools):
    """A tap of ARP: the arp on, the ARP pages open (mode 7), its LED lit;
    another tap there: off, the pages close back to the mode they came
    from, the LED dark. The stub popup is gone."""
    on = sim(tools, "--engine", "macro", "--button", "0.1:ARP", seconds=0.3)
    assert on["arp"]["on"][0] == 1 and on["mode"] == 7 and arp_led(on)
    assert on["popup"] == ["Arp on"]
    off = sim(tools, "--engine", "macro", "--button", "0.05:FX", "--button", "0.1:ARP",
              "--button", "0.3:ARP", seconds=0.5)
    assert off["arp"]["on"][0] == 0 and off["mode"] == 1 and not arp_led(off)
    assert off["popup"] == ["Arp off"]


def test_a_hold_latches(tools):
    """ARP held FM1_APP_ARP_HOLD_S (0.5 s): Latch on, and the arp with it;
    the release is no tap. Held again: Latch off, the arp stays on."""
    s = sim(tools, "--engine", "macro", "--button", "0.1:ARP:0.7", seconds=1.0)
    assert s["arp"]["on"][0] == 1 and param(s, "Latch") == 1 and s["popup"] == ["Latch on", "Arp on"]
    assert s["mode"] == 0, "a hold latches without opening the pages"
    again = sim(tools, "--engine", "macro", "--button", "0.1:ARP:0.7", "--button", "1.0:ARP:0.7",
                seconds=1.9)
    assert again["arp"]["on"][0] == 1 and param(again, "Latch") == 0
    short = sim(tools, "--engine", "macro", "--button", "0.1:ARP:0.3", seconds=0.6)
    assert param(short, "Latch") == 0 and short["arp"]["on"][0] == 1, "a short press is a tap"
    # Latched, tapped off (Latch stays set), then held: on and latched again,
    # not Latch switched off with the arp still off.
    back = sim(tools, "--engine", "macro", "--button", "0.1:ARP:0.7", "--button", "1.0:ARP",
               "--button", "1.3:ARP:0.7", seconds=2.2)
    assert back["arp"]["on"][0] == 1 and param(back, "Latch") == 1
    assert back["popup"] == ["Latch on", "Arp on"]


def test_another_input_during_the_press_is_no_tap(tools):
    s = sim(tools, "--engine", "macro", "--button", "0.1:ARP:0.3", "--turn", "0.2:KNOB1:1", seconds=0.6)
    assert s["arp"]["on"][0] == 0


def test_shift_arp_opens_the_pages_without_switching(tools):
    s = sim(tools, "--engine", "macro", "--button", "0.1:SEL:0.3", "--button", "0.2:ARP", seconds=0.6)
    assert s["mode"] == 7 and s["arp"]["on"][0] == 0 and not arp_led(s)


def test_the_led_blinks_while_it_latches(tools):
    """Lit while on; while latched, lit half of each second."""
    leds = [arp_led(sim(tools, "--engine", "macro", "--button", "0.1:ARP:0.7", seconds=t))
            for t in (2.25, 2.75)]
    assert sorted(leds) == [False, True]


def test_the_pages_knobs_and_presets(tools):
    """In ARP mode SELECT turns the pages (7), KNOB1-4 the page's parameters
    in their order, ALGORITHM the stock presets (Mode and Order)."""
    s = sim(tools, "--engine", "macro", "--button", "0.05:ARP", "--turn", "0.1:KNOB2:-2",
            "--turn", "0.15:KNOB4:2", "--turn", "0.2:SELECT:2", "--turn", "0.25:KNOB2:2",
            "--turn", "0.3:SELECT:9", seconds=0.5)
    assert param(s, "Rate") == 2 and param(s, "Octaves") == 2 and param(s, "Ratchet") == 2
    assert s["arp"]["page"] == 6
    presets = []
    for k in range(1, 6):
        p = sim(tools, "--engine", "macro", "--button", "0.05:ARP", "--turn", f"0.1:ALGORITHM:{k}",
                seconds=0.3)
        listed = p["popup_list"]
        assert listed["title"] == "Arp preset" and listed["total"] == PRESETS
        presets.append((p["popup"][listed["mark"]], param(p, "Mode"), param(p, "Order"),
                        p["arp"]["preset"]))
    assert presets == [("Down", 1, 0, 1), ("Up/Down", 2, 0, 2), ("Down/Up", 3, 0, 3),
                       ("Random", 19, 0, 4), ("Played", 0, 1, 5)]
    held = sim(tools, "--engine", "macro", "--button", "0.05:ARP", "--button", "0.1:OCT+:0.3",
               "--turn", "0.2:ALGORITHM:3", seconds=0.5)
    assert held["transpose"] == 3 and held["arp"]["preset"] == 0, "OCT + ALGORITHM still transposes"


def test_the_arp_on_another_sound(tools):
    """SHIFT + PRESETS makes Sound 2 current: ARP switches its arp, not
    Sound 1's."""
    s = sim(tools, "--engine", "macro", "--sound", "1:shapes", "--button", "0.05:SEL:0.1",
            "--turn", "0.1:PRESETS:1", "--button", "0.3:ARP", seconds=0.5)
    assert s["current"] == 1 and s["arp"]["on"] == [0, 1, 0, 0]


def test_the_ram_meter_refuses_an_arp_that_would_not_fit(tools):
    """A chain at the budget's edge: the arp's tap is refused with a popup
    that says what the chain would need (a percentage past 100, never
    bytes), and the arp stays off. (The second master
    effect is Limiter since glide: with Diffuse, Macro and Shapes no longer
    fit together once both carried glide's state.)"""
    chain = ["--engine", "macro", "--sound", "1:shapes", "--fx", "plate", "--fx", "limit"]
    before = sim(tools, *chain, seconds=0.1)
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    need = z["mfx_stage_bytes"] + z["arp_bytes"]
    assert before["ram"] + need > z["ram_budget"] >= before["ram"], "the chain is not at the edge"
    s = sim(tools, *chain, "--button", "0.1:ARP", seconds=0.3)
    assert s["arp"]["on"][0] == 0 and s["mode"] == 0
    pct = -(-(before["ram"] + need) * 100 // z["ram_budget"])
    assert pct > 100 and s["popup"] == ["Arp", "does not fit", f"needs {pct}% of RAM"]
    held = sim(tools, *chain, "--button", "0.1:ARP:0.7", seconds=1.0)
    assert held["arp"]["on"][0] == 0 and held["popup"][:2] == ["Arp", "does not fit"]


def record_script(tmp_path, end):
    path = tmp_path / "rec.verbs"
    # 240 BPM, a bar a second; stopped: REC counts in a bar, then records
    path.write_text(f"#! rate={RATE} block=64 tracks=8 end={end}\n@0 bpm 24000\n")
    return path


def test_the_sequencer_records_what_was_played(tools, tmp_path):
    """Owner, 2026-10-05: the sequencer records the keys before the arp. Two
    keys recorded with the arp on (two octaves) come back on playback as the
    keys' own pitches, which the arp plays again, an octave up included;
    with the arp switched off after the take, they play plainly. Both runs
    replay through fm1-render from the harness's log byte for byte."""
    end = int(RATE * 4.2)
    script = record_script(tmp_path, end)
    take = ["--engine", "test-sine", "--cmd", str(script), "--mfx", "0:arp", "--mfx-param", "0:Octaves=1",
            "--mfx-param", "0:Rate=2", "--button", "0.10:REC", "--key", "1.30:7:100:0.15",
            "--key", "1.55:11:90:0.15", "--button", "2.05:REC"]
    for name, extra in (("arp", []), ("plain", ["--mfx-on-at", "0:2.2:0"])):
        events, arp_log, verbs = (tmp_path / f"{name}.jsonl", tmp_path / f"{name}-arp.jsonl",
                                  tmp_path / f"{name}.verbs")
        s = run(tools["sim"], ["--seconds", "4.2", *take, *extra, "--log-events", str(events),
                               "--log-mfx", str(arp_log), "--log-cmds", str(verbs),
                               "--out", str(tmp_path / f"{name}.wav")])
        seq = [json.loads(line) for line in events.read_text().splitlines()]
        played = {e["a"] for e in seq if e["kind"] == "on" and e["frame"] >= RATE * 2.2}
        assert played == {60, 64}, "the clip holds the keys as played"
        arp = [json.loads(line) for line in arp_log.read_text().splitlines()]
        later = {e["key"] for e in arp if e["k"] == "on" and e["t"] >= RATE * 2.2}
        if name == "arp":
            assert {60, 64, 72, 76} <= later, "playback goes through the arp again"
        else:
            assert later == set() and s["seq_notes_to_engine"] >= 2, "and plainly without it"
        assert s["replayable"] == 1
        args = (tmp_path / f"{name}.args").read_text().splitlines()
        ref = run(tools["render"], ["--seconds", "4.2", "--cmd", str(verbs), *args,
                                    "--out", str(tmp_path / f"{name}-ref.wav")])
        assert (tmp_path / f"{name}-ref.wav").read_bytes() == (tmp_path / f"{name}.wav").read_bytes()
        assert ref["notes_hung"] == 0


def silent_tail(tools, tmp_path, *args, seconds=2.0):
    wav = tmp_path / "t.wav"
    run(tools["sim"], ["--seconds", str(seconds), *args, "--out", str(wav)])
    data = wav.read_bytes()[44:]
    tail = data[-4 * int(RATE * 0.25):]
    return max(abs(int.from_bytes(tail[i:i + 2], "little", signed=True)) for i in range(0, len(tail), 2))


@pytest.mark.parametrize("how", ["bypass", "new-sound", "seq-reset", "latch-off"])
def test_no_note_is_left_sounding(tools, tmp_path, how):
    """A latched arp playing a chord (the arp's gate held long) and a key
    still down: a bypass, a new sound on PRESETS, a sequencer reset, or
    Latch off after the keys are up, and nothing sounds a moment later."""
    script = tmp_path / "s.verbs"
    script.write_text(f"#! rate={RATE} block=64 tracks=8 end={RATE * 2}\n@0 bpm 12000\n")
    base = ["--engine", "test-sine", "--cmd", str(script), "--mfx", "0:arp",
            "--mfx-param", "0:Latch=1", "--mfx-param", "0:Gate=200", "--key", "0.10:7:100:0.2",
            "--key", "0.10:11:100:0.2"]
    ending = {"bypass": ["--mfx-on-at", "0:1.2:0"],
              "new-sound": ["--turn", "1.2:PRESETS:1"],
              "seq-reset": ["--seq-reset", "1.2:8"],
              "latch-off": ["--mfx-param-at", "0:1.2:Latch=0"]}[how]
    playing = silent_tail(tools, tmp_path, *base, seconds=1.2)
    assert playing > 1000, "the latched arp is not playing"
    assert silent_tail(tools, tmp_path, *base, *ending) == 0


def gesture_session(seed, secs=6.0):
    """A seeded panel session on two sounds: keys, ARP taps and holds, SHIFT
    + ARP, the ARP pages' knobs and presets, PLAY/STOP, REC, HOME, and the
    arps switched and turned through the harness's own flags; every key up
    and both arps bypassed a second before the end, the sequencer stopped."""
    rnd = random.Random(seed)
    args = ["--engine", "test-sine", "--sound", "1:test-sine", "--seconds", str(secs)]
    t = 0.05
    while t < secs - 1.2:
        r = rnd.random()
        if r < 0.35:
            dur = min(rnd.uniform(0.02, 1.5), secs - 1.1 - t)
            args += ["--key", f"{t:.3f}:{rnd.randrange(27)}:{rnd.randint(1, 127)}:{dur:.3f}"]
        elif r < 0.45:
            hold = f":{rnd.uniform(0.55, 0.9):.3f}" if rnd.random() < 0.4 else ""
            args += ["--button", f"{t:.3f}:ARP{hold}"]
        elif r < 0.5:
            args += ["--button", f"{t:.3f}:SEL:0.15", "--button", f"{t + 0.05:.3f}:ARP"]
        elif r < 0.62:
            enc = rnd.choice(["KNOB1", "KNOB2", "KNOB3", "KNOB4", "SELECT", "ALGORITHM"])
            args += ["--turn", f"{t:.3f}:{enc}:{rnd.choice([-3, -2, -1, 1, 2, 3])}"]
        elif r < 0.68:
            args += ["--button", f"{t:.3f}:PLAY/STOP"]
        elif r < 0.72:
            args += ["--button", f"{t:.3f}:REC"]
        elif r < 0.82:
            args += ["--mfx-on-at", f"{rnd.randint(0, 1)}:{t:.3f}:{rnd.randint(0, 1)}"]
        elif r < 0.94:
            name, lo, hi = rnd.choice([("Latch", 0, 1), ("Rate", 0, 16), ("Mode", 0, 21), ("Gate", 1, 200),
                                       ("Ratchet", 0, 3), ("Octaves", 0, 3), ("Join", 0, 1),
                                       ("Sync", 0, 1), ("Repeat", 0, 7), ("Chord %", 0, 100)])
            args += ["--mfx-param-at", f"{rnd.randint(0, 1)}:{t:.3f}:{name}={rnd.randint(lo, hi)}"]
        else:                               # HOME, or GLO, whose knobs set the project key
            args += ["--button", f"{t:.3f}:{rnd.choice(['HOME', 'GLO'])}"]
        t += rnd.uniform(0.03, 0.35)
    end = secs - 1.0
    args += ["--mfx-on-at", f"0:{end:.3f}:0", "--mfx-on-at", f"1:{end:.3f}:0"]
    verbs = (f"#! rate={RATE} block=64 tracks=8 end={int(RATE * secs)}\n"
             f"@0 bpm {rnd.choice([9000, 12000, 15500])};tog 0 0 {rnd.randint(40, 70)} 100 "
             f"{rnd.randint(40, 70)} 90;slen 0 0 0 -1 {rnd.randint(10, 400)};tog 0 6 {rnd.randint(40, 70)} 100\n"
             f"@{int(RATE * (end - 0.2)) // 64 * 64} stop\n")
    return args, verbs


@pytest.mark.parametrize("seed", range(8))
def test_random_gesture_sessions_replay_and_leave_nothing_hanging(tools, tmp_path, seed):
    """Seeded sessions of every ARP gesture with keys, the sequencer and REC:
    each replays through fm1-render from the harness's log and sidecar to
    the same samples and the same arp notes, and when the keys are up and
    the arps bypassed, no engine holds a note (nothing in the app's ledgers,
    nothing hung in fm1-render's)."""
    args, verbs = gesture_session(seed)
    (tmp_path / "in.verbs").write_text(verbs)
    s = run(tools["sim"], [*args, "--cmd", str(tmp_path / "in.verbs"), "--out", str(tmp_path / "app.wav"),
                           "--log-mfx", str(tmp_path / "app-arp.jsonl"),
                           "--log-cmds", str(tmp_path / "c.verbs")])
    assert s["replayable"] == 1
    assert s["sounding"] == 0 and s["seq_sounding"] == 0
    ref_args = ["--seconds", "6.0", "--rate", str(RATE), "--cmd", str(tmp_path / "c.verbs"),
                *(tmp_path / "c.args").read_text().splitlines()]
    arps = "--mfx" in ref_args          # the sidecar names an arp once one changed
    ref = run(tools["render"], [*ref_args, "--out", str(tmp_path / "ref.wav")]
              + (["--log-mfx", str(tmp_path / "ref-arp.jsonl")] if arps else []))
    assert (tmp_path / "app.wav").read_bytes() == (tmp_path / "ref.wav").read_bytes()
    app_arp = (tmp_path / "app-arp.jsonl").read_bytes()
    assert app_arp == ((tmp_path / "ref-arp.jsonl").read_bytes() if arps else b"")
    assert ref["notes_hung"] == 0 and ref.get("mfx_dropped", 0) == 0


# ---- Another MIDI effect in the slot ---------------------------------------------------------

@gpl_only
def test_algorithm_puts_acid_gen_in_the_slot_and_brings_the_arp_back(tools):
    """Past the stock presets, ALGORITHM on the ARP pages puts Acid Gen (a GPL
    MIDI effect) in the current sound's MIDI-FX slot, on: its pages are LINE,
    KEY, PLAY and SEED, its knobs its parameters, and a held key plays its
    line. Turned back, the arp returns at its defaults."""
    s = sim(tools, "--engine", "acid-bass", "--button", "0.05:ARP", "--turn", "0.1:ALGORITHM:6",
            "--key", "0.2:12:100:1.0", "--turn", "0.3:KNOB1:-10", "--turn", "0.4:SELECT:2",
            seconds=1.5)
    listed = s["popup_list"]
    assert s["arp"]["effect"][0] == "acid-gen" and s["arp"]["on"][0] == 1
    assert s["arp"]["preset"] == 6 and s["arp"]["page"] == 2
    assert s["arp"]["values"][0][0] == 60                    # Density 70 - 10
    assert s["arp"]["notes_out"] > 4 and s["peak"] > 0.05
    if listed:
        assert listed["total"] == PRESETS
    back = sim(tools, "--engine", "acid-bass", "--button", "0.05:ARP", "--turn", "0.1:ALGORITHM:6",
               "--turn", "0.2:ALGORITHM:-6", seconds=0.4)
    assert back["arp"]["effect"][0] == "arp" and back["arp"]["preset"] == 0
    assert back["arp"]["values"][0] == [p for p in sim(tools, "--engine", "acid-bass",
                                                         seconds=0.1)["arp"]["values"][0]]


@gpl_only
def test_the_harness_puts_acid_gen_in_the_slot(tools):
    """--mfx K:acid-gen, as fm1-render takes it: the effect in sound K's
    slot, on, with its parameters by name."""
    s = sim(tools, "--engine", "acid-bass", "--mfx", "0:acid-gen", "--mfx-param", "0:Density=100",
            "--mfx-param", "0:Rate=2", "--note", "0:45:100:1.0", seconds=1.2)
    assert s["arp"]["effect"][0] == "acid-gen" and s["arp"]["on"][0] == 1
    assert s["arp"]["values"][0][0] == 100 and s["arp"]["values"][0][8] == 2
    assert s["arp"]["notes_out"] > 10


# ---- The follow-ups (owner, 2026-10-06) ------------------------------------------------------

SET = f"#! rate={RATE} block=64 tracks=8 end={RATE}\n@0 bpm 12000\n"


def test_the_global_page_sets_the_project_key(tools, tmp_path):
    """GLO, then SELECT: the Key page (2/2). KNOB1 steps the root and KNOB2
    the scale in the panel's order (Major, Minor, Dorian, ... Chromatic),
    each detent a typed `key` command; turned on Globe, a knob shows the Key
    page. The summary's key is the set's, and fm1-render, replaying the
    harness's log, ends in the same key with the same samples."""
    (tmp_path / "in.verbs").write_text(SET)
    s = run(tools["sim"], ["--engine", "macro", "--cmd", str(tmp_path / "in.verbs"),
                           "--button", "0.05:GLO", "--turn", "0.10:SELECT:1",
                           "--turn", "0.15:KNOB1:3", "--turn", "0.20:KNOB2:2", "--turn", "0.25:KNOB2:-1",
                           "--turn", "0.30:SELECT:-1", "--turn", "0.35:KNOB1:-1",
                           "--out", str(tmp_path / "app.wav"), "--log-cmds", str(tmp_path / "c.verbs")])
    assert s["mode"] == 2 and s["glo_page"] == 1, "a knob on Globe turns to the Key page"
    assert s["seq_key"] == [2, 1], "D minor"
    # one command a turn: +2 places from Major is Dorian (3), then back to Minor (1)
    assert [c for _, c in s["seq_ui_cmds"]] == ["key 3 0", "key 3 3", "key 3 1", "key 2 1"]
    assert s["replayable"] == 1
    ref = run(tools["render"], ["--seconds", "1.0", "--rate", str(RATE), "--cmd", str(tmp_path / "c.verbs"),
                                *(tmp_path / "c.args").read_text().splitlines(),
                                "--out", str(tmp_path / "ref.wav")])
    assert ref["seq_key"] == [2, 1]
    assert (tmp_path / "app.wav").read_bytes() == (tmp_path / "ref.wav").read_bytes()
    # SELECT turns back to Globe; the bottom bar says which page
    g = sim(tools, "--engine", "macro", "--button", "0.05:GLO", "--turn", "0.1:SELECT:1",
            "--turn", "0.2:SELECT:-1", seconds=0.3)
    assert g["glo_page"] == 0 and g["key"] == [0, 0]


def test_an_import_brings_the_sets_key(tools, tmp_path):
    """The key is the set's: an import without a `key` line puts C major
    back, one with `key 9 1` gives A minor."""
    (tmp_path / "plain.movy1").write_text("movy1\nbpm 12000\nswing 50\nlink 0\n")
    (tmp_path / "keyed.movy1").write_text("movy1\nbpm 12000\nswing 50\nlink 0\nkey 9 1\n")
    (tmp_path / "in.verbs").write_text(SET)
    for name, want in (("plain", [0, 0]), ("keyed", [9, 1])):
        s = sim(tools, "--engine", "macro", "--cmd", str(tmp_path / "in.verbs"), "--seq-ui", "0.05:key 3 5",
                "--seq-import", f"0.2:{tmp_path / (name + '.movy1')}", seconds=0.3)
        assert s["seq_key"] == want, name
    s = sim(tools, "--engine", "macro", "--cmd", str(tmp_path / "in.verbs"), "--seq-ui", "0.05:key 3 5",
            seconds=0.2)
    assert s["seq_key"] == [3, 5]


def test_stop_takes_back_the_sequencers_notes_and_the_arp_finds_the_beat(tools, tmp_path):
    """The panel session arp-panel-stop (sim/web/test/arp/): a chord latched
    by hand plays alone before Play; track 1's notes join it while the
    sequencer plays; Stop takes them back and the hand's chord plays on;
    ARP's tap ends it all. In a second run ARP's tap mid-bar and a key: the
    key's first note waits for the grid's next 1/16; at Stop the hand's
    latched key plays on, the track's note does not. It replays through
    fm1-render byte for byte, the arp's notes included, and nothing hangs."""
    test = ROOT_SIM / "test" / "arp"
    common = ["--seconds", "6.6", "--rate", str(RATE)]
    s = run(tools["sim"], [*common, "--engine", "macro", "--param", "Model=4", "--fx", "plate",
                           "--fx-param", "Mix=0.2", "--cmd", str(test / "panel-arp-stop.verbs"),
                           "--panel", str(test / "panel-arp-stop.panel"),
                           "--log-mfx", str(tmp_path / "app-arp.jsonl"),
                           "--log-events", str(tmp_path / "ev.jsonl"),
                           "--log-cmds", str(tmp_path / "c.verbs"), "--out", str(tmp_path / "app.wav")])
    assert s["replayable"] == 1 and s["seq_key"] == [2, 1]
    ev = [json.loads(x) for x in (tmp_path / "app-arp.jsonl").read_text().splitlines()]

    def keys(a, b):
        return sorted({e["key"] for e in ev if e["k"] == "on" and a * RATE <= e["t"] < b * RATE})
    assert keys(1.1, 1.5) == [60, 64]
    assert keys(1.5, 3.6) == [43, 50, 60, 64]
    assert keys(3.62, 4.2) == [60, 64], "Stop: the hand's chord alone"
    assert keys(4.22, 4.93) == []
    assert 67 in keys(4.93, 5.9) and keys(5.92, 6.2) == [67]
    seq = [json.loads(x) for x in (tmp_path / "ev.jsonl").read_text().splitlines()]
    grid = sorted(e["frame"] for e in seq if e["kind"] == "clock" and e["tick"] % 24 == 0)
    first = min(e["t"] for e in ev if e["k"] == "on" and e["key"] == 67)
    pressed = next(f for f, c in s["seq_ui_cmds"] if c == "non 0 67 100")
    assert first == min(g for g in grid if g >= pressed) and first - pressed > 400, \
        "the key's first note is not on the grid's next step"
    ref = run(tools["render"], [*common, "--cmd", str(tmp_path / "c.verbs"),
                                *(tmp_path / "c.args").read_text().splitlines(),
                                "--log-mfx", str(tmp_path / "ref-arp.jsonl"), "--out", str(tmp_path / "ref.wav")])
    assert (tmp_path / "app.wav").read_bytes() == (tmp_path / "ref.wav").read_bytes()
    assert (tmp_path / "app-arp.jsonl").read_bytes() == (tmp_path / "ref-arp.jsonl").read_bytes()
    assert ref["notes_hung"] == 0 and ref["mfx_dropped"] == 0 and ref["seq_key"] == [2, 1]
