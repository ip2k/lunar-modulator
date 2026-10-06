"""The virtual FM-1 (sim/web): its app layer renders what fm1-render renders,
sequencer scripts included, every screen passes the layout check, the panel
follows the M-VAVE manual, the page is self-contained, and FM6's user bank
loads DX7 patches from .syx files, refusing what is not one.

The WebAssembly side is built and compared on aeon by sim/web/build-on-aeon.sh
(test/parity.mjs); its results are recorded in sim/web/www/fm1.wasm.json,
which the last tests here read.

Set FM1_SIM_EXTRA (and FM1_SIM_CC / FM1_SIM_CXX / FM1_SIM_OPT) to build the
harness with other flags, e.g. the ASan + UBSan set from engines/README.md;
that build goes to its own directory. So does the build with the GPL switch
off (FM1_GPL_MODS=0, engines/Makefile): native-mit, which
tests/test_gpl_switch.py also builds. A scenario marked "gpl" plays a GPL
module and skips there.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import warnings
from urllib.parse import unquote

import pytest

from tests.engine_helpers import GPL_MODS, ROOT, pitch_hz

SIM = ROOT / "sim" / "web"
ENGINES = ROOT / "engines"
SCENARIOS = json.loads((SIM / "test" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]


@pytest.fixture(scope="session")
def tools():
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    flags = {
        "EXTRA": extra,
        "OPT": os.environ.get("FM1_SIM_OPT", "-O2"),
        "CC": os.environ.get("FM1_SIM_CC", "cc"),
        "CXX": os.environ.get("FM1_SIM_CXX", "c++"),
    }
    tag = hashlib.sha256(json.dumps(flags, sort_keys=True).encode()).hexdigest()[:8]
    build = SIM / "build" / ("native" if not extra and flags["OPT"] == "-O2" else f"native-{tag}")
    if not GPL_MODS:                         # the MIT/BSD build has a directory of its own
        build = build.with_name(build.name + "-mit")
    targets = [build / "fm1-render", build / "fm1-sim-render"]
    subprocess.run(
        ["make", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
         f"SIM={SIM}", f"BUILD={build}", f"FM1_GPL_MODS={int(GPL_MODS)}", "-j4"]
        + [f"{k}={v}" for k, v in flags.items()] + [str(t) for t in targets],
        check=True, stdout=subprocess.DEVNULL)
    return {"render": targets[0], "sim": targets[1]}


def scenario_args(s):
    args = ["--seconds", str(s["seconds"]), "--rate", str(s.get("rate", 44118))]
    args += ["--engine", s["engine"]]
    if "cmd" in s:
        args += ["--cmd", str(SIM / "test" / s["cmd"])]
    if "sysex" in s:
        args += ["--sysex", str(SIM / "test" / s["sysex"])]
    if "load" in s:         # a state file loaded after the setup (stage A1)
        args += ["--load", str((SIM / "test" / s["load"]).resolve())]
    for p in s.get("params", []):
        args += ["--param", p]
    for n in s.get("notes", []):
        args += ["--note", n]
    for b in s.get("bends", []):
        args += ["--bend", b]
    for p in s.get("param_at", []):
        args += ["--param-at", p]
    for fx_id, fx_params in s.get("fx", []):
        args += ["--fx", fx_id]
        for p in fx_params:
            args += ["--fx-param", p]
    for p in s.get("fx_param_at", []):
        args += ["--fx-param-at", p]
    # Multi-sound (docs/15 §3.16): the other sound units, every unit's
    # inserts and levels, and notes on a given unit, as fm1-render takes them.
    for k, sound_id, sound_params in s.get("sounds", []):
        args += ["--sound", f"{k}:{sound_id}"]
        for p in sound_params:
            args += ["--sound-param", f"{k}:{p}"]
    for k, insert_id, insert_params in s.get("inserts", []):
        args += ["--insert", f"{k}:{insert_id}"]
        for p in insert_params:
            args += ["--insert-param", f"{k}:{p}"]
    for lv in s.get("levels", []):
        args += ["--level", lv]
    for n in s.get("sound_notes", []):
        args += ["--sound-note", n]
    if "mod" in s:
        args += ["--mod", str(SIM / "test" / s["mod"])]
    # The arpeggiator (engine API v3's MIDI effects), as fm1-render takes it.
    for k, mfx_id, mfx_params in s.get("mfx", []):
        args += ["--mfx", f"{k}:{mfx_id}"]
        for p in mfx_params:
            args += ["--mfx-param", f"{k}:{p}"]
    for p in s.get("mfx_param_at", []):
        args += ["--mfx-param-at", p]
    for p in s.get("mfx_on_at", []):
        args += ["--mfx-on-at", p]
    return args


def run(tool, args):
    res = subprocess.run([str(tool), *args], check=True, capture_output=True, text=True)
    return json.loads(res.stdout.strip().splitlines()[-1])


def left_channel(wav_bytes):
    data = wav_bytes[44:]
    return [int.from_bytes(data[i:i + 2], "little", signed=True) / 32767.0
            for i in range(0, len(data), 4)]


@pytest.mark.parametrize("s", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_app_renders_what_fm1_render_renders(tools, tmp_path, s):
    """Same engines, same events at the same block boundaries, same bus
    limiter: with MASTER at full gain the app's WAV is fm1-render's, byte for
    byte. The browser runs this layer; parity.mjs checks the WebAssembly build
    of it against fm1-render on aeon. The app always runs multi-sound and
    the default modulation rack; a scenario with one sound, no insert and no
    cable renders as fm1-render's one engine does, to the bit. A scenario
    played on the panel (`panel`) is replayed by fm1-render from what the
    harness logged (--log-cmds and its .args sidecar, which starts with
    --slots), as parity.mjs does; fm1-render's multi-sound flags imply
    --slots. A scenario marked "gpl" plays a GPL module, which the build with
    the GPL switch off leaves out: it skips there."""
    if s.get("gpl") and not GPL_MODS:
        pytest.skip("plays a GPL module; the GPL switch is off")
    ref, app = tmp_path / "ref.wav", tmp_path / "app.wav"
    logs = []
    if "cmd" in s:          # a sequencer script: the event logs must match too
        logs = [tmp_path / "ref.jsonl", tmp_path / "app.jsonl"]
    sim_args = scenario_args(s)
    ref_args = scenario_args(s)
    if "panel" in s:
        sim_args += ["--panel", str(SIM / "test" / s["panel"]), "--log-cmds", str(tmp_path / "c.verbs")]
    arp_logs = [tmp_path / "ref-arp.jsonl", tmp_path / "app-arp.jsonl"]
    summary = run(tools["sim"], sim_args + ["--out", str(app), "--log-mfx", str(arp_logs[1])]
                  + (["--log-events", str(logs[1])] if logs else []))
    if "panel" in s:
        assert summary["replayable"] == 1 and summary["seq_ui_cmds"]
        ref_args = (["--seconds", str(s["seconds"]), "--rate", str(s.get("rate", 44118)),
                     "--cmd", str(tmp_path / "c.verbs")]
                    + (tmp_path / "c.args").read_text().splitlines())
    arps = "--mfx" in ref_args            # the arp played: what it sent must match too
    ref_summary = run(tools["render"], ref_args + ["--out", str(ref)]
                      + (["--log-events", str(logs[0])] if logs else [])
                      + (["--log-mfx", str(arp_logs[0])] if arps else []))
    assert summary["engine"] == s["engine"]
    assert app.read_bytes() == ref.read_bytes()
    if arps:
        assert arp_logs[1].read_bytes() == arp_logs[0].read_bytes()
        assert ref_summary["notes_hung"] == 0 and ref_summary["mfx_dropped"] == 0
        assert ref_summary["mfx_notes_out"] > 0, "the arp played nothing"
    else:
        assert arp_logs[1].read_bytes() == b"", "an arp played in a scenario without one"
    assert summary["peak"] > 0.01, "the scenario makes no sound"
    if logs:
        assert logs[1].read_bytes() == logs[0].read_bytes()
        assert ref_summary["seq_dropped"] == summary["seq_dropped"] == 0
        assert summary["seq_notes_to_engine"] == ref_summary["seq_notes_to_engine"] > 0
        assert summary["seq_locks_to_engine"] == ref_summary["seq_locks_to_engine"]
        assert summary["seq_splits"] == ref_summary["seq_splits"]
        assert summary["seq_lines_left"] == summary["seq_held"] == 0
        header = (SIM / "test" / s["cmd"]).read_text(encoding="utf-8").splitlines()[0]
        assert re.search(r"\bblock=64\b", header), "parity runs at 64-frame blocks"


# ---- The sequencer in the app (docs/15 S2) --------------------------------------------------

RATE = 44118
FIXTURES = ROOT / "tests" / "fixtures" / "movy"


def sim_run(tools, tmp_path, script, *extra, engine="test-sine", name="s", tool="sim"):
    """A verb script through fm1-sim-render (tool="sim") or fm1-render ("render"):
    the summary, the WAV's bytes and the event log."""
    path = tmp_path / f"{name}.verbs"
    path.write_text(script)
    wav, log = tmp_path / f"{name}-{tool}.wav", tmp_path / f"{name}-{tool}.jsonl"
    args = ["--cmd", str(path), "--out", str(wav), "--log-events", str(log)]
    if engine:
        args += ["--engine", engine]
    summary = run(tools[tool], args + list(extra))
    events = [json.loads(line) for line in log.read_text().splitlines()]
    return summary, wav.read_bytes(), events


