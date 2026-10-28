"""Compare empty-voice shortcuts with the original scans through real lifecycles."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("sanitized", [False, True])
def test_voice_lifecycle_preserves_state_and_restorations(tmp_path, sanitized):
    if sys.platform != "linux":
        pytest.skip("bounded differential harness runs in Linux CI")
    compiler = os.environ.get("CC", "cc")
    if not shutil.which(compiler):
        pytest.skip("C compiler unavailable")
    baseline = tmp_path / "baseline"
    shutil.copytree(ROOT / "engines/mod", baseline)
    core = baseline / "mod_core.c"
    text = core.read_text()
    for statement in ("return -1;", "return;", "return 0;"):
        guard = "  if (!m->voice_ever_started) " + statement
        assert text.count(guard) == 1
        text = text.replace(guard, "", 1)
    core.write_text(text)
    mk = (ROOT / "engines/mk/mod.mk").read_text().replace("\\\n", " ")
    names = []
    for variable in ("MOD_SRC", "MODC_SRC"):
        match = re.search(r"^" + variable + r"\s*:=\s*(.*)$", mk, re.M)
        assert match
        names.extend(match.group(1).split())
    generated = tmp_path / "gen"
    generated.mkdir()
    registry = (ROOT / "engines/mod/mod_registry.c").read_text()
    flags = sorted(set(re.findall(r"FM1_WITH_[A-Z0-9_]+", registry)))
    (generated / "fm1_modules.h").write_text(
        "#define FM1_IF(flag, ...) __VA_ARGS__,\n" +
        "".join("#define " + flag + " 1\n" for flag in flags))
    traces = []
    for variant, mod in (("baseline", baseline), ("candidate", ROOT / "engines/mod")):
        sources = [mod / Path(name).relative_to("mod") for name in names]
        exe = tmp_path / (variant + ".exe")
        trace = tmp_path / (variant + ".trace")
        command = [compiler, "-std=c99", "-O2", "-ffp-contract=off", "-fwrapv",
                   "-I" + str(ROOT / "engines/include"), "-I" + str(mod),
                   "-I" + str(generated), "-DV154_CANDIDATE=1",
                   '-DCORE_TEST_SOURCE="' + str(ROOT / "engines/test/mod_core_test.c") + '"']
        if sanitized:
            command += ["-fsanitize=address,undefined", "-fno-sanitize=shift",
                        "-fno-omit-frame-pointer"]
        command += [str(ROOT / "tests/fixtures/mod_voice_lifecycle.c"),
                    *map(str, sources), "-lm", "-o", str(exe)]
        subprocess.run(command, check=True, capture_output=True, timeout=180)
        result = subprocess.run([str(exe), str(trace)], check=True,
                                capture_output=True, text=True, timeout=90)
        assert '"pass":true' in result.stdout
        traces.append(trace)
    assert traces[0].read_bytes() == traces[1].read_bytes()
    # These are reproducible intermediates; pytest removes the remaining temp tree.
    for trace in traces:
        trace.unlink()
