# Cold-boot clock comparison

[reported: owner, 2026-10-15] After physically power cycling the FM1, Lunar
booted but the sine-wave display remained very laggy and audio remained badly
distorted. This is a failed musical/performance acceptance, not a passed boot test.

[verified: passive host capture] Native USB enumerated on bench01 path1-1 as
bus1/dev86, 1209:0001. A 35-second input-only MIDI capture ran at
2026-10-15T08:30:39.113Z–08:31:14.120Z using the existing pinned prior
runtime. It recorded20 validated frames:8 render-profile,3 clock and3 PLL.
No MIDI output was opened and no reset, flash write or note stimulus was sent.
The installed-image expected hash was
3571d21401a921df425ff416824d32bca0f8ca4d1856ec007041cc5df875fbbb,
carried from the prior complete readback; this capture did not independently
read flash or cryptographically identify the executing image.

[verified: decoded evidence comparison] All recorded cold-boot startup clock
and PLL snapshots equal those in the previous loader-started ROM83 campaign:

| Register snapshot | Raw decimal value |
| --- | ---: |
| CLK_CON0 |449 |
| CLK_CON2 |6 |
| SYS_DIV |66048 |
| PLL multiplier |122695948 |
| PLL oscillator selector |1161822723 |
| PLL predivider |155189803 |

All snapshots report uptime0, so these compare firmware-reported startup
snapshots, not continuous live measurements or calibrated CPU frequency.
[inferred] These observations provide no evidence for a boot-path-specific
clock-register difference; they do not establish that clock configuration or
actual frequency is correct, nor identify the cause of starvation.

Private evidence on bench01: /home/claude/fm1-coldboot-rom86-20261015.
Local archive: scratch/producer-gap-result/coldboot-rom86-evidence.tar,
SHA256 cdfa401cdba115b73e09a04e463d851199dd29f1d9f37108abf21229b6d60546.
Raw SysEx SHA2561583d28b615f6fafa5a8a341ac5e2949a57bd41802dc6660036b4de7820760a5;
event log SHA256ea4f8a377a103b71ab7dd8937def0f05e82003ffe56a215530e4863d6524f5c7.
Prior comparison: scratch/hot-ram-fm-buffers-result/physical/campaign-evidence/
rom83-fm-buffers-cycle/diagnostic-audio/telemetry/events.jsonl.

[verified: passive sysfs] After its timed diagnostic return, path1-1 reported
bus1/dev87,4c4a:8057. No further owner power cycle is required at this point.
Next: finish offline admission of the producer-gap target, then compare audio
render work with time between producer calls. SAVE remains disarmed; goal ACTIVE.
