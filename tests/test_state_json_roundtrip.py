"""Project JSON read/write contract, without a renderer or engine build."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def names():
    return ls.Names({"kind": "metadata", "engines": [], "known_ids": [],
                     "mod": {"kinds": [], "sources": [], "host": []}})


@pytest.fixture(scope="module", params=["normal", "asan-ubsan"])
def json_probe(request, tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    exe = tmp_path_factory.mktemp("state-json") / "probe"
    flags = (["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
             if request.param == "asan-ubsan" else ["-O2"])
    build = subprocess.run([cc, "-std=c99", *flags, "-ffp-contract=off", "-Wall", "-Wextra",
                    "-Wpedantic", "-Werror", "-Iengines/state", "-Iengines/include",
                    "engines/test/state_json_roundtrip_test.c",
                    *[f"engines/state/{s}.c" for s in ["fm1_json", "fm1_num", "state_names",
                                                       "state_json_read", "state_json_write"]],
                    "-o", str(exe)], cwd=ROOT, capture_output=True, timeout=30)
    assert build.returncode == 0, build.stderr.decode(errors="replace")
    return exe


def probe(exe, data=b"", mode="roundtrip", piece=256):
    result = subprocess.run([str(exe), mode, str(piece)], input=data,
                            capture_output=True, timeout=10)
    assert result.returncode >= 0, result.stderr.decode(errors="replace")
    return result, json.loads(result.stderr)


@pytest.mark.parametrize("piece", [1, 7, 256])
@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_project_roundtrip(json_probe, names, piece, count):
    # Retain accepted shorthand; only the canonical form requires four slots.
    sounds = [{"engine": "unknown", "params": {"#7": 0.25}}] + [None] * (count - 1)
    if count == 4:
        sounds[1:] = [{"engine": f"future-{i}", "params": {"#42": -0.75}} for i in range(3)]
    doc = {"lunar": "1.0", "kind": "project", "sounds": sounds}
    if count == 4:
        doc.update(session={"current": 3, "octave": -1, "transpose": 2},
                   master=[None, None], mod={"seed": 17, "rack": [], "cables": []})
    data = json.dumps(doc, separators=(",", ":")).encode()
    result, report = probe(json_probe, data, piece=piece)
    assert result.returncode == 0, report
    assert report["read_ok"] == report["write_ok"] == report["stable"] == 1
    assert report["ends"] == 1
    records, _ = ls.read_json(data, names)
    canonical, _ = ls.write_json(records, names)
    assert result.stdout == canonical.encode()
    read_back, _ = ls.read_json(canonical, names)
    second, _ = ls.write_json(read_back, names)
    assert second == canonical
    saved = json.loads(canonical)
    assert saved["sounds"][0]["engine"] == "unknown"
    assert len(saved["sounds"]) == 4


@pytest.mark.parametrize("doc", [
    {"lunar": "1.0", "kind": "fx", "chain": []},
    {"lunar": "1.0", "kind": "settings", "settings": {}},
])
def test_other_kinds_can_be_empty(json_probe, names, doc):
    data = json.dumps(doc).encode()
    result, report = probe(json_probe, data, piece=1)
    assert result.returncode == 0, report
    assert report["read_ok"] == report["write_ok"] == report["stable"] == 1
    records, _ = ls.read_json(data, names)
    canonical, _ = ls.write_json(records, names)
    assert result.stdout == canonical.encode()
    again, _ = ls.read_json(canonical, names)
    assert ls.write_json(again, names)[0] == canonical


@pytest.mark.parametrize("piece", [1, 7, 256])
@pytest.mark.parametrize("data,code", [
    (b"", "NOT_LUNAR"),
    (b'{"lunar":"1.0","kind":"project"}', "BAD"),
    (b'{"lunar":"1.0","kind":"project","sounds":[]}', "BAD"),
    (b'{"lunar":"1.0","kind":"project","sounds":[null]}', "BAD"),
    (b'{"lunar":"1.0","kind":"project","sounds":[{}]}', "BAD"),
    (b'{"lunar":"1.0","kind":"project","sounds":{}}', "BAD"),
    (b'{"lunar":"1.0","kind":"project","sounds":[{"engine":"unknown"},null,null,null,null]}', "BAD"),
    (b'{"lunar":"1.0","kind":"project","sounds":[', "BAD"),
])
def test_refused_project_never_ends(json_probe, names, piece, data, code):
    result, report = probe(json_probe, data, piece=piece)
    assert result.returncode == 1, report
    assert report["read_ok"] == 0 and report["ends"] == 0 and report["code"] == code
    with pytest.raises(ls.Refused) as refused:
        ls.read_json(data, names)
    assert refused.value.code == code


def test_fresh_project_needs_sound_one(json_probe, names):
    result, report = probe(json_probe, mode="fresh")
    assert result.returncode == 1 and report["write_ok"] == 0 and report["code"] == "BAD"
    assert not result.stdout
    with pytest.raises(ls.Refused, match="Sound 1 is never empty"):
        ls.write_json([{"rec": "head", "kind": "project", "minor": 0}, {"rec": "end"}], names)


@pytest.mark.parametrize("sounds", [{}, {"sounds": []}])
def test_maps_only_api_retains_empty_envelope(json_probe, sounds):
    doc = {"lunar": "1.0", "kind": "project", **sounds,
           "browser": {"midiMap": {"version": 1, "bindings": []}}}
    result, report = probe(json_probe, json.dumps(doc).encode(), mode="maps", piece=1)
    assert result.returncode == 0, report
    assert report["read_ok"] == 1 and report["ends"] == 1
