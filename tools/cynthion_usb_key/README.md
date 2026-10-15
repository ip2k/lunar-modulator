# Cynthion r1.4 USB_KEY prototype

This is an offline gateware prototype. It does not program or communicate with
a board from its build script. Build with `python -m tools.cynthion_usb_key.build
--build-dir PATH`; default mode is `operation`. That image starts with both
target GPIOs high impedance and requires the physical USER button to be stably
released and then pressed before its finite attempt can begin.

`--mode disconnected-selftest` creates a separate image that automatically
drives the four USB line states through the N4/P3 series resistors after the
target PHY has passed its non-driving configuration/readback sequence. This
image has no reachable key-transmission state. **Both target ports must be
empty before configuring this image**, since the self-test intentionally drives
the target-side lines. It returns both GPIOs to high impedance on completion or
fault. The result checks GPIO-to-USB3343-RXCMD loopback only; it does not prove
ROM acknowledgement or key behavior.

The ECP5 exposes read-only JTAG registers using LUNA's `JTAGRegisterInterface`:

| Address | Meaning |
| --- | --- |
| `0x01` | Magic `0x4c554e52` (`LUNR`) |
| `0x02` | Register layout version `1` |
| `0x03` | Status snapshot |

Status register `0x03` packs state in bits 0–3, PHY ready/fault in bits 4–5,
the four-step self-test mask in bits 6–9, line-state-valid in bit 10, and the
USB3343 line-state value in bits 11–12. This is diagnostic telemetry and is not
a safety interlock or hardware acceptance result. All registers are read-only.
The snapshot is captured in the USB clock domain to avoid a multi-bit clock
domain crossing.

All VBUS switches and the target-A discharge control are set to zero. On r1.4
these switches are active high; in particular, leaving
`target_c_vbus_en` high would enable the TARGET-C-to-TARGET-A path. No
CONTROL-to-TARGET-A power mode is included in this image.

The target PHY configuration, electrical assumptions, remaining review gates,
and offline verification limits are recorded in the task handoff. This
prototype is not an accepted recovery method or an installability claim.
