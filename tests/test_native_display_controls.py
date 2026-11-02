"""Offline current-app proof. Products belong to caller-selected pytest basetemp.

No diagnostic startup, HAL, target image, device, or browser is executed.
Run normal and ASan/UBSan with FM1_SIM_CC/CXX/EXTRA on bounded LAN resources.
"""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_current_app_display_controls_offline(tmp_path):
    fragment = tmp_path / "proof.mk"
    fragment.write_text(
        "PROOF := $(abspath ../firmware/native)\n"
        "$(BUILD)/proof/%.o: $(PROOF)/%.c\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -c $< -o $@\n"
        "$(BUILD)/proof/check.o: $(abspath ../tests/fixtures/native_display_controls/check.c)\n"
        "\t@mkdir -p $(dir $@)\n"
        "\t$(CC) $(SIM_CFLAGS) -I$(PROOF) -c $< -o $@\n"
        "$(BUILD)/proof-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) "
        "$(BUILD)/proof/diagnostic_app.o $(BUILD)/proof/diagnostic_display.o $(BUILD)/proof/diagnostic_transport.o "
        "$(BUILD)/proof/check.o\n"
        "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm -pthread\n"
    )
    target = tmp_path / "build/proof-check"
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    extra += (" -DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1"
              " -DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1")
    subprocess.run([
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
        str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={tmp_path / 'build'}",
        "FM1_GPL_MODS=1", "FM1_MODULES=dx7,arp,lfo,env,chance",
        "FM1_DX7_SINE=trunc12", "OPT=-O1", "-j4",
        f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
        f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}", f"EXTRA={extra}", str(target),
    ], check=True)
    result = subprocess.run([str(target)], check=True, text=True,
                            capture_output=True, timeout=90)
    assert "display proof passed" in result.stdout
    print(result.stdout, end="")
