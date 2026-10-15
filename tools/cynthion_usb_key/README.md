# Cynthion r1.4 USB_KEY prototype

This is an offline gateware prototype. It does not program or communicate with
a board from its build script. Build with `python -m tools.cynthion_usb_key.build
--build-dir PATH`; default mode is `operation`. That image starts with both
target GPIOs high impedance and requires the physical USER button to be stably
released and then pressed before its finite attempt can begin.

Every image leaves VBUS controls off by default. An operation image may be
built with `--target-power-from-control`; this enables only the r1.4
CONTROL-to-TARGET-A VBUS switch. TARGET-C passthrough, AUX VBUS, and discharge
remain off. This is an explicit build-time choice, not a runtime control. It
does not establish that a particular unit, cable, or power source is suitable;
the owner must review the hardware sequence. Keep TARGET-C unplugged while the
key attempt can drive lines; connect it only after terminal high impedance.
The disconnected-selftest mode rejects this power option and always leaves
all switches off.

`--mode disconnected-selftest` creates a separate image that automatically
drives the four USB line states through the N4/P3 series resistors after the
target PHY has passed its non-driving configuration/readback sequence. This
image has no reachable key-transmission state. **Both target ports must be
empty before configuring this image**, since the self-test intentionally drives
the target-side lines. It spends 1 ms on each expected line state before
failing, then returns both GPIOs to high impedance. The result checks
GPIO-to-USB3343-RXCMD loopback only; it does not prove ROM acknowledgement or
key behavior.

The ECP5 exposes read-only JTAG registers using LUNA's `JTAGRegisterInterface`:

| Address | Meaning |
| --- | --- |
| `0x01` | Magic `0x4c554e52` (`LUNR`) |
| `0x02` | Register layout version `2` |
| `0x03` | Status snapshot |
| `0x04` | Live GPIO: DP input, DM input, DP output, DM output, DP OE, DM OE (bits 0–5) |
| `0x05` | Self-test failure: reason (bits 0–1), step (2–3), expected state (4–5), last observed state (6–7) |
| `0x06` | GPIO input/output/OE snapshot latched at self-test failure (same bit layout as `0x04`) |
| `0x07` | RXCMD event counts for K/J/SE0/SE1, one saturating byte per step |
| `0x08` | Last RXCMD line state for each K/J/SE0/SE1 step, two bits per step |
| `0x09` | Valid-observation mask for the four self-test steps |
| `0x0a` | Expected sequence `K, J, SE0, SE1`, packed as `0xc6` |

Status register `0x03` packs state in bits 0–3, PHY ready/fault in bits 4–5,
the four-step self-test mask in bits 6–9, line-state-valid in bit 10, the
USB3343 line-state value in bits 11–12, disconnected-selftest mode in bit 13,
and CONTROL-to-TARGET-A power selection in bit 14. This is diagnostic telemetry
and is not a safety interlock or hardware acceptance result. All registers are
read-only. Status and live GPIO snapshots are captured in the USB clock domain.
Failure registers preserve the first self-test fault evidence after the pads
return high impedance. The expected sequence uses bit 0 = DP and bit 1 = DM;
register `0x08` packs step 0 into bits 0–1 and then ascends by two bits per
step. Register `0x07` similarly packs step 0 into bits 0–7. Failure reasons
are 1 for RXCMD mismatch/timeout and 2 for loss of the drive interlock.

The protocol's finite attempt limit is 30,000 packets. With the current
16-bit word at 20 us per bit and 160 us release gap, the maximum packet train
is 30,000 × (16 × 20 + 160) us = 14.4 seconds, plus self-test and transition
time. The bound ends in fault without candidate ACK evidence; it is not a
success signal or an estimate of ROM acceptance.

On r1.4 these switches are active high; in particular, leaving
`target_c_vbus_en` high would enable the TARGET-C-to-TARGET-A path. It is always
set to zero here, even when CONTROL power is selected.

The prototype currently emits SOF by pulling D+ low through the onboard 1 kΩ
series resistor. Against the reported 1.5 kΩ ROM pull-up, an ideal divider
would leave about 1.32 V at the target side, above the USB full-speed single-
ended low maximum of 0.8 V. This is a source-derived concern, not a measured
result; post-ACK SOF acceptance is therefore unproven. The prototype does not
switch to PHY transmit mode.

The target PHY configuration, electrical assumptions, remaining review gates,
and offline verification limits are recorded in the task handoff. This
prototype is not an accepted recovery method or an installability claim.
