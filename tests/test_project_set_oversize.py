"""PROJECT saves retain the complete set or refuse before emitting any bytes.

Products live only in the caller-selected pytest temporary directory. Optional
FM1_PROJECT_SET_BASELINE_SOURCE proves old refusal failure and valid-byte parity.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_project_set_oversize(tmp_path):
    if not shutil.which("make") or not shutil.which("c++"):
        pytest.skip("native compiler unavailable")
    baseline = os.environ.get("FM1_PROJECT_SET_BASELINE_SOURCE")
    results = []
    for name in (["baseline", "fixed"] if baseline else ["fixed"]):
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
            "$(BUILD)/project-set-check: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(BUILD)/project-set-check.o\n"
            "\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n"
            "$(BUILD)/project-set-check.o: $(SIM)/test/fm1_project_set_oversize_check.c\n"
            "\t$(CC) $(SIM_CFLAGS) -Istate -Ihost -c $< -o $@\n"
            "$(BUILD)/c/seq/seq_persist.o: SEQ_CFLAGS += -Dfm1_seq_export_movy1=fm1_real_seq_export_movy1\n" + state_rule
        )
        target = build / "project-set-check"
        subprocess.run([
            "make", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
            str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
            f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=1",
            "FM1_MODULES=test-sine,test-gain,arp,lfo,env,calc,register,chance", "-j4",
            f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
            f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}",
            f"EXTRA={os.environ.get('FM1_SIM_EXTRA', '')}", str(target),
        ], check=True, stdout=subprocess.DEVNULL)
        valid = subprocess.check_output([str(target), "--valid"], text=True, timeout=180)
        print(name, valid, flush=True)
        results.append(valid)
        run = subprocess.run([str(target)], text=True, capture_output=True, timeout=180)
        print(name, run.stdout, run.stderr, flush=True)
        assert "ERROR: AddressSanitizer" not in run.stderr and "runtime error:" not in run.stderr
        if name == "baseline":
            assert run.returncode != 0 and "ok=1 code=0 calls=1" in run.stdout
        else:
            assert run.returncode == 0
    assert len(set(results)) == 1, results
