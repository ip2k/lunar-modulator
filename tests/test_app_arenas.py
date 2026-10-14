"""Shared application with embedded and caller-owned engine storage."""
import json
import os
import shutil
import subprocess

import pytest

from tests.engine_helpers import GPL_MODS, ROOT


@pytest.fixture(scope="session")
def arena_tools(tmp_path_factory):
    if not GPL_MODS:
        pytest.skip("Trio requires the GPL engine profile")
    if not shutil.which("make") or not shutil.which("c++"):
        pytest.skip("no native compiler")
    build = tmp_path_factory.mktemp("arena-build")
    native = ROOT / "firmware/native"
    vendor = ROOT / "firmware/third_party/tlsf"
    fragment = build / "native.mk"
    sources = [native / "project_start.c", native / "instance_pool.c", vendor / "tlsf.c"]
    # Separate objects per storage profile because EXTRA changes its ABI.
    tools = {}
    for external in (0, 1):
        out = build / str(external)
        binary = out / "fm1-arena-check"
        extra = os.environ.get("FM1_SIM_EXTRA", "")
        objects = [out / (name + ".o") for name in ("project_start", "instance_pool", "tlsf")]
        fragment.write_text(
            f"{binary}: " + " ".join(map(str, objects)) + "\n" +
            "".join(f"{obj}: {source}\n\t@mkdir -p $(dir $@)\n\t$(CC) $(SIM_CFLAGS) -Istate -I{native} -I{vendor} -c $< -o $@\n"
                    for obj, source in zip(objects, sources)))
        subprocess.run([
            "make", "-C", str(ROOT / "engines"), "-f", "Makefile",
            "-f", str(ROOT / "sim/web/mk/sim.mk"), "-f", str(fragment),
            f"SIM={ROOT / 'sim/web'}", f"BUILD={out}", "FM1_GPL_MODS=1",
            "FM1_MODULES=trio,dx7,test-sine,test-gain,arp,lfo,env",
            f"CC={os.environ.get('FM1_SIM_CC', 'cc')}",
            f"CXX={os.environ.get('FM1_SIM_CXX', 'c++')}",
            f"OPT={os.environ.get('FM1_SIM_OPT', '-O2')}",
            f"EXTRA={extra} -DFM1_APP_EXTERNAL_ARENAS={external} -I{native} -I{ROOT / 'engines/state'}",
            "-j4", str(binary),
        ], check=True, stdout=subprocess.DEVNULL)
        tools[external] = binary
    return tools


@pytest.mark.parametrize("case", range(30))
def test_project_scalar_startup(arena_tools, case):
    result = json.loads(subprocess.check_output(
        [str(arena_tools[1]), "--scalar", str(case)], text=True))
    assert result == {"passed": True, "case": case}


@pytest.mark.parametrize("case", range(30))
def test_project_dx7_startup(arena_tools, case):
    result = json.loads(subprocess.check_output(
        [str(arena_tools[1]), "--dx7", str(case)], text=True))
    assert result == {"passed": True, "case": case}


@pytest.mark.parametrize("shard", range(16))
def test_app_storage_and_audio(arena_tools, shard):
    results = []
    for external, binary in arena_tools.items():
        result = json.loads(subprocess.check_output([str(binary), str(shard)], text=True))
        assert result["passed"] and result["shard"] == shard
        assert result["external"] == external
        results.append(result)
    sizes = {r["external"]: r["app_bytes"] for r in results}
    assert sizes[0] - sizes[1] == 4 * 512 * 1024 + 10 * 256 * 1024
