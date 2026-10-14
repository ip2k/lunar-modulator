# SPDX-License-Identifier: MIT
"""Run full packed demo projects through the actual cold-app startup path."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

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
        f"\t$(CXX) $(OPT) $(EXTRA) -Wl,--wrap=lunar_instance_pool_alloc -o $@ $^ -lm\n"
        f"{harness_obj}: {harness}\n\t@mkdir -p $(dir $@)\n"
        f"\t$(CC) $(SIM_CFLAGS) -Istate -I{native} -I{tlsf} -c $< -o $@\n" +
        "".join(
            f"{obj}: {source}\n\t@mkdir -p $(dir $@)\n"
            f"\t$(CC) $(SIM_CFLAGS) -Istate -I{native} -I{tlsf} -c $< -o $@\n"
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
        assert metrics["allocation_failures"] == 0
        assert metrics["active_units"] > 0
        assert metrics["pool_live_allocations"] > 0
    else:
        assert result.returncode == 1, result.stderr + result.stdout
        assert not metrics["passed"] and metrics["report_code"] == 5
        assert metrics["allocation_failures"] == 1
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
    expected_code = 8 if project_id in ("event-horizon-showcase", "packet-bloom-showcase") else 5
    assert metrics["report_code"] == expected_code
    if expected_code in (5, 8):
        assert result.returncode == 1, result.stderr + result.stdout
        assert not metrics["passed"] and metrics["report_code"] in (5, 8)
        assert metrics["allocation_failures"] == (1 if metrics["report_code"] == 5 else 0)
        if metrics["report_code"] == 5:
            assert metrics["report_what"] == "candidate engines cannot coexist with live allocations"
        else:
            assert metrics["report_what"] == "project sequence importer refused content or observed loss"
        expected_request = (
            207728 if project_id == "satellite-hearts" else
            65744 if project_id == "afterglow-relay-showcase" else 31944)
        assert metrics["largest_allocation_request"] == expected_request
        assert metrics["pool_live_bytes"] == metrics["pool_live_allocations"] == 0
        assert metrics["active_units"] == 0
    print(project_id,
          "source_sha256=" + hashlib.sha256(source.read_bytes()).hexdigest(),
          "packed_sha256=" + hashlib.sha256(packed.read_bytes()).hexdigest(),
          "metrics=" + json.dumps(metrics, sort_keys=True),
          "harness_sha256=" + hashlib.sha256(
              (ROOT / "tests/native/demo_app_startup.c").read_bytes()).hexdigest(),
          "build_dir=" + str(build))
