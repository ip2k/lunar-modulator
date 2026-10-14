# SPDX-License-Identifier: MIT
"""Run full packed demo projects through the actual cold-app startup path."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Outcomes are the current, deliberately unchanged 192,000-byte app-probe
# instance pool. Two legacy projects start in this host configuration; two refuse allocation.
PROJECTS = (
    ("afterglow-relay", True),
    ("event-horizon", False),
    ("packet-bloom", True),
    ("neon-transit", False),
)



REPLACEMENT_PROJECTS = (
    "afterglow-relay-showcase",
    "event-horizon-showcase",
    "packet-bloom-showcase",
    "satellite-hearts",
)


def _production_modules(tmp_path):
    from tools.native.module_selection import resolve_modules

    _, catalogue = resolve_modules(ROOT, tmp_path / "module-catalogue", "all")
    modules = [item for item in catalogue["selected"] if not item.startswith("test-")]
    assert len(modules) == 55
    return ",".join(modules)


@pytest.fixture(scope="session")
def startup_tools(tmp_path_factory):
    build_root = tmp_path_factory.mktemp("native-demo-app-startup")
    modules = _production_modules(build_root)
    build = build_root / "engine-build"
    env = os.environ.copy()
    env["FM1_GPL_MODS"] = "1"
    env["FM1_MODULES"] = modules
    env["BUILD"] = str(build)
    subprocess.run([
        "make", "-s", "--no-print-directory", "-C", str(ROOT / "engines"),
        "-f", "Makefile",
        "FM1_GPL_MODS=1", "FM1_MODULES=" + modules, "BUILD=" + str(build),
        str(build / "fm1-state"),
    ], check=True, env=env)

    fragment = build_root / "demo-app.mk"
    native = ROOT / "firmware/native"
    tlsf = ROOT / "firmware/third_party/tlsf"
    harness = ROOT / "tests/native/demo_app_startup.c"
    harness_obj = build / "sim/test/demo_app_startup.o"
    sources = [native / name for name in (
        "project_boot.c", "project_seq.c", "project_engines.c",
        "project_start.c", "project_mod.c", "project_units.c",
        "instance_pool.c", "../third_party/tlsf/tlsf.c",
    )]
    objects = [build / ("demo-native-" + str(i) + ".o") for i in range(len(sources))]
    fragment.write_text(
        f"{build / 'demo-app-startup'}: $(SIM_APP_OBJ) {harness_obj} "
        f"$(SIM_ENGINE_OBJ) $(SIM_META_OBJ) " + " ".join(map(str, objects)) + "\n"
        f"\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n"
        f"{harness_obj}: {harness}\n\t@mkdir -p $(dir $@)\n"
        f"\t$(CC) $(SIM_CFLAGS) -Istate -I{native} -I{tlsf} -c $< -o $@\n" +
        "".join(
            f"{obj}: {source}\n\t@mkdir -p $(dir $@)\n"
            f"\t$(CC) $(SIM_CFLAGS) -Istate -I{native} -I{tlsf} "
            + ("-Dlunar_instance_pool_alloc=lunar_instance_pool_alloc_actual "
               if source.name == "instance_pool.c" else "")
            + "-c $< -o $@\n"
            for obj, source in zip(objects, sources)))
    subprocess.run([
        "make", "-s", "--no-print-directory", "-C", str(ROOT / "engines"),
        "-f", "Makefile", "-f", str(ROOT / "sim/web/mk/sim.mk"),
        "-f", str(fragment), "SIM=" + str(ROOT / "sim/web"),
        "BUILD=" + str(build), "FM1_GPL_MODS=1", "FM1_MODULES=" + modules,
        "CC=" + os.environ.get("FM1_SIM_CC", "cc"),
        "CXX=" + os.environ.get("FM1_SIM_CXX", "c++"),
        "OPT=-O2", "EXTRA=-DFM1_APP_EXTERNAL_ARENAS=1 -I" + str(native),
        "-j4", str(build / "demo-app-startup"),
    ], check=True)
    return build / "fm1-state", build / "demo-app-startup", build


@pytest.mark.parametrize(("project_id", "expected_success"), PROJECTS)
def test_demo_full_app_cold_start(project_id, expected_success,
                                 startup_tools, tmp_path):
    packer, startup, build = startup_tools
    source = ROOT / "engines/state/examples" / (project_id + ".lunar")
    packed = tmp_path / (project_id + ".lunarb")
    subprocess.run([str(packer), "pack", str(source), "-o", str(packed)], check=True)
    result = subprocess.run(
        [str(startup), str(packed)], check=False, capture_output=True, text=True)
    metrics = json.loads(result.stdout)
    assert metrics["seq_tracks"] == 8
    assert metrics["seq_bytes"] <= metrics["seq_capacity"] == 32768
    assert metrics["pool_capacity"] == 192000
    assert metrics["pool_peak_live_bytes"] <= metrics["pool_capacity"]
    assert metrics["pool_live_bytes"] <= metrics["pool_peak_live_bytes"]
    if expected_success:
        assert result.returncode == 0, result.stderr + result.stdout
        assert metrics["passed"] and metrics["report_code"] == 0
        assert metrics["allocation_failures"] == 0, metrics
        assert metrics["active_units"] > 0
        assert metrics["pool_live_allocations"] > 0
    else:
        assert result.returncode == 1, result.stderr + result.stdout
        assert not metrics["passed"] and metrics["report_code"] == 5
        assert metrics["allocation_failures"] == 1
        assert metrics["failed_allocation_request"] == 49888  # Hall master effect
        assert metrics["failed_allocation_attempt"] == 10
        assert metrics["largest_allocation_request"] == 65744
        assert metrics["pool_live_bytes"] == metrics["pool_live_allocations"] == 0
        assert metrics["active_units"] == 0
    print(project_id,
          "source_sha256=" + hashlib.sha256(source.read_bytes()).hexdigest(),
          "packed_sha256=" + hashlib.sha256(packed.read_bytes()).hexdigest(),
          "metrics=" + json.dumps(metrics, sort_keys=True),
          "harness_sha256=" + hashlib.sha256(
              (ROOT / "tests/native/demo_app_startup.c").read_bytes()).hexdigest(),
          "build_dir=" + str(build))



@pytest.mark.parametrize("project_id", REPLACEMENT_PROJECTS)
def test_replacement_showcase_full_app_cold_start(project_id, startup_tools, tmp_path):
    packer, startup, build = startup_tools
    source = ROOT / "engines/state/examples/replacement-showcases" / (project_id + ".lunar")
    packed = tmp_path / (project_id + ".lunarb")
    subprocess.run([str(packer), "pack", str(source), "-o", str(packed)], check=True)
    result = subprocess.run(
        [str(startup), str(packed)], check=False, capture_output=True, text=True)
    metrics = json.loads(result.stdout)
    assert metrics["seq_tracks"] == 8
    assert metrics["seq_bytes"] <= metrics["seq_capacity"] == 32768
    assert metrics["pool_capacity"] == 192000
    assert metrics["pool_peak_live_bytes"] <= metrics["pool_capacity"]
    expected_code = 0 if project_id == "event-horizon-showcase" else 5
    assert metrics["report_code"] == expected_code
    if expected_code == 0:
        assert result.returncode == 0, result.stderr + result.stdout
        assert metrics["passed"]
        assert metrics["allocation_failures"] == 0, metrics
        assert metrics["active_units"] == 6
        assert metrics["pool_live_allocations"] > 0
    else:
        assert result.returncode == 1, result.stderr + result.stdout
        assert not metrics["passed"]
        assert metrics["allocation_failures"] == 1
        assert metrics["report_what"] == "candidate engines cannot coexist with live allocations"
        expected_max_request = {
            "satellite-hearts": 207728,
            "afterglow-relay-showcase": 65744,
            "packet-bloom-showcase": 79344,
        }[project_id]
        expected_failed_request = {
            "satellite-hearts": 207728,  # Shapes engine
            "afterglow-relay-showcase": 49888,  # Hall master effect
            "packet-bloom-showcase": 49888,  # Hall master effect
        }[project_id]
        assert metrics["failed_allocation_request"] == expected_failed_request
        assert metrics["largest_allocation_request"] == expected_max_request
        assert metrics["pool_live_bytes"] == metrics["pool_live_allocations"] == 0
        assert metrics["active_units"] == 0
    print(project_id,
          "source_sha256=" + hashlib.sha256(source.read_bytes()).hexdigest(),
          "packed_sha256=" + hashlib.sha256(packed.read_bytes()).hexdigest(),
          "metrics=" + json.dumps(metrics, sort_keys=True),
          "harness_sha256=" + hashlib.sha256(
              (ROOT / "tests/native/demo_app_startup.c").read_bytes()).hexdigest(),
          "build_dir=" + str(build))


@pytest.fixture(scope="session", params=(12, 8), ids=("shapes12", "shapes8"))
def compressed_startup_tools(request, tmp_path_factory):
    """Build the cold-start fixture with exact generated tables and sanitizers."""
    import importlib.util
    import shutil

    cc, cxx = shutil.which("cc"), shutil.which("c++")
    if not cc or not cxx:
        pytest.skip("no host C/C++ compiler")
    shapes_voices = request.param
    # Linux ASan benefits from a fixed executable mapping; Darwin rejects -no-pie.
    pie_compile = "-fno-pie " if sys.platform.startswith("linux") else ""
    pie_link = "-fno-pie -no-pie " if sys.platform.startswith("linux") else ""
    build_root = tmp_path_factory.mktemp("native-compressed-demo-startup-shapes" + str(shapes_voices))
    modules = _production_modules(build_root)
    build = build_root / "engine-build"
    env = os.environ.copy()
    env["FM1_GPL_MODS"] = "1"
    env["FM1_MODULES"] = modules
    env["BUILD"] = str(build)
    subprocess.run([
        "make", "-s", "--no-print-directory", "-C", str(ROOT / "engines"),
        "-f", "Makefile", "FM1_GPL_MODS=1", "FM1_MODULES=" + modules,
        "BUILD=" + str(build), "EXTRA=-DFM1_SHAPES_VOICES=" + str(shapes_voices),
        str(build / "fm1-state"),
    ], check=True, env=env)

    tools_dir = ROOT / "tools/native"
    sys.path.insert(0, str(tools_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "prepare_wavetables", tools_dir / "prepare_wavetables.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        generated = build_root / "compressed-wave"
        generated.mkdir()
        records = module.prepare(generated)
    finally:
        sys.path.remove(str(tools_dir))

    # Compare every decoded byte with the exact source-derived table. The public
    # symbol names preserve upstream C++ linkage while this fixture substitutes
    # only their storage definitions.
    declarations = ["#include <stddef.h>", "#include <string.h>",
                    "int lunar_wave_tables_init(void);"]
    for relative, symbol, width, size in module.ASSETS:
        namespace = Path(relative).parent.name
        raw = module.asset_bytes((ROOT / relative).read_text(), symbol, width, size)
        declarations.append(
            f"static const unsigned char expected_{namespace}[{len(raw)}] = "
            "{" + ",".join(map(str, raw)) + "};")
        mangled = f'_ZN{len(namespace)}{namespace}{len(symbol)}{symbol}E'
        declarations.append(
            f'extern unsigned char lunar_waves_{namespace}[{size}] '
            f'__asm__("{mangled}");')
    declarations.append(
        "static int compressed_wave_tables_match(void) { return " +
        " && ".join(f"memcmp(lunar_waves_{r['namespace']}, "
                    f"expected_{r['namespace']}, {r['raw_bytes']}u) == 0"
                    for r in records) + "; }")
    (generated / "compressed_wave_expected.h").write_text(
        "\n".join(declarations) + "\n")

    native = ROOT / "firmware/native"
    tlsf = ROOT / "firmware/third_party/tlsf"
    tinf = ROOT / "firmware/third_party/tinf"
    harness = ROOT / "tests/native/demo_app_startup.c"
    harness_obj = build / "sim/test/compressed_demo_app_startup.o"
    native_sources = [native / name for name in (
        "project_boot.c", "project_seq.c", "project_engines.c",
        "project_start.c", "project_mod.c", "project_units.c",
        "instance_pool.c", "../third_party/tlsf/tlsf.c",
        "wave_tables.c", "../third_party/tinf/tinflate.c",
    )]
    native_objects = [build / ("compressed-native-" + str(i) + ".o")
                      for i in range(len(native_sources))]
    wave_objects = [build / "compressed-waves-plaits.o",
                    build / "compressed-waves-braids.o"]
    fragment = build_root / "compressed-demo-app.mk"
    fragment.write_text(
        "SIM_ENGINE_OBJ := $(filter-out $(BUILD)/tp/plaits/resources.o "
        "$(BUILD)/tp/braids/resources.o,$(SIM_ENGINE_OBJ))\n" +
        f"{build / 'compressed-demo-app-startup'}: $(SIM_APP_OBJ) {harness_obj} " +
        "$(SIM_ENGINE_OBJ) $(SIM_META_OBJ) " +
        " ".join(map(str, native_objects + wave_objects)) + "\n" +
        "\t$(CXX) $(OPT) $(EXTRA) -fsanitize=address,undefined " +
        "-fno-omit-frame-pointer " + pie_link + "-o $@ $^ -lm\n" +
        f"{harness_obj}: {harness}\n\t@mkdir -p $(dir $@)\n" +
        "\t$(CC) $(SIM_CFLAGS) -Istate -I" + str(native) + " -I" + str(tlsf) +
        " -I" + str(generated) + " -I" + str(tinf) +
        " -DLUNAR_COMPRESSED_WAVETABLES=1 -DINSTANCE_BYTES=165376u " +
        "-fsanitize=address,undefined -fno-omit-frame-pointer " + pie_compile + "-c $< -o $@\n" +
        "".join(
            f"{obj}: {source}\n\t@mkdir -p $(dir $@)\n"
            "\t$(CC) $(SIM_CFLAGS) -Istate -I" + str(native) + " -I" + str(tlsf) +
            " -I" + str(generated) + " -I" + str(tinf) +
            (" -Dlunar_instance_pool_alloc=lunar_instance_pool_alloc_actual"
             if source.name == "instance_pool.c" else "") +
            " -fsanitize=address,undefined -fno-omit-frame-pointer " + pie_compile + "-c $< -o $@\n"
            for obj, source in zip(native_objects, native_sources)) +
        "".join(
            f"{obj}: {generated / ('resources_' + namespace + '.cc')}\n"
            "\t@mkdir -p $(dir $@)\n"
            "\t$(CXX) -std=c++11 $(OPT) $(EXTRA) -I" + str(generated) +
            " -I" + str(ROOT / "engines/third_party/mutable") +
            " -fsanitize=address,undefined -fno-omit-frame-pointer " + pie_compile + "-c $< -o $@\n"
            for obj, namespace in zip(wave_objects, ("plaits", "braids"))))
    subprocess.run([
        "make", "-s", "--no-print-directory", "-C", str(ROOT / "engines"),
        "-f", "Makefile", "-f", str(ROOT / "sim/web/mk/sim.mk"),
        "-f", str(fragment), "SIM=" + str(ROOT / "sim/web"),
        "BUILD=" + str(build), "FM1_GPL_MODS=1", "FM1_MODULES=" + modules,
        "CC=" + cc, "CXX=" + cxx, "OPT=-O1",
        "EXTRA=-DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_SHAPES_VOICES=" +
        str(shapes_voices) + " -I" + str(native),
        "-j4", str(build / "compressed-demo-app-startup"),
    ], check=True)
    return build / "fm1-state", build / "compressed-demo-app-startup", build, records, shapes_voices


def test_compressed_event_horizon_full_app_cold_start_165376_arena(
        compressed_startup_tools, tmp_path):
    packer, startup, build, records, shapes_voices = compressed_startup_tools
    source = ROOT / "engines/state/examples/replacement-showcases/event-horizon-showcase.lunar"
    packed = tmp_path / "event-horizon-showcase.lunarb"
    subprocess.run([str(packer), "pack", str(source), "-o", str(packed)], check=True)
    result = subprocess.run(
        [str(startup), str(packed)], check=False, capture_output=True, text=True)
    metrics = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    assert metrics["passed"] and metrics["report_code"] == 0
    assert metrics["seq_tracks"] == 8
    assert metrics["seq_bytes"] <= metrics["seq_capacity"] == 32768
    assert metrics["pool_capacity"] == 165376
    assert metrics["pool_peak_live_bytes"] <= metrics["pool_capacity"]
    assert metrics["pool_live_bytes"] <= metrics["pool_peak_live_bytes"]
    assert metrics["allocation_failures"] == 0
    assert metrics["active_units"] == 6
    assert metrics["pool_live_allocations"] > 0
    assert [(r["namespace"], r["raw_bytes"], r["packed_bytes"]) for r in records] == [
        ("plaits", 50688, 32513), ("braids", 33024, 24159)]
    print(json.dumps({
        "project_id": "event-horizon-showcase",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "packed_sha256": hashlib.sha256(packed.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(
            (ROOT / "tests/native/demo_app_startup.c").read_bytes()).hexdigest(),
        "allocation_metrics": metrics,
        "compressed_tables": records,
        "pool_capacity_bytes": 165376,
        "build_dir": str(build),
    }, sort_keys=True))


def test_compressed_satellite_hearts_shapes_voice_profile(
        compressed_startup_tools, tmp_path):
    packer, startup, build, records, shapes_voices = compressed_startup_tools
    source = ROOT / "engines/state/examples/replacement-showcases/satellite-hearts.lunar"
    packed = tmp_path / "satellite-hearts.lunarb"
    subprocess.run([str(packer), "pack", str(source), "-o", str(packed)], check=True)
    result = subprocess.run(
        [str(startup), str(packed)], check=False, capture_output=True, text=True)
    metrics = json.loads(result.stdout)
    assert metrics["pool_capacity"] == 165376
    assert metrics["pool_peak_live_bytes"] <= metrics["pool_capacity"]
    print(json.dumps({"shape_voices": shapes_voices, "metrics": metrics}, sort_keys=True))
    if shapes_voices == 12:
        assert result.returncode == 1, result.stderr + result.stdout
        assert metrics["failed_allocation_request"] == 207728
        assert metrics["largest_allocation_request"] == 207728
        assert metrics["allocation_failures"] == 1
        assert metrics["active_units"] == 0
    else:
        assert shapes_voices == 8
        assert metrics["failed_allocation_request"] == 5072
        assert metrics["largest_allocation_request"] == 139024
        assert metrics["failed_allocation_live_bytes"] == 154352
        assert metrics["allocation_failures"] == 1
        assert metrics["active_units"] == 0
        assert result.returncode == 1, result.stderr + result.stdout
    print(json.dumps({
        "project_id": "satellite-hearts",
        "shapes_voices": shapes_voices,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "packed_sha256": hashlib.sha256(packed.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(
            (ROOT / "tests/native/demo_app_startup.c").read_bytes()).hexdigest(),
        "allocation_metrics": metrics,
        "pool_capacity_bytes": 165376,
        "build_dir": str(build),
    }, sort_keys=True))


SINGLE_ENGINE_SOURCES = {
    "acid-bass": "replacement-showcases/event-horizon-showcase.lunar",
    "comet": "replacement-showcases/satellite-hearts.lunar",
    "crater": "replacement-showcases/packet-bloom-showcase.lunar",
    "drawbar": "replacement-showcases/satellite-hearts.lunar",
    "drums": "afterglow-relay.lunar",
    "dx7": "afterglow-relay.lunar",
    "macro": "afterglow-relay.lunar",
    "macro-heavy": "replacement-showcases/packet-bloom-showcase.lunar",
    "phase-bend": "replacement-showcases/packet-bloom-showcase.lunar",
    "shapes": "replacement-showcases/satellite-hearts.lunar",
    "sixop": "replacement-showcases/event-horizon-showcase.lunar",
    "sw-sophie": "replacement-showcases/packet-bloom-showcase.lunar",
    "trio": "replacement-showcases/event-horizon-showcase.lunar",
}


@pytest.mark.parametrize("engine", tuple(SINGLE_ENGINE_SOURCES))
def test_compressed_single_engine_cold_start_at_eight_shapes_voices(
        engine, compressed_startup_tools, tmp_path):
    packer, startup, build, records, shapes_voices = compressed_startup_tools
    if shapes_voices != 8:
        pytest.skip("individual-engine matrix uses the proposed 8-voice Shapes profile")
    source = ROOT / "engines/state/examples" / SINGLE_ENGINE_SOURCES[engine]
    project = json.loads(source.read_text())
    sound = next(sound for sound in project["sounds"]
                 if sound.get("engine") == engine)
    sound["midi_fx"] = []
    project["sounds"] = [sound]
    project["master"] = [None, None]
    project["mod"]["rack"] = []
    project["mod"]["cables"] = []
    project["set"] = ["movy1"]
    single = tmp_path / ("single-" + engine + ".lunar")
    single.write_text(json.dumps(project, separators=(",", ":")) + "\n")
    packed = tmp_path / ("single-" + engine + ".lunarb")
    subprocess.run([str(packer), "pack", str(single), "-o", str(packed)], check=True)
    result = subprocess.run(
        [str(startup), str(packed)], check=False, capture_output=True, text=True)
    metrics = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    assert metrics["passed"] and metrics["report_code"] == 0
    assert metrics["pool_capacity"] == 165376
    assert metrics["allocation_failures"] == 0
    assert metrics["active_units"] >= 1
    assert metrics["pool_peak_live_bytes"] <= metrics["pool_capacity"]
    assert metrics["pool_live_allocations"] > 0
    assert metrics["largest_allocation_request"] > 0
    print(json.dumps({
        "project_id": "generated-single-" + engine,
        "shapes_voices": shapes_voices,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "packed_sha256": hashlib.sha256(packed.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(
            (ROOT / "tests/native/demo_app_startup.c").read_bytes()).hexdigest(),
        "allocation_metrics": metrics,
        "pool_capacity_bytes": 165376,
        "build_dir": str(build),
    }, sort_keys=True))
