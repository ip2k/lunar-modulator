#!/usr/bin/env python3
"""Print the fail-open image id of a flat application image (app.bin).

The firmware computes the same FNV-1a hash over its own flash image at boot
(firmware/failopen/failopen_core.c lunar_failopen_image_id, called from
failopen_sdk.c over .text through the load image of .cache_ram_data) and
prints it as `LUNAR_FAILOPEN image=XXXXXXXX ... bytes=N`; the two must match.
"""
import argparse
from pathlib import Path


def image_id(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value or 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    data = parser.parse_args().image.read_bytes()
    print('image={:08x} bytes={}'.format(image_id(data), len(data)))