def test_the_sequencer_fits_its_arena_and_budget(tools, tmp_path):
    """docs/15 §2.6: the 8-track instance (Capture included) fits the 32 KiB
    arena, and with the 272-event buffer (256 until stage S6), the pending
    command record, the UI state's bound and the metronome's click voice it
    stays inside the sequencer's 36,864 B, half of docs/13 §5's 72 KiB.
    fm1_app_t grew by about 36 KB for the sequencer, to 4.9 MB for
    multi-sound's arenas, and by the modulation runtime's memory, a block's
    writes to the effects and the pages' state (docs/16 MG3)."""
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    print(f"sizeof(fm1_app_t) = {z['app_bytes']} B")
    assert z["seq_tracks"] == 8                                   # owner decision O3 (2026-10-02)
    assert (z["seq_bytes_8"], z["seq_bytes_4"]) == (31944, 18120)
    assert z["seq_bytes_8"] <= z["seq_arena"] == 32768
    assert (z["seq_event_bytes"], z["seq_pending_bytes"], z["seq_click_bytes"]) == (3264, 240, 20)
    total = (z["seq_bytes_8"] + z["seq_event_bytes"] + z["seq_pending_bytes"] + z["seq_ui_bytes"]
             + z["seq_click_bytes"])
    assert total == 36492 <= z["seq_budget"] == 36864
    # Multi-sound (docs/15 §3.16): four 512 KiB sound arenas and ten 256 KiB
    # effect arenas (two master slots, two inserts per sound), 4.5 MiB of the
    # module's fixed 8 MiB; fm1_app_t is 4,939,984 B natively (clang, 64-bit).
    assert (z["sounds"], z["inserts"], z["master_slots"], z["units"]) == (4, 2, 2, 14)
    assert z["arena_bytes"] == 4 * 512 * 1024 + 10 * 256 * 1024
    assert z["app_bytes"] <= 4_960_000
    assert z["mod_bytes"] <= z["mod_arena"]
    assert z["seq_need"] == 201 <= z["seq_events"] == 272
    assert z["seq_ui_size"] <= z["seq_ui_bytes"]
    script = f"#! rate={RATE} block=64 tracks=8 end=6400\n@0 tog 0 0 60 100\n@0 play\n"
    for tracks, size in ((8, 31944), (4, 18120)):
        s, _, _ = sim_run(tools, tmp_path, script, "--tracks", str(tracks), name=f"t{tracks}")
        assert s["seq_bytes"] == size
        r, _, _ = sim_run(tools, tmp_path, script, "--tracks", str(tracks), name=f"t{tracks}",
                          tool="render")
        fixed = z["seq_pending_bytes"] + z["seq_ui_bytes"] + z["seq_click_bytes"] + z["mod_bytes"]
        assert s["ram"] == r["instance_bytes"] + size + 3264 + fixed, "the RAM figure counts the sequencer"


def full_load(stop_at, tracks=8):
    """8 tracks, each an 8-note chord on step 0 held for most of the bar, all
    8 lanes locked away from their base, every track on the engine: 64 gates
    and 64 lanes, both full. A stop then sends 128 events at once."""
    lines = [f"#! rate={RATE} block=64 tracks={tracks} end={stop_at * 2 + 640}"]
    for t in range(tracks):
        chord = " ".join(f"{48 + 3 * t + k} 100" for k in range(8))
        lines.append(f"@0 tog {t} 0 {chord};slen {t} 0 0 -1 380;route {t} 1 0")
        lines.append("@0 " + ";".join(f"alabel {t} {lane} synth:L{lane};aset {t} {lane} 0 100 1"
                                      for lane in range(8)))
    lines.append("@0 play")
    return lines


def test_a_burst_of_transport_lines_keeps_every_note_off(tools, tmp_path):
    """The event-room rule (fm1_seq_host.h) on script lines: stop, play and a
    restart in one gap at full load. The stop's 128 events leave less room
    than another op may need (201 of 256), so the rest waits a block, and
    nothing is dropped; a final stop leaves nothing sounding."""
    stop_at = 8192
    script = "\n".join(full_load(stop_at) + [f"@{stop_at} stop", f"@{stop_at} play",
                                             f"@{stop_at} play", f"@{stop_at * 2} stop"]) + "\n"
    log = tmp_path / "cmds.verbs"
    s, _, ev = sim_run(tools, tmp_path, script, "--log-cmds", str(log))
    assert s["seq_dropped"] == 0 and s["seq_lines_left"] == 0
    assert s["seq_sounding"] == 0 and s["seq_notes_to_engine"] == 128
    applied = [line for line in log.read_text().splitlines() if line.startswith("@")]
    assert applied[-4:] == [f"@{stop_at} stop", f"@{stop_at + 64} play", f"@{stop_at + 64} play",
                            f"@{stop_at * 2} stop"]
    assert len([e for e in ev if e["kind"] == "off"]) == 128


