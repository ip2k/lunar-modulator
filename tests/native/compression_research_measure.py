"""Measure compression sizes and require byte-identical round trips."""
import glob
import hashlib
import os
import random
import zlib
import ctypes


lib = ctypes.CDLL("liblz4.so.1")
lib.LZ4_versionString.restype = ctypes.c_char_p
lib.LZ4_compressBound.argtypes = [ctypes.c_int]
lib.LZ4_compressBound.restype = ctypes.c_int
lib.LZ4_compress_default.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
]
lib.LZ4_compress_default.restype = ctypes.c_int
lib.LZ4_decompress_safe.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
]
lib.LZ4_decompress_safe.restype = ctypes.c_int


def lz4_compress(data):
    bound = lib.LZ4_compressBound(len(data))
    if bound <= 0:
        raise RuntimeError(f"LZ4_compressBound failed for {len(data)} bytes: {bound}")
    output = ctypes.create_string_buffer(bound)
    size = lib.LZ4_compress_default(data, output, len(data), bound)
    if size <= 0:
        raise RuntimeError(f"LZ4_compress_default failed for {len(data)} bytes: {size}")
    return output.raw[:size]


def verify_round_trips(data):
    zdata = zlib.compress(data, 9)
    if zlib.decompress(zdata) != data:
        raise AssertionError("zlib round-trip mismatch")

    ldata = lz4_compress(data)
    decoded = ctypes.create_string_buffer(len(data))
    decoded_size = lib.LZ4_decompress_safe(
        ldata, decoded, len(ldata), len(data),
    )
    if decoded_size < 0:
        raise RuntimeError(f"LZ4_decompress_safe failed: {decoded_size}")
    if decoded_size != len(data) or decoded.raw[:decoded_size] != data:
        raise AssertionError(
            f"LZ4 round-trip mismatch: input={len(data)} decoded={decoded_size}"
        )
    return len(zdata), len(ldata)


print("versions", "zlib", zlib.ZLIB_VERSION, "lz4", lib.LZ4_versionString().decode())
fixture_paths = sorted(path for path in glob.glob("/corpus/*.lunarb")
                       if not os.path.basename(path).startswith("._"))
for path in fixture_paths:
    data = open(path, "rb").read()
    zsize, lsize = verify_round_trips(data)
    print("fixture", os.path.basename(path), len(data), zsize, lsize,
          hashlib.sha256(data).hexdigest(), "roundtrip=ok")

fixture_data = [open(path, "rb").read() for path in fixture_paths
                if not path.endswith("dense.native-save.lunarb")]
cases = [
    ("fixture-concat", b"".join(fixture_data)),
    ("dense-actual", open("/corpus/dense.native-save.lunarb", "rb").read()),
    ("zeros-98304", bytes(98304)),
    ("random-98304", random.Random(20261014).randbytes(98304)),
]
for name, data in cases:
    zsize, lsize = verify_round_trips(data)
    print("case", name, len(data), zsize, lsize, hashlib.sha256(data).hexdigest(),
          "roundtrip=ok")
