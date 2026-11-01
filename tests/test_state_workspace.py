"""Explicit state scratch preserves bytes/PCM and rejects unsafe ownership.

All generated products live in pytest's caller-selected temporary directory;
release checks select a lane-owned --basetemp and remove it after recording logs.
FM1_WORKSPACE_BASELINE_SOURCE optionally compares an exact pre-change state TU.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_state_workspace_equivalence_and_guards(tmp_path):
    if not shutil.which("make") or not shutil.which("c++"):
        pytest.skip("native compiler unavailable")
    configs = [("host", 0), ("external", 1), ("compact", 1)]
    baseline = os.environ.get("FM1_WORKSPACE_BASELINE_SOURCE")
    if baseline:
        configs.insert(0, ("baseline", 0))
    results = []
    for name, external in configs:
        build = tmp_path / name
        fragment = tmp_path / f"{name}.mk"
        state_rule = ""
        if name == "baseline":
            state_rule = (
                "$(BUILD)/sim/src/fm1_app_state.o: " + str(Path(baseline).resolve()) + "\n"
                "\t@mkdir -p $(dir $@)\n"
                "\t$(CC) $(SIM_CFLAGS) -c $< -o $@\n"
            )
        fragment.write_text(
            "$(BUILD)/workspace-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(BUILD)/workspace-check.o\n"
            "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n"
            "$(BUILD)/workspace-check.o: $(SIM)/test/fm1_state_workspace_check.c\n"
            "\t$(CC) $(SIM_CFLAGS) -Istate -Ihost -c $< -o $@\n" + state_rule
        )
        extra = os.environ.get("FM1_SIM_EXTRA", "")
        extra += f" -DFM1_APP_STATE_EXTERNAL_WORKSPACE={external}"
        extra += f" -DFM1_APP_EXTERNAL_ARENAS={int(name == 'compact')}"
        extra += f" -DFM1_WORKSPACE_BASELINE={int(name == 'baseline')}"
        target = build / "workspace-check"
        subprocess.run([
            "make", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
            str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
            f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=1",
            "FM1_MODULES=test-sine,test-gain,arp,lfo,env,calc,register,chance", "-j4",
            f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
            f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}", f"EXTRA={extra}", str(target),
        ], check=True, stdout=subprocess.DEVNULL)
        results.append(subprocess.check_output([str(target)], text=True, timeout=180).strip())
    assert len(set(results)) == 1, results
