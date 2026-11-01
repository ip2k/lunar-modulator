"""Future known-chunk tails remain readable, with truthful C/Python skip reports.

Both C reader APIs are compared inside the probe, including complete reports and
printed record streams. Products live only in the pytest lane's temporary tree.
"""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib

import pytest
from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]


def future_units(data, version, tails, compressed):
    count = struct.unpack_from("<H", data, 14)[0]
    chunks = []
    changed = 0
    for i in range(count):
        tag, ver, flags, off, size, _ = struct.unpack_from("<4sHHIII", data, 32 + 20 * i)
        body = data[off:off + size]
        if flags & 1:
            body = zlib.decompress(body[4:], -12)
        if tag == b"UNIT" and changed < len(tails):
            ver = version
            body += tails[changed]
            changed += 1
        if compressed:
            compressor = zlib.compressobj(wbits=-12)
            body = struct.pack("<I", len(body)) + compressor.compress(body) + compressor.flush()
        chunks.append((tag, ver, int(compressed), body))
    assert changed == len(tails)
    result = bytearray(data[:32]) + bytearray(20 * count + 4)
    for i, (tag, ver, flags, body) in enumerate(chunks):
        result += bytes((-len(result)) % 4)
        struct.pack_into("<4sHHIII", result, 32 + 20 * i, tag, ver, flags,
                         len(result), len(body), zlib.crc32(body))
        result += body
    struct.pack_into("<I", result, 32 + 20 * count, zlib.crc32(result[32:32 + 20 * count]))
    struct.pack_into("<I", result, 20, len(result))
    struct.pack_into("<I", result, 28, zlib.crc32(result[:28]))
    return bytes(result)


@pytest.mark.parametrize("sanitize", [False, True], ids=["normal", "asan-ubsan"])
def test_future_chunk_tail_reporting(tmp_path, sanitize):
    cc = shutil.which(os.environ.get("FM1_CODEC_CC", "clang"))
    if not cc:
        pytest.skip("C compiler unavailable")
    flags = ["-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
             f"-I{ROOT / 'engines/include'}", f"-I{ROOT / 'engines/state'}"]
    if sanitize:
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    sources = [ROOT / "tests/fixtures/native_state/forward_tail.c"]
    sources += [ROOT / "engines/state" / name for name in (
        "state_bin.c", "state_movy1.c", "state_names.c", "fm1_num.c", "fm1_deflate.c", "state_print.c")]
    original = (ROOT / "tests/fixtures/state/1.0/first-orbit.lunarb").read_bytes()
    records, report = ls.read_bin(original)
    assert report.skipped == 0
    with tempfile.TemporaryDirectory(prefix="forward-tail-", dir=tmp_path) as temporary:
        stage = Path(temporary)
        exe = stage / "reader"
        subprocess.run([cc, *flags, *map(str, sources), "-o", str(exe)], check=True)
        cases = 0
        for compressed in (False, True):
            for version in (1, 2, 65535):
                for tails in ([b""], [b"\xa5"], [b"\xa5" * 17, b"\x5a"]):
                    data = future_units(original, version, tails, compressed)
                    path = stage / "candidate.lunarb"
                    path.write_bytes(data)
                    result = subprocess.run([str(exe), str(path)], capture_output=True, text=True, timeout=10)
                    c_report = json.loads(result.stderr)
                    if version == 1 and any(tails):
                        assert result.returncode == 1 and c_report["code"] == "BAD"
                        assert c_report["skipped"] == 0
                        with pytest.raises(ls.Refused, match="chunk longer"):
                            ls.read_bin(data)
                    else:
                        assert result.returncode == 0, result.stderr
                        expected = sum(bool(tail) for tail in tails)
                        assert c_report["skipped"] == expected, c_report
                        py_records, py_report = ls.read_bin(data)
                        assert py_records == records
                        assert result.stdout == ls.records_text(records)
                        assert vars(py_report) == c_report
                        assert {**c_report, "skipped": 0} == vars(report)
                    cases += 1
        print(f"forward-tail cases={cases}: legacy/workspace reports and records, C/Python parity")
