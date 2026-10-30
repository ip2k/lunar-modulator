#!/usr/bin/env python3
"""Generate synthetic Workbench format vectors; no vendor or owner data.

Run with --out DIR to materialize vectors outside the source tree.
Project/timbre payloads are envelope-only probes, not playable vendor projects.
SEA5 chunks are marker-only probes, not encoded audio.
"""
import argparse
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools import dx7_bank


def envelope(tag, version, payload):
    return struct.pack("<4sIII", tag, version, len(payload), zlib.crc32(payload)) + payload


def sample_bank(frames=0):
    size = ((frames + 319) // 320) * 228
    out = bytearray(512 + size)
    struct.pack_into("<8I", out, 0, 0x53314D46, 1, len(out), 0, 0, 32000, 0, 0)
    for slot in range(16):
        struct.pack_into("<III", out, 32 + slot * 28, 512 if slot == 0 else len(out),
                         frames if slot == 0 else 0, size if slot == 0 else 0)
    for at in range(512, len(out), 228):
        struct.pack_into("<I", out, at, 0x5A144501)
    struct.pack_into("<I", out, 12, zlib.crc32(out))
    return bytes(out)


def vectors():
    single = dx7_bank.vced_syx(dx7_bank.bank()[0])
    bank = dx7_bank.vmem_syx(dx7_bank.bank())
    out = {"own-single.syx": single, "own-32-voice-bank.syx": bank,
           "truncated.syx": single[:-1], "empty.syx": b""}
    corrupt = bytearray(single)
    corrupt[-2] ^= 1
    out["bad-checksum.syx"] = bytes(corrupt)
    for version, size in ((3, 4048), (4, 4064), (4, 4264)):
        p = bytearray(size)
        p[3852] = version
        if size == 4264:
            p[4064:4068] = b"FM1T"
            struct.pack_into("<I", p, 4260, zlib.crc32(p[4064:4260]))
        out[f"envelope-only-project-v{version}-{size}.fm1"] = envelope(b"FM1P", version, p)
    out["envelope-only-timbre.fm1t"] = envelope(b"FM1T", 1, bytes(223))
    out["future-timbre.fm1t"] = envelope(b"FM1T", 2, bytes(223))
    out["sample-empty.fm1s"] = sample_bank()
    out["sample-round-up-1.fm1s"] = sample_bank(1)
    out["sample-round-up-321.fm1s"] = sample_bank(321)
    # Largest complete chunk count accepted by old read bound; the tail sector
    # reserved for tuning makes this exceed the new-transfer capacity.
    transfer_frames = ((462848 - 512) // 228) * 320
    out["sample-new-transfer-max.fm1s"] = sample_bank(transfer_frames)
    out["sample-over-new-transfer.fm1s"] = sample_bank(transfer_frames + 320)
    out["sample-legacy-max.fm1s"] = sample_bank(((466944 - 512) // 228) * 320)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in vectors().items():
        with (args.out / name).open("xb") as stream:
            stream.write(data)


if __name__ == "__main__":
    main()

