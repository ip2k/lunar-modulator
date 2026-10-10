"""Bounded six-word capture with extension/canary checks, no device access."""
import ctypes
from pathlib import Path
import subprocess


def test_capture_reads_six_words_and_keeps_destination_canaries(tmp_path):
    root = Path(__file__).resolve().parents[1]
    library = tmp_path / 'capture.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    '-I' + str(root / 'firmware/diagnostic'),
                    str(root / 'firmware/handover/capture.c'), '-o', str(library)], check=True)
    capture = ctypes.CDLL(str(library)).lunar_handover_capture
    capture.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    capture.restype = None
    source = (ctypes.c_uint32 * 8)(0xabcdef, 2, 3, 4, 5, 0xffffffff, 0xdeadbeef, 0xdeadbeef)
    target = (ctypes.c_uint32 * 25)(*[0xa5a5a5a5] * 25)
    capture(ctypes.byref(target, 4), source)
    assert list(target) == [0xa5a5a5a5] + list(source)[:6] + [0] * 17 + [0xa5a5a5a5]
    assert list(source)[6:] == [0xdeadbeef] * 2
