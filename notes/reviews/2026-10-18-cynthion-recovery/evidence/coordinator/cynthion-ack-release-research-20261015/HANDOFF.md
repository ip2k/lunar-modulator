# Cynthion ACK-release research — 2026-10-15

## Outcome

Attempt 3 is an electrically observed **candidate** ACK followed by a bounded `WAIT_DP` timeout, not ROM acceptance. The retained diagnostic record reports `receiver_live=1`, `ack_ticks=99`, 4,222 completed packets, then 500,000 us in `WAIT_DP`, no SOF/SOF-low ticks, GPIO output enables zero at the terminal snapshot, and no later J/DP-pullup witness. Owner notes say the FM-1 switch moved right-to-left and that its ON direction is still unverified. These facts leave both ACK authenticity and target power state unresolved.

No primary AC791N/WL82 mask-ROM source/spec located in this review specifies a required external SE1 bias, a both-high witness after SE0 ACK, or the exact ACK-release electrical state. The available project protocol summary attributes its description to kagaimiq's family-level write-ups, and explicitly labels WL82 retry behavior unknown. Therefore neither “ROM requires SE1” nor “the present J-only test is sufficient for WL82” is established.

## Evidence and interpretation

- Project protocol summary [`docs/10-usb-key-dongle.md`](../../docs/10-usb-key-dongle.md#L76) attributes the 0x16EF behavior to kagaimiq: key repeated until both lines are pulled low for roughly 1–2 ms; afterward the ROM initializes USB, reportedly pulls D+ up through 1.5 kΩ, and measures 1 ms SOF edges. It also says reliable ACK sensing requires an external strong pull-up on each line because target 15 kΩ pull-downs remain active during key receipt. This is a report about sensing conditions, **not evidence that the ROM needs external pull-up/SE1 bias to accept or release ACK**.
- The project's physical-design requirements [`docs/10-usb-key-dongle.md`](../../docs/10-usb-key-dongle.md#L284) define ACK sensing with the dongle driving nothing, followed by either host handoff or SOF edges. Its Pico reference flow first waits for both lines to release, then—after disabling its own pull-ups—waits for target D+ high. That is a design reference, not AC791N validation and not proof that a separate post-ACK both-high level is a ROM contract.
- The r1.4 Cynthion path has no external line pull-ups in the currently documented setup; the PHY is configured non-driving and the target GPIO path is through series resistors. Project feasibility notes say the PHY non-driving mode disables its DP/DM terminations. The model/source rationale for 15 kΩ target pull-downs is only reported. With the FPGA high-Z during GAP, “both lines low” can be the normal biased idle state; ACK is not sampled there in current gateware.
- Current gateware [`tools/cynthion_usb_key/gateware.py`](../../tools/cynthion_usb_key/gateware.py#L315) counts SE0 toward ACK while in actively driven `KEY` after `receiver_live`; it then accepts `ack_ticks` and moves to `WAIT_DP`. `WAIT_DP` only accepts a valid line-state value of `1` (J = DP high, DM low) [`gateware.py`](../../tools/cynthion_usb_key/gateware.py#L373). A SE1 (3), DP-high/DM-unknown observation, or an unchanging cached line-state that is not J does not start SOF. Timeout means no qualifying J was observed; it does not mean there was no DP edge, nor that ROM rejected the key.
- Official JieLi documentation located in this search covers normal USB download-mode entry by update+reset and SDK USB host/device operation, not USB_KEY’s mask-ROM handshake or ACK release: [AC79 USB download procedure](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.1.0/getting_started/preparation/update.html) and [AC79 USB examples](https://doc.zh-jieli.com/AC79/zh-cn/master/module_example/peripherals/usb.html). These official pages cannot resolve the ROM-specific question.
- Passive absence of an enumerated device after TARGET-C reconnect is consistent with the reported WAIT_DP timeout, but does not distinguish failed key recognition, a false SE0 candidate during power transition/clamping, or successful key recognition followed by failure to receive/observe SOF calibration.

## Assessment

Do **not** add external SE1 bias or alter the WAIT_DP acceptance rule based on current evidence. The reported post-ACK D+ pull-up makes a D+ rise after released SE0 a useful candidate witness. If the reported target D− pull-down persists, expected J is plausible. But persistence/strength/timing of that D− pull-down after ACK is not verified for WL82, and with the Cynthion PHY terminations disabled an absent/unknown external bias could leave DM not classifiable as low. Any alternative accept rule (DP-high independently of DM, SE1, or both-high) must be recorded as diagnostic-only until separately validated; it must not be called ROM acceptance.

The power transition remains an independent confounder. No exact switch-ON direction or timestamp ties the attempt's SE0 candidate to a known powered interval. A transition/clamp can mimic line-state SE0, while diagnostic `receiver_live` only proves at least one key-phase receiver report matched a high-phase state. Neither establishes that the SoC was powered and then entered ROM.

## Smallest useful next diagnostic

Before changing protocol behavior, add a bounded, low-overhead RXCMD event history to the existing terminal diagnostics (or expose equivalent passive capture): ring of ~32–64 records with relative timestamp, FSM state, key bit/phase, line-state value/update, cached-valid bit, `receiver_live`, ACK counter/confirmation, and DP/DM output-enable/value. Preserve event-on-change semantics: do not require periodic fresh RXCMDs, since a real held SE0 may produce no new event. Snapshot records immediately before and after candidate ACK and through WAIT_DP timeout. Keep outputs high-Z on terminal fault and retain the existing finite timeout.

This can separate:
1. SE0 already present during keying / no line transition around candidate;
2. candidate SE0 followed by a DP rise and J, SE1, or another state;
3. no RXCMD changes during the wait versus transitions that fail the current J predicate.

It cannot prove SoC power or ROM execution by itself. Pair it with the owner's timestamped switch action/state or a passive independent VBUS/current observation if available; do not infer switch direction from right/left labels. Do not issue another hardware action as part of this review.

## Limits

Read-only source/doc review only; no device, USB, flash, build, or waveform operation. Web research used official JieLi documentation for the limited conclusion that public official material found describes conventional USB mode rather than USB_KEY; the USB_KEY facts remain the project's cited report from third-party family documentation, not a primary WL82 ROM specification. No hardware line voltages were measured here.

## Source state / persistence

- Checkout: `/Users/REDACTED/.codex/worktrees/installable-firmware/mvave-fm1-firmware`
- HEAD observed during review: `3f183ef0909d499f7b0750e0c058138d885c4703`
- Attempt record: `scratch/cynthion-usb-key-20261015/fault-telemetry-operation/owner-attempt-3-status.json`
- This handoff is scratch-only; no tracked source changed.