def test_the_room_rule_holds_back_what_would_be_dropped(tools, tmp_path):
    """A stop at full load (128 events) and 128 audible lane bases (`abase`,
    one lock each) in one gap: fm1-render with the app's 256 events drops
    some; the app applies ops only while 201 are free, carries the rest of
    the line to the next blocks, and drops nothing."""
    stop_at = 8192
    bases = ";".join(f"abase {t} {lane} {20 + lane}" for t in range(8) for lane in range(8))
    script = "\n".join(full_load(stop_at) + [f"@{stop_at} stop", f"@{stop_at} {bases};{bases}"]) + "\n"
    r, _, _ = sim_run(tools, tmp_path, script, "--events", "256", tool="render")
    assert r["seq_dropped"] > 0
    s, _, ev = sim_run(tools, tmp_path, script)
    assert s["seq_dropped"] == 0 and s["seq_lines_left"] == 0 and s["seq_sounding"] == 0
    blocks = sorted({e["block"] for e in ev if e["kind"] == "cc" and e["block"] >= stop_at // 64})
    assert len(blocks) >= 2, "the bases went out over more than one block"


def test_typed_commands_wait_for_room(tools, tmp_path):
    """The UI's path (fm1_app_seq_cmd): stop, play and a restart sent in one
    gap at full load. The stop applies; the play no longer fits and is held
    in the pending record; the restart finds the record full (BUSY) and is
    sent again after the render. Both go in at the next block's start, in
    order, and nothing is dropped or left sounding."""
    stop_at = 8192
    script = "\n".join(full_load(stop_at) + [f"@{stop_at * 2} stop"]) + "\n"
    t = f"{(stop_at - 32) / RATE:.9f}"      # mid-block, so rounding cannot move it
    s, _, _ = sim_run(tools, tmp_path, script, "--seq-ui", f"{t}:stop", "--seq-ui", f"{t}:play",
                      "--seq-ui", f"{t}:play")
    assert (s["seq_held"], s["seq_busy"], s["seq_ui_left"]) == (1, 1, 0)
    assert s["seq_ui_frames"] == [stop_at, stop_at + 64, stop_at + 64]
    assert s["seq_dropped"] == 0 and s["seq_sounding"] == 0


TWO_TRACKS = (f"#! rate={RATE} block=64 tracks=4 end={RATE}\n"
              "@0 tog 0 0 84 100;tog 0 4 86 100;tog 1 2 76 100\n@0 play\n")


@pytest.mark.parametrize("routes,engine_tracks", [
    ([], {0}),                                            # the default route
    (["--route", "1:engine"], {1}),                       # a --route replaces it
    (["--route", "0:midi:1"], set()),
    (["--route", "0:engine", "--route", "1:engine"], {0, 1}),
])
def test_routes_play_the_engine_as_in_fm1_render(tools, tmp_path, routes, engine_tracks):
    """Track 0 plays the engine with no route given; --route and `route`
    verbs choose otherwise, and the app agrees with fm1-render on every
    note, event and sample."""
    for k, script in enumerate([TWO_TRACKS, TWO_TRACKS.replace("@0 play", "@0 route 2 1 0;play")]):
        r, rwav, rev = sim_run(tools, tmp_path, script, *routes, name=f"r{k}", tool="render")
        s, swav, sev = sim_run(tools, tmp_path, script, *routes, name=f"r{k}")
        want = engine_tracks | ({2} if k else set())
        ons = [e for e in sev if e["kind"] == "on"]
        assert s["seq_notes_to_engine"] == r["seq_notes_to_engine"] == \
            len([e for e in ons if e["track"] in want])
        assert (swav, sev) == (rwav, rev)


@pytest.mark.parametrize("extra,engine_tracks", [("", {0}), ("rt 2 1 0\n", {2}),
                                                 ("rt 0 0 5\n", set())])
def test_an_imported_set_keeps_its_routes(tools, tmp_path, extra, engine_tracks):
    """A set's own `rt` lines are its routing; a set without them plays track
    0 on the engine, by the default-route rule (an import first puts every
    track back on USB-MIDI channel t+1). --seq alone plays from the start."""
    path = tmp_path / "set.movy1"
    path.write_text((FIXTURES / "movy-chains.movy1").read_text() + extra)
    out = {}
    for tool, blocks in (("render", ["--frames", "64"]), ("sim", [])):   # a set alone: 128
        wav, log = tmp_path / f"{tool}.wav", tmp_path / f"{tool}.jsonl"
        out[tool] = (run(tools[tool], ["--seq", str(path), "--engine", "macro", "--seconds", "2",
                                       "--out", str(wav), "--log-events", str(log), *blocks]),
                     wav.read_bytes(), log.read_text())
    s, r = out["sim"][0], out["render"][0]
    ev = [json.loads(line) for line in out["sim"][2].splitlines()]
    assert s["seq_notes_to_engine"] == r["seq_notes_to_engine"] == \
        len([e for e in ev if e["kind"] == "on" and e["track"] in engine_tracks])
    assert out["sim"][1:] == out["render"][1:]
    assert s["seq_dropped"] == 0


HELD = (f"#! rate={RATE} block=64 tracks=2 end={RATE}\n"
        "@0 tog 0 0 60 100 64 100;slen 0 0 0 -1 380;tog 1 0 67 100;slen 1 0 0 -1 380;route 1 1 0\n"
        "@0 play\n")


@pytest.mark.parametrize("hook", [None, ["--seq-reset", "0.3:4"], ["--seq-import", "0.3:SET"],
                                  ["--select", "0.3:0:test-sine"]])
def test_a_reset_import_or_new_sound_leaves_no_note_hanging(tools, tmp_path, hook):
    """Three sequencer notes sound on the engine for most of a bar. Recreating
    the instance or importing a set mid-note emits no event, so the app
    releases the sequencer's notes itself; so does a change of sound. The
    engine is silent from then on (Test Sine holds a note until its
    note-off), and nothing counts as sounding."""
    empty = tmp_path / "empty.movy1"
    empty.write_text("movy1\nbpm 12000\n")
    extra = [a.replace("SET", str(empty)) for a in hook] if hook else []
    s, wav, _ = sim_run(tools, tmp_path, HELD, *extra)
    left = left_channel(wav)
    tail = left[int(0.32 * RATE):]
    assert s["seq_notes_to_engine"] == 3
    if hook:
        assert s["seq_sounding"] == 0
        assert max(abs(v) for v in tail) == 0
    else:
        assert s["seq_sounding"] == 3 and max(abs(v) for v in tail) > 0.1


def test_scenarios_cover_every_engine_effect_and_page(tools):
    """scenarios.json promises that every engine and effect appears at least
    once, so parity.mjs checks each in the browser's module. A sound engine's
    page past the first is covered when some scenario sets one of its
    parameters (Macro's page 3, the envelope and gate, needs a scenario that
    moves it)."""
    res = subprocess.run([str(tools["render"]), "--list"], check=True,
                         capture_output=True, text=True)
    catalog = json.loads(res.stdout)
    used = {s["engine"] for s in SCENARIOS} | {fx for s in SCENARIOS for fx, _ in s.get("fx", [])}
    used |= {m for s in SCENARIOS for _, m, _ in s.get("mfx", [])}       # the MIDI effects
    missing = sorted(e["id"] for e in catalog if e["id"] not in used)
    assert not missing, f"no parity scenario uses {missing}"
    set_names = {}
    for s in SCENARIOS:
        names = set_names.setdefault(s["engine"], set())
        for p in s.get("params", []) + [p.split(":", 1)[1] for p in s.get("param_at", [])]:
            names.add(p.split("=", 1)[0])
    for e in catalog:
        if e["kind"] != "sound" or e["id"] not in ("macro", "macro-heavy"):
            continue
        last_page = max(p["page"] for p in e["params"])
        on_last = {p["name"] for p in e["params"] if p["page"] == last_page}
        assert on_last & set_names.get(e["id"], set()), \
            f"no scenario sets a parameter on {e['id']}'s page {last_page + 1}"


def test_scenarios_turn_every_effect_mid_render(tools):
    """Every effect has a knob turned while a note sounds (`fx_param_at`,
    T:K:NAME=VALUE for the scenario's K-th effect: fm1-render
    --fx-param-at), so parity covers its glides and switches, not only its
    settings at the start. Each turn names an effect in the scenario's chain
    and one of its parameters, inside the run and after the first note, so
    there is sound (a note or its tail) going through."""
    res = subprocess.run([str(tools["render"]), "--list"], check=True,
                         capture_output=True, text=True)
    catalog = {e["id"]: e for e in json.loads(res.stdout)}
    turned = set()
    for s in SCENARIOS:
        first_on = min((float(n.split(":")[0]) for n in s.get("notes", [])), default=None)
        for p in s.get("fx_param_at", []):
            t, k, nv = p.split(":", 2)
            fx_id = s["fx"][int(k) - 1][0]
            names = {q["name"] for q in catalog[fx_id]["params"]}
            assert nv.split("=", 1)[0] in names, f"{s['name']}: {fx_id} has no {nv}"
            assert 0 < float(t) < s["seconds"], f"{s['name']}: {p} outside the run"
            assert first_on is not None and float(t) > first_on, f"{s['name']}: {p} before any note"
            turned.add(fx_id)
    missing = sorted(e for e, v in catalog.items() if v["kind"] == "audio_fx" and e not in turned)
    assert not missing, f"no parity scenario turns {missing} mid-render"


def test_fx_param_at_turns_an_effect_at_its_time(tools, tmp_path):
    """fm1-render and the app's harness apply --fx-param-at at the block
    boundary, through the effect's set_param, as --param-at for the sound."""
    base = ["--engine", "shapes", "--note", "0:57:100:0.5", "--seconds", "0.3",
            "--fx", "test-gain", "--fx", "fold"]
    for tool in ("render", "sim"):
        flat, turned = tmp_path / f"{tool}-a.wav", tmp_path / f"{tool}-b.wav"
        run(tools[tool], base + ["--fx-param", "Fold=0.4", "--out", str(flat)])
        run(tools[tool], base + ["--fx-param-at", "0.1:2:Fold=0.9", "--out", str(turned)])
        a, b = left_channel(flat.read_bytes()), left_channel(turned.read_bytes())
        first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
        assert first is not None and first >= int(0.1 * 44118) - 64, (tool, first)
    for bad in ("0.1:3:Fold=1", "0.1:0:Fold=1", "0.1:2:Nope=1", "0.1:Fold=1"):
        res = subprocess.run([str(tools["render"]), *base, "--fx-param-at", bad],
                             capture_output=True, text=True)
        assert res.returncode != 0, bad


def test_every_screen_passes_the_layout_check(tools, tmp_path):
    """Every page of every engine (HOME) and effect (on both master slots),
    at defaults, minima, maxima and each list entry, the global page and
    every popup (the refusals, the SAVE stub and an emptied slot
    included), every ARP page at its extremes and list entries with its
    popups (the arp on and off, a preset, Latch), and every list popup at
    every entry (ALGORITHM through each
    sound's list, Six-Op FM's 96 patches the longest, PRESETS through the
    engines, ALGORITHM in FX mode through the effects, the kind picker and
    the destination picker), each one's window checked: no text off screen or cut short, and no two labels, or a
    label and a bar, closer than 4 px (FM1_APP_LAYOUT_GAP). SEQ mode's Track view:
    empty, the demo pattern, the playhead on its first and last step, 20 and
    300 BPM playing and stopped, a four-bar clip, a loop inside it, a track
    with no clip, popups over it, and the hint line with every sound's every
    knob at its extremes and list entries, and every model; the harness
    also checks there that PLAY/STOP and SEQ light their LEDs, and that HOME,
    FX and GLO leave SEQ mode.
    Step entry (docs/15 S4): the grid's marks, SHIFT's legend and the full
    velocity popup, every bar of a 16-bar clip and an empty one, the Step
    pages with every field at its minimum and maximum, every length,
    probability and condition, the nudge at both ends, a 12-note chord,
    SHIFT's legend on a hold, sixteen steps held and the REC status, with
    the gestures that reach them checked on the way. Record and Capture
    (S5): the count-in and the take, step record's head on an empty clip,
    a chord, a tie, SHIFT's hint and the head in every bar of a 16-bar
    clip, Capture's toasts, a stopped Capture's picker and fitted tempo,
    and both overlays at their extremes (one to three candidates from 20 to
    300 BPM, tempos from 20 to 300 BPM), over SEQ mode and HOME. Tracks
    (S6): the status line's eight tracks, each focused and muted, the
    focus and Capture toasts, the mute map, SHIFT's legend with its states
    at both ends, the Set page at its extremes, the Clip page at every speed
    and its other extremes, with no clip, the Track page routed to each
    sound unit (the longest name), past them and to every MIDI channel,
    and Track page 2 with eight tracks' lane labels, none to eight, the
    longest cut to fit, bases 0 to 127. Locks (S8): the lock pages with no
    lane, one and eight, every sound engine's pages locked at both ends and
    laned without a lock, the toasts, SHIFT and CLEAR held, several steps
    held, another sound's lock pages, a lock on every grid step, a live
    take's hint and a spaced label on Track page 2.
    Multi-sound (docs/15 §3.16): FX mode's five slots, every effect as an
    insert at its extremes, the grab, the Mix page with one to four sounds
    and their levels, every sound as Sound 2 in HOME, the Mix page and SEQ
    mode, an empty current sound, the SHIFT + PRESETS and PRESETS popups,
    the RAM meter low, high and past the budget (a full chain beside a
    one-track sequencer, then eight tracks), and its refusals from PRESETS
    and ALGORITHM.
    Then modulation's pages (docs/16 MG3): RACK at every position and page,
    each kind at its extremes and list entries, routed and not, the kind
    picker and a grab; every sound's and effect's pages with a cable on each
    parameter (the marker, bracket and live tick); the gesture's popups;
    MATRIX with 0, 1, 7 and 32 slots, both pages, a refused, an off, a
    delayed and a per-voice row, every field's hint and the destination
    picker; CHAIN through each slot; MATRIX over racks of all sixteen kinds
    and over cables into every sound unit, insert and master slot, the
    target picker from Sound 2, with every short name checked unique; and
    the LEDs and the buttons that leave the pages. Per voice (MG9): RACK's
    `vN` with a chord held, MATRIX's per-voice and refused rows and every
    state's hint, one sound's note sources and the per-sound pitches, and
    a cable an engine change switched off under its old name.
    The audit's proposals in the app (2026-10-06): a knob on every list
    parameter of every sound and effect, from both ends (its list in MID,
    or no popup for a short one), banners over HOME, FX with four rows,
    GLO and MATRIX in both faces, a refusal kept whole, and FX mode's chip
    on each slot, held and not. Every text box is in one of the three
    faces at its height, nothing smaller than SMALL; the summary counts
    them by face."""
    res = subprocess.run([str(tools["sim"]), "--screens", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    summary = json.loads(res.stdout)
    assert summary["faults"] == 0
    assert summary["text_boxes"]["MID"] > 0              # the lists, context lines and banners
    assert summary["screens"] >= 3680            # 335 before S3, 815 before S4, 914 before fx pack 2,
    #                                              1016 before S5, 1055 before multi-sound and S6, 1266 before S8,
    #                                              1321 before the master-bus pack (1458), 2189 with modulation
    #                                              (docs/16 MG3) before Room, Hall, Gate and Plate's Freeze, 2325
    #                                              with them and 2366 with Comb and Test Ext (engine API v3), in
    #                                              the lab switch's two sets of screens; 2695 before every
    #                                              list popup's every entry, 3040 before FM6's user bank,
    #                                              Squash and Transient (all 2026-10-06), 3144 with them;
    #                                              3165 with per-voice modulation (MG9) too, 3204
    #                                              with the knobs' lists, banners and FX chips;
    #                                              3202 with MATRIX's nine rows (its 32
    #                                              slots take one window fewer a sweep: 6 screens
    #                                              fewer) and the strip by sound and tempos with
    #                                              decimals (4 more), 3408 with glide's pages;
    #                                              3507 with the global Key page (97 screens) and
    #                                              its two lists; 3543 with glide's own page on
    #                                              Shapes, Six-Op FM and FM6, Drums' fourth page
    #                                              and the Voice Mode keys; 3642 with both;
    #                                              3680 with Session and the Song page (S9+, 38)
    assert (tmp_path / "home-macro-p1.ppm").stat().st_size == 15 + 240 * 240 * 3


def test_font_header_is_current():
    subprocess.run(["python3", str(SIM / "tools" / "gen_font.py"), "--check"], check=True)



@pytest.mark.parametrize("engine", ["macro", "macro-heavy", "shapes", "sixop", "dx7"])
def test_shift_mono_and_poly_set_the_voice_mode(tools, tmp_path, engine):
    """SHIFT (SEL held) with MONO (C#5, key 20) or POLY (D#5, key 22), their
    printed labels, outside SEQ mode: the current sound's Voice Mode
    (engines/src/glide.h; owner, 2026-10-06). MONO sets Mono, and pressed on
    Mono, Legato; POLY sets Poly. Neither key then plays: two overlapping
    notes afterwards play as with the Voice Mode set as a parameter, byte
    for byte. Without SHIFT, MONO plays its note as before."""
    later = ["--key", "1.0:0:100:0.6", "--key", "1.2:4:100:0.6"]

    def go(name, panel, params=()):
        wav = tmp_path / f"{name}.wav"
        args = ["--engine", engine, "--seconds", "2.2", "--out", str(wav)] + later + list(panel)
        for prm in params:
            args += ["--param", prm]
        summary = run(tools["sim"], args)
        return summary, wav.read_bytes()

    def shift(t, key):
        return ["--button", f"{t}:SEL:0.3", "--key", f"{t + 0.1}:{key}:100:0.05"]
    assert go("mono", shift(0.1, 20))[1] == go("mono-ref", [], ["Voice Mode=1"])[1]
    assert go("legato", shift(0.1, 20) + shift(0.5, 20))[1] == go("legato-ref", [], ["Voice Mode=2"])[1]
    poly = go("poly", shift(0.1, 20) + shift(0.5, 22))[1]
    assert poly == go("poly-ref", [])[1] != go("mono-ref", [], ["Voice Mode=1"])[1]
    played = go("played", ["--key", "0.1:20:100:0.3"])[1]
    assert played != go("plain", [])[1]                     # no SHIFT: MONO is a key


def test_shift_mono_on_a_sound_without_voice_mode(tools, tmp_path):
    """Drums has no Voice Mode: SHIFT + MONO changes nothing and plays
    nothing, and the screen says so."""
    wav, plain = tmp_path / "d.wav", tmp_path / "p.wav"
    hits = ["--key", "0.5:0:100:0.1", "--key", "0.6:2:100:0.1"]
    run(tools["sim"], ["--engine", "drums", "--seconds", "1.0", "--out", str(wav),
                       "--button", "0.1:SEL:0.3", "--key", "0.2:20:100:0.05"] + hits)
    run(tools["sim"], ["--engine", "drums", "--seconds", "1.0", "--out", str(plain)] + hits)
    assert wav.read_bytes() == plain.read_bytes()


@pytest.mark.parametrize("engine", ["sw-sophie", "drums"] + (["comet", "crater"] if GPL_MODS else []))
@pytest.mark.parametrize("key,peak", [(0, True), (1, False), (2, True), (26, True)])
def test_pad_kits_play_their_pads_on_the_white_keys_at_any_octave(tools, engine, key, peak):
    """A pad kit (an engine with pad_count, fm1_engine.h: Sophie, Drums and,
    with the GPL switch on, Comet Kit and Crater Kit)
    only answers MIDI notes 36-51, below the keys' range (53-79 at octave
    0). With a kit as the sound the 16 white keys play pads 1-16 and the
    black keys play nothing, at any octave; other engines are unchanged."""
    for panel in ([], ["--button", "0.05:OCT+:0.02"], ["--button", "0.05:OCT-:0.02"]):
        summary = run(tools["sim"], ["--engine", engine, "--seconds", "0.7",
                                     "--key", f"0.1:{key}:110:0.3", *panel])
        assert (summary["peak"] > 0.05) is peak


# The FM-1's 27 keys run F3..G5: white keys F G A B C D E, from key 0.
WHITE_KEYS = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]
BLACK_KEYS = [k for k in range(27) if k not in WHITE_KEYS]


@pytest.mark.parametrize("white", range(16))
def test_a_white_key_plays_the_pad_a_drum_note_plays(tools, tmp_path, white):
    """White key w (F3, G3, A3, B3, C4... from key 0) plays pad w + 1, byte
    for byte what its MIDI note at MIDI IN plays: all sixteen, B3 (key 6)
    and the last octave's F and G included."""
    key = WHITE_KEYS[white]
    a, b = tmp_path / "key.wav", tmp_path / "midi.wav"
    run(tools["sim"], ["--engine", "drums", "--seconds", "0.5", "--out", str(a),
                       "--key", f"0.1:{key}:100:0.2"])
    run(tools["sim"], ["--engine", "drums", "--seconds", "0.5", "--out", str(b),
                       "--note", f"0.1:{36 + white}:100:0.2"])
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("engine,note,lit", [
    ("drums", 38, 4),       # the snare at MIDI IN lights A3, the key that plays it
    ("drums", 60, None),    # a note the kit ignores lights nothing (it lit C4)
    ("macro", 60, 7),       # a pitched sound: C4, as before
])
def test_a_key_lights_while_the_note_it_plays_sounds(tools, engine, note, lit):
    s = run(tools["sim"], ["--engine", engine, "--seconds", "0.3", "--note", f"0.1:{note}:100:0.5"])
    assert [k for k in range(27) if s["leds"][k] == "1"] == ([] if lit is None else [lit])


def test_a_pad_kits_black_keys_are_silent(tools):
    """All eleven black keys play nothing on a pad kit."""
    keys = [arg for i, k in enumerate(BLACK_KEYS)
            for arg in ("--key", f"{0.05 + 0.04 * i:.2f}:{k}:110:0.03")]
    summary = run(tools["sim"], ["--engine", "drums", "--seconds", "0.7", *keys])
    assert summary["peak"] == 0

@pytest.mark.parametrize("panel,note", [
    ([], 53),                                             # key 0 is F3 (manual p.10)
    (["--button", "0:OCT+"], 65),                         # one octave up
    (["--button", "0:OCT-", "--button", "0.05:OCT-"], 29),
    (["--button", "0:OCT+:0.2", "--turn", "0.1:ALGORITHM:3"], 68),   # OCT+ held: transpose
    (["--button", "0:OCT+", "--button", "0.05:OCT+:0.2", "--button", "0.1:OCT-"], 53),  # both: reset
])
def test_panel_keys_follow_the_manual(tools, tmp_path, panel, note):
    """note = key position + 53 + 12 x octave + transpose; OCT-/OCT+ shift an
    octave, ALGORITHM with an OCT button held transposes, both buttons reset."""
    wav = tmp_path / "k.wav"
    summary = run(tools["sim"], ["--engine", "test-sine", "--seconds", "1.0", "--out", str(wav),
                                 "--key", "0.3:0:100:0.6", *panel])
    expected = 440.0 * 2 ** ((note - 69) / 12)
    assert pitch_hz(left_channel(wav.read_bytes()), 0.5, 0.3) == pytest.approx(expected, rel=0.003)
    assert summary["sounding"] == 0


def test_buttons_and_encoders(tools, tmp_path):
    """PRESETS steps the sound, FX mode (opening on the master slot M1) and
    ALGORITHM pick the effect in the selected slot, SELECT walks M1's pages
    (Plate has two: its knobs and Freeze) and then moves to M2, KNOB1 turns
    a parameter there."""
    s = run(tools["sim"], ["--engine", "macro", "--seconds", "0.2",
                           "--turn", "0:PRESETS:1",
                           "--button", "0:FX", "--turn", "0.01:ALGORITHM:1",
                           "--turn", "0.02:SELECT:2", "--turn", "0.03:ALGORITHM:2",
                           "--turn", "0.04:KNOB1:10"])
    assert s["engine"] == "shapes"
    assert s["mode"] == 1
    assert s["fx"] == ["plate", "ensemble"]
    assert s["values2"][0] == pytest.approx(0.6)          # Ensemble Mix 0.5 + 10 x 0.01
    assert s["leds"][27 + 2] == "1"                       # the FX LED
    g = run(tools["sim"], ["--engine", "macro", "--seconds", "0.2", "--button", "0:GLO",
                           "--turn", "0.01:ALGORITHM:3"])
    assert g["mode"] == 2 and g["values0"][0] == 3        # GLO page; ALGORITHM = Model


# ---- The sequencer on the panel (docs/15 S3) ----------------------------------------------

PATTERN = "#! rate=44118 block=64 tracks=8 end={end}\n@0 tog 0 0 60 100;tog 0 4 64 100;tog 0 8 67 100\n"
WHITE = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]   # white key n -> key index


def pattern_run(tools, tmp_path, seconds, *panel):
    script = tmp_path / "pattern.verbs"
    script.write_text(PATTERN.format(end=int(seconds * 44118)))
    return run(tools["sim"], ["--engine", "test-sine", "--cmd", str(script), *panel])


def test_play_lights_its_led_while_playing(tools, tmp_path):
    playing = pattern_run(tools, tmp_path, 0.6, "--button", "0.1:PLAY/STOP")
    assert playing["leds"][27 + 12] == "1" and playing["seq_view"]["playing"] == 1
    stopped = pattern_run(tools, tmp_path, 0.6, "--button", "0.1:PLAY/STOP", "--button", "0.4:PLAY/STOP")
    assert stopped["leds"][27 + 12] == "0" and stopped["seq_view"]["playing"] == 0
    assert [t for _, t in stopped["seq_ui_cmds"]] == ["play", "stop"]


def test_seq_opens_seq_mode(tools, tmp_path):
    s = pattern_run(tools, tmp_path, 0.3, "--button", "0.1:SEQ")
    assert s["mode"] == 3 and s["leds"][27 + 11] == "1" and s["popup"] == []
    home = pattern_run(tools, tmp_path, 0.3, "--button", "0.1:SEQ", "--button", "0.2:HOME")
    assert home["mode"] == 0 and home["leds"][27 + 11] == "0"


@pytest.mark.parametrize("seconds", [0.30, 0.55, 0.80, 1.05, 1.30, 1.55, 1.80, 2.05])
def test_key_leds_follow_the_playhead_in_seq_mode(tools, tmp_path, seconds):
    """In SEQ mode the white keys show the bar: a step with a note lit, the
    playhead's step inverted; the playhead moves on with the transport."""
    s = pattern_run(tools, tmp_path, seconds, "--button", "0.05:SEQ", "--button", "0.1:PLAY/STOP")
    v = s["seq_view"]
    assert v["clip_playing"] == 1
    head = v["step"] % 16
    expected = {0, 4, 8} ^ {head}
    lit = {n for n in range(16) if s["leds"][WHITE[n]] == "1"}
    assert lit == expected
    assert v["key_leds"] == sum(1 << n for n in expected)
    # 120 BPM: a step is 0.125 s from the block PLAY went in at (frame 4416);
    # the run ends 0.6 of a step into one, so rounding cannot move it.
    assert head == int((seconds * 44118 - 4416) / 44118 * 8) % 16


def test_home_key_leds_are_unchanged(tools, tmp_path):
    """Outside SEQ mode the sequencer's notes light no key (owner decision
    O6): HOME's key LEDs while the pattern plays are those of a run where
    nothing plays, the keys held and nothing else."""
    playing = pattern_run(tools, tmp_path, 0.7, "--button", "0.1:PLAY/STOP", "--key", "0.2:5:100:0.4")
    still = pattern_run(tools, tmp_path, 0.7, "--key", "0.2:5:100:0.4")
    assert playing["mode"] == still["mode"] == 0
    assert playing["leds"][:27] == still["leds"][:27] == "0" * 27
    held = pattern_run(tools, tmp_path, 0.5, "--button", "0.1:PLAY/STOP", "--key", "0.2:5:100:0.4")
    assert held["leds"][:27] == "0" * 5 + "1" + "0" * 21
    assert playing["seq_notes_to_engine"] > 0 and still["seq_notes_to_engine"] == 0


def test_a_new_sound_clears_the_track_views_knob_hint(tools):
    """The Track view's hint line names the knob last turned for two
    seconds. PRESETS loads another sound, whose knob of that number nobody
    turned, so the hint gives way to the model line at once."""
    base = ["--engine", "macro", "--seconds", "0.6", "--button", "0.05:SEQ",
            "--turn", "0.1:KNOB2:5"]
    assert run(tools["sim"], base)["seq_view"]["knob"] == 1
    s = run(tools["sim"], base + ["--turn", "0.3:PRESETS:1"])
    assert s["engine"] != "macro" and s["mode"] == 3 and s["seq_view"]["knob"] == -1


def test_emptying_a_slot_returns_to_its_one_page(tools):
    """The Effect 2 dropdown's "(none)" on PSX Verb's second page: the empty
    slot shows page 1 of 1, not "2/1" (the select path used to keep the page).
    FX mode opens on M1 (slot 3 of In1, In2, Mix, M1, M2)."""
    s = run(tools["sim"], ["--engine", "macro", "--fx", "plate", "--fx", "sw-psxverb",
                           "--seconds", "0.1", "--button", "0:FX", "--turn", "0.01:SELECT:2",
                           "--select", "0.03:2:-"])
    assert s["fx"] == ["plate", ""]
    assert (s["fx_slot"], s["fx_page"]) == (4, 0)


# ------------------------------------------------- FM6's user bank (DX7) --
#
# The page's "Load DX7 patches" (app.js, worklet.js, fm1w_dx7_load) runs
# fm1_app_dx7_load and fm1_app_dx7_play, which the harness runs natively
# with --sysex and --sysex-play: the same C code, checked here on the Mac;
# test/sysex.mjs checks the module's export itself on aeon, recorded in
# fm1.wasm.json. The files are this repository's own (tools/dx7_bank.py
# --test-bank), or edits of them.

DX7 = SIM / "test" / "dx7"
VCED = 163


def test_dx7_test_files_are_what_the_tool_makes():
    """The original test bank: 32 voices of our own, LUNAR 01 to 32, as one
    bank dump and as 32 single-voice dumps; never Yamaha's."""
    subprocess.run([sys.executable, str(ROOT / "tools" / "dx7_bank.py"), "--test-bank", "--check"], check=True)


def dx7_run(tools, tmp_path, files, *extra, engine="dx7"):
    args = ["--seconds", "0.2", "--out", str(tmp_path / "x.wav")]
    if engine:
        args += ["--engine", engine]
    for k, data in enumerate(files):
        flag = "--sysex"
        if isinstance(data, tuple):
            flag, data = data
        path = tmp_path / f"f{k}.syx"
        path.write_bytes(data)
        args += [flag, str(path)]
    return run(tools["sim"], args + list(extra))


def lunar(k):
    return f"LUNAR {k + 1:02d}"


def bank():
    return (DX7 / "lunar-test-bank.syx").read_bytes()


def single(k):
    return (DX7 / "lunar-test-voices.syx").read_bytes()[k * VCED:(k + 1) * VCED]


def test_a_bank_fills_the_user_slots_with_their_names(tools, tmp_path):
    s = dx7_run(tools, tmp_path, [bank()])
    f = s["dx7"]["files"][0]
    assert (f["result"], f["voices"], f["first_slot"], f["messages"], f["bad_checksums"], f["raw"]) == \
        (32, 32, 0, 1, 0, 0)
    assert s["dx7"]["names"] == [lunar(k) for k in range(32)]
    assert s["popup"] == ["Loaded 32 voices", "User 1-32", "LUNAR 01"]


def test_turning_algorithm_names_the_loaded_voice(tools, tmp_path):
    """The Patch list shows the loaded voices' names: ALGORITHM from User 9
    to User 10 puts up the Patch list with LUNAR 10 chosen, among its
    neighbours' names."""
    s = dx7_run(tools, tmp_path, [bank()], "--param", "Patch=40", "--turn", "0.05:ALGORITHM:1")
    lst = s["popup_list"]
    assert (lst["title"], lst["total"]) == ("Patch", 64)
    assert s["popup"][lst["mark"]] == "LUNAR 10"
    assert s["popup"] == [lunar(k) for k in range(lst["first"] - 32, lst["first"] - 32 + len(s["popup"]))]
    assert s["values0"][0] == 41


@pytest.mark.parametrize("case", ["empty", "text", "foreign", "cut-short", "short-dump", "count",
                                  "too-big"])
def test_what_is_not_a_dx7_dump_loads_nothing_and_says_why(tools, tmp_path, case):
    """Each refusal is counted where the page can name it, and the bank,
    loaded before, stays as it was."""
    files = {
        "empty": b"",
        "text": b"LUNAR MODULATOR, not a patch\n" * 4,
        "foreign": bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]),
        "cut-short": bank()[:3000],
        "short-dump": single(0)[:100] + single(0)[101:],
        "count": single(0)[:5] + bytes([0x1A]) + single(0)[6:],
        "too-big": single(0) * 403,
    }
    s = dx7_run(tools, tmp_path, [bank(), files[case]])
    f = s["dx7"]["files"][1]
    want = {"empty": (0, 0, 0, 0, 0), "text": (0, 0, 0, 0, 116), "foreign": (0, 1, 0, 0, 0),
            "cut-short": (0, 0, 1, 0, 0), "short-dump": (0, 0, 0, 1, 0), "count": (0, 0, 0, 1, 0),
            "too-big": (-1, 0, 0, 0, 0)}[case]
    assert (f["result"], f["foreign"], f["truncated"], f["wrong_size"], f["outside"]) == want
    assert f["voices"] == 0
    assert s["dx7"]["names"] == [lunar(k) for k in range(32)]
    assert s["popup"] == ["No DX7 voices", "file too large" if case == "too-big" else "in that file"]


