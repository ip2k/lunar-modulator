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
"""
import json
import subprocess

import pytest

from tests.test_sim_web import RATE, run, tools  # noqa: F401

ARP = 10                                   # FM1_BTN_ARP: the LED string's key count + 10
KEYS = 27


def sim(tools, *args, seconds=1.0):
    return run(tools["sim"], ["--seconds", str(seconds), *args])


def arp_led(s):
    return s["leds"][KEYS + ARP] == "1"


def param(s, name, sound=0):
    return s["arp"]["values"][sound][PARAMS.index(name)]


PARAMS = ["Mode", "Rate", "Gate", "Octaves", "Pattern", "Fill", "Rotate", "Length", "Chance", "Ratchet",
          "Vel Spread", "Loop", "Oct Mode", "Velocity", "Swing", "Join", "Order", "Repeat", "Chord %",
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
        assert listed["title"] == "Arp preset" and listed["total"] == 6
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
    that says by how much, and the arp stays off."""
    chain = ["--engine", "macro", "--sound", "1:shapes", "--fx", "plate", "--fx", "diffuse"]
    before = sim(tools, *chain, seconds=0.1)
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    need = z["mfx_stage_bytes"] + z["arp_bytes"]
    assert before["ram"] + need > z["ram_budget"] >= before["ram"], "the chain is not at the edge"
    s = sim(tools, *chain, "--button", "0.1:ARP", seconds=0.3)
    assert s["arp"]["on"][0] == 0 and s["mode"] == 0
    over = before["ram"] + need - z["ram_budget"]
    assert s["popup"] == ["Arp", "does not fit", f"{-(-over // 1024)}K over budget"]
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
