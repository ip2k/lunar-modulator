# Cynthion USB_KEY protocol review — 2026-10-15

## Outcome

Independent review of `tools/cynthion_usb_key/gateware.py` and the live worker
`top.py` found no additional blocking RTL defect in event-based RXCMD self-test,
SOF completion, or reset/PHY-ready gating. I added four focused simulator
regressions in `tests/test_cynthion_usb_key_protocol_review.py` on the isolated
branch `codex/2026-10-15@cynthion-protocol-review`.

## Source and evidence

- Test branch base: `2290185a1f93ed0778d03ba9ea58272079ebf06e`.
- Reviewed gateware bytes: SHA-256
  `58d6f58436437ecd526b966916bf5b39e34eedb789ddcdb42e4b70b7359cdcd8`.
- Reviewed live worker top bytes: SHA-256
  `08fec5cccf837b651940509645d3c8233bc5324c86862f502f0272804d34a6d4`.
- Reviewed safe-PHY bytes: SHA-256
  `cba6735feb56185b9473049eb4f9d0f1e7857d8c0cbea14c2cb5016ac89fbf5c`.
- Current platform source confirms `button_user` is `PinsN("M14", dir="i")`,
  target ULPI reset uses `rst_invert=True`, and TARGET-C VBUS resource K5 is
  active-high (`cynthion/gateware/platform/cynthion_r1_4.py`, lines 96, 113–116,
  156). Amaranth `PinsN` is `Pins(..., invert=True)` (`amaranth/build/dsl.py`,
  lines 57–58); `ULPIResource` passes `rst_invert` to its reset pin definition
  (`cynthion/gateware/vendor/amaranth_boards/resources/interface.py`, line 128).
- The live top ties target PHY reset and clock to the USB domain
  (`top.py:55–62`), waits for domain reset release before PHY initialization
  (`top.py:80–87`), gates target pad OEs with `safe_phy.drive_allowed`
  (`top.py:102–112`), keeps TARGET-C/AUX/discharge low (`top.py:142–148`), and
  ties `phy_isolated` to `drive_allowed` and `ack_sense_valid` to `ready & ~fault`
  (`top.py:104–110`). `ULPISafePHY.drive_allowed` is combinationally
  `ready & ~fault` (`gateware/ulpi_safe_phy.py:131`); initialization checks
  identity, safe register values, and readback before `ready` (`:141–158`).
- Voltage confirmation remains a schematic assumption, not a live sensor:
  `top.py:89–93` documents it and `:106` hardcodes
  `bank6_3v3_confirmed=1`. This is a disclosed constraint, not a new hidden
  defect; board revision and voltage must be established before use.

## Test coverage and result

Four RTL simulations pass with Amaranth 0.5.10 and pytest 9.1.1:

1. A disconnected target echoes FPGA line states and resolves released lines
   to SE0. It completes two bounded packets, never enters `WAIT_DP`, and ends
   in `FAULT` with both pad OEs low.
2. A candidate sustained SE0 is sent once as an RXCMD change event and held as
   latched status. It reaches `WAIT_DP`; the test does not fabricate periodic
   RXCMD refreshes.
3. SOF is modeled as an event stream: the target pull-up makes D+ resolve to J
   while released, and the FPGA's own 4-us low pulse produces SE0. These pulses
   do not complete the 3-ms low qualification; the bounded phase ends in
   `FAULT`, not `DONE`.
4. Dropping the PHY-isolation interlock while SOF is active deasserts both pad
   OEs combinationally before the next clock edge; the state then faults.

Command: `python3.13` with the cached package archive paths prepended to
`sys.path`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and `pytest.main` for the one
file. Result: `4 passed`. The default environment lacked pytest/Amaranth; `uv`
offline resolution also could not resolve cached package metadata, so the
cached installed artifacts were used directly. Only the one test module ran.

## Findings and limits

- Treating unchanged latched SE0 as stale is **not** a bug: USB3343 RXCMD is
  event-on-change, so a sustained external SE0 can be represented by one event
  followed by a held value. Requiring periodic fresh reports would reject that
  candidate. The code's limits are correctly described in its module/class
  comments (`gateware.py:4–5`, `:21–22`).
- `ack_confirm` uses held SE0 plus a timer (`gateware.py:107–109`); its timer is
  cleared on a changed non-SE0 event (`:217–225`). The disconnected echo test
  gives confidence against self-ack from ordinary waveform transitions, but
  simulation cannot establish what ROM clamp waveform or RXCMD sequence occurs
  on hardware.
- SOF completion counts the current latched line-state (`gateware.py:260–273`).
  With actual event-on-change behavior, the target pull-up J transition on each
  released interval resets the low run. The new test checks this contract.
  It does not prove the divider produces a valid USB low at the target pin.
- The core's `phy_fault` input alone does not combinationally mask its outputs;
  in the integrated top it is paired with the `phy_isolated` gate from the
  same safe-PHY fault signal, and the physical pad OE also has the direct
  `safe_phy.drive_allowed` gate. Test coverage exercises loss of that actual
  gate. Keep the direct top-level gate in place.
- No FPGA build, bitstream, board, USB, or physical protocol operation was
  performed. No USB3343/ROM acceptance or electrical margin is established.
- Serena remained selected to the prior offline-audio worktree and Rarefaction
  to the primary checkout. I did not retarget those shared language servers
  during this parallel review; source was checked directly at the recorded
  paths and the standalone simulator was run against the isolated branch.

## Next step

Parent should review and cherry-pick this branch's test commit if desired,
then keep the live worker's source-specific simulations alongside these
independent cases. Any later change to SOF counting should continue to pass the
event-on-change model and a separate external-asserted continuous-SE0 case.
Physical acceptance remains solely with the authorized owner.
