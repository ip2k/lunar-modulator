"""Compile actual pinned/upstream-patched C functions with fake USB transfers.

The ignored local upstream checkout is explicit. No download or target build is
performed; absence of that source is a skip, not a claim of a passed C gate.
"""

import os
from pathlib import Path
import re
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PIN = "a7fb5e8ac692c528f8ed29e325911a3f4b8111d6"
SOURCE_ENV = "FM1_TRANSPORTER_SOURCE"
FUNCTIONS = {
    "src/pio_host.c": ("bot_cmd",),
    "src/jieli_uboot.c": (
        "jl_crc16", "jl_crc_cipher", "put_be32", "make_cdb",
        "cmd_exec", "jl_rom_mem_write",
    ),
    "src/transporter_proto.c": ("crc32_update", "do_memw"),
}


def _function(source: str, name: str) -> str:
    for match in re.finditer(rf"(?m)^(?:static )?[^\n]*\b{re.escape(name)}\(", source):
        brace = source.find("{", match.start())
        semicolon = source.find(";", match.start())
        if brace < 0 or (0 <= semicolon < brace):
            continue
        end = source.find("\n}", brace)
        if end < 0:
            continue
        return source[match.start():end + 2]
    raise AssertionError(f"function {name} absent from pinned patched source")


@pytest.fixture(scope="module")
def harness():
    source_path = os.environ.get(SOURCE_ENV)
    if not source_path:
        pytest.skip(f"set {SOURCE_ENV} to the local pinned upstream source checkout")
    source = Path(source_path).resolve(strict=True)
    subprocess.run(["git", "-C", str(source), "cat-file", "-e", f"{PIN}^{{commit}}"], check=True)
    parent = ROOT / "scratch/rom-bot-completion"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fm1t-bot-", dir=parent) as stage_name:
        stage = Path(stage_name)
        for relative in (*FUNCTIONS, "src/recovery.c", "pio/usb_key.pio"):
            dest = stage / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(subprocess.check_output(
                ["git", "-C", str(source), "show", f"{PIN}:{relative}"]
            ))
        # Give git-apply its own root. Otherwise it can quietly skip paths while
        # searching the parent Lunar worktree from this ignored scratch directory.
        subprocess.run(["git", "init", "--quiet", str(stage)], check=True)
        subprocess.run(["git", "apply", str(ROOT / "tools/fm1-transporter/0001-pico2-reject-false-d-pullups.patch")],
                       cwd=stage, check=True)
        if os.environ.get("FM1_BOT_CAUSAL_BASELINE") != "1":
            subprocess.run(["git", "apply", str(ROOT / "tools/fm1-transporter/0002-exact-bot-completion.patch")],
                           cwd=stage, check=True)
            assert "CBW incomplete" in (stage / "src/pio_host.c").read_text()
        sources = {relative: (stage / relative).read_text() for relative in FUNCTIONS}
        wire_assertions = [line for line in sources["src/pio_host.c"].splitlines()
                           if line.startswith("_Static_assert(sizeof(msc_")]
        if os.environ.get("FM1_BOT_CAUSAL_BASELINE") != "1":
            assert len(wire_assertions) == 2
        snippets = []
        for name in ("jl_crc16", "jl_crc_cipher", "put_be32", "make_cdb", "crc32_update",
                     "bot_cmd", "cmd_exec", "jl_rom_mem_write", "do_memw"):
            relative = next(path for path, names in FUNCTIONS.items() if name in names)
            snippets.append(_function(sources[relative], name))
        (stage / "actual_functions.inc").write_text(
            "\n".join(wire_assertions) + "\n\n" + "\n\n".join(snippets) + "\n")
        binary = stage / "bot_harness"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(stage),
                        str(ROOT / "tests/fixtures/fm1_transporter_bot_harness.c"), "-o", str(binary)],
                       check=True)
        yield binary


@pytest.mark.parametrize("case, expected", [
    ("ok", "OK 1 3 FB06"),
    ("cbw30", "ERR memw at 01C02000 1 1 FB06"),
    ("data511", "ERR memw at 01C02000 1 2 FB06"),
    ("data513", "ERR memw at 01C02000 1 2 FB06"),
    ("csw12", "ERR memw at 01C02000 1 3 FB06"),
    ("residue", "ERR memw at 01C02000 1 3 FB06"),
    ("tag", "ERR memw at 01C02000 1 3 FB06"),
    ("signature", "ERR memw at 01C02000 1 3 FB06"),
    ("status", "ERR memw at 01C02000 1 3 FB06"),
    ("timeout", "ERR memw at 01C02000 1 2 FB06"),
    ("disconnect", "ERR memw at 01C02000 1 1 FB06"),
    ("csw_timeout", "ERR memw at 01C02000 1 3 FB06"),
    ("got15", "0 0 0"),
    ("got16", "1 0 0"),
    ("echo", "0 0 0"),
])
def test_actual_patched_transport_functions(harness, case, expected):
    got = subprocess.check_output([str(harness), case], text=True).strip()
    assert got == expected
    if case not in {"got15", "got16", "echo"}:
        # This is the real do_memw/jl_rom_mem_write/bot_cmd path; it never emits
        # FB08 on an upload failure. Future host jump policy is a separate gate.
        assert got.endswith("FB06")


@pytest.mark.parametrize("case, expected", [
    ("caller_cbw", "0 DEADBEEF 1"),
    ("caller_data", "0 000001FF 2"),
    ("caller_csw", "0 00000200 3"),
    ("caller_ok", "1 00000200 3"),
])
def test_data_got_caller_contract(harness, case, expected):
    assert subprocess.check_output([str(harness), case], text=True).strip() == expected
