# Cynthion r1.4 USB3343 DP/DM reversal: source review follow-up

Date: 2026-10-15
Scope: read-only source and datasheet review. No device access, gateware edits, upload, or hardware operation was performed.

## Finding

The observed one-hot line-state reversal is explained by a platform-specific USB3343 register write that the standalone safe-PHY block does not reproduce. The installed `cynthion/gateware/platform/core.py` defines:

```python
ulpi_extra_registers = {
    0x39: 0b000110 # USB3343: swap D+ and D- to match the hardware design
}
```

The independently reviewed standalone `gateware/ulpi_safe_phy.py` configures and reads back PHY identity, Function Control (0x04), OTG Control (0x0a), and Charger Detection (0x32), but it does not write/read back register 0x39. It documents RXCMD bit 0 as DP and bit 1 as DM, which agrees with the USB334x datasheet; there is no source evidence here for changing that decoding.

Microchip USB334x datasheet DS00002646A, §7.1.3.5, says register 0x39 bit 1 is `SwapDP/DM`; asserting it swaps the transceiver DP and DM pins and is provided to avoid crossing board traces. In the same byte, bits 3:2 (`UART RegOutput`) default to `01b`; bits 5:4 are charger pull-ups; bits 7:6 are USB regulator output. Therefore 0x06 sets the required DP/DM swap while preserving UART RegOutput=`01`, charger pull-ups off, and USB RegOutput=`00`.

This matches the root-reported full four-state observation: commanded pad states `[K2,J1,SE0,SE1] = [2,1,0,3]` produced PHY RXCMD `[1,2,0,3]`. Swapping only the one-hot readings is exactly what an omitted DP/DM swap would produce; equal SE0 and SE1 values remain unchanged. Board evidence also places N4 on TARGET_FS_MONITOR_D+ and P3 on TARGET_FS_MONITOR_D−, so a GPIO pad-map swap is not indicated.

## Recommended gate

In the standalone PHY startup sequence, after authenticating USB3343 identity and before raising `ready` or `drive_allowed`:

1. Write ULPI immediate register 0x39 with exactly 0x06.
2. Read 0x39 back and require exact value 0x06 (or a documented mask only if a verified silicon/readback behavior requires it; do not silently ignore the swap bit or safety-relevant fields).
3. On write timeout, failed transaction, or mismatch, latch the existing fail-closed fault and keep GPIO drive permission low.
4. Add simulation coverage for correct readback, missing swap bit, and failed/timeout readback. Keep the existing raw RXCMD encoding and N4/P3 mapping unchanged.

The assignment worker owns implementation/tests; this report makes no claim that the fix is implemented or validated on hardware. Register readback only verifies the PHY's control setting, not analog pad wiring or physical waveform correctness. Any live confirmation remains a separate root-owned gate.

## Evidence and hashes

- Installed platform common source, exact path `/Users/REDACTED/.local/share/uv/tools/cynthion/lib/python3.12/site-packages/cynthion/gateware/platform/core.py`, SHA-256 `0d1f7c60432e2e219883efd6ca7c01495b69f1925897b6e7d9ba92267a8c4513`.
- Installed r1.4 platform source, exact path `/Users/REDACTED/.local/share/uv/tools/cynthion/lib/python3.12/site-packages/cynthion/gateware/platform/cynthion_r1_4.py`, SHA-256 `d874be68494149f685b2314bd7974c934727918f5f7a241e0ae079f1340f91fc`. It maps `target_usb_dp` to N4 and `target_usb_dm` to P3.
- Reviewed standalone module `/Users/REDACTED/.codex/worktrees/cynthion-ulpi-safe-2026-10-15/gateware/ulpi_safe_phy.py`, worktree HEAD `5044da99e925894e7c8f37ce96ebb43a8ed868b6`, SHA-256 `cba6735feb56185b9473049eb4f9d0f1e7857d8c0cbea14c2cb5016ac89fbf5c` at review time.
- Exact r1.4 PCB `/tmp/cynthion-pcb-13aa71c2.kicad_pcb`, SHA-256 `51e978f0e3c02f1b22c6e8013f2d26b309a6724749f27b39abd932545bcd5313`; monitor nets identify net 336 as TARGET_FS_MONITOR_D+ and net 339 as TARGET_FS_MONITOR_D−.
- Exact target-port schematic `/tmp/cynthion-target_port-13aa71c2.kicad_sch`, SHA-256 `be58be3fe30b6ebcc69ba58b7a12b2b0fcc13be62f4f4782a07bb37a579919e4`.
- Primary datasheet: [Microchip USB334x Data Sheet DS00002646A](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/USB334x-Data-Sheet-DS00002646A.pdf), §7.1.3.5, pp. 75–76 (register 0x39 bit definitions and defaults).

## Verification limits / next dependency

This was static inspection of installed platform source, an isolated worktree module, supplied r1.4 board files, the parent-provided 4-state result, and the Microchip primary datasheet. No tests were run here; no source was changed. Next: assignment worker implements 0x39=0x06 write/readback and failure-path simulation; root reviews that change and separately decides whether a controlled physical four-state confirmation is authorized.