def test_a_wrong_checksum_loads_and_is_counted(tools, tmp_path):
    """As the keyboards' editors do (engines/msfa.md): stored all the same;
    the page says the file may be damaged."""
    v = bytearray(single(6))
    v[161] ^= 1
    s = dx7_run(tools, tmp_path, [bytes(v)])
    f = s["dx7"]["files"][0]
    assert (f["result"], f["bad_checksums"]) == (1, 1) and s["dx7"]["names"][0] == lunar(6)


def test_single_voices_follow_each_other_and_a_bank_starts_again(tools, tmp_path):
    s = dx7_run(tools, tmp_path, [single(4), single(9), bank(), single(2), bank()[6:6 + 4096]])
    firsts = [f["first_slot"] for f in s["dx7"]["files"]]
    assert firsts == [0, 1, 0, 0, 0]
    assert s["dx7"]["files"][4]["raw"] == 1
    s = dx7_run(tools, tmp_path, [single(4), single(9), bank(), single(2)])
    assert s["dx7"]["names"][:3] == [lunar(2), lunar(1), lunar(2)]
    assert s["dx7"]["next"] == 1


def test_several_dumps_and_other_messages_in_one_file(tools, tmp_path):
    data = single(3) + bytes([0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]) + single(8) + b"xy" + single(5)[:50]
    f = dx7_run(tools, tmp_path, [data])["dx7"]["files"][0]
    assert (f["result"], f["messages"], f["foreign"], f["truncated"], f["outside"]) == (2, 2, 1, 1, 2)


