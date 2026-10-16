# Cynthion ULPI debug readback handoff

This change adds a one-shot, read-only USB3343 Debug register `0x15` read after
the protocol core reaches FAULT specifically from a WAIT_DP timeout. The read
uses the existing LUNA `ULPIRegisterWindow`; it does not write PHY state or
change the protocol, VBUS, or arming behavior. A bounded transaction timeout
is reported independently from PHY initialization fault. The top latches the
raw debug byte, cached RXCMD value/validity and age, and GPIO input/output/OE
after the diagnostic finishes. RXCMD updates are suppressed during the
diagnostic transaction so register response bytes cannot masquerade as a new
line-state event.

## Source and checks

- Base: `84f7f909f5efaaf526bf87b65ae6fd2261e62abf`.
- Branch: `codex/cynthion-debug-readback-20261016`.
- Owned source: `gateware/ulpi_safe_phy.py`,
  `tools/cynthion_usb_key/top.py`, `tests/test_ulpi_safe_phy.py`, and the
  diagnostic register-map section of `tools/cynthion_usb_key/README.md`.
- Focused validation: 28 tests passed across `test_ulpi_safe_phy.py`,
  `test_cynthion_usb_key_gateware.py`, and
  `test_cynthion_usb_key_protocol_review.py`; `git diff --check` passed.
- Routed FPGA build: pending exact committed source on Hera.

## Limits and next step

The test proves the software transaction/readback contract against a fake
USB3343 and LUNA's actual register-window implementation. The timeout case
withholds acceptance of the ULPI read command; it does not prove detection of
a PHY that accepts a command but returns an incorrect byte. Debug register
`0x15` remains raw and is not treated as an ACK. No device was accessed or
reconfigured. Root owns any subsequent review or hardware action.
