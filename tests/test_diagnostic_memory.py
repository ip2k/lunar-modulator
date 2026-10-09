"""Host behavior check for the independently authored freestanding memory init."""
import ctypes
import pathlib
import subprocess


def test_copies_data_and_zeros_only_requested_bss(tmp_path):
    root = pathlib.Path(__file__).resolve().parents[1]
    library = tmp_path / "memory.so"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                    str(root / "firmware/diagnostic/memory.c"), "-o", str(library)], check=True)
    initialize = ctypes.CDLL(str(library)).lunar_diag_memory_init
    initialize.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                           ctypes.c_void_p, ctypes.c_uint]
    initialize.restype = None
    data = (ctypes.c_ubyte * 7)(*[0xCC] * 7)
    source = (ctypes.c_ubyte * 5)(1, 9, 27, 81, 243)
    bss = (ctypes.c_ubyte * 9)(*[0xDD] * 9)
    initialize(ctypes.byref(data, 1), source, 5, ctypes.byref(bss, 1), 7)
    assert list(data) == [0xCC, 1, 9, 27, 81, 243, 0xCC]
    assert list(bss) == [0xDD] + [0] * 7 + [0xDD]
    initialize(ctypes.byref(data, 1), source, 0, ctypes.byref(bss, 1), 0)
    assert list(data) == [0xCC, 1, 9, 27, 81, 243, 0xCC]
    assert list(bss) == [0xDD] + [0] * 7 + [0xDD]