def test_the_app_plays_the_bank_as_fm1_render_does(tools, tmp_path):
    """User 2, 7 and 32 of the test bank, through the app's bank and
    through fm1-render --sysex: the same samples (also a parity scenario,
    dx7-user-bank, against the browser's module)."""
    args = ["--engine", "dx7", "--sysex", str(DX7 / "lunar-test-bank.syx"), "--param", "Patch=33",
            "--param-at", "0.3:Patch=38", "--param-at", "0.6:Patch=63", "--note", "0:60:100:0.25",
            "--note", "0.3:64:100:0.25", "--note", "0.6:67:110:0.3", "--seconds", "1.0"]
    a, b = tmp_path / "app.wav", tmp_path / "render.wav"
    s = run(tools["sim"], args + ["--out", str(a)])
    subprocess.run([str(tools["render"]), *args, "--out", str(b)], check=True, capture_output=True)
    assert a.read_bytes() == b.read_bytes() and s["peak"] > 0.01


def test_load_and_play_makes_the_current_sound_fm6(tools, tmp_path):
    """What the page does after a load (fm1_app_dx7_play): Macro gives way
    to FM6 on the first voice loaded, and it sounds."""
    s = dx7_run(tools, tmp_path, [single(0), ("--sysex-play", single(11) + single(12))],
                "--note", "0.02:60:110:0.15", engine="macro")
    assert s["engine"] == "dx7" and s["values0"][0] == 33 and s["peak"] > 0.01
    assert s["dx7"]["files"][1]["played"] == 0 and s["dx7"]["names"][1] == lunar(11)


