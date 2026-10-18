"""Synthesize/package the offline r1.4 image. This script never programs hardware."""

import argparse
from pathlib import Path

from tools.cynthion_usb_key.top import CynthionUsbKeyPlatform, CynthionUsbKeyTop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("operation", "disconnected-selftest", "staged-operation"),
                        default="operation")
    parser.add_argument("--target-power-from-control", action="store_true",
                        help="enable CONTROL-to-TARGET-A VBUS in operation mode only")
    args = parser.parse_args()
    if args.target_power_from_control and args.mode not in {"operation", "staged-operation"}:
        parser.error("--target-power-from-control requires --mode operation or staged-operation")
    args.build_dir.mkdir(parents=True, exist_ok=True)

    platform = CynthionUsbKeyPlatform()
    platform.build(CynthionUsbKeyTop(
        mode=args.mode,
        target_power_from_control=args.target_power_from_control,
    ), name="cynthion_usb_key", do_program=False, build_dir=str(args.build_dir))


if __name__ == "__main__":
    main()
