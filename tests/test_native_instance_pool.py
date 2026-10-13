"""Aligned native instance storage: fragmentation, OOM and live pointer stability."""
import importlib.util
import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT


@pytest.fixture(scope="session", params=[165376, 196608, 216064])
def instance_pool_binary(tmp_path_factory, request):
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("no host C compiler")
    spec = importlib.util.spec_from_file_location("native_build_probe", ROOT / "tools/native/build_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vendor = ROOT / "firmware/third_party/tlsf"
    module.check_pins(vendor)
    binary = tmp_path_factory.mktemp("native-instance-pool") / "check"
    subprocess.run([
        compiler, "-DTEST_POOL_BYTES=" + str(request.param), "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        "-I" + str(ROOT / "firmware/native"), "-I" + str(vendor),
        str(ROOT / "firmware/native/instance_pool.c"), str(vendor / "tlsf.c"),
        str(ROOT / "tests/native_instance_pool_check.c"), "-o", str(binary),
    ], check=True)
    return binary


@pytest.mark.parametrize("shard", range(16))
def test_native_instance_pool(instance_pool_binary, shard):
    subprocess.run([str(instance_pool_binary), str(shard)], check=True)
