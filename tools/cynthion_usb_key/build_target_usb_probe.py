"""Offline build for the temporary r1.4 TARGET-PHY descriptor probe."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from cynthion.gateware.platform.cynthion_r1_4 import CynthionPlatformRev1D4

from tools.cynthion_usb_key.target_usb_probe import TargetUsbDescriptorProbe


EXPECTED_PLATFORM_ULPI_REGISTERS = {0x39: 0x06}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args()
    args.build_dir.mkdir(parents=True, exist_ok=True)

    platform = CynthionPlatformRev1D4()
    if platform.ulpi_extra_registers != EXPECTED_PLATFORM_ULPI_REGISTERS:
        raise SystemExit(
            "Cynthion r1.4 ULPI register profile changed: "
            f"{platform.ulpi_extra_registers!r}"
        )
    products = platform.build(
        TargetUsbDescriptorProbe(), name="cynthion_target_usb_probe",
        do_program=False, build_dir=str(args.build_dir)
    )
    bitstream = args.build_dir / "cynthion_target_usb_probe.bit"
    if not bitstream.is_file():
        raise SystemExit(f"build did not produce bitstream: {bitstream}")
    source_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    receipt = {
        "purpose": "temporary standard-descriptor TARGET-C cable diagnostic",
        "hardware_programmed": False,
        "platform": "Cynthion r1.4",
        "usb_bus": "target_phy",
        "usb_device_stack": "LUNA USBDevice + standard control endpoint",
        "descriptor_vid_pid": "1209:cc01 (temporary development identity)",
        "raw_target_gpio": "not requested; input/high-impedance",
        "ulpi_extra_registers": {"0x39": "0x06"},
        "vbus_controls_active_high": {
            "target_c_vbus_en": 0,
            "control_vbus_en": 0,
            "aux_vbus_en": 0,
            "target_a_discharge": 0,
        },
        "source_commit": source_sha,
        "bitstream_path": str(bitstream.resolve()),
        "bitstream_sha256": hashlib.sha256(bitstream.read_bytes()).hexdigest(),
        "timing_reports": sorted(
            p.name for p in args.build_dir.glob("*timing*")
            if p.is_file()
        ),
    }
    receipt_path = args.build_dir / "cynthion_target_usb_probe_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
