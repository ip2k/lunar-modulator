"""Known MIDI mapping metadata survives canonical codecs and native project state."""
import json
import struct
import subprocess

import pytest

from tests.engine_helpers import renderer  # noqa: F401
from tests.test_app_state import cycle, refused, schema_ok
from tests.test_sim_web import tools  # noqa: F401
from tests.test_state_codec import c_records, names, py_records, run, tool  # noqa: F401
from tools import lunar_state as ls


def binding(target="panel:key:0", source="keyboard-α", channel=3, kind="note", number=60):
    return dict(target=target, source=source, channel=channel, kind=kind, number=number)


def doc(bindings=None, version=1):
    return {"lunar": "1.0", "kind": "project", "sounds": [{"engine": "macro"}],
            "browser": {"midiMap": {"version": version, "bindings": [binding()] if bindings is None else bindings}}}


def raw(document):
    return json.dumps(document, ensure_ascii=False).encode()


def test_mapping_codecs_agree(tool, names):
    data = raw(doc([binding(), binding("panel:master", "keyboard-α", 15, "cc", 127)]))
    recs, _ = ls.read_json(data, names)
    assert c_records(tool, data)[1] == ls.records_text(recs)
    for pieces in (1, 7, 256):
        assert c_records(tool, data, pieces)[1] == ls.records_text(recs)
    canonical = run(tool, "canon", "-", data=data, check=True).stdout
    assert canonical == ls.write_json(recs, names)[0].encode()
    for compressed in (True, False):
        binary = ls.write_bin(recs, deflate_chunks=compressed)
        assert c_records(tool, binary)[1] == ls.records_text(recs)
        assert ls.read_bin(binary)[0] == recs
        assert run(tool, "unpack", "-", data=binary, check=True).stdout == canonical
        if compressed:
            normalized, _ = ls.read_json(canonical, names)
            assert run(tool, "pack", "-", data=data, check=True).stdout == ls.write_bin(normalized)
    schema_ok(json.loads(canonical))


def test_maps_roundtrip_app_and_host(tools, renderer, tmp_path):
    source = tmp_path / "mapped.lunar"
    source.write_bytes(raw(doc([binding(), binding("editor:param:snd1:#1", "knobs", 0, "cc", 1)])))
    out = cycle(tools, tmp_path, "--load", source)
    assert out["browser"] == json.loads(source.read_text())["browser"]
    schema_ok(out)
    for suffix in ("lunar", "lunarb"):
        saved = tmp_path / ("render." + suffix)
        subprocess.run([str(renderer), "--load", str(source), "--save", f"project:{saved}", "--seconds", "0.01",
                        "--out", str(tmp_path / "render.wav")], check=True, capture_output=True)
        recs, _ = ls.read_any(saved.read_bytes(), ls.Names.from_build())
        decoded = json.loads(ls.write_json(recs, ls.Names.from_build())[0])
        assert decoded["browser"] == out["browser"]


def test_empty_and_legacy_project_reload(tools, tmp_path):
    source = tmp_path / "empty.lunar"
    source.write_bytes(raw(doc([])))
    assert cycle(tools, tmp_path, "--load", source)["browser"]["midiMap"] == {"version": 1, "bindings": []}
    mapped = tmp_path / "mapped.lunar"
    mapped.write_bytes(raw(doc()))
    legacy = doc(); del legacy["browser"]
    source.write_bytes(raw(legacy))
    result = cycle(tools, tmp_path, "--load", mapped, "--load", source)
    assert "browser" not in result


@pytest.mark.parametrize("change,code", [
    ({"channel": 16}, "BAD"), ({"channel": -1}, "BAD"), ({"channel": 1.5}, "BAD"),
    ({"number": 128}, "BAD"), ({"kind": "pitch"}, "BAD"), ({"target": ""}, "BAD"),
    ({"target": "x" * 193}, "TOO_BIG"), ({"target": "target-α"}, "BAD"),
    ({"source": "α" * 65}, "TOO_BIG"), ({"source": "device\0"}, "BAD"), ({"source": ""}, "BAD"),
])
def test_invalid_binding_refuses_atomically(tools, tool, names, tmp_path, change, code):
    d = doc(); d["browser"]["midiMap"]["bindings"][0].update(change)
    data = raw(d)
    rc, _, report = c_records(tool, data)
    assert rc and report["code"] == code
    assert py_records(data, names)[2] == code
    src = tmp_path / "bad.lunar"; src.write_bytes(data)
    refused(tools, tmp_path, ["--start"], src, code)


def test_binding_count_and_pool_caps(tools, tool, names, tmp_path):
    # Repeated source strings take one pool slot, so all 64 records fit.
    records = [binding(f"panel:key:{i}", number=i) for i in range(64)]
    src = tmp_path / "cap.lunar"; src.write_bytes(raw(doc(records)))
    assert cycle(tools, tmp_path, "--load", src)["browser"]["midiMap"]["bindings"] == records
    for entries in (records + [binding("overflow")],
                    [binding(f"editor:param:{i}:" + "x" * 170, "y" * 128, number=i) for i in range(24)]):
        data = raw(doc(entries)); src.write_bytes(data)
        assert py_records(data, names)[2] == "TOO_BIG"
        assert run(tool, "canon", "-", data=data).returncode != 0
        refused(tools, tmp_path, ["--start"], src, "TOO_BIG")


