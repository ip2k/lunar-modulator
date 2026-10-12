"""Native sample-frame insert/master/mixer automation acceptance probe."""
import os
import subprocess

from tests.test_sim_web import ENGINES, SIM, GPL_MODS, tools


def test_native_seq_automation(tools):
    build = tools["sim"].parent
    subprocess.run([
        "make", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
        "-f", str(SIM / "test" / "automation.mk"), f"SIM={SIM}", f"BUILD={build}", f"FM1_GPL_MODS={int(GPL_MODS)}",
        f"EXTRA={os.environ.get('FM1_SIM_EXTRA', '')}",
        f"OPT={os.environ.get('FM1_SIM_OPT', '-O2')}",
        f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
        f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}",
        str(build / "fm1-seq-automation-check"),
    ], check=True, stdout=subprocess.DEVNULL)
    result = subprocess.run([str(build / "fm1-seq-automation-check")],
                            check=True, text=True, capture_output=True)
    assert result.stdout.startswith("PASS sample frames,")
