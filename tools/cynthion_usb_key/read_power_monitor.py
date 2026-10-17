"""Read-only PAC2 JTAG telemetry; never configures or writes an FPGA/device.

Run with the Cynthion Python environment after separately reviewing/loading the
monitor bitstream. Register sweeps are non-atomic, not instantaneous power pairs.
"""

import argparse
from datetime import datetime, timezone
import json
import time

MAGIC = 0x50414332
LAYOUT_VERSION = 2
EXPECTED_ID_AND_ACTIVE_RANGE = (0x4000 << 8) | 0x54
CLOCK_HZ = 60_000_000
MAX_AGE_CYCLES = CLOCK_HZ // 4  # Two nominal 125 ms sample periods.


def decode_registers(registers):
    """Preserve a raw sweep and only convert authenticated, fresh readings."""
    if set(registers) != set(range(1, 11)) or any(
        type(value) is not int or not 0 <= value <= 0xFFFFFFFF
        for value in registers.values()
    ):
        raise ValueError("expected exactly ten unsigned 32-bit monitor registers")
    status = registers[3]
    problems = []
    if registers[1] != MAGIC or registers[2] != LAYOUT_VERSION:
        problems.append("wrong gateware magic or register layout")
    if status & 0x1FF != 0x105:
        problems.append("PHY/PAC not ready, faulted, or no sample")
    if status & ~0x1FF:
        problems.append("unknown monitor status bits")
    if registers[4] != EXPECTED_ID_AND_ACTIVE_RANGE:
        problems.append("PAC manufacturer or active range mismatch")
    if registers[10] != 1:
        problems.append("unexpected VBUS controls")
    if registers[7] == 0 or registers[8] > MAX_AGE_CYCLES:
        problems.append("missing or stale sample")
    if registers[5] > 0xFFFF or registers[6] > 0xFFFF:
        problems.append("measurement exceeds 16-bit PAC range")
    valid = not problems
    return {
        "schema": "lunar-cynthion-power-sweep-v2",
        "raw_registers": {str(k): registers[k] for k in range(1, 11)},
        "valid": valid,
        "problems": problems,
        "atomic": False,
        "scope": "TARGET-A USB supply; not FM1 CPU rail or recovery proof",
        "current_sign": "positive TARGET_A_to_CONTROL; negative CONTROL_to_TARGET_A",
        "sample_sequence": registers[7],
        "sample_age_cycles": registers[8],
        "pac_error_code": (status >> 4) & 15,
        "vbus_uv": (registers[5] * 32_000_000 + 32_768) // 65_536 if valid else None,
        "current_raw_signed": (
            registers[6] if registers[6] < 0x8000 else registers[6] - 0x1_0000
        ) if valid else None,
        "current_ua": _current_ua_from_bipolar_raw(registers[6]) if valid else None,
    }


def _current_ua_from_bipolar_raw(raw, shunt_uohm=20_000):
    """Convert PAC195x two's-complement ±100 mV VSENSE to signed µA."""
    signed = raw if raw < 0x8000 else raw - 0x1_0000
    numerator = signed * 100_000 * 1_000_000
    denominator = shunt_uohm * 32_768
    magnitude = (abs(numerator) + denominator // 2) // denominator
    return magnitude if numerator >= 0 else -magnitude


def read_sweep(register_read):
    # Check identity before interpreting any other address of an unknown image.
    raw = {1: register_read(1), 2: register_read(2)}
    if raw != {1: MAGIC, 2: LAYOUT_VERSION}:
        raise ValueError("PAC2 layout2 is not loaded; refusing unknown register map")
    # Read status last, so a fault during the sweep is included in validation.
    for address in (4, 5, 6, 7, 8, 9, 10, 3):
        raw[address] = register_read(address)
    return decode_registers(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0,
                        help="seconds between completed sweeps (default: 1)")
    args = parser.parse_args()
    if not 1 <= args.samples <= 120 or not 0.125 <= args.interval <= 10:
        parser.error("samples must be 1..120 and interval 0.125..10 seconds")
    # No gateware/Amaranth dependency is needed for offline decoding/tests.
    from apollo_fpga import ApolloDebugger
    debugger = ApolloDebugger()
    invalid = False
    for index in range(args.samples):
        started = datetime.now(timezone.utc).isoformat()
        result = read_sweep(debugger.registers.register_read)
        result.update(started_utc=started, completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(result, sort_keys=True), flush=True)
        invalid |= not result["valid"]
        if index + 1 < args.samples:
            time.sleep(args.interval)
    return int(invalid)


if __name__ == "__main__":
    raise SystemExit(main())
