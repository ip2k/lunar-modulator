"""Dense project size through the real application collector and SAVE bridge.

This intentionally measures a concrete app state, not an estimate from JSON or
hand-authored binary records.  It uses the native SAVE simulator hook, which
collects twice, serializes through the compact writer, commits both NOR slots,
validates recovery, and emits the committed body for the independent reader.
The fixture reaches every tested app pool, but its byte size is not a proof of
the maximum app project or of physical flash-bank headroom.
"""
import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.engine_helpers import GPL_MODS
from tests.test_app_state import DX7, sim
from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim" / "web"
ENGINES_DIR = ROOT / "engines"


@pytest.fixture(scope="session")
def save_tools(tmp_path_factory):
    """Build a test-owned host app with the production SAVE writer enabled."""
    build = tmp_path_factory.mktemp("native-project-capacity-save")
    targets = [build / "fm1-render", build / "fm1-sim-render"]
    subprocess.run([
        "make", "-C", str(ENGINES_DIR), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
        f"SIM={SIM}", f"BUILD={build}", f"FM1_GPL_MODS={int(GPL_MODS)}",
        "EXTRA=-DFM1_STATE_BIN_COMPACT_WRITER -DFM1_TFT_INDEXED=1", "-j4",
        *map(str, targets),
    ], check=True, stdout=subprocess.DEVNULL)
    return {"render": targets[0], "sim": targets[1]}
SEQ_TRACKS = 8
NOTES_PER_TRACK = 192
LOCKS_PER_TRACK = 192
TRIGS_PER_TRACK = 32
MOD_SLOTS = 32
MOD_DATA_BYTES = 5  # Register's kind-specific payload, from `fm1-render --list-mod`.
MOD_MODULES = 8
DX7_VOICES = 32
APP_SOUND_UNITS = 4
APP_INSERT_SLOTS = 8
APP_MASTER_FX_SLOTS = 2
APP_FX_SLOTS = APP_INSERT_SLOTS + APP_MASTER_FX_SLOTS
NATIVE_SLOT_BYTES = int(os.environ.get("FM1_TEST_NATIVE_SLOT_BYTES", "102400"))
NATIVE_PAYLOAD_LIMIT = 98304
CONSERVATIVE_COLLECTOR_BOUND = 43130
MAX_METADATA = {"name": "N" * 16, "title": "T" * 64, "about": "A" * 240,
                "author": "U" * 64, "licence": "L" * 32}
MAX_SEQ_LABEL = "ABCDEFGHIJKLMNOPQRSTUVW"  # 23 bytes, no whitespace: ALABEL token limit.


def _dense_set(path: Path) -> tuple[int, int]:
    """Fill the known default set pools and return text length and record counts."""
    lines = ["movy1", "bpm 30000", "swing 99", "link 1", "key 11 7"]
    for track in range(SEQ_TRACKS):
        # Vary values so the serialized size is not an unrealistically tiny,
        # repeated-pattern result while staying within sequencer value limits.
        notes = ";".join(
            f"{i * 24}:{48 + ((i * 37 + track * 11) % 80)}:"
            f"{1 + ((i * 29 + track) % 126)}:127:{i % 256}"
            for i in range(NOTES_PER_TRACK)
        )
        locks = ";".join(
            f"{i % 8}:{i // 8}:{(i * 13 + track * 7) % 128}"
            for i in range(LOCKS_PER_TRACK)
        )
        trigs = ";".join(
            f"{i}:-1:{(i * 3) % 128}:{(i * 7) % 256}:255:1"
            for i in range(TRIGS_PER_TRACK)
        )
        lines.extend((f"tk {track} 0 0", f"rt {track} 1 {track % 4}",
                      f"cl {track} 0 256 0 {notes}",
                      f"cp {track} 0 24 1 -127 100",
                      f"lk {track} 0 {locks}", f"tg {track} 0 {trigs}"))
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return len(content.encode()), (SEQ_TRACKS * NOTES_PER_TRACK,
                                  SEQ_TRACKS * LOCKS_PER_TRACK,
                                  SEQ_TRACKS * TRIGS_PER_TRACK)