def mutate_browser(binary, byte_offset, value):
    binary = bytearray(binary)
    hdr, count, size = struct.unpack_from("<HHH", binary, 12)
    for i in range(count):
        entry = hdr + i * size
        if binary[entry:entry + 4] != b"BROW":
            continue
        off, length = struct.unpack_from("<II", binary, entry + 8)
        assert struct.unpack_from("<H", binary, entry + 6)[0] == 0
        binary[off + byte_offset] = value
        struct.pack_into("<I", binary, entry + 16, ls.crc32(binary[off:off + length]))
        struct.pack_into("<I", binary, hdr + count * size, ls.crc32(binary[hdr:hdr + count * size]))
        return bytes(binary)
    raise AssertionError("BROW missing")


@pytest.mark.parametrize("offset,value,code", [(0, 2, "TOO_NEW"), (0, 0, "BAD"), (1, 65, "TOO_BIG"),
                                                   (4, 1, "BAD"), (8, 16, "BAD"), (9, 2, "BAD"),
                                                   (10, 128, "BAD"), (11, 1, "BAD"), (12, 0xff, "BAD")])
def test_binary_map_is_bounded_and_atomic(tools, tool, names, tmp_path, offset, value, code):
    recs, _ = ls.read_json(raw(doc()), names)
    binary = mutate_browser(ls.write_bin(recs, deflate_chunks=False), offset, value)
    rc, _, report = c_records(tool, binary)
    assert rc and report["code"] == code
    assert py_records(binary, names)[2] == code
    src = tmp_path / "bad.lunarb"; src.write_bytes(binary)
    refused(tools, tmp_path, ["--start"], src, code)


@pytest.mark.parametrize("version,code", [(0, "BAD"), (2, "TOO_NEW")])
def test_json_mapping_version_refusal(tool, names, version, code):
    data = raw(doc(version=version))
    assert c_records(tool, data)[2]["code"] == code
    assert py_records(data, names)[2] == code


def test_maps_only_setter_preserves_transport(tools):
    result = subprocess.run([str(tools["sim"]), "--edit-check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["failed"] == 0


def test_duplicate_target_or_midi_address_refuses(tools, tool, names, tmp_path):
    for entries in ([binding(), binding(number=61)], [binding(), binding("panel:key:1")]):
        data = raw(doc(entries))
        assert py_records(data, names)[2] == "BAD"
        assert run(tool, "canon", "-", data=data).returncode != 0
        assert run(tool, "check", "-", data=data).returncode != 0
        source = tmp_path / "duplicate.lunar"; source.write_bytes(data)
        refused(tools, tmp_path, ["--start"], source, "BAD")


def test_exact_source_and_printable_target_bytes(tool, names):
    data = raw(doc([binding("editor:action:My control", "device\nα")]))
    assert c_records(tool, data)[1] == py_records(data, names)[1]
    recs, _ = ls.read_json(data, names)
    assert c_records(tool, ls.write_bin(recs))[1] == ls.records_text(recs)


def test_newer_binary_browser_chunk_refuses(tools, tool, names, tmp_path):
    recs, _ = ls.read_json(raw(doc()), names)
    binary = bytearray(ls.write_bin(recs, deflate_chunks=False))
    hdr, count, size = struct.unpack_from("<HHH", binary, 12)
    for i in range(count):
        entry = hdr + i * size
        if binary[entry:entry + 4] == b"BROW":
            struct.pack_into("<H", binary, entry + 4, 2)
            break
    else:
        raise AssertionError("BROW missing")
    struct.pack_into("<I", binary, hdr + count * size, ls.crc32(binary[hdr:hdr + count * size]))
    binary = bytes(binary)
    assert c_records(tool, binary)[2]["code"] == "TOO_NEW"
    assert py_records(binary, names)[2] == "TOO_NEW"
    source = tmp_path / "future.lunarb"; source.write_bytes(binary)
    refused(tools, tmp_path, ["--start"], source, "TOO_NEW")


def test_fixed_mapping_storage_keeps_ram_budget_strict(tools, tmp_path):
    # Shapes + Plate + Room was just inside the old budget; the bounded map
    # storage now makes it exceed the same limit. The live and file paths
    # must both refuse instead of silently undercounting project preferences.
    result = subprocess.run([str(tools["sim"]), "--seconds", "0", "--engine", "shapes",
                             "--fx", "plate", "--fx", "room"], capture_output=True, text=True)
    assert result.returncode and "cannot load room (-4)" in result.stderr
    project = cycle(tools, tmp_path, "--engine", "shapes", "--fx", "plate")
    project["master"][1] = {"engine": "room"}
    source = tmp_path / "past-budget.lunar"; source.write_bytes(raw(project))
    refused(tools, tmp_path, ["--start"], source, "RAM")
