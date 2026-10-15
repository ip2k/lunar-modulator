"""Synthesize/package the offline r1.4 image. This script never programs hardware."""

import argparse
from pathlib import Path

from tools.cynthion_usb_key.top import CynthionUsbKeyPlatform, CynthionUsbKeyTop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("operation", "disconnected-selftest"),
                        default="operation")
    args = parser.parse_args()
    args.build_dir.mkdir(parents=True, exist_ok=True)

    platform = CynthionUsbKeyPlatform()
    platform.build(CynthionUsbKeyTop(mode=args.mode), name="cynthion_usb_key", do_program=False,
                   build_dir=str(args.build_dir))


if __name__ == "__main__":
    main()
