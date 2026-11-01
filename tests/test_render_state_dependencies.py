"""Saving a sound or FX preset retains its upstream modulation patch (MIT)."""
import copy
import json
import subprocess

import pytest

from tests.engine_helpers import renderer  # noqa: F401


def cable(slot, source, dest):
    return dict(slot=slot, on=True, **{"from": source}, via=None, to=dest,
                amount=50, offset=0, polarity="auto", curve="lin", voice=False,
                lock=0)


def output(pos, port="Out"):
    return {"module": pos, "port": port}


def patch(case, unit):
    """Explicit expected sets, including gaps and reverse cable dependency order."""
    sink = {"unit": unit, "param": "Gain" if unit == "fx1" else "Volume"}
    rack = [{"pos": 1, "kind": "lfo", "params": {"Rate": 0.63}}]
    routes = []
    if case == "chain":
        rack += [{"pos": 2, "kind": "calc"}]
        routes = [cable(1, output(2), sink),
                  cable(9, output(1), {"module": 2, "param": "A"})]
        positions, slots = [1, 2], [1, 9]
    elif case == "via-gate-data":
        rack += [{"pos": p, "kind": k} for p, k in
                 [(2, "calc"), (3, "env"), (4, "calc"), (5, "register"), (6, "calc")]]
        routes = [cable(1, output(6), sink),
                  cable(3, output(4), {"module": 6, "param": "A"}),
                  cable(5, output(2), {"module": 4, "param": "A"}),
                  cable(9, output(1), {"module": 2, "param": "A"}),
                  cable(11, output(1, "Wrap"), {"module": 3, "gate": "Gate"}),
                  cable(13, {"source": "S2KEY"}, {"module": 5, "gate": "Clock"}),
                  cable(15, {"source": "VEL"}, {"module": 2, "param": "B"})]
        next(r for r in rack if r["pos"] == 5)["data"] = {"version": 1, "hex": "1234567810"}
        routes[0]["via"] = output(3, "Env")
        routes[2]["via"] = output(5, "CV")
        routes[-1]["on"] = False
        positions, slots = list(range(1, 7)), [1, 3, 5, 9, 11, 13, 15]
    elif case == "cycle":
        rack += [{"pos": p, "kind": "calc"} for p in [2, 4]]
        routes = [cable(1, output(4), sink),
                  cable(5, output(2), {"module": 4, "param": "A"}),
                  cable(9, output(4), {"module": 2, "param": "B"}),
                  cable(13, output(1), {"module": 2, "param": "A"})]
        positions, slots = [1, 2, 4], [1, 5, 9, 13]
    elif case == "eight":
        rack += [{"pos": p, "kind": "calc"} for p in range(2, 9)]
        routes = [cable(1, output(8), sink)] + [
            cable(10 - p, output(p - 1), {"module": p, "param": "A"})
            for p in range(8, 1, -1)]
        routes += [cable(32, {"source": "TRIG"}, {"module": 1, "gate": "Reset"})]
        positions, slots = list(range(1, 9)), list(range(1, 9)) + [32]
    else:
        routes = [cable(1, {"source": "VEL"}, sink)]
        positions, slots = [], [1]
    if case != "eight":
        # Disconnected cycle and an outgoing route from a required module:
        # none belongs to the selected sink's upstream patch.
        rack += [{"pos": p, "kind": "calc"} for p in [7, 8]]
        routes += [cable(25, output(7), {"module": 8, "param": "A"}),
                   cable(27, output(8), {"module": 7, "param": "A"}),
                   cable(29, output(1), {"unit": "snd4", "param": "Volume"})]
    return {"seed": 1, "rack": rack, "cables": routes}, positions, slots


def run(renderer, *args):
    return subprocess.run([str(renderer), *map(str, args)], check=True,
                          capture_output=True, text=True, timeout=20)


@pytest.mark.parametrize("target", ["sound", "sound2", "fx"])
@pytest.mark.parametrize("case", ["chain", "via-gate-data", "cycle", "eight", "system"])
@pytest.mark.parametrize("suffix", ["lunar", "lunarb"])
def test_preset_keeps_upstream_patch(renderer, tmp_path, target, case, suffix):
    unit = {"sound": "snd1", "sound2": "snd2", "fx": "fx1"}[target]
    mod, positions, slots = patch(case, unit)
    project = {"lunar": "1.0", "kind": "project",
               "sounds": [{"engine": "test-sine"}] * 4,
               "master": [{"engine": "test-gain"}], "mod": mod}
    source = tmp_path / "source.lunar"
    source.write_text(json.dumps(project))
    full, preset = tmp_path / "full.lunar", tmp_path / f"preset.{suffix}"
    kind = "fx" if target == "fx" else "sound"
    save_kind = "sound2" if target == "sound2" else kind
    note = ["--sound-note", "1:0:60:100:0.12"] if target == "sound2" else ["--note", "0:60:100:0.12"]
    common = [*note, "--seconds", "0.2"]
    original = tmp_path / "original.wav"
    run(renderer, "--load", source, "--save", f"project:{full}",
        "--save", f"{save_kind}:{preset}", *common, "--out", original)
    # Re-read either encoding and save JSON, exercising the real state loader.
    restored = tmp_path / "restored.lunar"
    reload = f"s2:{preset}" if target == "sound2" else preset
    replay = tmp_path / "replay.wav"
    run(renderer, "--engine", "test-sine", "--load", reload,
        "--save", f"{save_kind}:{restored}", *common, "--out", replay)
    expected = json.loads(full.read_text())["mod"]
    got = json.loads(restored.read_text())["mod"]
    assert [r["pos"] for r in got["rack"]] == positions
    assert got["rack"] == [r for r in expected["rack"] if r["pos"] in positions]
    wanted_cables = [copy.deepcopy(c) for c in expected["cables"] if c["slot"] in slots]
    for c in wanted_cables:
        if c["to"].get("unit") == unit and kind == "sound":
            c["to"]["unit"] = "snd"
        if target == "sound2":
            for field in ["from", "via"]:
                if c[field] and c[field].get("source") == "S2KEY":
                    c[field]["source"] = "S1KEY"
    assert got["cables"] == wanted_cables
    if case == "via-gate-data":
        assert next(r for r in got["rack"] if r["pos"] == 5)["data"] == {
            "version": 1, "hex": "1234567810"}
    assert replay.read_bytes() == original.read_bytes()
