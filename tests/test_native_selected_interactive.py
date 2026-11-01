"""Fixed selected-Trio actual-app owner oracle. Host only; owned build products."""
import os
import shlex
from pathlib import Path
import subprocess
from tools.native.prepare_selected_project import prepare
ROOT = Path(__file__).resolve().parents[1]


def test_actual_selected_owner(tmp_path):
    build = tmp_path / "build"
    prepared = tmp_path / "prepared"
    sources = ["selected_project", "selected_diagnostic_app", "selected_interactive_owner",
               "selected_interactive_platform", "diagnostic_spi_model", "diagnostic_display",
               "diagnostic_transport"]
    fragment = tmp_path / "proof.mk"
    fragment.write_text(
        f"PROOF := {ROOT / 'firmware/native'}\n"
        f"BLOB := {prepared}\n"
        "$(BUILD)/proof/%.o: $(PROOF)/%.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -Istate -I$(BLOB) -c $< -o $@\n"
        f"$(BUILD)/proof/check.o: {ROOT / 'tests/fixtures/selected_interactive/check.c'}\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -Istate -I$(BLOB) -I$(PROOF)/../third_party/dinghy/hal -Wno-unused-function -c $< -o $@\n"
        "$(BUILD)/proof/blob.o: $(BLOB)/selected_project_blob.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(BLOB) -c $< -o $@\n"
        "$(BUILD)/proof-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) "
        + " ".join(f"$(BUILD)/proof/{s}.o" for s in sources)
        + " $(BUILD)/proof/blob.o $(BUILD)/proof/check.o\n"
        "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm -pthread\n")
    extra = os.environ.get("FM1_SIM_EXTRA", "") + (
        " -DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1"
        " -DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1 -DLUNAR_SELECTED_INTERACTIVE_PROOF=1")
    cmd = ["make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
           str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
           f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_MODULES=trio",
           "FM1_GPL_MODS=1", "FM1_DX7_SINE=trunc12", "OPT=-O1", "-j4",
           f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
           f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}", f"EXTRA={extra}"]
    # Sanitized short-lived packing CLI retains its output allocation at exit.
    # Keep preparation separate: every app/reader/Trio/proof object below still
    # uses the full requested sanitizer flags and leak detection remains on.
    flags = shlex.split(os.environ.get("FM1_SIM_EXTRA", ""))
    sanitized = any(f.startswith("-fsanitize=") for f in flags)
    prep_build = tmp_path / "prep-build" if sanitized else build
    prep_cmd = [f"BUILD={prep_build}" if arg == f"BUILD={build}" else arg for arg in cmd]
    if sanitized:
        prep_flags = [f for f in flags if not f.startswith("-fsanitize=")
                      and f != "-fno-omit-frame-pointer"]
        prep_extra = " ".join(prep_flags) + (
            " -DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1"
            " -DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1 -DLUNAR_SELECTED_INTERACTIVE_PROOF=1")
        prep_cmd = [f"EXTRA={prep_extra}" if arg.startswith("EXTRA=") else arg for arg in prep_cmd]
    render, state = prep_build / "fm1-render", prep_build / "fm1-state"
    subprocess.run([*prep_cmd, str(render), str(state)], check=True, timeout=300)
    receipt = prepare(render, state, prepared)
    assert receipt["packed_bytes"] == 597 and not receipt["hardware_admitted"]
    exe = build / "proof-check"
    subprocess.run([*cmd, str(exe)], check=True, timeout=300)
    frame = tmp_path / "selected-trio.ppm"
    for mode in ["positive", "overflow", "spi-fault", "repeat", "scan-fail", "audio-fail", "bad-config"]:
        result = subprocess.run([str(exe), mode, str(frame)], check=True,
                                text=True, capture_output=True, timeout=60)
        print(result.stdout, end="")
    assert frame.stat().st_size == 240 * 240 * 3 + len(b"P6\n240 240\n255\n")
