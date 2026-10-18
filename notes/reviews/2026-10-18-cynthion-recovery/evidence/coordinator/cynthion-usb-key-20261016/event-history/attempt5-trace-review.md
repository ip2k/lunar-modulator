# Attempt 5 retained event trace review

Read-only review of `owner-attempt-5-status.json` captured from integration source `4113cddf4fb7fe2ce878c52cd4bc82e6cb48b4ee`. No source, image, or hardware was changed. Owner reports an accidental USER press while plugging TARGET-A may have occurred, so this is not a clean controlled attempt.

## Decoded result

The terminal receipt is status `0x47d8`, reason/origin `0x855` (WAIT_DP timeout), terminal packet count `0x59ee` (23,022), ACK snapshot `0x18d` (`receiver_live=1`, `ack_confirm=1`, ACK ticks 99), WAIT_DP 500,000 us, SOF 0. The frozen history has 32 entries and wraps at slot 6; timestamps are USB-domain microseconds. The last retained sequence is:

- `212043310 us`: GAP state, cached RXCMD SE0 (line 0) event; GPIO input is SE0, OEs released.
- `212043470 us`: KEY begins with cached line 0, no RXCMD update; GPIO inputs SE0 while outputs/OEs are active. ACK progress is zero.
- `212043570 us` (+100 us): transitions to WAIT_DP with `ack_confirmed=1`, still cached line 0, but GPIO snapshot is `0x01`: DP input high, DM input low, outputs and OEs off. No RXCMD event was recorded between KEY entry and this transition.
- `212543570 us`: FAULT after 500 ms WAIT_DP, still cached SE0, `ack_confirmed=1`, SOF 0.

The ring records RXCMD line changes and FSM transitions, not periodic samples (README lines 108–121; gateware lines 14–53 and 202–220). Thus the 100-us absence of events is expected for a held RXCMD value; it does not prove the PHY sampled continuously or that the physical bus stayed SE0.

## Interpretation and limits

The strongest concrete concern is a **possible stale-SE0 candidate ACK**. SE0 was last observed in the released GAP 160 us before KEY began. KEY starts with that cached SE0 and no new RXCMD transition; the ACK counter reaches 100 us and enters WAIT_DP. The logic counts cached `line_state_value==SE0` while `receiver_live` and valid, resetting at packet/GAP boundaries, but it does not require an RXCMD SE0 update during that KEY packet (gateware lines 223–227 and 407–436). Therefore a pulldown/held cached state can satisfy the timer without new receiver evidence during the candidate window.

At the exact transition to WAIT_DP, the FPGA-side GPIO reads J (`DP=1, DM=0`) while RXCMD remains cached SE0. This disagreement is consistent with stale PHY line-state, a target-side transition not delivered as an RXCMD event, or electrical differences across the series resistor. It does not identify which occurred. A legitimate ROM ACK remains possible because no owner-controlled clean power/arm timing is known; the accidental button press is an independent alignment confounder. However this trace does not establish a genuine ROM ACK: WAIT_DP never observed RXCMD J, no SOF was emitted, and the attempt terminated in timeout.

`receiver_live=1` is sticky after a matching driven high-phase RXCMD event (gateware lines 277–287), so its presence here is not evidence of a recent event. The finite 32-entry ring contains only the final ~1.5 ms of the long attempt; earlier key/ACK-related history was overwritten. Its omission of J from the retained events cannot be generalized to the full attempt. GPIO samples are on the FPGA side of the 1-kohm resistors, not direct target-side measurements.

## Next discriminator

Do not reinterpret this as protocol success or alter the waveform based on this attempt. For a clean, owner-controlled retry only after existing hardware gates: preserve the first moment SE0 is observed and correlate it with (a) a fresh RXCMD SE0 transition during an actively driven KEY interval, (b) GPIO input state while outputs are driven and immediately after release, and (c) RXCMD J transition after release. A candidate ACK should not advance solely from SE0 cached before KEY entry; any proposed change requires root review and a regression that models held/stale SE0 and an absent target. Record button-arm and physical power-switch timing separately.

Source evidence: `tools/cynthion_usb_key/gateware.py:223-227,277-287,407-436,455-471`; `tools/cynthion_usb_key/README.md:108-121`; `tools/cynthion_usb_key/top.py:207-218`. These are source-level interpretation of one owner trace, not proof of device behavior or physical acceptance.
