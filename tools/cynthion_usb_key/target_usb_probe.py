"""Minimal LUNA USB device responder on Cynthion r1.4 TARGET PHY.

This temporary, offline diagnostic exposes only standard USB descriptors. It
does not use or drive the direct TARGET D+/D- GPIO resources and never enables
a Cynthion VBUS switch or discharge path.
"""

from amaranth import Elaboratable, Module
from usb_protocol.emitters import DeviceDescriptorCollection
from luna.gateware.usb.usb2.device import USBDevice


def make_descriptors():
    """Return a descriptor-only device identity for the temporary cable check."""
    descriptors = DeviceDescriptorCollection()
    with descriptors.DeviceDescriptor() as device:
        # Temporary open-hardware development VID/PID; not a product identity.
        device.idVendor = 0x1209
        device.idProduct = 0xCC01
        device.iManufacturer = "Lunar development test"
        device.iProduct = "Cynthion TARGET-C descriptor probe"
        device.iSerialNumber = "temporary"
        device.bNumConfigurations = 1

    with descriptors.ConfigurationDescriptor() as configuration:
        configuration.bmAttributes = 0x80
        configuration.bMaxPower = 0
        with configuration.InterfaceDescriptor() as interface:
            interface.bInterfaceNumber = 0
            interface.bInterfaceClass = 0xFF
            interface.bInterfaceSubclass = 0
            interface.bInterfaceProtocol = 0

    return descriptors


class TargetUsbDescriptorProbe(Elaboratable):
    """Serve standard device/configuration requests through ``target_phy``."""

    VBUS_SWITCHES_OFF = {
        "target_c_vbus_en": 0,
        "control_vbus_en": 0,
        "aux_vbus_en": 0,
        "target_a_discharge": 0,
    }

    def elaborate(self, platform):
        m = Module()
        m.submodules.car = platform.clock_domain_generator()

        # This is the TARGET port PHY. Do not use platform.default_usb_connection
        # (aux_phy), or the CONTROL PHY used by the stock analyzer.
        target_phy = platform.request("target_phy")
        m.submodules.device = device = USBDevice(bus=target_phy)
        device.add_standard_control_endpoint(make_descriptors())
        m.d.comb += [device.connect.eq(1), device.full_speed_only.eq(1)]

        # The base Cynthion r1.4 platform enables these switches active-high.
        # Assign every VBUS path explicitly off for this diagnostic image.
        for resource, value in self.VBUS_SWITCHES_OFF.items():
            m.d.comb += getattr(platform.request(resource), "o").eq(value)

        # No target_usb_dp/dm resource is requested here: those raw GPIO pads
        # remain inputs/high-impedance. The USB3343 on target_phy handles USB.
        return m
