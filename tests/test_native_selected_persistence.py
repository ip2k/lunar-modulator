"""Offline actual selected-app PROJECT stage; no live owner/pause admission."""
import os
import shlex
from pathlib import Path
import subprocess
from tools.native.prepare_selected_project import prepare
ROOT = Path(__file__).resolve().parents[1]


def test_actual_selected_project_stage(tmp_path):
    build = tmp_path / "build"
    prepared = tmp_path / "prepared"
    sources = ["selected_project", "selected_diagnostic_app"]
    fragment = tmp_path / "proof.mk"
    fragment.write_text(
        f"PROOF := {ROOT / 'firmware/native'}\n"
        f"BLOB := {prepared}\n"
        "$(BUILD)/proof/%.o: $(PROOF)/%.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -Istate -I$(BLOB) -c $< -o $@\n"
        f"$(BUILD)/proof/check.o: {ROOT / 'tests/fixtures/selected_persistence/check.c'}\n"
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
        " -DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1 -DLUNAR_SELECTED_INTERACTIVE_PROOF=1 -DLUNAR_SELECTED_PROJECT_STAGE_PROOF=1")
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
            " -DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1 -DLUNAR_SELECTED_INTERACTIVE_PROOF=1 -DLUNAR_SELECTED_PROJECT_STAGE_PROOF=1")
        prep_cmd = [f"EXTRA={prep_extra}" if arg.startswith("EXTRA=") else arg for arg in prep_cmd]
    render, state = prep_build / "fm1-render", prep_build / "fm1-state"
    subprocess.run([*prep_cmd, str(render), str(state)], check=True, timeout=300)
    receipt = prepare(render, state, prepared)
    assert receipt["packed_bytes"] == 597 and not receipt["hardware_admitted"]
    exe = build / "proof-check"
    subprocess.run([*cmd, str(exe)], check=True, timeout=300)
    for mode in ["positive", "1", "2", "3", "4", "5", "6", "7", "8"]:
        result = subprocess.run([str(exe), mode], check=True,
                                text=True, capture_output=True, timeout=60)
        print(result.stdout, end="")
    # ASan enlarges global symbols with redzones. Check allocation/symbol
    # compatibility in the normal build; all runtime cases above stay sanitized.
    if sanitized:
        return
    # Opt-in alone grows the shared cold-reader/stage allocation. Compile the
    # original profile too: its 16-KiB reader and absent stage API must remain.
    default = build / "default.o"
    with fragment.open("a") as out:
        out.write("$(BUILD)/default.o: $(PROOF)/selected_diagnostic_app.c\n"
                  "\t$(CC) $(SIM_CFLAGS) -ULUNAR_SELECTED_PROJECT_STAGE_PROOF "
                  "-ULUNAR_SELECTED_INTERACTIVE_PROOF -ULUNAR_DIAGNOSTIC_OFFLINE_PROOF "
                  "-I$(PROOF) -Istate -I$(BLOB) -c $< -o $@\n")
    subprocess.run([*cmd, str(default)], check=True, timeout=60)
    for obj, expected, exported in [(default, 16384, False),
                                  (build / "proof/selected_diagnostic_app.o", 65536, True)]:
        symbols = subprocess.check_output(["nm", "-S", str(obj)], text=True)
        reader = [line.split() for line in symbols.splitlines()
                  if line.split() and line.split()[-1] == "reader_space"]
        assert len(reader) == 1 and int(reader[0][1], 16) == expected
        assert (" T lunar_selected_interactive_stage" in symbols) == exported

