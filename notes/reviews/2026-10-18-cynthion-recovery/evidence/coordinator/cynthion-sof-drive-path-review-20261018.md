# Cynthion USB_KEY pulse path review (offline)

Date: 2026-10-18. Scope: source/schematic/API feasibility only. No source edits, builds, USB commands, FPGA loads, cable operations, or hardware observations were made for this review.

## Finding

The 1 kΩ concern is a real schematic topology for the currently reviewed Cynthion r1.4 design, not merely an inferred board resistor. The official r1.4 target-port sheet places R58 (1 kΩ, 5%, 0402) between the FPGA-side `TARGET_FS_MONITOR_D+` hierarchical net and `TARGET_A_D+`; R57 similarly connects the D− monitor net to `TARGET_A_D−`. The project’s platform declares those monitor pads N4/P3 input-only; the USB_KEY top deliberately overrides them as LVCMOS33, no-pull bidirectional pins, and only enables them for the finite KEY/SOF states. Therefore the SOF code’s D+ sink path goes through the 1 kΩ series resistor to the Target-A bus.

Under a simplified DC divider assumption of a 3.3 V, 1.5 kΩ pull-up and an ideal 0 V FPGA output, the bus node during D+ sink would be `3.3 × 1k / (1.5k + 1k) = 1.32 V`. If the target receiver requires the USB full-speed compliant low threshold (0.8 V maximum), 1.32 V would not guarantee a valid low. This is a plausible electrical failure mechanism, but the FM-1 ROM’s pull-up value, receiver threshold, the actual GPIO low voltage, and the pulse voltage at the connector have not been measured here. It cannot explain the outcome as a proven cause; retry1/2’s repeated 1.503 s local SOF-to-DONE sequence and host descriptor `-71` remain compatible with multiple causes.

## Existing PHY/library path

Cynthion r1.4 has a USB3343 PHY on ULPI; the pinned project’s `ULPISafePHY` intentionally initializes it to FS non-driving mode (`Function Control=0x49`) and verifies readback before permitting the separate GPIO path. The USB334x datasheet documents normal transmit as a Link-originated ULPI TX command followed by packet bytes, with NXT flow control and STP termination. This would use the PHY’s proper differential USB output stage rather than the FPGA GPIO plus 1 kΩ resistor.

However, installed LUNA 0.2.3 documents that it has no USB-host support. Its UTMI/ULPI transmit translator is a byte-stream/packet transmit building block, not a maintained host controller with token scheduling, frame/CRC generation, retries, reset/attach sequencing, and host-mode arbitration. The USB3343 is a PHY rather than a host controller. No existing reviewed LUNA/Cynthion API in this tree was found that safely emits the requested custom 4 µs D+ low pulse at 1 ms cadence, or a complete standard host SOF schedule. A new PHY-driven experiment would need a separately designed and reviewed link/controller state machine and changed PHY configuration/interlocks; it must not be treated as a drop-in substitution or authorized from this research.

The physical host path is distinct: Cynthion’s TARGET-A/TARGET-C data path is pass-through, and after C is connected the external host performs ordinary USB reset/enumeration. That is standards-based host signaling, but it is not a controllable “SOF after key” primitive and does not establish the ROM’s special calibration condition. Retry2 already used the DONE-only LED as the connection gate and still ended in host descriptor `-71` without FM-1 identity. Repeating it unchanged has little discriminating value. Retry3, per parent’s latest status, instead timed out in WAIT_DP before SOF (12,696 packets / 500,000 µs; FAULT/OEs low), so its result is a distinct ordering outcome, not evidence for or against the GPIO pulse voltage.

## Safety/decision boundary

No waveform change is recommended from this offline review alone. The JTAG ring observes the FPGA-side GPIO, and the PAC monitor observes VBUS/current; neither measures the voltage after R58 at the Target-A connector. Therefore a high-impedance scope measurement is necessary to confirm or rule out the analog-divider hypothesis. If avoiding a scope, leave this electrical cause unresolved and do not alter the waveform based on digital/JTAG evidence alone. Any measurement would need a separately owner-approved procedure after current bounded attempts. Do not connect the host before the exact reviewed controller is terminal and both pad OEs are verified low. A PHY-based design requires its own source review, simulation, build receipts, and physical gate; it is not covered by the current bitstream approval.

## Pins and source references

Local checkout HEAD: `1aa529704a8f14f0267bd9c001d5470f9bb71720`; only unrelated `uv.lock` was dirty at inspection.

SHA-256:
- `tools/cynthion_usb_key/gateware.py`: `bdf35f75758f9278a80eacb5b9f375a567c7ea6b30f8873262e3753d8d46da4a`
- `tools/cynthion_usb_key/top.py`: `0519ef72bdb621b7ccc2014928065ce55bbd633b72d5bb366a19d98688e2bdc5`
- `gateware/ulpi_safe_phy.py`: `88483a1b828c52ec5e3e64c3600af29a270bc8cd2029364a851087f85eab21f1`
- `tools/cynthion_usb_key/README.md`: `46542cfc7eceae4cdd25e3b58ce223d983e61f7294f086821d38e4943ef13355`
- `notes/2026-10-18-cynthion-staged-key-preflight.md`: `f2f0c2197206edacb40900366ad914939de34863c35d1412f2a2765a85d96b94`

External primary source pins:
- Cynthion hardware r1.4.0 target-port schematic (R57/R58 and A-port nets): https://github.com/greatscottgadgets/cynthion-hardware/blob/r1.4.0/target_port.kicad_sch
- Cynthion hardware r1.4.0 USB PHY schematic (USB3343): https://github.com/greatscottgadgets/cynthion-hardware/blob/r1.4.0/usb_phy.kicad_sch
- Microchip USB334x datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/334x.pdf
- LUNA feature support table/source: https://github.com/greatscottgadgets/luna/blob/main/docs/features.rst
- LUNA ULPI/UTMI transmitter implementation: https://github.com/greatscottgadgets/luna/blob/main/luna/gateware/interface/ulpi.py

Semantic tooling: Serena was initialized for the current absolute worktree; Rarefaction status returned the primary checkout (`/Users/REDACTED/Developer/mvave-fm1-firmware`), so it was not used or retargeted. Findings above were checked against bounded source excerpts and the r1.4.0 schematic/API references.
