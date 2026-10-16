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
- Routed FPGA build: completed on Hera from `e3b4cfa156f357e09474a7002286e527db1b938b`.

## Hera build receipt

- Output directory:
  `/home/claude/.local/share/codex-builds/cynthion-debug-readback-20261016-homefix`.
- `cynthion_usb_key.bit`: 176,450 bytes, SHA-256
  `ea634822258a7075ba60f2d980d85300484c7d935351a4cec3d0822437112664`.
- Routed timing file: `cynthion_usb_key.tim`, SHA-256
  `d10e43de54b924cae36c3f6e808093130572774c824a68a5e340bfc3f808c3ce`.
- Machine-readable receipt: `build-receipt.json` in the output directory;
  netlist SHA-256 `938a1157d82ca04a853b75e0d0704aa406d249a572b135494c99931d4e25c244`.
- Timing passes: USB 60 MHz domain maximum 69.05 MHz; 120 MHz domain maximum
  212.63 MHz.
- Resource use: 4,371/24,288 LUT4s and 2,552/24,288 flip-flops.
- Netlist inspection confirmed CONTROL VBUS, TARGET C VBUS, AUX VBUS, and
  TARGET A discharge output constants are all zero.
- Toolchain: Cynthion 0.2.5, Amaranth 0.5.10, LUNA USB 0.2.3,
  Apollo FPGA 1.1.1, Yosys 0.70+16, nextpnr-ecp5 0.11.1-63, ecppack 1.4-86.
- Build ran offline in the configured `docker-batch.slice` container with
  4 CPUs, 8 GiB memory/swap, and exact source mounted read-only. A first build
  attempt with an invalid default HOME was preserved separately; the clean
  HOME rerun above completed without those warnings and produced the same bit
  hash.

## Limits and next step

The tests prove the software transaction/readback contract against a fake
USB3343 and LUNA's actual register-window implementation. The timeout case
withholds acceptance of the ULPI read command; it does not prove detection of
a PHY that accepts a command but returns an incorrect byte. Debug register
`0x15` remains raw and is not treated as an ACK. No device was accessed or
reconfigured. Root owns any subsequent review or hardware action.
