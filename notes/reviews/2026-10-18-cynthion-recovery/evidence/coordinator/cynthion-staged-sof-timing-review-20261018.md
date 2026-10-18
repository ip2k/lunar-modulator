# Staged USB-key SOF timing review (offline)

Review date: 2026-10-18. This is a source/evidence interpretation only. No hardware, USB, power, FPGA, or device operation was performed by this review.

## Outcome

The staged Cynthion run reached its local `DONE` state, but that state is not evidence that the FM-1 ROM accepted oscillator calibration or entered its USB loader. The captured timing is consistent with both a ROM retry/drop-pull-up window and successful calibration followed by pull-up removal; the host result and the limited trace do not distinguish those cases. The direct-cable cold boot later produced no USB attachment, but it happened at a different time/state and cannot identify a Cynthion electrical-path fault.

No further active key attempt is recommended from this evidence. The owner has since confirmed a direct FM-1-to-bench cable and performed a LEFT/OFF-to-RIGHT/ON cold boot; at 2026-10-18 07:45:19 UTC there was no USB attachment/event and only the KA6 device and root hubs were listed. No further key attempt is requested. Owner was asked to report screen state and whether a scope/logic analyzer is available; that observation is pending. Any new active procedure remains subject to the current dump/byte-identical-restore gate and owner authorization.

## Evidence pins

Integration worktree HEAD at review: `f8fe86dac00476a543be8b689fd08b86765138a5`.

Staged Cynthion capture files:

- `scratch/cynthion-staged-key-20261018/post-power-on-status.json` SHA-256 `3a8908c07b9a60b79078e16dcf7d0302a016bd06748c14a2bddf0c5219b17e71`.
- `scratch/cynthion-staged-key-20261018/post-target-c-status.json` SHA-256 `983f165e387ae5ed3c2ebee0653c2f78e583fa46f8f39c20c0aac5adf1d6de49`.
- `scratch/cynthion-staged-key-20261018/post-power-on-kernel-log.txt` SHA-256 `adce03e9008c293ea1e3625bca4d181c45e8404d07ad1d83273d1f65739c9679`.

Reviewed source/reference pins:

- `tools/cynthion_usb_key/gateware.py` SHA-256 `bdf35f75758f9278a80eacb5b9f375a567c7ea6b30f8873262e3753d8d46da4a`.
- `dongle/firmware/main.c` SHA-256 `21d7e62383d6a69115f863c81540f0ff73a8561f232a515fe079191e573eb548`.
- `dongle/firmware/config.h` SHA-256 `82686343ad43505fd58fb7a24c3bdb744521ee6abb046eb47226084ea4ebb0e2`.
- Primary checkout reference `reference/jielie/isp/usb/usb-key.md` SHA-256 `6e664256ae59d4ec85c3b328623dadc5e797d56bb702218fac39862c6ddd5661`.
- Primary checkout reference `reference/jl-uboot-tool/docs/how-to-enter-uboot.md` SHA-256 `a79568dd66d7cd7b9b3df9c0198f8c0ebf6a8532027f4ee64ffe3a3dd310d566`.

## What the trace establishes

The read-only layout-7 captures agree on terminal state 7 and receipt `0x701`; packet count is 873, WAIT_DP elapsed 1,628 us, SOF elapsed 1,503,000 us, and the recorded continuous-low count is 2,999 ticks at the snapshot. GPIO output-enable is zero and the state/ring did not change during the status sweep, supporting that the terminal state was stable and outputs were released at capture.

The ring is frozen and saturated at 32 entries. Its retained tail contains periodic GPIO-low events 4 us wide, spaced 1,000 us apart, followed by the terminal low-line events. It does not retain the first SOF intervals, so it cannot establish the initial four consistent periods described in one reference. `gateware.py` 475–515 waits for valid J, generates the 1,000-us phase with a 4-us D+ low, and enters DONE after 3,000 consecutive microsecond ticks where the USB3343 receiver’s latest valid line-state value is SE0. This is the core’s own threshold; it is not a ROM acknowledgement and does not directly measure connector voltage continuously.

The companion Pico C implementation in `dongle/firmware/main.c` 193–212 uses a different observation path: release lines, wait for D+ high, generate pulses, then sample the GPIO every 100 us and declare its local “calibration done” condition after 3 ms low. The Cynthion implementation’s use of sampled/cached RXCMD line-state data is therefore not equivalent evidence to a continuous analog measurement at the FM-1 connector.

The kernel log shows a full-speed attach on the Cynthion path at 00:40:51 Pacific, followed by descriptor read and setup-address failures (`-71`) and “unable to enumerate USB device.” It proves the host saw an attach/pull-up on that path; it does not prove the device identity, ROM mode, valid SOF reception, or successful control transfers.

## Ambiguity and limits

The 1.503 s SOF interval is not a success signature. `how-to-enter-uboot.md` describes an approximately one-second retry/drop-pull-up behavior if calibration does not complete, while also describing four similar falling-edge intervals as its success heuristic. Thus a pull-up disappearance around 1.5 s could follow either calibration acceptance or a retry/failure path. That document is community/vendor research with qualifiers, not a verified FM-1_092 ROM specification. The more general `usb-key.md` describes calibration from USB SOF falling edges but does not establish the exact retry timing or threshold for this unit.

Likely explanations remain unresolved: pulses may not have met target-side voltage/timing thresholds; the ROM may have rejected/noised its calibration and retried; or the host’s attach/error sequence may reflect later USB signaling or device state. The known 1 kΩ path and reported 1.5 kΩ ROM pull-up motivate checking actual levels, but divider math is not a measurement. The later direct-cable boot was not simultaneous with the Cynthion run and cannot rule the Cynthion route in or out. No USB identity was obtained in either case.

The direct cold-boot observation at 07:45:19 UTC is also only a negative enumeration observation. It does not show whether the key protocol ran, whether the target entered its transient ROM window, or what the screen displayed. Owner screen/scope availability is pending. No scope/logic-analyzer capture exists in this handoff.

## Next useful evidence

Do not repeat the key attempt merely to reproduce the same terminal code. If the owner later clears the current recovery gate and authorizes a new attempt, the discriminating measurement is a high-impedance capture at the FM-1 connector, starting before the first generated pulse and spanning the full calibration/retry interval. It should correlate the key pulse and phase timing with target-side D+ and D− voltage, pulse width/period, pull-up rise/drop time, and host attach/control-transfer results. Preserve the full time series rather than only the final 32-event ring. That can separate a local timer/receiver-state result from actual target-pin levels and identify whether the pull-up drop precedes or follows stable calibration intervals. A separate host enumeration result should be recorded after the observed handoff/window, without adding host SOFs during the ROM’s calibration interval unless the protocol requires them.

Before any such trial, the coordinator must resolve the current strict backup/restore gate and confirm the planned physical setup. The current evidence alone does not justify another active key sequence, recovery claim, or write operation.

## Checks and tooling limits

This review hashed the evidence and source/reference files listed above, read the local trace and bounded source windows, and checked the known project references. No tests, source edits, builds, containers, SSH, or device operations were run. Serena was read for its configured state and selected the correct worktree; Rarefaction’s status pointed at the primary checkout, so I did not retarget the shared semantic server or rely on its index. This report is scratch evidence, not a source change or release/hardware acceptance.