def _dense_mod(path: Path) -> int:
    """Fill the rack, its parameter records, cable slots, and Register data."""
    mix_params = ("Gain1=1.75 Gain2=-1.5 Gain3=1.25 Gain4=-1.0 Offset=0.75 "
                  "In1=0.875 In2=-0.625 In3=0.5 In4=-0.375")
    lines = ["seed 4294967295"]
    lines.extend(f"mod {pos} mix {mix_params}" for pos in range(1, MOD_MODULES))
    lines.extend((f"mod {MOD_MODULES} register Change=-1 Length=32 Level=-0.75 "
                  "Offset=0.5 Span=60 Slew=0.75",
                  f"data {MOD_MODULES} 1 a5c3f00e08"))
    lines.extend(f"slot {slot} mix1.sum > host:amp amt={(slot * 61 % 201) - 100}"
                 for slot in range(1, MOD_SLOTS + 1))
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return len(content.encode())


def _start_args(seq: Path, mod: Path) -> list[str]:
    """Populate high-payload pad state, voice bank, mod rack, and set."""
    # Drums exposes nine pad parameters (more than the other registered pad
    # engines), so four instances maximize the fixture's accepted pad records.
    args = ["--engine", "drums", "--sysex", DX7]
    drums_pad_values = (("Tune", 23.5), ("Decay", .91), ("Level", .83), ("Tone", .77),
                        ("Snap", .69), ("Sweep", .61), ("Drive", .53), ("Model", 4), ("Choke", 4))
    # The collector is separately checked for every pad's serialized vector,
    # including default values on pads other than the focused pad.
    args += ["--param", "Pad=15"]
    for name, value in drums_pad_values:
        args += ["--param", f"{name}={value}"]
    for sound in (1, 2, 3):
        engine = "drums"
        args += ["--sound", f"{sound}:{engine}"]
        # The sim CLI's deferred --sound-param helper stores at most 16 values
        # per unit and applies them after selection. One focused pad exercises
        # all parameter setters; the collector later emits all 16 pad values.
        args += ["--sound-param", f"{sound}:Pad=15"]
        for name, value in drums_pad_values:
            args += ["--sound-param", f"{sound}:{name}={value}"]
        args += ["--mfx", f"{sound}:arp"]
        args += ["--insert", f"{sound}:filter", "--insert-param", f"{sound}:Cutoff=17000",
                 "--insert-param", f"{sound}:Resonance=0.91", "--insert", f"{sound}:drive",
                 "--insert-param", f"{sound}:Drive=34", "--insert-param", f"{sound}:Bias=-0.8"]
    # The first sound has two insert positions too; all four chains plus the
    # two master positions make ten populated audio-effect slots.
    args += ["--insert", "0:filter", "--insert-param", "0:Cutoff=17000",
             "--insert-param", "0:Resonance=0.91", "--insert", "0:drive",
             "--insert-param", "0:Drive=34", "--insert-param", "0:Bias=-0.8"]
    args += ["--fx", "hall", "--fx-param", "Decay=0.99", "--fx-param", "Size=0.99",
             "--fx", "limit", "--fx-param", "Ceiling=-0.1", "--fx-param", "Release=0.99"]
    args += ["--mfx", "0:arp"]
    # Keep the complete matrix occupied.  Each slot is a distinct amount and
    # feeds the same valid destination; the independent reader checks storage.
    args += ["--mod", str(mod), "--seq", str(seq)]
    return args


def _dense_max_args(seq: Path, mod: Path) -> list[str]:
    """Fill four Drums sounds (the highest registered expansion) and app pools."""
    return _start_args(seq, mod)


