# SPDX-License-Identifier: MIT
import struct
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(os.environ['LUNAR_SOURCE']) if 'LUNAR_SOURCE' in os.environ else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools/native'))
from tools import lunar_state as ls
from recompress_project import _raw_chunk, recompress

FIXTURE = ROOT / 'tests/fixtures/state/1.0/first-orbit.lunarb'


def test_recompress_fixture_preserves_records_and_native_reader_output():
    original = FIXTURE.read_bytes()
    expected, _ = ls.read_bin(original)
    packed, receipt = recompress(original)
    actual, _ = ls.read_bin(packed)
    assert actual == expected
    assert receipt['records_equal'] is True
    assert receipt['output_bytes'] == len(packed)
    tool = Path(os.environ.get('FM1_STATE_NATIVE', ROOT / 'engines/build/fm1-state'))
    if not tool.exists():
        pytest.skip('native fm1-state tool is not built in this checkout')
    result = subprocess.run([str(tool), 'records', '-'], input=packed,
                            capture_output=True, check=True)
    assert result.stdout.decode() == ls.records_text(expected)


def test_recompress_is_deterministic_and_nonexpanding_for_fixture():
    source = FIXTURE.read_bytes()
    first, _ = recompress(source)
    second, _ = recompress(source)
    assert first == second
    assert len(first) <= len(source)


def test_cli_imports_when_invoked_outside_repository():
    script = ROOT / 'tools/native/recompress_project.py'
    result = subprocess.run([sys.executable, str(script), '--help'], cwd='/tmp',
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'LUNARB chunks' in result.stdout


@pytest.mark.parametrize('damage', ['crc', 'truncated'])
def test_recompress_refuses_tampered_or_truncated_input(damage):
    source = bytearray(FIXTURE.read_bytes())
    if damage == 'crc':
        source[-1] ^= 1
    else:
        source.pop()
    with pytest.raises(ls.Refused):
        recompress(bytes(source))


def test_inflater_rejects_declared_output_over_tag_cap_before_expansion():
    with pytest.raises(ValueError, match='tag cap'):
        _raw_chunk(struct.pack('<I', ls.CAP[3] + 1) + b'\x03\x00', 1,
                   ls.CAP[3])


def test_inflater_rejects_expansion_over_declared_length():
    import zlib
    c = zlib.compressobj(9, zlib.DEFLATED, -12)
    stream = c.compress(b'X' * 128) + c.flush()
    with pytest.raises(ValueError, match='exceeds declared'):
        _raw_chunk(struct.pack('<I', 16) + stream, 1, ls.CAP[3])


def test_recompress_refuses_duplicate_unit_records():
    records, _ = ls.read_bin(FIXTURE.read_bytes())
    unit_index = next(i for i, record in enumerate(records) if record.get('rec') == 'unit')
    duplicate = dict(records[unit_index])
    with pytest.raises(ls.Refused):
        recompress(ls.write_bin(records[:unit_index + 1] + [duplicate] + records[unit_index + 1:]))
