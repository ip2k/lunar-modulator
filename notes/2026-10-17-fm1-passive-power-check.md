# FM1 passive power check — 2026-10-17

[verified: owner connection confirmation and five live PAC2 register sweeps]
Owner connected FM1 to Cynthion TARGET A using the verified data cable,
CONTROL to Mac, TARGET C empty, FM1 switch RIGHT. No USER/RESET, recovery-key,
flash, power-control or reboot command was issued by the coordinator.

PAC2/layout2, active bipolar range 0x4000, VBUS controls 1; five fresh samples
all valid with no PAC errors. Negative current denotes CONTROL toward TARGET A.

| UTC sample completion | Supply V | Current mA |
| --- | ---: | ---: |
| 2026-10-17T16:42:55.233038+00:00 | 4.970215 | -348.053 |
| 2026-10-17T16:42:57.107020+00:00 | 4.972656 | -347.137 |
| 2026-10-17T16:42:58.966018+00:00 | 4.973633 | -348.206 |
| 2026-10-17T16:43:00.797986+00:00 | 4.977539 | -348.358 |
| 2026-10-17T16:43:02.632968+00:00 | 4.972656 | -348.053 |

Raw JSONL retained privately at `scratch/cynthion-pac2-root-direct-20261017/fm1-target-a-switch-right-monitor.jsonl`;
SHA-256 `218f5aba40dcf73d19876b36c3db26124edc72acdee66e4af0087da416408788`.

[verified] About 347–348 mA reaches the attached FM1 at 4.97–4.98 V.
This invalidates the earlier unipolar zero-current interpretation. It does
not identify the processor's power rail, prove CPU execution, establish the
switch ON position, distinguish battery charging from operating current, or
establish USB recovery. The TARGET C data path is intentionally disconnected.

Next: owner requested to move RIGHT to LEFT with cabling unchanged and report
screen/lights, then coordinator takes the same passive sweep. No key/flash
experiment follows automatically from this measurement.
