"""Fixed selected-Trio offline builder plan and actual host startup proof."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

from tools.native.prepare_selected_project import prepare

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fixed_diagnostic_builder", ROOT / "tools/native/build_diagnostic.py"
)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def test_fixed_build_plans_keep_default_fm6_unchanged(tmp_path):
    default = BUILDER.diagnostic_plan()
    assert default == dict(
        modules="dx7,arp,lfo,env,chance",
        extra=[ROOT / "firmware/native/diagnostic_app.c",
               ROOT / "firmware/native/diagnostic_platform.c",
               ROOT / "firmware/native/diagnostic_crt0.S",
               ROOT / "firmware/third_party/dinghy/hal/fm1_vec.S",
               ROOT / "firmware/third_party/dinghy/hal/fm1_isr.S"],
        stem="lunar-diagnostic", profile="sdk-free-single-fm6-diagnostic-v1",
        arena_bytes=65536,
    )
    with pytest.raises(ValueError, match="freshly prepared"):
        BUILDER.diagnostic_plan(selected=True)
    selected = BUILDER.diagnostic_plan(selected=True, prepared=tmp_path)
    assert selected["modules"] == "trio"
    assert selected["profile"] == "sdk-free-selected-trio-offline-diagnostic-v1"
    assert selected["arena_bytes"] == 16384
    assert selected["extra"][:3] == [
        ROOT / "firmware/native/selected_diagnostic_app.c",
        ROOT / "firmware/native/selected_project.c",
        tmp_path / "selected_project_blob.c",
    ]
    assert BUILDER.manifest(True)["tools/native/build_selected_trio_diagnostic.py"] == \
        BUILDER.digest(ROOT / "tools/native/build_selected_trio_diagnostic.py")


def test_selected_startup_consumes_generated_blob_and_matches_current_app(tmp_path):
    build = tmp_path / "build"
    prepared = tmp_path / "prepared"
    rules = tmp_path / "selected.mk"
    rules.write_text("\n".join([
        f"NATIVE := {ROOT / 'firmware/native'}",
        f"PREPARED := {prepared}",
        "$(BUILD)/selected/selected_diagnostic_app.o: $(NATIVE)/selected_diagnostic_app.c",
        "\t@mkdir -p $(dir $@)",
        "\t$(CC) $(SIM_CFLAGS) -I$(NATIVE) -I$(PREPARED) -Istate -c $< -o $@",
        "$(BUILD)/selected/selected_project.o: $(NATIVE)/selected_project.c",
        "\t@mkdir -p $(dir $@)",
        "\t$(CC) $(SIM_CFLAGS) -I$(NATIVE) -Istate -c $< -o $@",
        "$(BUILD)/selected/selected_project_blob.o: $(PREPARED)/selected_project_blob.c",
        "\t@mkdir -p $(dir $@)",
        "\t$(CC) $(SIM_CFLAGS) -I$(PREPARED) -c $< -o $@",
        f"$(BUILD)/selected/check.o: {ROOT / 'tests/fixtures/selected_diagnostic/check.c'}",
        "\t@mkdir -p $(dir $@)",
        "\t$(CC) $(SIM_CFLAGS) -I$(NATIVE) -I$(PREPARED) -Istate -c $< -o $@",
        "$(BUILD)/selected-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) "
        "$(BUILD)/selected/selected_diagnostic_app.o $(BUILD)/selected/selected_project.o "
        "$(BUILD)/selected/selected_project_blob.o $(BUILD)/selected/check.o",
        "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm -pthread",
        "",
    ]))
    command = [
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile",
        "-f", str(ROOT / "sim/web/mk/sim.mk"), "-f", str(rules),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={build}",
        "FM1_MODULES=trio", "FM1_GPL_MODS=1", "FM1_DX7_SINE=trunc12",
        "OPT=-O1", "EXTRA=-DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1",
        "-j4",
    ]
    renderer = build / "fm1-render"
    tool = build / "fm1-state"
    subprocess.run([*command, str(renderer), str(tool)], check=True, timeout=300)
    receipt = prepare(renderer, tool, prepared)
    assert receipt["parameters"] == 14 and receipt["packed_bytes"] == 597
    subprocess.run([*command, str(build / "selected-check")], check=True, timeout=300)
    subprocess.run([str(build / "selected-check")], check=True, timeout=30)