def _dense_max_mod(path: Path) -> int:
    """Use eight registered Mix modules (nine params each) and all cable slots."""
    mix_params = ("Gain1=1.75 Gain2=-1.5 Gain3=1.25 Gain4=-1.0 Offset=0.75 "
                  "In1=0.875 In2=-0.625 In3=0.5 In4=-0.375")
    lines = ["seed 4294967295"]
    lines.extend(f"mod {pos} mix {mix_params}" for pos in range(1, MOD_MODULES + 1))
    lines.extend(f"slot {slot} mix1.sum > host:amp amt={(slot * 61 % 201) - 100}"
                 for slot in range(1, MOD_SLOTS + 1))
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return len(content.encode())


def _max_drums_set(path: Path) -> int:
    """Use all default track/clip pools and every accepted lane-label slot."""
    _, counts = _dense_set(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    for track in range(SEQ_TRACKS):
        for lane in range(8):
            lines.append(f"au {track} {lane} 255 {MAX_SEQ_LABEL}")
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return len(content.encode())


def test_dense_actual_app_project_fits_native_payload(save_tools, tmp_path):
    """Measure one dense app project using full sequencer and cable pools."""
    seq, mod = tmp_path / "dense.movy1", tmp_path / "dense.mod"
    set_text_bytes, counts = _dense_set(seq)
    mod_text_bytes = _dense_mod(mod)
    native = tmp_path / "dense.native-save.lunarb"
    args = _start_args(seq, mod) + ["--save", f"project:{native}"]
    sim(save_tools, *args)

    body = native.read_bytes()
    records, _ = ls.read_bin(body)
    assert len(body) <= NATIVE_PAYLOAD_LIMIT
    assert len(body) < NATIVE_SLOT_BYTES
    assert body[24] == 2  # FM1_STATE_WRITER_FIRMWARE
    assert [r["text"] for r in records
            if r["rec"] == "info" and r["key"] == "by"] == ["firmware"]
    modules = [r for r in records if r["rec"] == "module"]
    cables = [r for r in records if r["rec"] == "cable"]
    data_records = [r for r in records if r["rec"] == "data"]
    assert len(modules) == MOD_MODULES
    assert len(cables) == MOD_SLOTS
    assert {r["pos"] for r in modules} == set(range(MOD_MODULES))
    mod_params = [r for r in records if r["rec"] == "param" and r["role"] == "module"]
    assert len(mod_params) == (MOD_MODULES - 1) * 9 + 6
    assert data_records == [{"rec": "data", "pos": MOD_MODULES - 1, "version": 1,
                             "hex": "a5c3f00e08"}]
    voices = [r for r in records if r["rec"] == "dx7"]
    assert len(voices) == DX7_VOICES
    assert {r["slot"] for r in voices} == set(range(DX7_VOICES))
    units = [r for r in records if r["rec"] == "unit"]
    for role, count in (("sound", APP_SOUND_UNITS), ("insert", APP_INSERT_SLOTS),
                        ("master", APP_MASTER_FX_SLOTS)):
        assert sum(r["role"] == role for r in units) == count
    assert sum(bool(r["rec"] == "unit" and r["role"] in ("insert", "master") and r["engine"])
               for r in records) == APP_FX_SLOTS
    fx_params = [r for r in records if r["rec"] == "param" and r["role"] in ("insert", "master")]
    assert len(fx_params) >= APP_FX_SLOTS * 2
    # Four Drums units save nine focus-scoped parameters for all 16 pads;
    # unit-scoped parameters are excluded here.
    pad_params = [r for r in records if r["rec"] == "param" and r["role"] == "sound" and
                  r.get("focus") is not None]
    assert len(pad_params) == 4 * 9 * 16
    assert {r["focus"] for r in pad_params} == set(range(16))
    assert {r["sound"] for r in pad_params} == set(range(APP_SOUND_UNITS))
    assert all(sum(r["sound"] == sound for r in pad_params) == 9 * 16
               for sound in range(APP_SOUND_UNITS))
    set_records = [r for r in records if r["rec"] == "line" and r["which"] == "set"]
    assert set_records, "collector omitted the app's active sequencer set"
    set_text = "\n".join(str(r.get("text", "")) for r in set_records)
    # Check every accepted row and every list item, independently of the
    # generator's intended count: importer loss/clamping must not masquerade
    # as a dense fixture.  Each track has one full pool in clip 0.
    decoded_lines = set_text.splitlines()
    assert sum(line.startswith("tk ") for line in decoded_lines) == SEQ_TRACKS
    assert sum(line.startswith("cl ") for line in decoded_lines) == SEQ_TRACKS
    assert sum(line.startswith("lk ") for line in decoded_lines) == SEQ_TRACKS
    assert sum(line.startswith("tg ") for line in decoded_lines) == SEQ_TRACKS
    for track in range(SEQ_TRACKS):
        cl = next(line for line in decoded_lines if line.startswith(f"cl {track} 0 "))
        note_rows = cl.split(" ", 5)[5].split(";")
        assert len(note_rows) == NOTES_PER_TRACK
        clip_steps = int(cl.split()[3])
        assert clip_steps == 256
        notes = [tuple(map(int, row.split(":"))) for row in note_rows]
        assert all(0 <= pitch <= 127 and 0 <= velocity <= 127 and
                   0 <= tick < clip_steps * 24 and 0 <= gate <= 65535 and 0 <= start <= 255
                   for tick, gate, pitch, velocity, start in notes)
        locks = next(line for line in decoded_lines if line.startswith(f"lk {track} 0 "))
        assert len(locks.split(" ", 3)[3].split(";")) == LOCKS_PER_TRACK
        trigs = next(line for line in decoded_lines if line.startswith(f"tg {track} 0 "))
        assert len(trigs.split(" ", 3)[3].split(";")) == TRIGS_PER_TRACK

    # The measured input itself and the independently decoded native file are
    # retained as test diagnostics.  They distinguish source-text size from
    # the actual committed binary size.
    print({"native_bytes": len(body), "binary_payload_limit": NATIVE_PAYLOAD_LIMIT,
           "slot_bytes": NATIVE_SLOT_BYTES, "dense_set_text_bytes": set_text_bytes,
           "dense_mod_text_bytes": mod_text_bytes, "mod_data_bytes": MOD_DATA_BYTES,
           "set_pool_counts": {"notes": counts[0], "locks": counts[1], "trigs": counts[2]},
           "decoded_state_counts": {"modules": len(modules), "module_params": len(mod_params),
                                    "cables": len(cables), "data_bytes": sum(len(r["hex"]) // 2 for r in data_records),
                                    "dx7_voices": len(voices), "pad_params": len(pad_params),
                                    "fx_slots": APP_FX_SLOTS, "fx_params": len(fx_params)},
           "binary_record_count": len(records)})


def test_max_drums_metadata_and_registered_pools_recover_through_native_save(save_tools, tmp_path):
    """Round-trip maximum sound rows, metadata, and accepted pools via native SAVE."""
    seq, mod = tmp_path / "max-drums.movy1", tmp_path / "max-drums.mod"
    set_text_bytes = _max_drums_set(seq)
    mod_text_bytes = _dense_max_mod(mod)
    initial = tmp_path / "initial.lunar"
    args = _dense_max_args(seq, mod) + ["--save", f"project:{initial}"]
    sim(save_tools, *args)

    # Load maximum-length metadata through the app's project loader; then the
    # native SAVE adapter performs its collect/serialize/commit/recovery path.
    doc = json.loads(initial.read_text(encoding="utf-8"))
    doc.update(MAX_METADATA)
    prepared = tmp_path / "max-metadata.lunar"
    prepared.write_text(json.dumps(doc), encoding="utf-8")
    native = tmp_path / "max-drums.native-save.lunarb"
    sim(save_tools, "--load", prepared, "--save", f"project:{native}")

    body = native.read_bytes()
    records, _ = ls.read_bin(body)
    assert len(body) <= CONSERVATIVE_COLLECTOR_BOUND
    assert len(body) <= NATIVE_PAYLOAD_LIMIT
    assert body[24] == 2  # FM1_STATE_WRITER_FIRMWARE
    info = {r["key"]: r.get("text", "") for r in records if r["rec"] == "info"}
    assert {key: info[key] for key in MAX_METADATA} == MAX_METADATA

    sounds = [r for r in records if r["rec"] == "unit" and r["role"] == "sound"]
    assert len(sounds) == APP_SOUND_UNITS
    params = [r for r in records if r["rec"] == "param" and r["role"] == "sound"]
    focused = [r for r in params if r.get("focus") is not None]
    assert len(params) == APP_SOUND_UNITS * 149
    assert len(focused) == APP_SOUND_UNITS * 9 * 16
    assert {r["focus"] for r in focused} == set(range(16))
    assert {r["sound"] for r in params} == set(range(APP_SOUND_UNITS))

    modules = [r for r in records if r["rec"] == "module"]
    module_params = [r for r in records if r["rec"] == "param" and r["role"] == "module"]
    cables = [r for r in records if r["rec"] == "cable"]
    assert len(modules) == MOD_MODULES
    assert len(module_params) == MOD_MODULES * 9
    assert len(cables) == MOD_SLOTS
    assert {r["slot"] for r in cables} == set(range(MOD_SLOTS))

    voices = [r for r in records if r["rec"] == "dx7"]
    assert len(voices) == DX7_VOICES
    units = [r for r in records if r["rec"] == "unit"]
    assert sum(r["role"] == "insert" for r in units) == APP_INSERT_SLOTS
    assert sum(r["role"] == "master" for r in units) == APP_MASTER_FX_SLOTS
    assert sum(r["role"] in ("insert", "master") and bool(r["engine"]) for r in units) == APP_FX_SLOTS
    mfx_params = [r for r in records if r["rec"] == "param" and r["role"] == "mfx"]
    assert len(mfx_params) == APP_SOUND_UNITS * 24

    set_records = [r for r in records if r["rec"] == "line" and r["which"] == "set"]
    decoded_lines = "\n".join(str(r.get("text", "")) for r in set_records).splitlines()
    labels = [line for line in decoded_lines if line.startswith("au ")]
    assert len(labels) == SEQ_TRACKS * 8
    assert all(line.endswith(MAX_SEQ_LABEL) for line in labels)
    for track in range(SEQ_TRACKS):
        cl = next(line for line in decoded_lines if line.startswith(f"cl {track} 0 "))
        assert len(cl.split(" ", 5)[5].split(";")) == NOTES_PER_TRACK
        lk = next(line for line in decoded_lines if line.startswith(f"lk {track} 0 "))
        assert len(lk.split(" ", 3)[3].split(";")) == LOCKS_PER_TRACK
        tg = next(line for line in decoded_lines if line.startswith(f"tg {track} 0 "))
        assert len(tg.split(" ", 3)[3].split(";")) == TRIGS_PER_TRACK
    assert len(ls.encode_line(f"au 7 7 255 {'A' * 11} {'B' * 11}")) == 37
    assert ls.encode_line(f"au 7 7 255 {'A' * 11} {'B' * 11}")[0] == 0x01

    print({"native_bytes": len(body), "conservative_bound": CONSERVATIVE_COLLECTOR_BOUND,
           "parameter_records": len(params) + len(module_params), "drums_focused_records": len(focused),
           "modules": len(modules), "module_params": len(module_params), "cables": len(cables),
           "midi_fx_params": len(mfx_params), "dx7_voices": len(voices), "audio_fx_slots": APP_FX_SLOTS,
           "au_labels": len(labels), "notes": SEQ_TRACKS * NOTES_PER_TRACK,
           "locks": SEQ_TRACKS * LOCKS_PER_TRACK, "trigs": SEQ_TRACKS * TRIGS_PER_TRACK,
           "set_text_bytes": set_text_bytes, "mod_text_bytes": mod_text_bytes})
