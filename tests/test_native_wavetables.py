"""Exercise the firmware startup decoder and generated C++ resource symbols."""
import importlib.util
import shutil
import subprocess
import sys

import pytest

from tests.engine_helpers import ROOT


@pytest.fixture(scope="session")
def wavetable_binary(tmp_path_factory):
    cc, cxx = shutil.which("cc"), shutil.which("c++")
    if not cc or not cxx:
        pytest.skip("no host C/C++ compiler")
    directory = ROOT / "tools/native"
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location("prepare_wavetables", directory / "prepare_wavetables.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out = tmp_path_factory.mktemp("native-waves")
        module.prepare(out, storage_section=(
            '__DATA,__lunar_waves' if sys.platform == 'darwin' else '.pool.wavetable'))
    finally:
        sys.path.remove(str(directory))
    objects = []
    for namespace in ("plaits", "braids"):
        obj = out / (namespace + ".o")
        subprocess.run([cxx, "-std=c++11", "-O2", "-I" + str(out), "-I" + str(ROOT / "engines/third_party/mutable"),
                        "-c", str(out / ("resources_" + namespace + ".cc")), "-o", str(obj)], check=True)
        objects.append(str(obj))
    expected = []
    for relative, symbol, width, size in module.ASSETS:
        raw = module.asset_bytes((ROOT / relative).read_text(), symbol, width, size)
        expected.append("static const unsigned char expected_" + str(width) + "[] = {" +
                        ",".join(map(str, raw)) + "};")
    (out / "expected.inc").write_text("\n".join(expected))
    binary = out / "check"
    subprocess.run([cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I" + str(out), "-I" + str(ROOT / "firmware/third_party/tinf"),
                    "-I" + str(ROOT / "firmware/native"),
                    str(ROOT / "tests/native_wavetables_check.c"),
                    str(ROOT / "firmware/third_party/tinf/tinflate.c"), *objects,
                    "-o", str(binary)], check=True)
    return binary


@pytest.mark.parametrize("shard", range(16))
def test_native_wavetables(wavetable_binary, shard):
    subprocess.run([str(wavetable_binary), str(shard)], check=True)
