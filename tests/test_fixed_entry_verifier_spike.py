from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPIKE = ROOT / "tests/native/fixed_entry_verifier_spike"


def _crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _image(body: bytes, *, magic: int = 0x31525646, size: int | None = None, crc: int | None = None, version: int = 1) -> bytes:
    return body + struct.pack("<IIHH", magic, len(body) if size is None else size,
                               _crc16(body) if crc is None else crc, version)


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("host C compiler unavailable")
    output = tmp_path_factory.mktemp("fixed-entry") / "verifier-probe"
    subprocess.run([cc, "-DSPIKE_HOST_TEST", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    str(SPIKE / "verifier.c"), str(SPIKE / "host_probe.c"),
                    "-o", str(output)], check=True)
    return output


def _run(probe: Path, tmp_path: Path, payload: bytes, *, maximum=64) -> int:
    src = tmp_path / "candidate.bin"
    src.write_bytes(payload)
    return subprocess.run([str(probe), str(src), str(maximum)], check=False).returncode


def test_shared_target_validator_accepts_two_distinct_bodies(probe, tmp_path):
    body_a = bytes(range(32))
    body_b = bytes(reversed(range(32)))
    assert _run(probe, tmp_path, _image(body_a)) == 0
    assert _run(probe, tmp_path, _image(body_b)) == 0
    assert _image(body_a) != _image(body_b)


def test_shared_target_validator_rejects_corruption_and_bad_metadata(probe, tmp_path):
    valid = _image(bytes(range(32)))
    altered = bytearray(valid)
    altered[7] ^= 0x40
    assert _run(probe, tmp_path, bytes(altered)) == 2
    assert _run(probe, tmp_path, _image(bytes(range(32)), magic=0)) == 1
    assert _run(probe, tmp_path, _image(bytes(range(32)), size=31)) == 1
    assert _run(probe, tmp_path, _image(bytes(range(32)), version=2)) == 1


def test_shared_target_validator_rejects_oversized_and_truncated_extent(probe, tmp_path):
    assert _run(probe, tmp_path, _image(bytes(range(50))), maximum=32) == 1
    assert _run(probe, tmp_path, b"short") == 93


def test_link_contract_places_validation_before_c_runtime():
    startup = (SPIKE / "startup.S").read_text()
    assert startup.index("sp = _ustack_top") < startup.index("call lunar_validate_mutable")
    assert startup.index("ssp = _sstack_top") < startup.index("call lunar_validate_mutable")
    assert startup.index("call lunar_validate_mutable") < startup.index("call fm1_cstart")
    linker = (SPIKE / "app.ld").read_text()
    assert "0x02000120" in linker and "0x02001000" in linker and "0x020D3000" in linker