def test_an_fm6_made_after_a_load_plays_the_bank(tools, tmp_path):
    """The bank stands for voices kept in flash: a sound that becomes FM6
    later gets them when it is created."""
    path = DX7 / "lunar-test-bank.syx"
    later = run(tools["sim"], ["--engine", "macro", "--sysex", str(path), "--select", "0:0:dx7",
                               "--turn", "0.01:ALGORITHM:52", "--note", "0.05:60:100:0.2",
                               "--seconds", "0.4", "--out", str(tmp_path / "a.wav")])
    first = run(tools["sim"], ["--engine", "dx7", "--sysex", str(path), "--turn", "0.01:ALGORITHM:52",
                               "--note", "0.05:60:100:0.2", "--seconds", "0.4", "--out", str(tmp_path / "b.wav")])
    assert later["engine"] == "dx7" and later["values0"][0] == 52 and later["peak"] > 0.01
    assert later["popup_list"]["title"] == "Patch"
    assert later["popup"][later["popup_list"]["mark"]] == "LUNAR 21"
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()
    assert first["peak"] == later["peak"]


def test_the_modules_sysex_export_passed_its_checks():
    """build.sh runs test/sysex.mjs on the module it records: every case of
    the export (loads, refusals and their reasons, play, the voices'
    samples) passed."""
    record = json.loads((SIM / "www" / "fm1.wasm.json").read_text(encoding="utf-8"))
    sysex = record["dx7_sysex"]
    assert sysex["failed"] == 0 and sysex["passed"] >= 18
    assert all(c["pass"] for c in sysex["cases"])


