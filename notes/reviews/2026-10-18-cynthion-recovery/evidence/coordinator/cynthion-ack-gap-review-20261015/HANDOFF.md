# ACK-duration counter across packet GAP — focused regression proposal

## Finding

At `tools/cynthion_usb_key/gateware.py:333-354`, `ack_ticks` is reset when a non-SE0 line-state update arrives or when the cached line state is not SE0 during a KEY `us_tick`; otherwise it increments while `receiver_live` is true. On the final KEY bit (`:342-350`) an incomplete key packet transitions to GAP without clearing `ack_ticks`. GAP (`:355-372`) never touches the ACK counter. Therefore SE0 ticks accumulated before packet end are retained across the 160-us released GAP and can be combined with cached/held SE0 ticks in the next KEY packet. With a threshold of 100 us, e.g. 99 candidate ticks before the packet boundary plus one tick in the next KEY can assert `ack_confirm` even though the candidate counter did not run through the GAP.

The counter should represent candidate duration within a single actively driven KEY interval, not sum observations on both sides of an unobserved/released interval. Minimal safe implementation: clear only `ack_ticks` in the existing KEY final-bit → GAP transition assignment (around lines 344-346). An unconditional clear during GAP is also robust but redundant; clearing in the transition makes the boundary semantics explicit immediately. Do not clear `receiver_live`, `line_state_valid`, or cached `line_state_value` as part of this fix.

## Receiver witness / genuine ACK reachability

Resetting `ack_ticks` alone does not revoke the required earlier high-phase receiver witness. `receiver_live` is set only by a matching `line_state_update` during KEY high phase at lines 200-210; it remains set until self-test restart (`:314-315`). RXCMD line-state values are event-on-change and may remain valid/cached without periodic refresh, as the module's own docstring warns (`:1-5`). So preserve the policy: keep the existing `receiver_live` condition and allow a held valid SE0 value to be evaluated on KEY `us_tick`s without demanding another RXCMD event.

This means a held candidate SE0 can still reach WAIT_DP: a 100-us threshold is reachable within a 320-us KEY packet after GAP, even if SE0 began in the prior GAP/at the previous packet boundary and the cached status produces no additional update. The counter resets the elapsed evidence at the boundary; it does not make recognition impossible. It also does not prove physical SE0 was sampled continuously—the existing limitation remains.

## Regression cases for implementation owner

1. **No cross-gap accumulation:** Configure `clock_hz=1_000_000`, packet limit ≥2, `ack_duration_us=100`, `auto_selftest=True`, and a small self-test interval. Reach KEY with the existing four-state echo and establish `receiver_live` with a valid high-phase event. Keep a non-SE0 state until the final 99 KEY microsecond ticks before the first packet boundary, then deliver one SE0 event and hold `line_state_valid=1`, `line_state_value=0`, `line_state_update=0`. Verify `debug_ack_ticks` reaches 99 (or the measured exact pre-boundary count), becomes 0 on entering GAP, remains 0 throughout GAP, and does not enter WAIT_DP on the first subsequent KEY tick. This is the regression for the defect: without the reset, the first subsequent SE0 tick can hit 100 and transition.
2. **Still accepts a held candidate after reset:** In the same setup, leave the SE0 cache held through GAP and into the next KEY, with no periodic RXCMD refresh. Verify `receiver_live` stays true, counter starts at zero, and WAIT_DP occurs only after 100 KEY-state microsecond ticks in that next KEY interval. This catches an over-broad “fix” that clears receiver qualification or requires a fresh event.
3. **Witness gate unchanged:** Separate or fold into case 2: present cached SE0 without ever delivering a matching high-phase witness; verify it never increments the candidate counter / never reaches WAIT_DP and reaches the packet-limit fault. This confirms only duration reset, not witness-policy relaxation.

Test timing should key off FSM state plus `debug_key_bit`/`debug_key_phase` (signals exported at `gateware.py:175-176`) rather than assume simulator coroutine wall time. Note that the current test helper `tests/test_cynthion_usb_key_gateware.py:11-44` reaches candidate ACK directly and does not exercise packet/GAP carry. The absent-target echo tests in `tests/test_cynthion_usb_key_gateware.py:195-231` and `tests/test_cynthion_usb_key_protocol_review.py:43-78` are useful patterns for change-only RXCMD modeling; the sustained-SE0 test at `tests/test_cynthion_usb_key_protocol_review.py:81-127` demonstrates a single event followed by held cached state.

## Acceptance boundary

These are RTL simulation regressions for state/counter semantics only. They cannot establish USB3343 sample continuity, actual ROM timing, electrical ACK validity, or FM-1 power state. No source or device changes were made in this review.

## State

- Checkout: `/Users/REDACTED/.codex/worktrees/installable-firmware/mvave-fm1-firmware`
- HEAD observed: `3f183ef0909d499f7b0750e0c058138d885c4703`
- Scratch-only recommendation; no tests executed and no tracked files edited.
