"""Compare pinned soft-float conversions with independent host hardware casts."""
import hashlib
import json
import shutil
import subprocess
import pytest
from tests.engine_helpers import ROOT

@pytest.fixture(scope="session")
def conversion_check(tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no host C compiler")
    source = ROOT / "firmware/third_party/compiler-rt"
    inventory = json.loads((source / "inventory.json").read_text())
    for name, digest in inventory["files"].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    build = tmp_path_factory.mktemp("native-conversions")
    objects = []
    for name, symbol in [("floatdidf", "signed"), ("floatundidf", "unsigned")]:
        obj = build / (name + ".o")
        subprocess.run([cc, "-O2", "-D__SOFTFP__", "-fno-builtin",
                        "-D__" + name + "=lunar_test_" + symbol,
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        "-c", str(source / (name + ".c")), "-o", str(obj)], check=True)
        objects.append(str(obj))
    binary = build / "check"
    subprocess.run([cc, "-O2", "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    str(ROOT / "tests/native_i64_double_check.c"), *objects,
                    "-o", str(binary)], check=True)
    return binary

@pytest.mark.parametrize("shard", range(16))
def test_native_i64_double(conversion_check, shard):
    subprocess.run([str(conversion_check), str(shard)], check=True)
