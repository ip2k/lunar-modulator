"""Execute the actual patched CMake target selector without building firmware."""

import os
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PIN = "a7fb5e8ac692c528f8ed29e325911a3f4b8111d6"
PATCH = ROOT / "tools/fm1-transporter/0003-fixed-return-r01-rom-mode.patch"


@pytest.fixture
def patched_selector(tmp_path):
    source = os.environ.get("FM1_TRANSPORTER_SOURCE")
    if not source:
        pytest.skip("set FM1_TRANSPORTER_SOURCE to the pinned local upstream checkout")
    upstream = Path(source).resolve(strict=True)
    subprocess.run(["git", "-C", str(upstream), "cat-file", "-e", f"{PIN}^{{commit}}"], check=True)
    cmake = subprocess.check_output(
        ["git", "-C", str(upstream), "show", f"{PIN}:CMakeLists.txt"]
    )
    (tmp_path / "CMakeLists.txt").write_bytes(cmake)
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(["git", "apply", "--include=CMakeLists.txt", str(PATCH)],
                   cwd=tmp_path, check=True)
    patched = (tmp_path / "CMakeLists.txt").read_text()
    selector = re.search(
        r"function\(fm1t_add_firmware TARGET\)\s*(.*?)\s*add_executable\(\$\{TARGET\}",
        patched, re.DOTALL,
    )
    assert selector, "actual patched target selector missing"
    return tmp_path, selector.group(1)


@pytest.mark.parametrize("target,proto,log", [
    ("fm1_transporter_return_r01", "src/return_r01_proto.c", "src/return_r01_log_stub.c"),
    ("fm1_transporter", "src/transporter_proto.c", "src/log.c"),
    ("fm1_transporter_hostonly", "src/transporter_proto.c", "src/log.c"),
])
def test_actual_patched_selector_executes_both_branches(patched_selector, target, proto, log):
    stage, selector = patched_selector
    script = stage / f"select-{target}.cmake"
    script.write_text(
        "function(fm1t_add_firmware TARGET)\n" + selector + "\n"
        "message(STATUS \"SELECTED=${FM1T_PROTO_SOURCE}|${FM1T_LOG_SOURCE}\")\n"
        "endfunction()\n" + f"fm1t_add_firmware({target})\n"
    )
    result = subprocess.run(["cmake", "-P", str(script)], text=True,
                            capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={proto}|{log}" in result.stdout
