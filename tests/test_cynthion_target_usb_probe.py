import pytest

pytest.importorskip("amaranth")
pytest.importorskip("luna")

from cynthion.gateware.platform.cynthion_r1_4 import CynthionPlatformRev1D4
from tools.cynthion_usb_key.build_target_usb_probe import EXPECTED_PLATFORM_ULPI_REGISTERS
from tools.cynthion_usb_key.target_usb_probe import TargetUsbDescriptorProbe, make_descriptors


def test_probe_descriptors_are_standard_control_only():
    descriptors = make_descriptors()
    device = descriptors._descriptors[(1, 0)]
    configuration = descriptors._descriptors[(2, 0)]
    assert len(device) == 18
    assert device[1] == 1
    assert int.from_bytes(device[8:10], "little") == 0x1209
    assert int.from_bytes(device[10:12], "little") == 0xCC01
    assert len(configuration) == 18
    assert configuration[1] == 2
    assert configuration[7] == 0x80
    assert configuration[8] == 0
    assert configuration[13] == 0  # no non-control endpoints
    assert configuration[14] == 0xFF  # vendor-specific interface


def test_probe_keeps_cynthion_r14_ulpi_profile_and_explicit_off_controls():
    platform = CynthionPlatformRev1D4()
    assert platform.ulpi_extra_registers == EXPECTED_PLATFORM_ULPI_REGISTERS == {0x39: 0x06}
    assert TargetUsbDescriptorProbe.VBUS_SWITCHES_OFF == {
        "target_c_vbus_en": 0,
        "control_vbus_en": 0,
        "aux_vbus_en": 0,
        "target_a_discharge": 0,
    }
    top = TargetUsbDescriptorProbe()
    top.elaborate(platform)
    assert not any(name in {"target_usb_dp", "target_usb_dm"}
                   for name, _number in platform._requested)
