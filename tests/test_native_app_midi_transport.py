# SPDX-License-Identifier: MIT
"""Exercise MIDI transport FIFO behavior through the real native app layer."""
import os
from pathlib import Path
import subprocess

from tests.test_sim_web import tools  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim" / "web"
ENGINES = ROOT / "engines"


def test_app_midi_transport_fifo(tools, tmp_path):
    build = Path(tools["sim"]).parent
    harness = ROOT / "tests" / "native" / "app_midi_transport.c"
    harness_obj = build / "sim" / "test" / "app_midi_transport.o"
    executable = build / "app-midi-transport-test"
    fragment = tmp_path / "app-midi-transport.mk"
    fragment.write_text(
        f"{executable}: $(SIM_APP_OBJ) {harness_obj} $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) $(SEQ_HOST_OBJ)\n"
        f"\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n"
        f"{harness_obj}: {harness}\n"
        f"\t@mkdir -p $(dir $@)\n"
        f"\t$(CC) $(SIM_CFLAGS) -Istate -Ihost -I{ROOT / 'firmware/native'} "
        f"-c $< -o $@\n",
        encoding="utf-8",
    )
    flags = {
        "EXTRA": os.environ.get("FM1_SIM_EXTRA", ""),
        "OPT": os.environ.get("FM1_SIM_OPT", "-O2"),
        "CC": os.environ.get("FM1_SIM_CC", "cc"),
        "CXX": os.environ.get("FM1_SIM_CXX", "c++"),
    }
    command = [
        "make", "-s", "--no-print-directory", "-C", str(ENGINES),
        "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"), "-f", str(fragment),
        f"SIM={SIM}", f"BUILD={build}",
    ] + [f"{key}={value}" for key, value in flags.items()] + ["-j4", str(executable)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    result = subprocess.run([str(executable)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "app MIDI transport FIFO: PASS"
