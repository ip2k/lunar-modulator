"""Saved modulation state the parameters do not hold (notes/2026-10-06-state-
files.md §5.4, §5.5, ST12): a module's pattern data (Register's locked or
hand-edited loop, fm1_mod_get_data / fm1_mod_set_data) and a cable's lock
uid (MG6), in the mod script (engines/host/mod_script.h), the replay log's
format, so it can say everything a saved file can:

- `data P VERSION HEX` gives a module its data: a Register given a loop
  plays that loop; what fm1-render --save-mod-data writes reads back to
  the same line; a version, a size, a length or a position the kind does
  not take is refused with a message;
- `lock=UID` on a slot is taken for 0-4095 and refused otherwise;
- --list-mod says which kinds keep data, in which layout.

fm1-mod-kinds-test checks the runtime side in C (a saved loop plays on in a
Register of another seed; refusals change nothing; the rules of kinds with
data).
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

KINDS_TEST = ENGINES / "build" / "fm1-mod-kinds-test"
SCENE = "mod 1 register change=1 length=8\nmod 2 lfo rate=0.75 shape=square\nslot 1 lfo2 > reg1.clock\n"


def run(renderer, tmp_path, mod, name="r", seconds="0.6"):
    """Renders a test sine under the rack; returns (returncode, stderr, CV
    per tick of position 1, the saved data lines)."""
    mpath, log, data = (tmp_path / f"{name}.mod", tmp_path / f"{name}.jsonl", tmp_path / f"{name}.data")
    mpath.write_text(mod)
    res = subprocess.run([str(renderer), "--engine", "test-sine", "--note", "0:60:100:0.5",
                          "--seconds", seconds, "--out", str(tmp_path / f"{name}.wav"),
                          "--mod", str(mpath), "--log-mod", str(log), "--save-mod-data", str(data)],
                         capture_output=True, text=True)
    if res.returncode:
        return res.returncode, res.stderr, None, None
    cv = []
    for line in log.read_text().splitlines():
        tick = json.loads(line)
        cv += [f32(m["o"][0]) for m in tick["m"] if m["p"] == 1]
    return 0, res.stderr, cv, data.read_text().splitlines()


def f32(x):
    import struct
    return struct.unpack("<f", struct.pack("<f", x))[0]


def test_a_loaded_loop_is_the_loop_that_plays(renderer, tmp_path):
    """Change +1 locks the loop; the data puts 0xA5 in its low byte, so with
    Length 8 the CV steps through that byte's rotations, from the first
    tick on."""
    rc, err, cv, data = run(renderer, tmp_path, SCENE + "data 1 1 a500000008\n", seconds="2")
    assert rc == 0, err
    steps = [cv[0]] + [b for a, b in zip(cv, cv[1:]) if b != a]
    rotations, byte = [], 0xA5
    for _ in range(len(steps) + 1):
        rotations.append(f32(f32(byte) * f32(1 / 255)))
        byte = ((byte << 1) | (byte >> 7)) & 0xFF
    # The square starts high: its first edge may come at the first tick.
    start = rotations.index(steps[0])
    assert start in (0, 1) and len(steps) >= 9
    assert steps == rotations[start:start + len(steps)]
    # The seed's own loop is another one.
    rc, err, other, _ = run(renderer, tmp_path, SCENE, name="seed")
    assert rc == 0 and other[0] != cv[0]


def test_saved_data_reads_back_as_the_same_line(renderer, tmp_path):
    """A loop locked and edited by hand (WRITE from each note's trigger),
    saved as the render ends, given to a fresh rack of another seed with
    no clock, saves as the same line: get_data and set_data are each
    other's inverse through the format."""
    rc, err, _, data = run(renderer, tmp_path, SCENE + "slot 2 trig > reg1.write\n", name="a")
    assert rc == 0, err
    assert len(data) == 1 and data[0].startswith("data 1 1 ")
    hexed = data[0].split()[3]
    assert len(hexed) == 10 and int(hexed[8:], 16) == 8
    rc, err, cv, again = run(renderer, tmp_path, "seed 12345\nmod 1 register change=1 length=8\n"
                             + data[0] + "\n", name="b", seconds="0.05")
    assert rc == 0, err
    assert again == data
    assert cv[0] == f32(f32(int(hexed[0:2], 16)) * f32(1 / 255))


def test_bad_data_is_refused_with_a_reason(renderer, tmp_path):
    cases = {
        "data 1 2 a500000008": "does not take",         # another layout
        "data 1 1 a50000": "does not take",             # another size
        "data 1 1 a500000021": "does not take",         # length 33
        "data 1 1 a50000000": "odd number",
        "data 1 1 a500000008zz": "not hex",
        "data 1 1 a5000000 08": "data wants",           # one word of hex
        "data 3 1 a500000008": "empty",                 # nothing at 3
        "data 2 1 00": "does not take",                 # an LFO keeps no data
        "data 1 256 00": "data wants",
        "data 1": "data wants",
    }
    for line, why in cases.items():
        rc, err, _, _ = run(renderer, tmp_path, SCENE + line + "\n", name="bad")
        assert rc != 0 and why in err, (line, err)


def test_a_slot_carries_its_lock_uid(renderer, tmp_path):
    for ok in ("0", "300", "4095"):
        rc, err, _, _ = run(renderer, tmp_path, SCENE + f"slot 3 lfo2 > reg1.level lock={ok}\n")
        assert rc == 0, (ok, err)
    for bad in ("4096", "-1", "1.5", "x"):
        rc, err, _, _ = run(renderer, tmp_path, SCENE + f"slot 3 lfo2 > reg1.level lock={bad}\n")
        assert rc != 0 and "lock wants a uid" in err, (bad, err)


def test_list_mod_says_which_kinds_keep_data(renderer):
    listed = json.loads(subprocess.run([str(renderer), "--list-mod"], check=True,
                                       capture_output=True, text=True).stdout)
    data = {k["id"]: k["data"] for k in listed["kinds"]}
    assert data["register"] == {"bytes": 5, "version": 1}
    assert all(v is None for k, v in data.items() if k != "register")
    assert not any(k["poly_ok"] for k in listed["kinds"] if k["data"])


def test_the_runtime_checks_pass(renderer):
    out = subprocess.run([str(KINDS_TEST)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["failed"] == 0


@pytest.mark.parametrize("line", ["mod nan lfo", "seed nan", "seed inf", "seed 1e999",
    "data 1 nan 00", "slot 3 lfo2 > reg1.level lock=nan"])
def test_nonfinite_integer_fields_refused(renderer, tmp_path, line):
    rc, err, _, _ = run(renderer, tmp_path, SCENE + line + "\n", seconds="0.01")
    assert rc != 0, (line, err)
