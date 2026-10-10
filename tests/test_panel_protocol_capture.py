"""RAM-only target-link sink: protocol equivalence, reset and bounds evidence."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys

import pytest
from tests.test_panel_probe import probe as protocol_probe, run

ROOT = Path(__file__).resolve().parents[1]


def load_capture(directory, stub=None):
    library = directory / 'capture.so'
    sources = [str(ROOT / 'firmware/display/protocol_capture.c')]
    if stub is None:
        sources.append(str(ROOT / 'firmware/display/panel_probe.c'))
    else:
        source = directory / 'stub.c'
        source.write_text('#include "panel_probe.h"\n'
            'enum lunar_panel_result lunar_panel_probe(const struct lunar_panel_transport *t) {'
            + stub + '}\n')
        sources.append(str(source))
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
        '-I' + str(ROOT / 'firmware/display'), *sources, '-o', str(library)], check=True)
    capture = c.CDLL(str(library)).lunar_panel_capture_run
    capture.argtypes = [c.c_void_p]
    capture.restype = None
    return capture


def event_hash(trace):
    """Independent fold of the separately exercised mock transport transcript."""
    value = 2166136261
    for command, data in trace:
        if command == 'wait':
            event = b'T' + data.to_bytes(4, 'little')
        else:
            event = b'B' + bytes([command])
            event += b''.join(b'W' + bytes([byte]) for byte in data) + b'E'
        for byte in event:
            value = ((value ^ byte) * 16777619) & 0xffffffff
    return value


def test_ram_capture_matches_transport_and_preserves_canaries(tmp_path, protocol_probe):
    capture = load_capture(tmp_path)
    result, trace, _ = run(protocol_probe)
    assert result == 0
    expected = [0x4c504354, 1, 0, 22, 115254, 22, 2, 220, event_hash(trace), 0, 0]
    target = (c.c_uint32 * 13)(*[0xa5a5a5a5] * 13)
    capture(c.byref(target, 4))
    assert list(target) == [0xa5a5a5a5] + expected + [0xa5a5a5a5]
    # A second invocation must start a fresh transcript instead of accumulating.
    capture(c.byref(target, 4))
    assert list(target) == [0xa5a5a5a5] + expected + [0xa5a5a5a5]


@pytest.mark.parametrize('stub,result', [
    ('return t->write(t->context, 0) ? LUNAR_PANEL_OK : LUNAR_PANEL_TRANSFER_FAILED;', 2),
    ('t->begin(t->context, 0); return t->begin(t->context, 1) ? '
     'LUNAR_PANEL_OK : LUNAR_PANEL_TRANSFER_FAILED;', 2),
    ('return t->wait_ms(t->context, 221) ? LUNAR_PANEL_OK : LUNAR_PANEL_DELAY_FAILED;', 3),
    ('t->wait_ms(t->context, 220); return t->wait_ms(t->context, 1) ? '
     'LUNAR_PANEL_OK : LUNAR_PANEL_DELAY_FAILED;', 3),
])
def test_malformed_transport_is_flagged_before_counter_overflow(tmp_path, stub, result):
    capture = load_capture(tmp_path, stub)
    target = (c.c_uint32 * 13)(*[0xa5a5a5a5] * 13)
    capture(c.byref(target, 4))
    assert target[3] == result and target[11] == 1
    assert target[0] == target[12] == 0xa5a5a5a5
    assert target[4] <= 22 and target[5] <= 115254 and target[8] <= 220


def test_optional_target_link_passes_handover_but_inert_profile_rejects_it(tmp_path):
    directory = os.environ.get('LUNAR_PANEL_PROTOCOL_ARTIFACT_DIR')
    if not directory:
        pytest.skip('optional ignored vendor target artifacts are not available')
    import json
    sys.path.insert(0, str(ROOT / 'tools/jieli'))
    from diagnostic_report import report
    directory = Path(directory)
    elf = (directory / 'diagnostic.elf').read_bytes()
    flat = (directory / 'diagnostic.bin').read_bytes()
    audit = json.loads((directory / 'audit_link.json').read_text())
    result = report(elf, flat, audit, 'handover')
    assert result['profile'] == 'handover' and result['ram_reserved_bytes'] <= 16384
    with pytest.raises(ValueError, match='section'):
        report(elf, flat, audit)
    import importlib.util
    spec = importlib.util.spec_from_file_location('stage_panel_capture',
        ROOT / 'tools/jieli/stage-diagnostic.py')
    staging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(staging)
    destination = tmp_path / 'must-not-stage'
    with pytest.raises(ValueError, match='section'):
        staging.stage(tmp_path / 'no-stock', directory / 'diagnostic.elf',
                      directory / 'diagnostic.bin', destination)
    assert not destination.exists()
