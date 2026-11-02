"""Run the real trunc12 staging recipe against an immutable source fixture."""
import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_msfa_stage_replaces_readonly_vendor_sine(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("read-only overwrite regression requires an unprivileged user")
    make = shutil.which("make")
    if not make:
        pytest.skip("make unavailable")
    source = tmp_path / "source"
    vendor = source / "third_party/msfa"
    vendor.mkdir(parents=True)
    (source / "src").mkdir()
    (source / "mk").mkdir()
    originals = list((ROOT / "engines/third_party/msfa").glob("*.h"))
    originals += list((ROOT / "engines/third_party/msfa").glob("*.cc"))
    for original in originals:
        shutil.copyfile(original, vendor / original.name)
    shutil.copyfile(ROOT / "engines/src/msfa_sin_trunc12.h", source / "src/msfa_sin_trunc12.h")
    shutil.copyfile(ROOT / "engines/mk/msfa.mk", source / "mk/msfa.mk")
    before = {}
    for path in source.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
            before[path.relative_to(source)] = path.read_bytes()
    directories = [source, *(path for path in source.rglob("*") if path.is_dir())]
    for path in directories:
        path.chmod(0o555)
    build = tmp_path / "build"
    stage = build / "gen/msfa-trunc12"
    command = [make, "-f", "mk/msfa.mk", "BUILD=" + str(build),
               "FM1_DX7_SINE=trunc12", str(stage / ".staged")]
    try:
        assert not os.access(vendor / "sin.h", os.W_OK)
        for force in ([], ["-B"]):
            result = subprocess.run(command + force, cwd=source, capture_output=True,
                                    text=True, timeout=15)
            assert result.returncode == 0, result.stdout + result.stderr
            assert (stage / ".staged").is_file()
            assert (stage / "sin.h").read_bytes() == before[Path("src/msfa_sin_trunc12.h")]
            for original in originals:
                copied = stage / original.name
                assert stat.S_IMODE(copied.stat().st_mode) == 0o444
                if original.name != "sin.h":
                    assert copied.read_bytes() == before[Path("third_party/msfa") / original.name]
            for relative, raw in before.items():
                assert (source / relative).read_bytes() == raw
                assert stat.S_IMODE((source / relative).stat().st_mode) == 0o444
            assert all(stat.S_IMODE(path.stat().st_mode) == 0o555 for path in directories)
    finally:
        # Only the private fixture directories need write permission for cleanup.
        for path in directories:
            path.chmod(0o755)