def test_a_sound_that_refuses_the_rate_is_stepped_over(tools):
    """Above 47,872 Hz the Plaits-based sounds (Macro, Macro Heavy, Six-Op)
    refuse the host. PRESETS steps over them and says why; a refused load
    puts the previous sound back with its values instead of leaving silence.
    FM6, next in the list, runs at the host's rate."""
    up = run(tools["sim"], ["--engine", "shapes", "--rate", "48000", "--seconds", "0.1",
                            "--turn", "0:PRESETS:1"])
    assert up["engine"] == "dx7"
    assert up["popup"] == ["Macro Heavy", "refuses 48000 Hz"]
    down = run(tools["sim"], ["--engine", "shapes", "--rate", "48000", "--seconds", "0.1",
                              "--turn", "0:PRESETS:-1"])
    assert down["engine"] == "test-sine"
    kept = run(tools["sim"], ["--engine", "shapes", "--param", "Timbre=0.8", "--rate", "48000",
                              "--seconds", "0.3", "--select", "0.1:0:macro",
                              "--key", "0.15:0:100:0.1"])
    assert kept["engine"] == "shapes"
    assert kept["values0"][1] == pytest.approx(0.8)
    assert kept["peak"] > 0.01
    at_plaits_rate = run(tools["sim"], ["--engine", "shapes", "--rate", "47872", "--seconds", "0.1",
                                        "--turn", "0:PRESETS:1"])
    assert at_plaits_rate["engine"] == "macro-heavy"


def test_page_is_self_contained():
    """No CDN, nothing fetched from another origin, every reference relative:
    the page works from a local static server and can be published as static
    files, at any path, over http://localhost or https. Its fonts are its own
    files (fonts/)."""
    www = SIM / "www"
    for f in www.iterdir():
        if f.suffix in (".html", ".js", ".mjs", ".css"):
            # The SVG namespace is an identifier, never fetched.
            text = f.read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", "")
            assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}/", text, re.I), f.name
    html = (www / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"#]+)"', html)
    css = (www / "style.css").read_text(encoding="utf-8")
    refs += re.findall(r'url\("?([^")]+)"?\)', css)
    for ref in refs:
        assert not ref.startswith("/"), f"{ref} is not relative"
        assert (www / unquote(ref)).is_file(), ref   # browsers percent-decode: Exo2%5Bwght%5D.ttf
    for name in ("worklet.js", "fm1-wasm.mjs", "fm1.wasm"):
        assert (www / name).exists(), name
    # The worklet and the module are found next to app.js, wherever it is.
    app = (www / "app.js").read_text(encoding="utf-8")
    assert "new URL(name, import.meta.url)" in app
    assert "addModule(asset('worklet.js'))" in app and "fetch(asset('fm1.wasm'))" in app


# Git blob hashes of google/fonts' ofl/audiowide files (main, 2026-10-01):
# the font must stay unmodified, since a subset or any other change is a
# Modified Version that the SIL OFL's Reserved Font Name clause forbids
# calling "Audiowide".
FONTS = {
    "audiowide/Audiowide-Regular.ttf": "8b50bedc0f99bcfcb5686a3dbeb5b51d1c0190d5",
    "audiowide/OFL.txt": "19bb4adffab57778a892f98e9552441208896226",
    "exo2/Exo2[wght].ttf": "9cb20188a07687580312d2099e6c79ca8ecb7b58",
    "exo2/OFL.txt": "5bec9840d2e0df42d80d6fac55279d1d5e5b9199",
}


def test_fonts_are_unmodified_and_licensed():
    fonts = SIM / "www" / "fonts"
    for rel, blob in FONTS.items():
        data = (fonts / rel).read_bytes()
        assert hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == blob, rel
    for font in fonts.rglob("*.ttf"):
        assert (font.parent / "OFL.txt").is_file(), font
        assert str(font.relative_to(fonts)) in FONTS, f"{font} has no recorded hash"


def test_wasm_exports_match_the_web_layer():
    exported = set(re.findall(r"^\S.*?\b(fm1w_\w+)\(", (SIM / "src" / "fm1_web.c").read_text(encoding="utf-8"), re.M))
    mk = (SIM / "mk" / "sim.mk").read_text(encoding="utf-8")
    listed = set(re.findall(r"\bfm1w_\w+", mk.split("WASM_EXPORTS :=")[1].split("comma")[0]))
    assert exported == listed


def test_the_staleness_gate_covers_what_the_module_links():
    """fm1.wasm links the sequencer core and bridge and the modulation
    runtime with its kinds and script reader, and the parity record covers
    the sequencer and modulation scripts: a change to any of them makes the
    module stale (a CI failure), not only a warning (docs/15 §6.5)."""
    sys.path.insert(0, str(SIM / "tools"))
    try:
        from source_hash import sim_files
    finally:
        sys.path.pop(0)
    hashed = {p.relative_to(ROOT).as_posix() for p in sim_files(ROOT)}
    for s in SCENARIOS:
        for key in ("cmd", "panel", "mod", "sysex"):
            if key in s:
                assert f"sim/web/test/{s[key]}" in hashed, s["name"]
    want = [p.relative_to(ROOT).as_posix() for p in (ENGINES / "seq").glob("*.[ch]")]
    want += ["engines/include/fm1_seq.h", "engines/include/fm1_seq_host.h"]
    want += [p.relative_to(ROOT).as_posix() for p in (ENGINES / "mod").rglob("*.[ch]")]
    want += ["engines/include/fm1_mod.h", "engines/include/fm1_mod_host.h",
             "engines/host/mod_script.c", "engines/host/mod_script.h"]
    # The MIDI effects and their host stage (engine API v3): the arp.
    want += [p.relative_to(ROOT).as_posix() for p in (ENGINES / "midi_fx").glob("*.[ch]")]
    want += ["engines/include/fm1_mfx_host.h", "engines/include/fm1_midi_ev.h", "engines/seq/mfx_host.c"]
    # The metadata export's writer and tables, whose id the module returns
    # (fm1w_meta_id; stage ED0), and the check of that id.
    want += ["engines/state/fm1_meta.c", "engines/state/fm1_known.c", "engines/state/fm1_num.c",
             "engines/state/fm1_num.h", "engines/include/fm1_meta.h", "engines/src/editor_meta.cc",
             "engines/include/fm1_engine_meta.h", "engines/include/fm1_refusal.h",
             "engines/include/fm1_tele.h", "sim/web/test/meta.mjs"]
    assert want and not [w for w in want if w not in hashed]
    assert "engines/mod/README.md" not in hashed, "documentation never makes the module stale"


def test_committed_wasm_matches_its_build_record():
    """build-on-aeon.sh writes fm1.wasm.json next to the module: its hash, the
    hashes of the sources it was built from, and the parity results.

    When sim/web's own inputs (src/, mk/, build.sh, the parity test) have
    changed since, the module is stale: a warning locally, a failure in CI
    (CI=true), so a pull request that changes the simulator carries its
    rebuilt module. When only engines/ has changed, CI warns too: engine
    work elsewhere should not need aeon, but rebuild before the module is
    published."""
    record = json.loads((SIM / "www" / "fm1.wasm.json").read_text(encoding="utf-8"))
    wasm = (SIM / "www" / "fm1.wasm").read_bytes()
    assert hashlib.sha256(wasm).hexdigest() == record["wasm_sha256"]
    parity = record["parity"]
    assert parity["failed"] == 0 and parity["passed"] >= len(SCENARIOS)
    assert record["imports"] == []
    names = {s["name"]: s for s in record["scenarios"]}
    for s in SCENARIOS:
        if "cmd" in s and s["name"] in names:
            assert names[s["name"]]["seq"]["lines_match"] and names[s["name"]]["seq"]["dropped"] == 0
    assert all("@sha256:" in i for i in record["images"]) and len(record["images"]) >= 2
    current = source_hashes()
    stale = [k for k in ("engines", "sim") if current[k] != record["sources_sha256"].get(k)]
    if "sim" in stale and os.environ.get("CI") == "true":
        pytest.fail("sim/web changed since www/fm1.wasm was built; rebuild it with "
                    "sim/web/build-on-aeon.sh and commit www/fm1.wasm and fm1.wasm.json")
    if stale:
        warnings.warn(f"sim/web/www/fm1.wasm was built from other {' and '.join(stale)} "
                      "sources than these; rebuild with sim/web/build-on-aeon.sh")


def source_hashes():
    """The hashes build-on-aeon.sh records (sim/web/tools/source_hash.py)."""
    res = subprocess.run(["python3", str(SIM / "tools" / "source_hash.py"), str(ROOT)],
                         check=True, capture_output=True, text=True)
    return json.loads(res.stdout)
